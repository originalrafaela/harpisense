#!/usr/bin/env python3
"""Orquestra uma coleta P08, evidências de fonte e gates P08 -> P09.

Não persiste no P11. Não executa RF/IF nem IPS. Cada sessão usa nomes novos e
publicação exclusiva; fontes externas precisam fornecer manifests assinados.
"""

import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from coverage_evidence import (
    GATEWAY_SOURCE,
    build_coverage_report,
    canonical_json,
    link_auxiliary_events,
    load_profile,
    sign_payload,
    verify_json_signature,
)

BASE = Path("/opt/harpisense")
DEFAULT_PYTHON = BASE / "venv/bin/python"
DEFAULT_CONTROLLER = BASE / "staging/p08-captura/capture_session_v4.py"
DEFAULT_INTEGRATOR = BASE / "staging/p08-captura/integracao/integrar_p08_v2.py"
DEFAULT_DIAGNOSTIC = BASE / "staging/p08-captura/integracao/diagnosticar_cobertura.py"
DEFAULT_CAPTURES = BASE / "capturas"
DEFAULT_P09 = BASE / "staging/p09-deteccao-decisao/adaptador_logs_p08_p09"


def write_json_exclusive(path: Path, document: dict) -> None:
    payload = json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(__import__("os"), "O_NOFOLLOW"):
        flags |= __import__("os").O_NOFOLLOW
    fd = __import__("os").open(path, flags, 0o600)
    with __import__("os").fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        __import__("os").fsync(stream.fileno())


def run_command(command, timeout_seconds):
    return subprocess.run(
        command, capture_output=True, text=True, timeout=timeout_seconds,
        check=False,
    )


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _wait_for_source_manifests(evidence_dir: Path, profile: dict, wait_seconds: float) -> None:
    external = [source for source in profile["required_sources"] if source["kind"] == "signed_log_bundle"]
    deadline = time.monotonic() + wait_seconds
    while external and time.monotonic() < deadline:
        ready = all(
            (evidence_dir / source["source"]).is_dir()
            and any((evidence_dir / source["source"]).glob("*.manifest.json"))
            for source in external
        )
        if ready:
            return
        time.sleep(min(2.0, max(0, deadline - time.monotonic())))


def _empty_coverage(session, profile, session_path, signature_path, reason):
    source_coverage = {
        source["source"]: {
            "status": "INCOMPLETE" if source["source"] == GATEWAY_SOURCE else "UNKNOWN",
            "reasons": [reason if source["source"] == GATEWAY_SOURCE else "Manifest obrigatório ausente"],
            "evidence": [],
        }
        for source in profile["required_sources"]
    }
    return {
        "schema_version": "harpisense.p08.coverage.evidence.v1",
        "session": session,
        "session_report": str(session_path.resolve()),
        "session_signature": str(signature_path.resolve()),
        "session_pcap_sha256": None,
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "required_sources": [source["source"] for source in profile["required_sources"]],
        "source_coverage": source_coverage,
        "coverage_records": [],
        "intervals": [],
        "source_coverage_status": "INCOMPLETE",
        "collection_complete": False,
        "ready_for_inference": False,
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "log_counts": {},
        "limitations": [reason, "Nenhuma inferência ou IPS autorizada."],
    }


def _run_p09_gate(adapter_dir, captures, session, coverage, profile, batch_path):
    adapter_dir = Path(adapter_dir).resolve(strict=True)
    if str(adapter_dir) not in sys.path:
        sys.path.insert(0, str(adapter_dir))
    module = importlib.import_module("p08_p09_pipeline")
    gateway = next(source for source in profile["required_sources"] if source["source"] == GATEWAY_SOURCE)
    coverage_path = Path(captures) / f"{session}.coverage.json"
    signature_path = Path(str(coverage_path) + ".sig")
    signature_verified = verify_json_signature(coverage_path, signature_path, gateway)
    if not signature_verified:
        raise ValueError("Assinatura do relatório de cobertura inválida")
    windows = [
        {
            "window_id": item["observation_id"],
            "window_start": item["window_start"],
            "window_end": item["window_end"],
            "collection_session_id": item["collection_session_id"],
            "sensor_id": item["sensor_id"],
            "target_ref": item["target_ref"],
        }
        for item in coverage["intervals"] if not item["partial_window"]
    ]
    kwargs = {
        "base_dir": captures,
        "session_name": session,
        "events": None if batch_path else [],
        "windows": windows,
        "coverage_records": coverage["coverage_records"],
        "required_sources": coverage["required_sources"],
        "coverage_provenance_verified": signature_verified and coverage["source_coverage_status"] == "COMPLETE",
    }
    if batch_path:
        kwargs["batch_path"] = batch_path
    result = module.run_pipeline(**kwargs)
    result["coverage_report_signature_verified"] = signature_verified
    result["collection_complete"] = False
    result["ready_for_inference"] = False
    result["authorized_for_inference"] = False
    result["authorized_for_ips"] = False
    result["log_counts"] = {}
    return result


