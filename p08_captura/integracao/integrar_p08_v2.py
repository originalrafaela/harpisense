#!/usr/bin/env python3
"""HarpiSense V2 - Integracao de sessao validada com P08."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from validar_sessao import validar_sessao

BASE = Path("/opt/harpisense")
INTEGRADOR = BASE / "staging/p08-captura/integracao/integrar_p08.py"


def main():
    parser = argparse.ArgumentParser(
        description="Valida sessao de captura e executa integracao P08"
    )
    parser.add_argument("--session-report", required=True, type=Path)
    parser.add_argument("--sensor-id", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--profile", default="tcp-observacao")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile-config", type=Path)
    args = parser.parse_args()

    session = validar_sessao(args.session_report, args.profile_config)
    if args.profile_config:
        from coverage_evidence import load_profile
        profile = load_profile(args.profile_config)
        signed = json.loads(args.session_report.read_text(encoding="utf-8"))
        expected = {"sensor_id": args.sensor_id, "destination_ip": args.destination,
                    "session_id": args.session, "traffic_profile": args.profile}
        if any(signed.get(key) != value for key, value in expected.items()):
            raise ValueError("Argumentos da integração divergem da sessão assinada")

    if args.output.exists():
        parser.error("Relatorio de saida ja existe")

    if not args.output.parent.is_dir():
        parser.error("Diretorio de saida nao existe")

    command = [
        sys.executable,
        str(INTEGRADOR),
        "--pcap", session["pcap_path"],
        "--sensor-id", args.sensor_id,
        "--interface", session["interface"],
        "--destination", args.destination,
        "--session", args.session,
        "--profile", args.profile,
        "--output", str(args.output),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=150,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Integrador original falhou: " + completed.stderr.strip()
        )

    report = json.loads(args.output.read_text(encoding="utf-8"))

    if report["pcap"]["sha256"] != session["pcap_sha256"]:
        raise RuntimeError("Hash do PCAP divergiu apos processamento")

    if report["pcap"]["size_bytes"] != session["pcap_size_bytes"]:
        raise RuntimeError("Tamanho do PCAP divergiu apos processamento")

    if report["aggregation"]["ready_for_inference"] is not False:
        raise RuntimeError("Inferencia indevidamente autorizada")

    print(json.dumps({
        "status": "SESSAO_INTEGRADA",
        "session_report": session["session_report"],
        "pcap_integrity_verified": session["integrity_verified"],
        "events_converted": report["events_converted"],
        "windows": len(report["aggregation"]["windows"]),
        "quality": report["aggregation"]["quality"]["status"],
        "ready_for_inference": False,
        "output": str(args.output),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
