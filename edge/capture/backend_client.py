from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BACKEND_USERNAME_ENV = "HARPISENSE_BACKEND_USERNAME"
DEFAULT_BACKEND_PASSWORD_ENV = "HARPISENSE_BACKEND_PASSWORD"


@dataclass(frozen=True)
class BackendClientConfig:
    url: str
    timeout_seconds: float = 5.0
    username_env: str = DEFAULT_BACKEND_USERNAME_ENV
    password_env: str = DEFAULT_BACKEND_PASSWORD_ENV


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    status_code: int | None
    error: str | None = None
    duplicate: bool | None = None


class BackendClient:
    def __init__(self, config: BackendClientConfig) -> None:
        self.config = config

    def post_network_event(self, event: dict[str, Any]) -> DeliveryResult:
        if event.get("event_type") != "network_event":
            return DeliveryResult(
                delivered=False,
                status_code=None,
                error="backend delivery only supports event_type=network_event",
            )

        credentials = self._load_basic_credentials()
        if credentials is None:
            return DeliveryResult(
                delivered=False,
                status_code=None,
                error=(
                    "missing backend Basic credentials: set "
                    f"{self.config.username_env} and {self.config.password_env}"
                ),
            )

        data = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": self._basic_authorization_header(*credentials),
        }

        request = urllib.request.Request(self.config.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                status_code = int(response.status)
                body = _read_json_response(response)
                if status_code == 202:
                    return DeliveryResult(
                        delivered=True,
                        status_code=status_code,
                        duplicate=body.get("duplicate") if isinstance(body.get("duplicate"), bool) else None,
                    )
                return DeliveryResult(
                    delivered=False,
                    status_code=status_code,
                    error=_delivery_error(status_code, body),
                )
        except urllib.error.HTTPError as exc:
            body = _read_json_response(exc)
            return DeliveryResult(delivered=False, status_code=exc.code, error=_delivery_error(exc.code, body))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return DeliveryResult(delivered=False, status_code=None, error=str(exc))

    def _load_basic_credentials(self) -> tuple[str, str] | None:
        username = os.getenv(self.config.username_env)
        password = os.getenv(self.config.password_env)
        if not username or not password:
            return None
        return username.strip(), password

    def _basic_authorization_header(self, username: str, password: str) -> str:
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"


def _read_json_response(response: Any) -> dict[str, Any]:
    try:
        payload = response.read()
    except OSError:
        return {}
    if not payload:
        return {}
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _delivery_error(status_code: int, body: dict[str, Any]) -> str:
    code = None
    message = None
    error = body.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
    elif isinstance(error, str):
        message = error

    if not message:
        message = body.get("detail") if isinstance(body.get("detail"), str) else None
    if code and message:
        return f"backend returned HTTP {status_code}: {code}: {message}"
    if code:
        return f"backend returned HTTP {status_code}: {code}"
    if message:
        return f"backend returned HTTP {status_code}: {message}"
    return f"backend returned HTTP {status_code}"
