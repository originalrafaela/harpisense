"""Verificação conservadora de evidências de cobertura P08.

Usa o perfil P08 selecionado e manifests assinados pelas fontes. A validação
temporal nunca habilita inferência, IPS nem contagens opcionais de features.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import ipaddress
import re
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PROFILE_SCHEMA = "harpisense.p08.capture-profile.v1"
SOURCE_SCHEMA = "harpisense.p08.source-evidence.v1"
COVERAGE_SCHEMA = "harpisense.p08.coverage.evidence.v1"
GATEWAY_SOURCE = "gateway_capture"


def parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamp deve ser texto ISO-8601")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp sem fuso horário")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_profile(path: Path) -> dict:
    profile_path = Path(path).resolve(strict=True)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or profile.get("schema_version") != PROFILE_SCHEMA:
        raise ValueError("Schema de perfil P08 inválido")
    for key in ("profile_id", "traffic_profile", "sensor_id", "target_ref", "interface", "source_ip", "destination_ip"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError(f"Perfil sem {key}")
    sources = profile.get("required_sources")
    for key in ("source_ip", "destination_ip"):
        if ipaddress.ip_address(profile[key]).version != 4:
            raise ValueError("Perfil exige IPv4")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Perfil sem fontes obrigatórias")
    seen = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Fonte obrigatória inválida")
        source_id = source.get("source")
        if not isinstance(source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source_id) or source_id in seen:
            raise ValueError("Identificador de fonte ausente ou duplicado")
        seen.add(source_id)
        if source.get("kind") not in ("gateway_capture", "signed_log_bundle"):
            raise ValueError(f"Tipo de fonte não suportado: {source_id}")
        if not isinstance(source.get("host_id"), str) or not source["host_id"].strip():
            raise ValueError(f"Host esperado não definido para {source_id}")
        if not isinstance(source.get("public_key"), str) or not source["public_key"].strip():
            raise ValueError(f"Chave pública não definida para {source_id}")
        if not isinstance(source.get("public_key_sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", source["public_key_sha256"]):
            raise ValueError(f"Fingerprint SHA-256 ausente para {source_id}")
    gateway = [s for s in sources if s["source"] == GATEWAY_SOURCE]
    if len(gateway) != 1 or gateway[0]["kind"] != "gateway_capture":
        raise ValueError("O perfil precisa de exatamente uma fonte gateway_capture")
    return profile


def _run_openssl(arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["openssl", *arguments], input=input_bytes, capture_output=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("OpenSSL indisponível ou expirou") from exc
    if result.returncode != 0:
        raise ValueError("Falha na operação Ed25519")
    return result.stdout


def public_key_fingerprint(public_key: Path) -> str:
    der = _run_openssl([
        "pkey", "-pubin", "-in", str(public_key), "-outform", "DER"
    ])
    return hashlib.sha256(der).hexdigest()


def private_key_fingerprint(private_key: Path) -> str:
    path = Path(private_key).resolve(strict=True)
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise ValueError("A chave privada precisa de permissão 0600 ou mais restrita")
    der = _run_openssl([
        "pkey", "-in", str(path), "-pubout", "-outform", "DER"
    ])
    return hashlib.sha256(der).hexdigest()


def verify_signature(payload: bytes, signature_b64: str, source: dict) -> bool:
    public_key = Path(source["public_key"]).resolve(strict=True)
    actual_fingerprint = public_key_fingerprint(public_key)
    if actual_fingerprint.lower() != source["public_key_sha256"].lower():
        raise ValueError("Fingerprint da chave pública diverge do perfil")
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Assinatura Ed25519 inválida") from exc
    with tempfile.TemporaryDirectory(prefix="harpisense-p08-verify-") as temp:
        payload_path = Path(temp) / "payload.json"
        signature_path = Path(temp) / "payload.sig"
        payload_path.write_bytes(payload)
        signature_path.write_bytes(signature)
        try:
            _run_openssl([
                "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key),
                "-rawin", "-in", str(payload_path), "-sigfile", str(signature_path),
            ])
        except ValueError:
            return False
    return True


def sign_payload(payload: bytes, private_key: Path) -> str:
    key = Path(private_key).resolve(strict=True)
    if not key.is_file():
        raise ValueError("Chave privada de assinatura ausente")
    if os.name == "posix" and key.stat().st_mode & 0o077:
        raise ValueError("A chave privada precisa de permissão 0600 ou mais restrita")
    with tempfile.TemporaryDirectory(prefix="harpisense-p08-sign-") as temp:
        payload_path = Path(temp) / "payload.json"
        signature_path = Path(temp) / "payload.sig"
        payload_path.write_bytes(payload)
        _run_openssl([
            "pkeyutl", "-sign", "-inkey", str(key), "-rawin", "-in",
            str(payload_path), "-out", str(signature_path),
        ])
        return base64.b64encode(signature_path.read_bytes()).decode("ascii")


def verify_signed_session(session: dict, signature_path: Path, profile: dict) -> dict:
    gateway = next(s for s in profile["required_sources"] if s["source"] == GATEWAY_SOURCE)
    signature_path = Path(signature_path).resolve(strict=True)
    signature = signature_path.read_text(encoding="ascii").strip()
    if not verify_signature(canonical_json(session), signature, gateway):
        raise ValueError("Assinatura da sessão inválida")
    if profile.get("_sha256") and session.get("profile_sha256") != profile["_sha256"]:
        raise ValueError("Hash do perfil diverge da configuração assinada na sessão")
    expected = {
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "sensor_id": profile["sensor_id"],
        "target_ref": profile["target_ref"],
        "interface": profile["interface"],
        "source_ip": profile["source_ip"],
    }
    for field, value in expected.items():
        if session.get(field) != value:
            raise ValueError(f"Sessão diverge do perfil em {field}")
    if session.get("destination_ip") != profile["destination_ip"]:
        raise ValueError("Sessão diverge do perfil em destination_ip")
    required = [s["source"] for s in profile["required_sources"]]
    if session.get("required_sources") != required:
        raise ValueError("Fontes obrigatórias da sessão divergem do perfil")
    return {"source": GATEWAY_SOURCE, "signature_verified": True}


def _safe_record_file(manifest_path: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("records_file deve ser um nome simples, sem caminho")
    path = manifest_path.parent / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Arquivo de registros ausente ou não regular")
    return path.resolve(strict=True)


def _read_signed_manifest(manifest_path: Path, source_config: dict, identity: dict) -> dict:
    if Path(manifest_path).is_symlink():
        raise ValueError("Manifest não pode ser link simbólico")
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError("Schema de evidência de fonte inválido")
    signature = manifest.get("signature_ed25519")
    unsigned = {key: value for key, value in manifest.items() if key != "signature_ed25519"}
    if not isinstance(signature, str) or not verify_signature(canonical_json(unsigned), signature, source_config):
        raise ValueError("Assinatura do manifest da fonte inválida")
    for field in ("collection_session_id", "sensor_id", "target_ref"):
        if manifest.get(field) != identity[field]:
            raise ValueError(f"Manifest da fonte diverge em {field}")
    for field in ("profile_id", "traffic_profile", "session_report_sha256", "pcap_sha256"):
        if manifest.get(field) != identity.get(field):
            raise ValueError(f"Manifest da fonte diverge em {field}")
    if manifest.get("source") != source_config["source"]:
        raise ValueError("Manifest associado a fonte diferente da permitida")
    if manifest.get("host_id") != source_config["host_id"]:
        raise ValueError("Manifest originado de host não autorizado pelo perfil")
    if manifest.get("coverage_status") != "COMPLETE" or manifest.get("continuity_verified") is not True:
        reason = manifest.get("coverage_reason")
        raise ValueError(str(reason)[:300] if isinstance(reason, str) and reason.strip() else "A fonte não atesta intervalo completo e contínuo")
    for field in ("host_id", "boot_id", "cursor_start", "cursor_end"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f"Manifest sem {field}")
    start = parse_time(manifest.get("interval_start"))
    end = parse_time(manifest.get("interval_end"))
    if end <= start:
        raise ValueError("Intervalo do manifest inválido")
    record_file = _safe_record_file(manifest_path, manifest.get("records_file"))
    actual_hash = sha256_file(record_file)
    if actual_hash != manifest.get("records_sha256"):
        raise ValueError("Hash dos registros diverge do manifest assinado")
    if type(manifest.get("record_count")) is not int or manifest["record_count"] < 0:
        raise ValueError("record_count inválido")
    records = []
    seen = set()
    with record_file.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido na linha {line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError("Registro de fonte deve ser objeto")
            event_id = row.get("event_id")
            if not isinstance(event_id, str) or not event_id.strip() or event_id in seen:
                raise ValueError("event_id ausente ou duplicado")
            seen.add(event_id)
            observed = parse_time(row.get("observed_at"))
            if not start <= observed < end:
                raise ValueError("Registro de fonte fora do intervalo assinado")
            if not identity["start"] <= observed < identity["end"]:
                raise ValueError("Evidência de fonte fora do período efetivo da sessão")
            if row.get("journal_boot_id") is not None and row["journal_boot_id"] != manifest["boot_id"]:
                raise ValueError("Boot do registro diverge do manifesto")
            records.append({
                "event_id": event_id,
                "observed_at": observed,
                "journal_cursor": row.get("journal_cursor"),
                "journal_boot_id": row.get("journal_boot_id"),
            })
    if len(records) != manifest["record_count"]:
        raise ValueError("record_count diverge do JSONL")
    return {
        "source": manifest["source"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "records_sha256": actual_hash,
        "start": start,
        "end": end,
        "boot_id": manifest["boot_id"],
        "cursor_start": manifest["cursor_start"],
        "cursor_end": manifest["cursor_end"],
        "previous_cursor": manifest.get("previous_cursor"),
        "records": records,
        "signature_verified": True,
    }


def load_external_evidence(evidence_dir: Path, profile: dict, identity: dict) -> tuple[dict, list[dict]]:
    root = Path(evidence_dir)
    statuses = {}
    bundles = []
    for source_config in profile["required_sources"]:
        source_id = source_config["source"]
        if source_config["kind"] == "gateway_capture":
            continue
        source_dir = root / source_id
        if source_dir.is_symlink():
            statuses[source_id] = {"status": "INCOMPLETE", "reasons": ["Diretório da fonte não pode ser link simbólico"], "evidence": []}
            continue
        manifests = sorted(source_dir.glob("*.manifest.json")) if source_dir.is_dir() else []
        if not manifests:
            statuses[source_id] = {"status": "UNKNOWN", "reasons": ["Manifest obrigatório ausente"], "evidence": []}
            continue
        valid = []
        errors = []
        for manifest_path in manifests:
            try:
                valid.append(_read_signed_manifest(manifest_path, source_config, identity))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                errors.append(type(exc).__name__ + ": " + str(exc))
        if errors:
            statuses[source_id] = {"status": "INCOMPLETE", "reasons": errors, "evidence": valid}
        elif _intervals_cover(valid, identity["start"], identity["end"], require_cursor_chain=True):
            statuses[source_id] = {"status": "COMPLETE", "reasons": [], "evidence": valid}
            bundles.extend(valid)
        else:
            statuses[source_id] = {"status": "INCOMPLETE", "reasons": ["Intervalos/cursors não cobrem toda a sessão sem lacuna"], "evidence": valid}
            bundles.extend(valid)
    return statuses, bundles


def _intervals_cover(bundles: list[dict], start: datetime, end: datetime, *, require_cursor_chain: bool) -> bool:
    ordered = sorted(bundles, key=lambda row: row["start"])
    if not ordered:
        return False
    if not require_cursor_chain:
        cursor = start
        for item in (row for row in ordered if row["end"] > start and row["start"] < end):
            if item["start"] > cursor:
                return False
            cursor = max(cursor, item["end"])
            if cursor >= end:
                return True
        return False
    cursor = start
    previous = None
    for index, item in enumerate(ordered):
        if index == 0:
            if item["start"] > start or item["end"] <= start:
                return False
        elif item["start"] != cursor:
            return False
        if previous is not None and require_cursor_chain:
            if item["boot_id"] != previous["boot_id"] or item["previous_cursor"] != previous["cursor_end"]:
                return False
        cursor = max(cursor, item["end"])
        previous = item
    return cursor >= end and ordered[-1]["end"] >= end


def _local_capture_status(session: dict, signature_path: Path, profile: dict, pcap_path: Path) -> dict:
    gateway = next(s for s in profile["required_sources"] if s["source"] == GATEWAY_SOURCE)
    try:
        verify_signed_session(session, signature_path, profile)
        if not pcap_path.is_file() or sha256_file(pcap_path) != session.get("pcap_sha256"):
            raise ValueError("PCAP ausente ou hash divergente")
        start = parse_time(session.get("capture_effective_started_at"))
        end = parse_time(session.get("capture_effective_ended_at"))
        duration = end.timestamp() - start.timestamp()
        monitoring = session.get("process_monitoring", {})
        captured_samples = [o for o in monitoring.get("observations", []) if o.get("phase") == "capturing"]
        sample_times = [parse_time(o.get("timestamp")).timestamp() for o in captured_samples]
        heartbeat = monitoring.get("heartbeat_interval_seconds")
        heartbeat_valid = type(heartbeat) in (int, float) and heartbeat > 0
        heartbeat_complete = (
            heartbeat_valid
            and len(sample_times) >= 2
            and sample_times[0] <= start.timestamp() + heartbeat * 1.5
            and sample_times[-1] >= end.timestamp() - heartbeat * 1.5
            and all(
                0 < right - left <= heartbeat * 2.0
                for left, right in zip(sample_times, sample_times[1:])
            )
        )
        stats = session.get("tcpdump_stats", {})
        valid = (
            session.get("session_basic_checks_passed") is True
            and session.get("termination_reason") == "duration_elapsed"
            and session.get("interruption") is None
            and session.get("capture_errors") == []
            and duration >= session.get("duration_requested_seconds", math.inf)
            and heartbeat_complete
            and all(
                o.get("tcpdump_active") is True
                and o.get("process_active") is True
                and o.get("monitor_scan_complete") is True
                for o in captured_samples
            )
            and all(type(stats.get(k)) is int and stats[k] >= 0 for k in ("packets_captured", "packets_received_by_filter", "packets_dropped_by_kernel"))
            and stats.get("packets_dropped_by_kernel") == 0
        )
        return {
            "status": "COMPLETE" if valid else "INCOMPLETE",
            "reasons": [] if valid else ["Prontidão, duração efetiva, heartbeats, encerramento ou estatística de perda insuficientes"],
            "source": GATEWAY_SOURCE,
            "start": start,
            "end": end,
            "signature_verified": True,
            "records": [],
            "manifest_path": str(signature_path),
            "manifest_sha256": sha256_file(signature_path),
            "boot_id": session.get("boot_id"),
            "cursor_start": session.get("capture_effective_started_at"),
            "cursor_end": session.get("capture_effective_ended_at"),
            "public_key_fingerprint": gateway["public_key_sha256"],
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"status": "INCOMPLETE", "reasons": [type(exc).__name__ + ": " + str(exc)], "source": GATEWAY_SOURCE, "evidence": []}


def _pcap_counts(path: Path, start: datetime, end: datetime,
                 artifact_start: datetime, artifact_end: datetime) -> tuple[dict[int, int], int, int]:
    counts = {}
    startup_records_excluded = 0
    shutdown_tail_records_excluded = 0
    with path.open("rb") as stream:
        header = stream.read(24)
        magic = {
            b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
            b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
            b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
            b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
        }
        if len(header) != 24 or header[:4] not in magic:
            raise ValueError("PCAP clássico inválido ou formato não suportado")
        endian, scale = magic[header[:4]]
        lower = start.timestamp()
        last = end.timestamp()
        while True:
            record = stream.read(16)
            if not record:
                break
            if len(record) != 16:
                raise ValueError("Registro PCAP truncado")
            seconds, fraction, captured_len, _wire_len = struct.unpack(endian + "IIII", record)
            if fraction >= scale or captured_len > 64 * 1024 * 1024:
                raise ValueError("Timestamp/comprimento PCAP inválido")
            packet_data = stream.read(captured_len)
            if len(packet_data) != captured_len:
                raise ValueError("Pacote PCAP truncado")
            instant = seconds + fraction / scale
            if not artifact_start.timestamp() <= instant < artifact_end.timestamp():
                raise ValueError("Registro PCAP fora do período da sessão")
            if instant < lower:
                startup_records_excluded += 1
                continue
            if instant >= last:
                shutdown_tail_records_excluded += 1
                continue
            bucket = int(instant // 10)
            counts[bucket] = counts.get(bucket, 0) + 1
    return counts, startup_records_excluded, shutdown_tail_records_excluded


def build_coverage_report(session: dict, session_path: Path, signature_path: Path,
                          integration: dict, profile: dict, evidence_dir: Path,
                          pcap_path: Path) -> dict:
    start = parse_time(session["capture_effective_started_at"])
    end = parse_time(session["capture_effective_ended_at"])
    if end <= start:
        raise ValueError("Intervalo efetivo da sessão inválido")
    identity = {
        "collection_session_id": session["session_id"],
        "sensor_id": profile["sensor_id"],
        "target_ref": profile["target_ref"],
        "start": start,
        "end": end,
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "session_report_sha256": sha256_file(Path(session_path)),
        "pcap_sha256": session.get("pcap_sha256"),
    }
    gateway = _local_capture_status(session, signature_path, profile, pcap_path)
    statuses = {GATEWAY_SOURCE: {k: v for k, v in gateway.items() if k not in ("start", "end", "records")}}
    external_statuses, bundles = load_external_evidence(evidence_dir, profile, identity)
    for source_id, status in external_statuses.items():
        statuses[source_id] = {
            "status": status["status"],
            "reasons": status["reasons"],
            "evidence": [{
                "manifest_path": item["manifest_path"],
                "manifest_sha256": item["manifest_sha256"],
                "records_sha256": item["records_sha256"],
                "interval_start": iso_utc(item["start"]),
                "interval_end": iso_utc(item["end"]),
                "boot_id": item["boot_id"],
                "cursor_start": item["cursor_start"],
                "cursor_end": item["cursor_end"],
                "signature_verified": item["signature_verified"],
            } for item in status.get("evidence", [])],
        }
    gateway_bundles = [gateway] if gateway.get("start") and gateway.get("end") else []
    all_bundles = gateway_bundles + bundles
    complete = all(statuses.get(src["source"], {}).get("status") == "COMPLETE" for src in profile["required_sources"])

    packet_counts, startup_packets_excluded, shutdown_tail_packets_excluded = _pcap_counts(
        pcap_path, start, end, parse_time(session["started_at"]),
        parse_time(session["finished_at"]),
    )
    integration_windows = integration.get("aggregation", {}).get("windows", [])
    feature_by_start = {}
    window_ids = set()
    for window in integration_windows:
        for field, expected in (("collection_session_id", session["session_id"]),
                                ("sensor_id", profile["sensor_id"]),
                                ("traffic_profile", profile["traffic_profile"]),
                                ("src_ip", profile["source_ip"]),
                                ("dst_ip", profile["destination_ip"])):
            if window.get(field) != expected:
                raise ValueError(f"Janela da integração diverge em {field}")
        wid = window.get("window_id")
        if not isinstance(wid, str) or not wid or wid in window_ids:
            raise ValueError("ID de janela ausente ou duplicado")
        window_ids.add(wid)
        left, right = parse_time(window["window_start"]), parse_time(window["window_end"])
        if not start <= left < right <= end or (right-left).total_seconds() != 10:
            raise ValueError("Janela da integração parcial ou fora do período efetivo")
        bucket_id = int(left.timestamp() // 10)
        if left.timestamp() % 10 or bucket_id in feature_by_start:
            raise ValueError("Janela desalinhada ou ambígua no intervalo de cobertura")
        feature_by_start[bucket_id] = window

    first_bucket = math.floor(start.timestamp() / 10)
    last_bucket = math.ceil(end.timestamp() / 10)
    intervals = []
    for bucket in range(first_bucket, last_bucket):
        window_start = datetime.fromtimestamp(bucket * 10, timezone.utc)
        window_end = datetime.fromtimestamp((bucket + 1) * 10, timezone.utc)
        full = start <= window_start and window_end <= end
        covered_sources = []
        missing_sources = []
        evidence_refs = []
        event_count = 0
        for source_config in profile["required_sources"]:
            source_id = source_config["source"]
            source_status = statuses.get(source_id, {}).get("status", "UNKNOWN")
            source_bundles = [item for item in all_bundles if item.get("source") == source_id]
            covered = source_status == "COMPLETE" and _intervals_cover(
                source_bundles, window_start, window_end, require_cursor_chain=False
            )
            if covered:
                covered_sources.append(source_id)
                for item in source_bundles:
                    if item["start"] < window_end and item["end"] > window_start:
                        evidence_refs.append({"source": source_id, "manifest_sha256": item["manifest_sha256"]})
                event_count += sum(
                    window_start <= event["observed_at"] < window_end
                    for item in source_bundles for event in item.get("records", [])
                )
            else:
                missing_sources.append(source_id)
        packets = packet_counts.get(bucket, 0)
        if not full:
            observation = "PARTIAL_WINDOW"
            coverage_state = "INCOMPLETE" if any(statuses.get(s, {}).get("status") == "INCOMPLETE" for s in missing_sources) else "UNKNOWN"
        elif not missing_sources:
            observation = "OBSERVED_WITH_EVENTS" if packets + event_count > 0 else "OBSERVED_NO_EVENTS"
            coverage_state = "COMPLETE"
        elif packets + event_count > 0:
            observation = "OBSERVED_WITH_EVENTS"
            coverage_state = "INCOMPLETE" if any(statuses.get(s, {}).get("status") == "INCOMPLETE" for s in missing_sources) else "UNKNOWN"
        else:
            observation = "UNKNOWN"
            coverage_state = "INCOMPLETE" if any(statuses.get(s, {}).get("status") == "INCOMPLETE" for s in missing_sources) else "UNKNOWN"
        feature_window = feature_by_start.get(bucket)
        intervals.append({
            "observation_id": hashlib.sha256(f"coverage-v1\0{identity['collection_session_id']}\0{iso_utc(window_start)}".encode()).hexdigest(),
            "feature_window_id": feature_window.get("window_id") if feature_window else None,
            "collection_session_id": identity["collection_session_id"],
            "sensor_id": identity["sensor_id"],
            "target_ref": identity["target_ref"],
            "window_start": iso_utc(window_start),
            "window_end": iso_utc(window_end),
            "window_seconds": 10,
            "partial_window": not full,
            "packet_records": packets if GATEWAY_SOURCE in covered_sources else None,
            "source_event_records": event_count if not missing_sources else None,
            "observation_status": observation,
            "coverage_status": coverage_state,
            "covered_sources": covered_sources,
            "missing_sources": missing_sources,
            "evidence_refs": evidence_refs,
        })

    coverage_records = []
    for source_config in profile["required_sources"]:
        if statuses.get(source_config["source"], {}).get("status") == "COMPLETE":
            source_id = source_config["source"]
            source_bundles = [item for item in all_bundles if item.get("source") == source_id]
            coverage_records.append({
                "source": source_id,
                "start": iso_utc(start),
                "end": iso_utc(end),
                "collection_session_id": identity["collection_session_id"],
                "sensor_id": identity["sensor_id"],
                "target_ref": identity["target_ref"],
                "verified": True,
                "verification_method": "ed25519_signed_manifest_and_interval_chain",
                "evidence_refs": [{
                    "manifest_sha256": item["manifest_sha256"],
                    "signature_verified": item["signature_verified"],
                } for item in source_bundles],
            })
    overall = "COMPLETE" if complete else (
        "INCOMPLETE" if any(v.get("status") == "INCOMPLETE" for v in statuses.values()) else "UNKNOWN"
    )
    return {
        "schema_version": COVERAGE_SCHEMA,
        "session": identity["collection_session_id"],
        "session_report": str(Path(session_path).resolve()),
        "session_signature": str(Path(signature_path).resolve()),
        "session_pcap_sha256": session.get("pcap_sha256"),
        "pcap_startup_packets_excluded_from_effective_windows": startup_packets_excluded,
        "pcap_shutdown_tail_packets_excluded_from_effective_windows": shutdown_tail_packets_excluded,
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "required_sources": [item["source"] for item in profile["required_sources"]],
        "source_coverage": statuses,
        "coverage_records": coverage_records,
        "intervals": intervals,
        "source_coverage_status": overall,
        # A complete bounded source result is evidence; downstream release remains disabled.
        "collection_complete": False,
        "ready_for_inference": False,
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "log_counts": {},
        "limitations": [
            "A cobertura descreve somente fontes, interfaces e filtros definidos no perfil.",
            "Cobertura completa não habilita contagens, inferência ou IPS nesta entrega.",
            "Uma janela sem registros só é OBSERVED_NO_EVENTS quando todas as fontes comprovam o intervalo.",
        ],
    }


def sign_json_file(path: Path, private_key: Path) -> str:
    return sign_payload(canonical_json(json.loads(Path(path).read_text(encoding="utf-8"))), private_key)


def verify_json_signature(path: Path, signature_path: Path, source_config: dict) -> bool:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    signature = Path(signature_path).read_text(encoding="ascii").strip()
    return verify_signature(canonical_json(document), signature, source_config)


def link_auxiliary_events(auxiliary_audit: dict | None, evidence_dir: Path,
                          profile: dict, identity: dict, intervals: list[dict]) -> dict:
    """Liga eventos MQTT somente por cursor/boot/timestamp confirmados por fonte assinada."""
    if auxiliary_audit is None:
        return {"status": "NOT_PROVIDED", "events": []}
    events = auxiliary_audit.get("auxiliary_evidence")
    if not isinstance(events, list):
        return {"status": "UNBOUND", "reason": "A saída do adaptador não tem auxiliary_evidence", "events": []}
    _statuses, bundles = load_external_evidence(evidence_dir, profile, identity)
    auxiliary_sources = {
        item["source"] for item in profile["required_sources"]
        if item.get("auxiliary_mqtt") is True
    }
    output = []
    for event in events:
        if not isinstance(event, dict):
            output.append({"status": "UNBOUND", "reason": "Evento auxiliar inválido"})
            continue
        try:
            observed = parse_time(event.get("observed_at"))
        except (TypeError, ValueError):
            observed = None
        matches = [
            bundle for bundle in bundles
            if bundle["source"] in auxiliary_sources
            for row in bundle["records"]
            if event.get("journal_cursor") is not None
            and event.get("journal_boot_id") is not None
            and row.get("journal_cursor") == event.get("journal_cursor")
            and row.get("journal_boot_id") == event.get("journal_boot_id")
            and observed is not None and row["observed_at"] == observed
            and identity["start"] <= observed < identity["end"]
        ]
        if not matches:
            output.append({
                "status": "UNBOUND",
                "event_type": event.get("event_type"),
                "reason": "Cursor/boot/timestamp não correspondem a registro de fonte assinado dentro da sessão",
            })
            continue
        source_bundle = matches[0]
        interval = next((item for item in intervals if parse_time(item["window_start"]) <= observed < parse_time(item["window_end"])), None)
        auxiliary_id = hashlib.sha256(canonical_json({
            "session": identity["collection_session_id"],
            "source": source_bundle["source"],
            "boot_id": event["journal_boot_id"],
            "cursor": event["journal_cursor"],
            "event_type": event.get("event_type"),
            "observed_at": iso_utc(observed),
        })).hexdigest()
        output.append({
            "status": "SESSION_LINKED",
            "auxiliary_id": auxiliary_id,
            "event_type": event.get("event_type"),
            "source": source_bundle["source"],
            "journal_cursor": event["journal_cursor"],
            "journal_boot_id": event["journal_boot_id"],
            "observed_at": iso_utc(observed),
            "manifest_sha256": source_bundle["manifest_sha256"],
            "observation_id": interval.get("observation_id") if interval else None,
            "feature_window_id": interval.get("feature_window_id") if interval else None,
        })
    return {
        "status": "SESSION_LINKED" if output and all(row.get("status") == "SESSION_LINKED" for row in output) else "UNBOUND",
        "events": output,
        "limitations": ["Eventos auxiliares permanecem fora das features e não demonstram cobertura por si só."],
    }
