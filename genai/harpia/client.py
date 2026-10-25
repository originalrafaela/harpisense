"""Adaptador preparatório; não é instalado/importado pelo backend nesta entrega."""
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from .contracts import OPTIONAL_EVIDENCE, context_dto, valid_text

LOG = logging.getLogger("harpia.client")


def fallback(context):
    # Reutiliza a redação e os campos do backend11/bitnet.py aprovado (P11 v2),
    # com rótulo explícito e identificador preservado; sem importar seu servidor.
    facts = context.get("facts", {})
    return {
        "source": "deterministic_fallback", "incident_id": context["incident_id"],
        "revision": context["revision"],
        "text": "Explicação alternativa determinística. Incidente " + context["incident_id"]
        + "; revisão " + str(context["revision"]) + ". Estado registrado: "
        + str(facts.get("status", "não informado"))
        + ". Consulte os dados estruturados para risco, evidências e execução. "
        + "Dados ausentes não permitem concluir ataque ou mitigação.",
    }


def endpoint_url(url, *, loopback=False):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError("invalid service URL")
    if loopback and (p.scheme != "http" or p.hostname != "127.0.0.1"):
        raise ValueError("loopback 127.0.0.1 required")
    if p.path not in {"", "/"}:
        raise ValueError("URL must be a base URL")
    _ = p.port  # validate port
    return url.rstrip("/")


def post_json(url, payload, timeout, token=""):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, json.dumps(payload, ensure_ascii=False).encode(), headers)
    # No environment proxy or redirects: never leak context/token to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        data = response.read(16385)
        if len(data) > 16384:
            raise ValueError("response too large")
        return json.loads(data)


class Client:
    """Cache limitada 5 min; serializa chamadas deste cliente e evita repetição."""
    def __init__(self, url=None, token=None, timeout=60, transport=None,
                 expected_model=None, expected_source='bitnet_unverified_text'):
        if expected_model is not None and (not isinstance(expected_model, str) or not 1 <= len(expected_model) <= 128):
            raise ValueError('invalid expected model identity')
        if expected_source not in {'bitnet_unverified_text', 'model_unverified_text'} or (
                expected_source == 'model_unverified_text' and not expected_model):
            raise ValueError('generic model source requires explicit expected model')
        self.expected_model, self.expected_source = expected_model, expected_source
        self.url = endpoint_url(url or os.getenv("HARPIA_URL", "http://127.0.0.1:8091"))
        self.token = token if token is not None else os.getenv("HARPIA_TOKEN", "")
        if not 0 < timeout <= 120:
            raise ValueError("invalid timeout")
        self.timeout = timeout
        self.transport = transport or post_json
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def explanation(self, context):
        context = context_dto(context)  # invalid input is not disguised as LLM failure
        deadline = time.monotonic() + self.timeout
        key = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        if not self.lock.acquire(timeout=self.timeout):
            return {**fallback(context), "bitnet_status": "client_busy"}
        try:
            now = time.monotonic()
            if key in self.cache and now - self.cache[key][0] < 300:
                return dict(self.cache[key][1])
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("client deadline")
                result = self.transport(self.url + "/explain", context, remaining, self.token)
                if not isinstance(result, dict) or result.get("incident_id") != context["incident_id"] or type(result.get("revision")) is not int or result["revision"] != context["revision"]:
                    raise ValueError("response identity mismatch")
                if result.get("source") != self.expected_source or result.get("bitnet_status") != "responded_unverified":
                    raise ValueError("invalid response source")
                if self.expected_model is not None and result.get('model_id') != self.expected_model:
                    raise ValueError('response model mismatch')
                omitted = result.get('omitted_context_fields', [])
                if not isinstance(omitted, list) or len(omitted) > 2 or any(k not in OPTIONAL_EVIDENCE for k in omitted):
                    raise ValueError("invalid omission notice")
                result = {"incident_id": context["incident_id"], "revision": context["revision"],
                          "source": self.expected_source, "bitnet_status": "responded_unverified",
                          "text": valid_text(result.get("text"))}
                if self.expected_model is not None:
                    result['model_id'] = self.expected_model
                if omitted:
                    result['omitted_context_fields'] = list(omitted)
                self.cache[key] = (now, result)
                while len(self.cache) > 64:
                    self.cache.popitem(last=False)
                return dict(result)
            except Exception as exc:
                # Only exception class; URL, request fields and token never logged.
                reason = "http_" + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
                LOG.warning("explanation fallback: %s", reason)
                return {**fallback(context), "bitnet_status": "unavailable_or_timeout",
                        "technical_reason": reason}
        finally:
            self.lock.release()
