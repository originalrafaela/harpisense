"""HTTP local limitado, sem execução administrativa ou dependência do HarpiServer."""
from collections import OrderedDict
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
import time

from .contracts import (MAX_BODY, MAX_TOKENS, ModelOutputRejected, context_dto,
                        frame, prompt, valid_model_text, valid_text)

LOG = logging.getLogger("harpia.server")


class Busy(Exception):
    pass


class Engine:
    def __init__(self, runtime, max_waiting=2, queue_wait_seconds=2):
        if type(max_waiting) is not int or not 0 <= max_waiting <= 2 or not 0 <= queue_wait_seconds <= 2:
            raise ValueError("invalid queue limits")
        self.runtime = runtime
        self.slots = threading.BoundedSemaphore(1 + max_waiting)
        self.queue_wait_seconds = queue_wait_seconds
        self.generation = threading.Lock()
        self.cache = OrderedDict()
        self.preparation = threading.local()

    def generate(self, text, tokens, context=None):
        if not self.slots.acquire(blocking=False):
            raise Busy()
        locked = False
        try:
            locked = self.generation.acquire(timeout=self.queue_wait_seconds)
            if not locked:
                raise Busy()
            if not self.runtime.ready():
                raise RuntimeError("model_not_ready")
            tokens = min(tokens, getattr(self.runtime, 'output_tokens', MAX_TOKENS))
            self.preparation.omitted = []
            if context is not None and hasattr(self.runtime, 'prepare_context'):
                text = self.runtime.prepare_context(context, tokens)
                self.preparation.omitted = list(self.runtime.last_budget['omitted_fields'])
            key = hashlib.sha256((text + str(tokens)).encode()).hexdigest()
            now = time.monotonic()
            if key in self.cache and now - self.cache[key][0] < 300:
                return self.cache[key][1]
            result = valid_text(self.runtime.complete(text, tokens))
            self.cache[key] = (time.monotonic(), result)
            while len(self.cache) > 64:
                self.cache.popitem(last=False)
            return result
        finally:
            if locked:
                self.generation.release()
            self.slots.release()


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = True
    request_queue_size = 8

    def __init__(self, address, runtime, token="", max_waiting=2, queue_wait_seconds=2):
        if address[0] != "127.0.0.1" or not 0 <= address[1] <= 65535:
            raise ValueError("only IPv4 loopback allowed")
        self.engine = Engine(runtime, max_waiting, queue_wait_seconds)
        self.token = token
        self.handlers = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def get_request(self):
        sock, addr = super().get_request()
        sock.settimeout(5)
        return sock, addr

    def process_request(self, request, client_address):
        if not self.handlers.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.handlers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.handlers.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "HarpIA"
    sys_version = ""

    def log_message(self, *args):
        pass  # No raw request path, payload or credentials in logs.

    def send_json(self, code, value):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
        except (OSError, TimeoutError):
            pass

    def authenticated(self):
        if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
            self.send_json(403, {"error": "invalid_host"})
            return False
        expected = self.server.token
        if expected and not hmac.compare_digest(self.headers.get("Authorization", "").encode(),
                                                ("Bearer " + expected).encode()):
            self.send_json(401, {"error": "authentication_required"})
            return False
        # Browser is not an integration client. No CORS and no cross-origin posts.
        if self.headers.get("Origin"):
            self.send_json(403, {"error": "browser_access_disabled"})
            return False
        return True

    def do_GET(self):
        if not self.authenticated():
            return
        if self.path == "/health":
            self.send_json(200, {"service": "active"})
        elif self.path == "/ready":
            ready = self.server.engine.runtime.ready()
            self.send_json(200 if ready else 503, {"model_loaded": ready, "ready": ready})
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        started = time.monotonic()
        if not self.authenticated():
            return
        if self.path not in {"/complete", "/explain"}:
            self.send_json(404, {"error": "not_found"})
            return
        try:
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                self.send_json(411, {"error": "single_content_length_required"})
                return
            size = int(self.headers["Content-Length"])
            if not 0 < size <= MAX_BODY:
                self.send_json(413, {"error": "body_too_large_or_empty"})
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json(415, {"error": "json_required"})
                return
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("incomplete body")
            def reject_constant(value):
                raise ValueError("nonfinite JSON")
            value = json.loads(raw, parse_constant=reject_constant)
            if self.path == "/explain":
                context = context_dto(value)
                text = self.server.engine.generate(prompt(context), MAX_TOKENS, context=context)
                try:
                    text = valid_model_text(text)
                except ModelOutputRejected as exc:
                    LOG.warning("model output rejected: %s", exc.reason)
                    self.send_json(503, {"error": "model_output_rejected", "reason": exc.reason})
                    return
                result = {"incident_id": context["incident_id"], "revision": context["revision"],
                          "source": "bitnet_unverified_text", "bitnet_status": "responded_unverified", "text": text}
                if self.server.engine.preparation.omitted:
                    result['omitted_context_fields'] = self.server.engine.preparation.omitted
            else:
                # Existing P11 wire format; preserve compatibility with {prompt,max_tokens}.
                if not isinstance(value, dict) or set(value) != {"prompt", "max_tokens"}:
                    raise ValueError("invalid completion fields")
                supplied, tokens = value["prompt"], value["max_tokens"]
                if not isinstance(supplied, str) or not 1 <= len(supplied) <= 2000 or type(tokens) is not int or not 1 <= tokens <= MAX_TOKENS:
                    raise ValueError("invalid completion input")
                # Treat the old prompt as untrusted data, never as a role instruction.
                safe = supplied.replace("<|", "＜｜").replace("|>", "｜＞")
                composed = frame("Dados legados P11: " + json.dumps(safe, ensure_ascii=False))
                result = {"text": self.server.engine.generate(composed, tokens)}
            self.send_json(200, result)
            LOG.info("explanation completed seconds=%.3f", time.monotonic() - started)
        except Busy:
            self.send_json(429, {"error": "queue_full_or_wait_timeout"})
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self.send_json(422, {"error": "invalid_input_or_output"})
        except TimeoutError:
            self.send_json(504, {"error": "timeout"})
        except Exception as exc:
            LOG.warning("inference unavailable: %s", type(exc).__name__)
            self.send_json(503, {"error": "model_unavailable"})
