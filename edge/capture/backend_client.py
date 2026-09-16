from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackendClientConfig:
    url: str
    timeout_seconds: float = 5.0
    token_env: str | None = None
    token_file: Path | None = None


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    status_code: int | None
    error: str | None = None


class BackendClient:
    def __init__(self, config: BackendClientConfig) -> None:
        self.config = config

    def post_network_event(self, event: dict[str, Any]) -> DeliveryResult:
        data = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        token = self._load_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(self.config.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                status_code = int(response.status)
                if status_code == 202:
                    return DeliveryResult(delivered=True, status_code=status_code)
                return DeliveryResult(
                    delivered=False,
                    status_code=status_code,
                    error=f"backend returned HTTP {status_code}, expected 202",
                )
        except urllib.error.HTTPError as exc:
            return DeliveryResult(delivered=False, status_code=exc.code, error=f"backend returned HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return DeliveryResult(delivered=False, status_code=None, error=str(exc))

    def _load_token(self) -> str | None:
        if self.config.token_env:
            token = os.getenv(self.config.token_env)
            if token:
                return token.strip()
        if self.config.token_file:
            try:
                token = self.config.token_file.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                return None
            return token or None
        return None
