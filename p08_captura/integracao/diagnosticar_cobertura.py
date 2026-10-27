#!/usr/bin/env python3
"""HarpiSense V2 - Diagnostico conservador de cobertura temporal P08."""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from coverage_evidence import build_coverage_report, load_profile


def timestamp(valor):
    dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp sem fuso horario")
    return dt.astimezone(timezone.utc).timestamp()


def diagnosticar(sessao, integracao, *, profile=None, session_path=None,
                 signature_path=None, evidence_dir=None, pcap_path=None):
    if profile is not None:
        return build_coverage_report(
            sessao, session_path, signature_path, integracao, profile,
            evidence_dir, pcap_path,
        )
    if sessao.get("schema_version") != "harpisense.capture.session.v1":
        raise ValueError("Schema de sessao incompatível")

    if integracao.get("schema_version") != "harpisense.p08.integration.v1":
        raise ValueError("Schema de integracao incompatível")

    if sessao.get("pcap_sha256") != integracao.get("pcap", {}).get("sha256"):
        raise ValueError("Hashes do PCAP divergentes")

    if sessao.get("pcap_path") != integracao.get("pcap", {}).get("path"):
        raise ValueError("Caminhos do PCAP divergentes")

    if sessao.get("interface") != integracao.get("interface"):
        raise ValueError("Interfaces divergentes")

    if sessao.get("collection_complete") is not False:
        raise ValueError("Estado de coleta inesperado")

    if integracao.get("ready_for_inference") is not False:
        raise ValueError("Inferencia indevidamente autorizada")

    inicio = timestamp(sessao["started_at"])
    fim = timestamp(sessao["finished_at"])

    if not math.isfinite(inicio) or not math.isfinite(fim) or fim <= inicio:
        raise ValueError("Intervalo temporal invalido")

    janelas = integracao["aggregation"]["windows"]

    intervalos = {}

    for janela in janelas:
        segundos = janela["window_seconds"]

        if segundos != 10:
            raise ValueError("Janela diferente de 10 segundos")

        inicio_janela = timestamp(janela["window_start"])
        fim_janela = timestamp(janela["window_end"])

        if fim_janela - inicio_janela != 10:
            raise ValueError("Duracao da janela invalida")

        if fim_janela <= inicio or inicio_janela >= fim:
            raise ValueError("Janela fora da sessao")

        intervalos[inicio_janela] = (
            intervalos.get(inicio_janela, 0)
            + janela["packet_count"]
        )

    primeiro = math.floor(inicio / 10) * 10
    ultimo = math.ceil(fim / 10) * 10

    resultado = []

    atual = primeiro

    while atual < ultimo:
        quantidade = intervalos.get(atual)

        resultado.append({
            "inicio": datetime.fromtimestamp(
                atual, timezone.utc
            ).isoformat(),
            "fim": datetime.fromtimestamp(
                atual + 10, timezone.utc
            ).isoformat(),
            "pacotes_agregados": quantidade,
            "possui_eventos": quantidade is not None and quantidade > 0,
            "intervalo_parcial": atual < inicio or atual + 10 > fim,
            "cobertura_comprovada": False,
        })

        atual += 10

    return {
        "schema_version": "harpisense.p08.coverage.diagnostic.v1",
        "session": integracao["session"],
        "intervalos": resultado,
        "intervalos_total": len(resultado),
        "intervalos_com_eventos": sum(
            item["possui_eventos"] for item in resultado
        ),
        "intervalos_sem_eventos": sum(
            not item["possui_eventos"] for item in resultado
        ),
        "intervalos_sem_dados_agregados": sum(
            item["pacotes_agregados"] is None for item in resultado
        ),
        "collection_complete": False,
        "ready_for_inference": False,
        "observacao": (
            "Ausencia de eventos nao comprova ausencia de trafego. "
            "Cobertura temporal continua ainda nao demonstrada."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-report", required=True)
    parser.add_argument("--integration-report", required=True)
    parser.add_argument("--profile-config", type=Path)
    parser.add_argument("--source-evidence-dir", type=Path)
    args = parser.parse_args()

    with Path(args.session_report).open(encoding="utf-8") as arquivo:
        sessao = json.load(arquivo)

    with Path(args.integration_report).open(encoding="utf-8") as arquivo:
        integracao = json.load(arquivo)

    profile = load_profile(args.profile_config) if args.profile_config else None
    if profile is not None:
        profile["_sha256"] = __import__("hashlib").sha256(args.profile_config.read_bytes()).hexdigest()
    session_path = Path(args.session_report)
    report = diagnosticar(
        sessao,
        integracao,
        profile=profile,
        session_path=session_path,
        signature_path=Path(str(session_path) + ".sig"),
        evidence_dir=args.source_evidence_dir,
        pcap_path=Path(sessao["pcap_path"]),
    )
    print(json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        sys.exit(1)
