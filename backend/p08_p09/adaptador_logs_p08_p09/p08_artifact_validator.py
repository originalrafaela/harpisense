"""Validação experimental de consistência dos artefatos P08.

Não autentica a origem dos arquivos, não comprova cobertura
contínua e não autoriza inferência ou ações IPS.
"""

import hashlib
import json
from pathlib import Path


def validate_p08_artifacts(base_dir, session_name):
    base = Path(base_dir)

    if (
        not isinstance(session_name, str)
        or not session_name
        or session_name in (".", "..")
        or "/" in session_name
        or "\\" in session_name
    ):
        raise ValueError("Nome de sessão inválido")

    session_path = base / f"{session_name}.session.json"
    coverage_path = base / f"{session_name}.coverage.json"
    pcap_path = base / f"{session_name}.pcap"

    session = json.loads(session_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    digest = hashlib.sha256()
    with pcap_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    checks = {
        "pcap_path_matches": (
            session.get("pcap_path") == str(pcap_path)
        ),
        "pcap_size_matches": (
            pcap_path.stat().st_size == session.get("pcap_size_bytes")
        ),
        "pcap_sha256_matches": (
            digest.hexdigest() == session.get("pcap_sha256")
        ),
        "coverage_session_matches": (
            coverage.get("session") == session_name
        ),
        "collection_state_matches": (
            isinstance(session.get("collection_complete"), bool)
            and session.get("collection_complete")
                is coverage.get("collection_complete")
        ),
        "inference_state_matches": (
            isinstance(session.get("ready_for_inference"), bool)
            and session.get("ready_for_inference")
                is coverage.get("ready_for_inference")
        ),
        "inference_blocked": (
            session.get("ready_for_inference") is False
            and coverage.get("ready_for_inference") is False
        ),
    }

    return {
        "session": session_name,
        "checks": checks,
        "consistent": all(checks.values()),
        "authorized_for_inference": False,
        "authorized_for_ips": False,
    }
