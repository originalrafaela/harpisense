#!/usr/bin/env python3
"""Sanitiza eventos de uma fonte e assina seu manifest de cobertura.

O operador da fonte assume explicitamente a afirmação de completude e
continuidade; o utilitário não infere esses fatos a partir de linhas vazias.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from coverage_evidence import (
    SOURCE_SCHEMA,
    canonical_json,
    load_profile,
    parse_time,
    private_key_fingerprint,
    sha256_file,
    sign_payload,
    verify_signed_session,
)


def build_source_bundle(*, profile_path, session_report_path, source_id,
                        input_records, output_dir, signing_key, boot_id,
                        cursor_start, cursor_end, interval_start, interval_end,
                        continuity_verified=False, coverage_status="UNKNOWN",
                        coverage_reason=None, previous_cursor=None):
    profile = load_profile(profile_path)
    profile["_sha256"] = sha256_file(Path(profile_path))
    source_config = next((item for item in profile["required_sources"] if item["source"] == source_id), None)
    if source_config is None or source_config["kind"] != "signed_log_bundle":
        raise ValueError("Fonte não está declarada como signed_log_bundle no perfil")
    if private_key_fingerprint(signing_key) != source_config["public_key_sha256"].lower():
        raise ValueError("Chave privada não corresponde à fonte do perfil")
    session_path = Path(session_report_path).resolve(strict=True)
    session = json.loads(session_path.read_text(encoding="utf-8"))
    verify_signed_session(session, Path(str(session_path) + ".sig"), profile)
    if source_id not in session.get("required_sources", []):
        raise ValueError("Fonte não consta na lista obrigatória assinada da sessão")
    start = parse_time(session["capture_effective_started_at"])
    end = parse_time(session["capture_effective_ended_at"])
    source_start = parse_time(interval_start)
    source_end = parse_time(interval_end)
    if source_start > start or source_end < end or source_end <= source_start:
        raise ValueError("Intervalo da fonte não cobre o intervalo efetivo da sessão")
    if coverage_status not in ("COMPLETE", "INCOMPLETE", "UNKNOWN"):
        raise ValueError("coverage_status inválido")
    if coverage_status == "COMPLETE":
        if not continuity_verified or not cursor_start or not cursor_end or not boot_id:
            raise ValueError("Completo exige cursor, boot ID e continuidade explicitamente confirmados")
    elif not isinstance(coverage_reason, str) or not coverage_reason.strip():
        raise ValueError("Fonte incompleta/desconhecida exige motivo explícito")

    sanitized = []
    seen = set()
    with Path(input_records).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Linha {line_number}: evento deve ser objeto JSON")
            event_id = row.get("event_id")
            if not isinstance(event_id, str) or not event_id.strip() or event_id in seen:
                raise ValueError(f"Linha {line_number}: event_id ausente/duplicado")
            seen.add(event_id)
            observed_at = parse_time(row.get("observed_at"))
            if not start <= observed_at < end:
                raise ValueError(f"Linha {line_number}: evidência fora do período da sessão")
            sanitized.append({
                "event_id": event_id,
                "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                "journal_cursor": row.get("journal_cursor"),
                "journal_boot_id": row.get("journal_boot_id"),
            })

    destination = Path(output_dir)
    if not destination.is_dir():
        raise ValueError("Diretório da fonte precisa existir")
    records_path = destination / "records.jsonl"
    manifest_path = destination / f"{source_id}.manifest.json"
    payload = b"".join(canonical_json(row) + b"\n" for row in sanitized)
    for path in (records_path, manifest_path):
        if path.exists():
            raise ValueError("Bundle já existe; sobrescrita proibida")

    manifest = {
        "schema_version": SOURCE_SCHEMA,
        "evidence_id": hashlib.sha256((session["session_id"] + "\0" + source_id + "\0" + boot_id).encode()).hexdigest(),
        "collection_session_id": session["session_id"],
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "session_report_sha256": sha256_file(session_path),
        "pcap_sha256": session["pcap_sha256"],
        "source": source_id,
        "host_id": source_config["host_id"],
        "sensor_id": profile["sensor_id"],
        "target_ref": profile["target_ref"],
        "boot_id": boot_id,
        "interval_start": source_start.isoformat().replace("+00:00", "Z"),
        "interval_end": source_end.isoformat().replace("+00:00", "Z"),
        "cursor_start": cursor_start,
        "cursor_end": cursor_end,
        "previous_cursor": previous_cursor,
        "coverage_status": coverage_status,
        "continuity_verified": continuity_verified is True,
        "coverage_reason": coverage_reason,
        "records_file": records_path.name,
        "records_sha256": hashlib.sha256(payload).hexdigest(),
        "record_count": len(sanitized),
    }
    manifest["signature_ed25519"] = sign_payload(canonical_json(manifest), signing_key)
    _write_exclusive(records_path, payload)
    try:
        _write_exclusive(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    except Exception:
        records_path.unlink(missing_ok=True)
        raise
    return manifest_path, records_path


def _write_exclusive(path, payload):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description="Cria bundle de evidência de fonte P08 sem payloads")
    parser.add_argument("--profile-config", type=Path, required=True)
    parser.add_argument("--session-report", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--input-records", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--boot-id")
    parser.add_argument("--cursor-start")
    parser.add_argument("--cursor-end")
    parser.add_argument("--interval-start", required=True)
    parser.add_argument("--interval-end", required=True)
    parser.add_argument("--coverage-status", choices=("COMPLETE", "INCOMPLETE", "UNKNOWN"), required=True)
    parser.add_argument("--continuity-verified", action="store_true")
    parser.add_argument("--coverage-reason")
    parser.add_argument("--previous-cursor")
    args = parser.parse_args()
    try:
        manifest, records = build_source_bundle(
            profile_path=args.profile_config,
            session_report_path=args.session_report,
            source_id=args.source,
            input_records=args.input_records,
            output_dir=args.output_dir,
            signing_key=args.signing_key,
            boot_id=args.boot_id,
            cursor_start=args.cursor_start,
            cursor_end=args.cursor_end,
            interval_start=args.interval_start,
            interval_end=args.interval_end,
            continuity_verified=args.continuity_verified,
            coverage_status=args.coverage_status,
            coverage_reason=args.coverage_reason,
            previous_cursor=args.previous_cursor,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "SOURCE_BUNDLE_CREATED", "manifest": str(manifest), "records": str(records), "record_count": json.loads(manifest.read_text(encoding="utf-8"))["record_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
