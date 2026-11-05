"""Integração experimental P08: logs e cobertura temporal.

Modo fail-closed. Não autoriza inferência nem executa IPS.
"""

from coverage_gate import validate_coverage


def prepare_verified_log_counts(
    events, windows, coverage_records, required_sources
):
    """Avalia cobertura sem liberar contagens não certificadas."""

    result = {
        "authorized_for_inference": False,
        "log_counts": {},
        "reasons": [],
    }

    if not isinstance(events, list):
        result["reasons"].append("Lista de evidências inválida")
        return result

    if not isinstance(windows, list) or not windows:
        result["reasons"].append("Janelas ausentes ou inválidas")
        return result

    if not isinstance(coverage_records, list):
        result["reasons"].append("Registros de cobertura inválidos")
        return result

    if not isinstance(required_sources, (list, tuple)) or not required_sources:
        result["reasons"].append("Fontes obrigatórias não definidas")
        return result

    for window in windows:
        if not isinstance(window, dict):
            result["reasons"].append("Janela inválida")
            continue

        window_id = window.get("window_id", "UNKNOWN")

        reasons = validate_coverage(
            window_start=window.get("window_start"),
            window_end=window.get("window_end"),
            coverage_records=coverage_records,
            required_sources=required_sources,
            collection_session_id=window.get("collection_session_id"),
            sensor_id=window.get("sensor_id"),
            target_ref=window.get("target_ref"),
        )

        for reason in reasons:
            result["reasons"].append(f"{window_id}: {reason}")

    # A validação temporal não comprova procedência independente.
    # Não liberar contagens até existir certificação confiável.
    result["reasons"].append(
        "Procedência independente da cobertura não comprovada"
    )

    return result
