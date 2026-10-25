"""Processo persistente oficial llama-server do BitNet; CPU e loopback."""
import json
import os
from pathlib import Path
import subprocess
import time
import threading
from collections import deque
import urllib.request

from .client import endpoint_url, post_json
from .contracts import MAX_TOKENS, DEFAULT_OUTPUT_TOKENS, ContextBudgetExceeded, frame, prepare_prompt, valid_text
from .memory import MemoryPolicy, available_memory, process_memory


class Runtime:
    def __init__(self, url="http://127.0.0.1:8092", timeout=45, memory_policy=None,
                 output_tokens=DEFAULT_OUTPUT_TOKENS):
        self.url = endpoint_url(url, loopback=True)
        if not 0 < timeout <= 120:
            raise ValueError("invalid runtime timeout")
        self.timeout = timeout
        self.process = None
        self.log = None
        self.failed = False
        self.load_seconds = None
        self.error = "not_started"
        if type(output_tokens) is not int or not 1 <= output_tokens <= MAX_TOKENS:
            raise ValueError("invalid output limit")
        self.output_tokens = output_tokens
        self.context_tokens = 1024
        self.memory_policy = memory_policy or MemoryPolicy()
        self.memory_samples = deque(maxlen=2400)
        self.last_budget = None
        self._monitor_stop = threading.Event()
        self._monitor = None
        self._process_lock = threading.Lock()
        self._generation = threading.Lock()
        self._instance_handle = None

    def ready(self):
        if self.failed or not self.process or self.process.poll() is not None:
            return False
        return self.probe()

    def probe(self):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(self.url + "/health", timeout=0.5) as response:
                return json.loads(response.read(1024)).get("status") == "ok"
        except Exception:
            return False

    def start(self, executable, model, logs, threads=2, context=1024, reserve_mb=None):
        if self.process:
            raise RuntimeError("runtime already started")
        if not 1 <= threads <= 4 or not 512 <= context <= 4096 or (reserve_mb is not None and reserve_mb < 4096):
            raise ValueError("resource limits outside conservative profile")
        self.context_tokens = context
        executable, model = Path(executable).resolve(), Path(model).resolve()
        if not executable.is_file() or not model.is_file():
            self.error = "runtime_or_model_missing"
            return False
        # Legacy explicit reserve keeps its former meaning. New callers use the
        # experimental policy, requiring physical AND system commit headroom.
        for _ in range(3):
            try:
                memory = available_memory()
            except OSError:
                self.error = "memory_inspection_failed"
                return False
            self.memory_samples.append({"phase": "before_load", "system": memory})
            if reserve_mb is not None and memory and memory['available_bytes'] < (reserve_mb + 2560) * 1024**2:
                self.error = "insufficient_available_memory"
            else:
                self.error = self.memory_policy.entry_reason(memory)
            if self.error:
                return False
            time.sleep(0.2)
        if self.probe():
            self.error = "runtime_port_already_in_use"
            return False
        if os.name == "nt":
            import ctypes
            create = ctypes.windll.kernel32.CreateMutexW
            create.restype = ctypes.c_void_p
            create.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
            handle = create(None, False, "Local\\HarpiSenseHarpIABitNet")
            if not handle:
                raise OSError("instance guard failed")
            if ctypes.windll.kernel32.GetLastError() == 183:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle))
                self.error = "runtime_instance_already_owned"
                return False
            self._instance_handle = handle
        from urllib.parse import urlsplit
        port = urlsplit(self.url).port or 80
        args = [str(executable), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                "-t", str(threads), "-c", str(context), "-np", "1", "-ngl", "0",
                "--no-webui", "--no-context-shift", "--log-disable", "--sleep-idle-seconds", "-1", "-b", "128", "-ub", "128"]
        started = time.monotonic()
        try:
            Path(logs).mkdir(parents=True, exist_ok=True)
            self.log = open(Path(logs) / "runtime.log", "ab")
            environment = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_")}
            self.process = subprocess.Popen(args, stdout=self.log, stderr=self.log, env=environment,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._monitor_stop.clear()
            self._monitor = threading.Thread(target=self._watch_memory, daemon=True)
            self._monitor.start()
            while time.monotonic() - started < 90:
                if self.process.poll() is not None:
                    break
                if self.ready():
                    # /health is the runtime's loaded-state probe, not wrapper liveness.
                    self.load_seconds = time.monotonic() - started
                    self.error = None
                    return True
                time.sleep(0.2)
            self.error = self.error or "load_failed_or_timeout"
        except OSError:
            self.error = "runtime_start_failed"
        self.stop()
        return False

    def count_tokens(self, text, timeout=5):
        result = post_json(self.url + "/tokenize", {"content": text,
                           "add_special": True, "parse_special": True}, min(self.timeout, timeout, 5))
        tokens = result.get("tokens")
        if not isinstance(tokens, list) or any(type(t) is not int for t in tokens):
            raise ValueError("invalid tokenizer response")
        return len(tokens)

    def prepare_context(self, context, tokens):
        deadline = time.monotonic() + 5
        def count(text):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("context preparation deadline")
            return self.count_tokens(text, timeout=remaining)
        text, self.last_budget = prepare_prompt(context, count,
                                                self.context_tokens, min(tokens, self.output_tokens), self.frame_data)
        return text

    def frame_data(self, data):
        return frame(data)

    def _completion_payload(self, text, tokens):
        return {"prompt": text, "n_predict": tokens,
                "temperature": 0, "seed": 42, "stream": False, "cache_prompt": True,
                "n_keep": 0, "stop": ["<|eot_id|>", "<|end_of_text|>"]}

    def complete(self, text, tokens):
        if not self.ready():
            raise RuntimeError("model_not_ready")
        if not self._generation.acquire(blocking=False):
            raise RuntimeError("runtime_busy")
        started = time.monotonic()
        try:
            tokens = min(tokens, MAX_TOKENS, self.output_tokens)
            if self.count_tokens(text) + tokens + 16 > self.context_tokens:
                raise ContextBudgetExceeded("essential context exceeds token budget")
            payload = self._completion_payload(text, tokens)
            answer = post_json(self.url + "/completion", payload,
                               max(0.1, self.timeout - (time.monotonic() - started)))
            self._observe_completion(payload, answer)
            return valid_text(answer.get("content"))
        except ContextBudgetExceeded:
            raise
        except Exception:
            # Prevent an abandoned generation from consuming resources after timeout.
            if not self.failed:
                self.error = "inference_failed"
            self.failed = True
            self.stop()
            raise
        finally:
            self._generation.release()

    def _observe_completion(self, payload, response):
        """Diagnostic subclass hook; production does not retain raw prompts/output."""
        pass

    def _watch_memory(self):
        low_count = 0
        while not self._monitor_stop.is_set():
            if self.process is None or self.process.poll() is not None:
                return
            try:
                system, process = available_memory(), process_memory(self.process)
                self.memory_samples.append({"phase": "loaded", "monotonic": time.monotonic(),
                                            "system": system, "process": process})
                reason, low_count = self.memory_policy.pressure_reason(system, process, low_count)
            except Exception:
                reason = "memory_inspection_failed"
            if reason:
                self.failed, self.error = True, reason
                self._terminate_owned()
                return
            self._monitor_stop.wait(0.25)

    def _terminate_owned(self):
        with self._process_lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)

    def stop(self):
        self._monitor_stop.set()
        if self._monitor and self._monitor is not threading.current_thread():
            self._monitor.join(timeout=6)
        self._terminate_owned()
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
        if self._instance_handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._instance_handle))
            self._instance_handle = None
