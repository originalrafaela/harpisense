#!/usr/bin/env python3
"""Coletor P08 com início efetivo após prontidão observada.

Mantém o schema harpisense.capture.session.v1 e os campos históricos. Novos
relatórios registram a sessão/perfil, a prontidão, os estados do processo,
interrupções e erros. Heartbeat e hash, isoladamente, não comprovam cobertura.
"""

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "integracao"))
from coverage_evidence import (  # noqa: E402
    GATEWAY_SOURCE,
    canonical_json,
    load_profile,
    private_key_fingerprint,
    sign_payload,
)
from monitorar_tcpdump_v1 import consultar_tcpdump_detalhado  # noqa: E402


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_stats(stderr):
    patterns = {
        "packets_captured": r"(\d+) packets captured",
        "packets_received_by_filter": r"(\d+) packets received by filter",
        "packets_dropped_by_kernel": r"(\d+) packets dropped by kernel",
    }
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, stderr or "")
        result[key] = int(match.group(1)) if match else None
    return result


def write_exclusive(path, payload, mode=0o600):
    """Escreve bytes sem substituir destinos existentes, com publicação atômica."""
    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".harpisense-p08-", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        with os.fdopen(fd, "wb") as stream:
            if os.name == "posix":
                os.fchmod(stream.fileno(), mode)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp_path, path, follow_symlinks=False)
        if os.name == "posix":
            dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_process_group(process):
    pgid = process.pid
    result = {
        "process_group_id": pgid,
        "group_existed_before_cleanup": group_exists(pgid),
        "sigint_attempted": False,
        "sigkill_attempted": False,
        "cleanup_completed": False,
    }
    if not result["group_existed_before_cleanup"]:
        process.wait(timeout=5)
        result["cleanup_completed"] = True
        return result
    try:
        result["sigint_attempted"] = True
        os.killpg(pgid, signal.SIGINT)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and group_exists(pgid):
        process.poll()
        time.sleep(0.1)
    if group_exists(pgid):
        try:
            result["sigkill_attempted"] = True
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)
    result["cleanup_completed"] = True
    return result


def _profile_identity(profile, session_id):
    return {
        "session_id": session_id,
        "profile_id": profile["profile_id"],
        "traffic_profile": profile["traffic_profile"],
        "sensor_id": profile["sensor_id"],
        "target_ref": profile["target_ref"],
        "interface": profile["interface"],
        "source_ip": str(ipaddress.ip_address(profile["source_ip"])),
        "destination_ip": str(ipaddress.ip_address(profile["destination_ip"])),
        "required_sources": [source["source"] for source in profile["required_sources"]],
    }


