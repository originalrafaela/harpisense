"""Processo persistente oficial llama-server do BitNet; CPU e loopback."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

from .client import endpoint_url, post_json
from .contracts import MAX_TOKENS, valid_text


def available_memory():
    if os.name != "nt":
        return None
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError("memory inspection failed")
    return {"total_bytes": value.total, "available_bytes": value.available}


class Runtime:
    def __init__(self, url="http://127.0.0.1:8092", timeout=45):
        self.url = endpoint_url(url, loopback=True)
        if not 0 < timeout <= 120:
            raise ValueError("invalid runtime timeout")
        self.timeout = timeout
        self.process = None
        self.log = None
        self.failed = False
        self.load_seconds = None
        self.error = "not_started"

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

    def start(self, executable, model, logs, threads=2, context=2048, reserve_mb=4096):
        if self.process:
            raise RuntimeError("runtime already started")
        if not 1 <= threads <= 4 or not 512 <= context <= 4096 or reserve_mb < 4096:
            raise ValueError("resource limits outside conservative profile")
        executable, model = Path(executable).resolve(), Path(model).resolve()
        if not executable.is_file() or not model.is_file():
            self.error = "runtime_or_model_missing"
            return False
        memory = available_memory()
        # Preserve reserve for VMs plus conservative 2.5 GiB runtime allowance.
        if memory and memory["available_bytes"] < (reserve_mb + 2560) * 1024**2:
            self.error = "insufficient_available_memory"
            return False
        if self.probe():
            self.error = "runtime_port_already_in_use"
            return False
        Path(logs).mkdir(parents=True, exist_ok=True)
        self.log = open(Path(logs) / "runtime.log", "ab")
        from urllib.parse import urlsplit
        port = urlsplit(self.url).port or 80
        args = [str(executable), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                "-t", str(threads), "-c", str(context), "-np", "1", "-ngl", "0",
                "--no-webui", "--log-disable", "--sleep-idle-seconds", "-1", "-b", "128", "-ub", "128"]
        started = time.monotonic()
        try:
            environment = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_")}
            self.process = subprocess.Popen(args, stdout=self.log, stderr=self.log, env=environment,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while time.monotonic() - started < 90:
                if self.process.poll() is not None:
                    break
                if self.ready():
                    # /health is the runtime's loaded-state probe, not wrapper liveness.
                    self.load_seconds = time.monotonic() - started
                    self.error = None
                    return True
                time.sleep(0.2)
            self.error = "load_failed_or_timeout"
        except OSError:
            self.error = "runtime_start_failed"
        self.stop()
        return False

    def complete(self, text, tokens):
        if not self.ready():
            raise RuntimeError("model_not_ready")
        try:
            answer = post_json(self.url + "/completion", {
                "prompt": text, "n_predict": min(tokens, MAX_TOKENS),
                "temperature": 0, "seed": 42, "stream": False, "cache_prompt": True,
                "stop": ["<|eot_id|>", "<|end_of_text|>"],
            }, self.timeout)
            return valid_text(answer.get("content"))
        except Exception:
            # Prevent an abandoned generation from consuming resources after timeout.
            self.failed = True
            self.error = "inference_failed"
            self.stop()
            raise

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.log:
            self.log.close()
            self.log = None
