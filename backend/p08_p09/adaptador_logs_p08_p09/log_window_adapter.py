"""Adaptador experimental de evidências normalizadas para janelas P08.

Somente preparação de dados. Não certifica cobertura,
não autoriza inferência e não executa ações IPS.
"""

from datetime import datetime, timezone


EVENT_FEATURES = {
    "mqtt_auth_failure": "auth_failures",
    "mqtt_auth_success": "auth_successes",
    "mqtt_acl_denial": "mqtt_acl_denials",
    "api_auth_failure": "api_auth_failures",
    "telemetry_identifier_conflict": "telemetry_identifier_conflicts",
    "telemetry_stale": "telemetry_stale_count",
}


def parse_timestamp(value):
    """Converte timestamp ISO 8601 com fuso explícito para UTC."""
    if not isinstance(value, str):
        raise ValueError("Timestamp inválido")

    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if timestamp.tzinfo is None:
        raise ValueError("Timestamp sem fuso horário")

    return timestamp.astimezone(timezone.utc)


def prepare_log_counts(events, windows):
    """Prepara contagens por janela sem certificar completude dos logs."""
    if not isinstance(events, list) or not isinstance(windows, list):
        raise ValueError("Eventos e janelas devem ser listas")

    result = {}
    context_fields = ("collection_session_id", "sensor_id", "target_ref")

    for window in windows:
        window_id = window["window_id"]

        if window_id in result:
            raise ValueError("Identificador de janela duplicado")

        start = parse_timestamp(window["window_start"])
        end = parse_timestamp(window["window_end"])

        if end <= start:
            raise ValueError("Intervalo temporal inválido")

        counts = {}
        seen = set()

        for event in events:
            # Falha fechada: contexto ausente ou divergente não é associado.
            if any(
                not isinstance(window.get(field), str)
                or not window[field].strip()
                or event.get(field) != window[field]
                for field in context_fields
            ):
                continue

            if event.get("coverage") != "COMPLETE":
                continue

            feature = EVENT_FEATURES.get(event.get("event_type"))
            if feature is None:
                continue

            observed = parse_timestamp(event["observed_at"])

            if not start <= observed < end:
                continue

            evidence_id = event["evidence_id"]

            if evidence_id in seen:
                continue

            seen.add(evidence_id)
            counts[feature] = counts.get(feature, 0) + 1

        result[window_id] = counts

    return result