def run_capture(*, session_id, interface, source_ip, duration, heartbeat_seconds,
                startup_timeout, output, profile=None, signing_key=None,
                process_probe=consultar_tcpdump_detalhado, popen_factory=subprocess.Popen,
                monotonic=time.monotonic, sleep=time.sleep, now=utc_now,
                stop_requested=lambda: None, stop_group=stop_process_group):
    report_path = output.with_suffix(".session.json")
    signature_path = Path(str(report_path) + ".sig")
    if output.exists() or report_path.exists() or signature_path.exists():
        raise ValueError("PCAP, relatório ou assinatura já existem; sobrescrita proibida")
    if not output.parent.is_dir():
        raise ValueError("Diretório de destino não existe")

    source_ip = ipaddress.ip_address(source_ip)
    if source_ip.version != 4:
        raise ValueError("Esta versão aceita somente IPv4")
    if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,32}", interface):
        raise ValueError("Nome de interface inválido")

    if profile is not None:
        identity = _profile_identity(profile, session_id)
        if identity["interface"] != interface or identity["source_ip"] != str(source_ip):
            raise ValueError("Interface/IP divergem do perfil selecionado")
        gateway = next(source for source in profile["required_sources"] if source["source"] == GATEWAY_SOURCE)
        if signing_key is None:
            raise ValueError("Perfil exige assinatura do relatório de captura")
        if private_key_fingerprint(signing_key) != gateway["public_key_sha256"].lower():
            raise ValueError("Chave privada não corresponde à fonte gateway_capture do perfil")
        profile_path_hash = profile.get("_sha256")
        destination_ip = ipaddress.ip_address(profile["destination_ip"])
        if destination_ip.version != 4:
            raise ValueError("Esta versão aceita somente IPv4")
    else:
        identity = {
            "session_id": session_id,
            "profile_id": None,
            "traffic_profile": None,
            "sensor_id": None,
            "target_ref": None,
            "interface": interface,
            "source_ip": str(source_ip),
            "destination_ip": None,
            "required_sources": [],
        }
        profile_path_hash = None
        destination_ip = None

    command = [
        "tcpdump", "-i", interface, "-nn", "-s", "0", "-B", "4096", "-U",
        "-w", str(output), "tcp", "and", "host", str(source_ip),
    ]
    if destination_ip is not None:
        command.extend(["and", "host", str(destination_ip)])
    reserve_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    reserve_fd = os.open(output, reserve_flags, 0o600)
    os.close(reserve_fd)
    started_at = now()
    session_monotonic_start = monotonic()
    observations = []
    capture_errors = []
    interruption = None
    process = None
    cleanup = None
    stderr = ""
    termination_reason = "capture_error"
    capture_effective_started_at = None
    effective_start = None
    capture_stop_requested_at = None
    effective_end_monotonic = None

    def observe(phase):
        details = process_probe(process.pid)
        active = [item for item in details.get("processes", []) if item.get("active") is True]
        row = {
            "timestamp": now(),
            "elapsed_seconds": round(monotonic() - session_monotonic_start, 3),
            "phase": phase,
            "process_active": process.poll() is None,
            "tcpdump_detected": bool(details.get("processes")),
            "tcpdump_active": bool(active),
            "tcpdump_processes": details.get("processes", []),
            "monitor_scan_complete": details.get("scan_complete") is True,
            "monitor_errors": details.get("errors", []),
        }
        observations.append(row)
        if row["monitor_errors"]:
            capture_errors.append({"kind": "process_monitor_read_error", "timestamp": row["timestamp"], "count": len(row["monitor_errors"])})
        return row

    try:
        process = popen_factory(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        subprocess_started_at = now()
        startup_deadline = monotonic() + startup_timeout
        ready = False
        while monotonic() < startup_deadline:
            if stop_requested():
                interruption = {"signal": stop_requested(), "phase": "startup", "at": now()}
                termination_reason = "interrupted_before_ready"
                break
            if process.poll() is not None:
                termination_reason = "process_exited_before_ready"
                capture_errors.append({"kind": "tcpdump_exited_before_ready", "exit_status": process.poll()})
                break
            observation = observe("startup")
            try:
                pcap_ready = output.is_file() and output.stat().st_size >= 24
            except OSError:
                pcap_ready = False
            if observation["tcpdump_active"] and pcap_ready:
                ready = True
                capture_effective_started_at = now()
                effective_start = monotonic()
                break
            sleep(min(heartbeat_seconds, max(0.0, startup_deadline - monotonic())))
        if not ready and termination_reason == "capture_error":
            termination_reason = "startup_timeout"
            capture_errors.append({"kind": "tcpdump_readiness_timeout", "timeout_seconds": startup_timeout})

        if ready:
            effective_deadline = effective_start + duration
            while monotonic() < effective_deadline:
                if stop_requested():
                    interruption = {"signal": stop_requested(), "phase": "capturing", "at": now()}
                    termination_reason = "interrupted"
                    break
                if process.poll() is not None:
                    termination_reason = "process_exited_during_capture"
                    capture_errors.append({"kind": "tcpdump_exited_early", "exit_status": process.poll()})
                    break
                observation = observe("capturing")
                if not observation["tcpdump_active"]:
                    capture_errors.append({"kind": "tcpdump_not_observed", "timestamp": observation["timestamp"]})
                sleep(min(heartbeat_seconds, max(0.0, effective_deadline - monotonic())))
            else:
                termination_reason = "duration_elapsed"

    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        termination_reason = "capture_error"
        capture_errors.append({"kind": type(exc).__name__, "message": str(exc)[:500]})
    finally:
        if process is not None:
            capture_stop_requested_at = now()
            if effective_start is not None:
                effective_end_monotonic = monotonic()
        if process is not None:
            try:
                cleanup = stop_group(process)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                cleanup = {"cleanup_completed": False, "error": type(exc).__name__}
                capture_errors.append({"kind": "process_cleanup_failed", "error": type(exc).__name__})
            try:
                if process.stderr is not None:
                    stderr = process.stderr.read() or ""
                    process.stderr.close()
            except OSError as exc:
                capture_errors.append({"kind": "stderr_read_failed", "error": type(exc).__name__})

    finished_at = now()
    effective_seconds = (
        round(effective_end_monotonic - effective_start, 3)
        if effective_start is not None and effective_end_monotonic is not None else 0.0
    )
    try:
        pcap_exists = output.is_file()
        pcap_size = output.stat().st_size if pcap_exists else None
        pcap_hash = sha256_file(output) if pcap_exists else None
    except OSError as exc:
        pcap_exists, pcap_size, pcap_hash = False, None, None
        capture_errors.append({"kind": "pcap_read_failed", "error": type(exc).__name__})
    stats = extract_stats(stderr)
    stats_available = all(type(value) is int and value >= 0 for value in stats.values())
    cleanup_ok = cleanup is not None and cleanup.get("cleanup_completed") is True
    capture_observations = [row for row in observations if row["phase"] == "capturing"]
    monitor_ok = bool(capture_observations) and all(
        row["tcpdump_active"] and row["process_active"] and row["monitor_scan_complete"]
        for row in capture_observations
    )
    basic_checks = (
        termination_reason == "duration_elapsed"
        and effective_seconds >= duration
        and pcap_exists and pcap_size is not None and pcap_size >= 24
        and stats_available and cleanup_ok and monitor_ok and not capture_errors
    )
    report = {
        "schema_version": "harpisense.capture.session.v1",
        **identity,
        "profile_sha256": profile_path_hash,
        "started_at": started_at,
        "subprocess_started_at": subprocess_started_at if process is not None else None,
        "capture_effective_started_at": capture_effective_started_at,
        "capture_stop_requested_at": capture_stop_requested_at,
        "capture_effective_ended_at": capture_stop_requested_at if capture_effective_started_at is not None else None,
        "finished_at": finished_at,
        "elapsed_seconds": round(monotonic() - session_monotonic_start, 3),
        "effective_duration_seconds": effective_seconds,
        "duration_requested_seconds": duration,
        "startup_timeout_seconds": startup_timeout,
        "termination_reason": termination_reason,
        "timeout_exit_status": process.returncode if process is not None else None,
        "expected_timeout": termination_reason == "duration_elapsed",
        "interruption": interruption,
        "capture_errors": capture_errors,
        "interface": interface,
        "source_ip": str(source_ip),
        "pcap_path": str(output.resolve()),
        "pcap_size_bytes": pcap_size,
        "pcap_sha256": pcap_hash,
        "tcpdump_stats": stats,
        "session_basic_checks_passed": basic_checks,
        "process_monitoring": {
            "schema_version": "harpisense.capture.monitoring.v1",
            "heartbeat_interval_seconds": heartbeat_seconds,
            "tcpdump_first_observed_at": next((row["timestamp"] for row in observations if row["tcpdump_active"]), None),
            "tcpdump_last_observed_at": next((row["timestamp"] for row in reversed(observations) if row["tcpdump_active"]), None),
            "observations": observations,
            "observations_total": len(observations),
            "tcpdump_observations_active": sum(row["tcpdump_active"] for row in capture_observations),
            "tcpdump_observations_missing": sum(not row["tcpdump_active"] for row in capture_observations),
            "tcpdump_observed_in_all_heartbeats": monitor_ok,
            "monitor_errors_total": sum(len(row["monitor_errors"]) for row in observations),
            "continuous_capture_proven": False,
        },
        "process_cleanup": cleanup,
        "collection_complete": False,
        "ready_for_inference": False,
        "signature_algorithm": "Ed25519" if signing_key else None,
        "signature_path": str(signature_path.resolve()) if signing_key else None,
        "notes": [
            "A duração efetiva começa somente após processo tcpdump ativo e PCAP inicializado.",
            "Heartbeats, estatística de perdas e hash são evidências complementares; isoladamente não comprovam cobertura.",
            "UNKNOWN/INCOMPLETE permanece até verificar as fontes obrigatórias do perfil.",
            "Nenhuma inferência ou ação IPS foi executada.",
        ],
    }
    payload = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    write_exclusive(report_path, payload)
    if signing_key:
        signature = sign_payload(canonical_json(report), signing_key).encode("ascii") + b"\n"
        write_exclusive(signature_path, signature)
    return report


def main():
    parser = argparse.ArgumentParser(description="Coleta P08 com prontidão e duração efetiva registradas")
    parser.add_argument("--session", required=True)
    parser.add_argument("--interface")
    parser.add_argument("--source-ip")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--heartbeat-seconds", type=float, default=1.0)
    parser.add_argument("--profile-config", type=Path)
    parser.add_argument("--signing-key", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.session):
        parser.error("Identificador de sessão inválido")
    if not 1 <= args.duration <= 300:
        parser.error("duration deve estar entre 1 e 300 segundos")
    if not math.isfinite(args.heartbeat_seconds) or not 0.5 <= args.heartbeat_seconds <= 10:
        parser.error("heartbeat-seconds deve estar entre 0.5 e 10")
    if not math.isfinite(args.startup_timeout) or not 1 <= args.startup_timeout <= 120:
        parser.error("startup-timeout deve estar entre 1 e 120 segundos")
    profile = None
    if args.profile_config:
        try:
            profile = load_profile(args.profile_config)
            profile["_sha256"] = sha256_file(args.profile_config)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            parser.error(f"Perfil inválido: {exc}")
    interface = args.interface or (profile and profile["interface"])
    source_ip = args.source_ip or (profile and profile["source_ip"])
    if not interface or not source_ip:
        parser.error("Informe --profile-config ou interface/source-ip")
    if bool(profile) != bool(args.signing_key):
        parser.error("--profile-config e --signing-key devem ser fornecidos juntos")

    interrupted = {"signal": None}
    stop_event = threading.Event()
    old_handlers = {}
    def on_signal(signum, _frame):
        interrupted["signal"] = signal.Signals(signum).name
        stop_event.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, on_signal)
    try:
        report = run_capture(
            session_id=args.session, interface=interface, source_ip=source_ip,
            duration=args.duration, heartbeat_seconds=args.heartbeat_seconds,
            startup_timeout=args.startup_timeout, output=args.output,
            profile=profile, signing_key=args.signing_key,
            stop_requested=lambda: interrupted["signal"] if stop_event.is_set() else None,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERRO: captura não publicada: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["session_basic_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
