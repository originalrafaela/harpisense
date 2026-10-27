#!/usr/bin/env python3
"""Consulta conservadora de processos tcpdump no /proc."""

from pathlib import Path


def consultar_tcpdump_detalhado(pgid):
    encontrados = []
    errors = []

    try:
        entries = list(Path("/proc").iterdir())
    except OSError as exc:
        return {
            "processes": [],
            "scan_complete": False,
            "errors": [{"type": type(exc).__name__, "errno": exc.errno}],
        }

    for entrada in entries:
        if not entrada.name.isdigit():
            continue

        pid = int(entrada.name)

        try:
            texto = (entrada / "stat").read_text()
            fechamento = texto.rfind(")")

            if fechamento < 0:
                continue

            campos = texto[fechamento + 2:].split()

            estado = campos[0]
            ppid = int(campos[1])
            grupo = int(campos[2])
            starttime = int(campos[19])

            if grupo != pgid:
                continue

            argumentos = [
                item.decode("utf-8", errors="replace")
                for item in (entrada / "cmdline").read_bytes().split(b"\0")
                if item
            ]

            if not argumentos:
                continue

            executavel = Path(argumentos[0]).name

            if executavel != "tcpdump":
                continue

            encontrados.append({
                "pid": pid,
                "ppid": ppid,
                "pgrp": grupo,
                "state": estado,
                "starttime": starttime,
                "active": estado not in ("Z", "X", "x"),
            })

        except FileNotFoundError:
            # Processo pode encerrar entre a enumeração e a leitura de /proc.
            continue
        except (OSError, ValueError, IndexError) as exc:
            errors.append({"type": type(exc).__name__, "errno": getattr(exc, "errno", None)})

    return {
        "processes": sorted(encontrados, key=lambda item: item["pid"]),
        "scan_complete": not errors,
        "errors": errors,
    }


def consultar_tcpdump(pgid):
    """API legada preservada; consumidores novos usam a variante detalhada."""
    return consultar_tcpdump_detalhado(pgid)["processes"]