def main():
    parser = argparse.ArgumentParser(description="Coleta e avalia cobertura P08 com evidências por fonte")
    parser.add_argument("--session", required=True)
    parser.add_argument("--profile-config", required=True, type=Path)
    parser.add_argument("--signing-key", required=True, type=Path)
    parser.add_argument("--source-evidence-dir", required=True, type=Path)
    parser.add_argument("--audit-batch", type=Path)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--startup-timeout", type=float, default=30)
    parser.add_argument("--heartbeat-seconds", type=float, default=1)
    parser.add_argument("--source-evidence-wait-seconds", type=float, default=180)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CAPTURES)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--controller", type=Path, default=DEFAULT_CONTROLLER)
    parser.add_argument("--integrator", type=Path, default=DEFAULT_INTEGRATOR)
    parser.add_argument("--diagnostic", type=Path, default=DEFAULT_DIAGNOSTIC)
    parser.add_argument("--p09-adapter-dir", type=Path, default=DEFAULT_P09)
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.session):
        parser.error("Identificador de sessão inválido")
    if not 1 <= args.duration <= 300:
        parser.error("Duração efetiva deve estar entre 1 e 300 segundos")
    if args.source_evidence_wait_seconds < 0 or args.source_evidence_wait_seconds > 900:
        parser.error("source-evidence-wait-seconds deve estar entre 0 e 900")
    try:
        profile = load_profile(args.profile_config)
        profile["_sha256"] = hashlib.sha256(args.profile_config.read_bytes()).hexdigest()
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f"Perfil inválido: {exc}")
    if not args.output_dir.is_dir():
        parser.error("Diretório de artefatos não existe; não é criado automaticamente")
    if not args.source_evidence_dir.is_dir():
        parser.error("Diretório de importação de evidências de fonte não existe")

    captures = args.output_dir.resolve()
    paths = {
        "pcap": captures / f"{args.session}.pcap",
        "session": captures / f"{args.session}.session.json",
        "session_sig": captures / f"{args.session}.session.json.sig",
        "integration": captures / f"{args.session}.p08.json",
        "coverage": captures / f"{args.session}.coverage.json",
        "coverage_sig": captures / f"{args.session}.coverage.json.sig",
        "gate": captures / f"{args.session}.p09-gate.json",
    }
    if any(path.exists() for path in paths.values()):
        parser.error("Um ou mais artefatos desta sessão já existem; sobrescrita proibida")
    if args.audit_batch and not args.audit_batch.is_file():
        parser.error("Lote auxiliar MQTT não existe")

    capture = run_command([
        str(args.python), str(args.controller),
        "--session", args.session,
        "--profile-config", str(args.profile_config.resolve()),
        "--signing-key", str(args.signing_key.resolve()),
        "--duration", str(args.duration),
        "--startup-timeout", str(args.startup_timeout),
        "--heartbeat-seconds", str(args.heartbeat_seconds),
        "--output", str(paths["pcap"]),
    ], args.duration + args.startup_timeout + 30)
    if not paths["session"].is_file():
        raise RuntimeError("Coletor não publicou relatório de sessão: " + capture.stderr[-500:])
    session_doc = _read_json(paths["session"])

    integration_doc = {"aggregation": {"windows": []}, "ready_for_inference": False}
    integration_error = None
    if session_doc.get("session_basic_checks_passed") is True:
        integration = run_command([
            str(args.python), str(args.integrator),
            "--session-report", str(paths["session"]),
            "--profile-config", str(args.profile_config.resolve()),
            "--sensor-id", profile["sensor_id"],
            "--destination", profile["destination_ip"],
            "--session", args.session,
            "--profile", profile["traffic_profile"],
            "--output", str(paths["integration"]),
        ], 180)
        if integration.returncode == 0 and paths["integration"].is_file():
            integration_doc = _read_json(paths["integration"])
        else:
            integration_error = integration.stderr[-1000:]
    else:
        integration_error = "Captura não passou nas verificações básicas; integração não executada"

    _wait_for_source_manifests(args.source_evidence_dir, profile, args.source_evidence_wait_seconds)
    try:
        coverage = build_coverage_report(
            session_doc, paths["session"], paths["session_sig"],
            integration_doc, profile, args.source_evidence_dir, paths["pcap"],
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        coverage = _empty_coverage(
            args.session, profile, paths["session"], paths["session_sig"],
            "Falha ao validar artefatos/fontes: " + type(exc).__name__ + ": " + str(exc)[:300],
        )
    if integration_error:
        coverage["integration_status"] = "INCOMPLETE"
        coverage.setdefault("limitations", []).append("Integração de janelas: " + integration_error)
    coverage_payload = json.dumps(coverage, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    fd_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = __import__("os").open(paths["coverage"], fd_flags, 0o600)
    with __import__("os").fdopen(fd, "wb") as stream:
        stream.write(coverage_payload)
        stream.flush()
        __import__("os").fsync(stream.fileno())
    gateway = next(source for source in profile["required_sources"] if source["source"] == GATEWAY_SOURCE)
    coverage_signature = sign_payload(canonical_json(coverage), args.signing_key).encode("ascii") + b"\n"
    fd = __import__("os").open(paths["coverage_sig"], fd_flags, 0o600)
    with __import__("os").fdopen(fd, "wb") as stream:
        stream.write(coverage_signature)
        stream.flush()
        __import__("os").fsync(stream.fileno())

    try:
        gate = _run_p09_gate(args.p09_adapter_dir, captures, args.session, coverage, profile, args.audit_batch)
    except (OSError, ValueError, ImportError, AttributeError, TypeError, KeyError) as exc:
        gate = {
            "status": "BLOCKED",
            "reasons": ["Gate P08 -> P09 não foi executado: " + type(exc).__name__ + ": " + str(exc)[:300]],
            "authorized_for_inference": False,
            "authorized_for_ips": False,
            "log_counts": {},
        }
    identity = None
    try:
        from coverage_evidence import parse_time
        identity = {
            "collection_session_id": args.session,
            "sensor_id": profile["sensor_id"],
            "target_ref": profile["target_ref"],
            "profile_id": profile["profile_id"],
            "traffic_profile": profile["traffic_profile"],
            "session_report_sha256": hashlib.sha256(paths["session"].read_bytes()).hexdigest(),
            "pcap_sha256": session_doc.get("pcap_sha256"),
            "start": parse_time(session_doc["capture_effective_started_at"]),
            "end": parse_time(session_doc["capture_effective_ended_at"]),
        }
    except (KeyError, ValueError, TypeError):
        pass
    if args.audit_batch:
        auxiliary = gate.get("auxiliary_audit") if isinstance(gate, dict) else None
        gate["auxiliary_mqtt_linkage"] = (
            link_auxiliary_events(auxiliary, args.source_evidence_dir, profile, identity, coverage.get("intervals", []))
            if identity else {"status": "UNBOUND", "reason": "Sessão sem intervalo efetivo", "events": []}
        )
    gate["coverage_file"] = str(paths["coverage"])
    gate["source_coverage_status"] = coverage.get("source_coverage_status", "UNKNOWN")
    gate["coverage_signature_verified"] = verify_json_signature(paths["coverage"], paths["coverage_sig"], gateway)
    gate["collection_complete"] = False
    gate["ready_for_inference"] = False
    gate["authorized_for_inference"] = False
    gate["authorized_for_ips"] = False
    gate["log_counts"] = {}
    write_json_exclusive(paths["gate"], gate)

    print(json.dumps({
        "status": "SESSION_EVIDENCE_RECORDED",
        "session": args.session,
        "duration_requested_seconds": args.duration,
        "duration_effective_seconds": session_doc.get("effective_duration_seconds"),
        "capture_status": session_doc.get("termination_reason"),
        "source_coverage_status": coverage.get("source_coverage_status", "INCOMPLETE"),
        "source_status": {name: row.get("status") for name, row in coverage.get("source_coverage", {}).items()},
        "coverage_intervals": len(coverage.get("intervals", [])),
        "p09_gate_status": gate.get("artifact_consistent"),
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "log_counts": {},
        "artifacts": {key: str(value) for key, value in paths.items()},
        "p11_persistence": "NOT_RUN",
    }, indent=2, ensure_ascii=False))
    return 0 if session_doc.get("session_basic_checks_passed") is True else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
