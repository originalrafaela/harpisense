
#!/usr/bin/env python3
"""Validação de integridade de sessão de captura HarpiSense P08."""

import hashlib
import json
from pathlib import Path

from coverage_evidence import load_profile, sha256_file as shared_sha256_file, verify_signed_session


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validar_sessao(report_path, profile_path=None):
    report_path = Path(report_path).resolve(strict=True)

    if not report_path.is_file():
        raise ValueError("Relatorio de sessao invalido")

    with report_path.open("r", encoding="utf-8") as handle:
        report = json.load(handle)

    if not isinstance(report, dict):
        raise ValueError("Relatorio deve ser um objeto JSON")

    if report.get("schema_version") != "harpisense.capture.session.v1":
        raise ValueError("Schema de sessao incompatível")

    if report.get("session_basic_checks_passed") is not True:
        raise ValueError("Verificacoes basicas da sessao falharam")

    if report.get("collection_complete") is not False:
        raise ValueError("Cobertura temporal nao deve ser presumida")

    if report.get("ready_for_inference") is not False:
        raise ValueError("Inferencia nao autorizada nesta etapa")

    signature_verified = False
    if profile_path is not None:
        profile_path = Path(profile_path).resolve(strict=True)
        profile = load_profile(profile_path)
        if report.get("profile_sha256") != shared_sha256_file(profile_path):
            raise ValueError("Hash do perfil diverge do relatório assinado")
        profile["_sha256"] = shared_sha256_file(profile_path)
        if not isinstance(report.get("session_id"), str) or not report["session_id"]:
            raise ValueError("Identificador de sessão ausente")
        if not report.get("capture_effective_started_at"):
            raise ValueError("Início efetivo da captura ausente")
        signature_verified = verify_signed_session(
            report, Path(str(report_path) + ".sig"), profile
        )["signature_verified"]

    interface = report.get("interface")
    source_ip = report.get("source_ip")

    if not isinstance(interface, str) or not interface:
        raise ValueError("Interface ausente")

    if not isinstance(source_ip, str) or not source_ip:
        raise ValueError("IP de origem ausente")

    pcap_value = report.get("pcap_path")
    if not isinstance(pcap_value, str) or not pcap_value:
        raise ValueError("Caminho do PCAP ausente")

    pcap = Path(pcap_value).resolve(strict=True)

    if not pcap.is_file():
        raise ValueError("PCAP nao encontrado")

    expected_size = report.get("pcap_size_bytes")
    if type(expected_size) is not int or expected_size < 24:
        raise ValueError("Tamanho de PCAP invalido")

    actual_size = pcap.stat().st_size
    if actual_size != expected_size:
        raise ValueError("Tamanho do PCAP diverge do relatorio")

    expected_hash = report.get("pcap_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError("SHA-256 registrado invalido")

    actual_hash = sha256_file(pcap)

    if actual_hash != expected_hash:
        raise ValueError("SHA-256 do PCAP diverge do relatorio")

    stats = report.get("tcpdump_stats")
    if not isinstance(stats, dict):
        raise ValueError("Estatisticas de captura ausentes")

    for key in (
        "packets_captured",
        "packets_received_by_filter",
        "packets_dropped_by_kernel",
    ):
        value = stats.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"Estatistica invalida: {key}")

    return {
        "session_report": str(report_path),
        "pcap_path": str(pcap),
        "pcap_sha256": actual_hash,
        "pcap_size_bytes": actual_size,
        "interface": interface,
        "source_ip": source_ip,
        "tcpdump_stats": stats,
        "collection_complete": False,
        "ready_for_inference": False,
        "integrity_verified": True,
        "signature_verified": signature_verified,
        "required_sources": report.get("required_sources", []),
        "profile_id": report.get("profile_id"),
        "capture_effective_started_at": report.get("capture_effective_started_at"),
        "finished_at": report.get("finished_at"),
        "termination_reason": report.get("termination_reason"),
        "capture_errors": report.get("capture_errors", []),
    }
