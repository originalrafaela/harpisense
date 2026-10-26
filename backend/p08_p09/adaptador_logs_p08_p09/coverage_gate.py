"""Validação experimental de cobertura temporal dos logs.

Não certifica a procedência dos registros nem autoriza inferência.
"""

from datetime import datetime, timezone


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp inválido")

    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        raise ValueError("Timestamp sem fuso horário")

    return dt.astimezone(timezone.utc)


def validate_coverage(
    window_start, window_end, coverage_records, required_sources,
    collection_session_id=None, sensor_id=None, target_ref=None
):
    """Retorna motivos de rejeição. Lista vazia indica aprovação apenas temporal."""
    try:
        start = parse_time(window_start)
        end = parse_time(window_end)
    except (ValueError, TypeError):
        return ["Intervalo temporal inválido"]

    if end <= start:
        return ["Intervalo temporal inválido"]

    if not isinstance(coverage_records, list):
        return ["Registros de cobertura inválidos"]

    if not isinstance(required_sources, (list, tuple)) or not required_sources:
        return ["Fontes obrigatórias não definidas"]

    context = {
        "collection_session_id": collection_session_id,
        "sensor_id": sensor_id,
        "target_ref": target_ref,
    }

    if any(not isinstance(v, str) or not v.strip() for v in context.values()):
        return ["Contexto de cobertura ausente ou inválido"]

    reasons = []

    for source in required_sources:
        intervals = []

        for record in coverage_records:
            if not isinstance(record, dict):
                continue

            if record.get("source") != source or record.get("verified") is not True:
                continue

            if any(record.get(field) != value for field, value in context.items()):
                continue

            try:
                interval_start = parse_time(record.get("start"))
                interval_end = parse_time(record.get("end"))
            except (ValueError, TypeError):
                continue

            if interval_end > interval_start:
                intervals.append((interval_start, interval_end))

        intervals.sort()
        cursor = start

        for interval_start, interval_end in intervals:
            if interval_start > cursor:
                break

            if interval_end > cursor:
                cursor = interval_end

            if cursor >= end:
                break

        if cursor < end:
            reasons.append(f"Cobertura temporal insuficiente: {source}")

    return reasons
