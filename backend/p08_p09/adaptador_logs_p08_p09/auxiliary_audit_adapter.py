"""Integração auxiliar P08 -> P09, sem inferência ou IPS."""

AUXILIARY_EVENTS = frozenset({
    "telemetry_validation_failure",
    "telemetry_duplicate",
})

RAW_EVENT_TYPES = {
    "validation_failure": "telemetry_validation_failure",
    "duplicate_message": "telemetry_duplicate",
}


def prepare_auxiliary_audit(events):
    if not isinstance(events, list):
        raise TypeError("events deve ser uma lista")

    evidence = []
    rejected = 0

    for item in events:
        if not isinstance(item, dict):
            rejected += 1
            continue

        # Aceita o envelope original do coletor V5.
        if "event" in item:
            event = item["event"]
            if not isinstance(event, dict):
                rejected += 1
                continue
        else:
            event = item

        raw_type = event.get("event_type")
        event_type = RAW_EVENT_TYPES.get(raw_type, raw_type)

        if event_type not in AUXILIARY_EVENTS:
            continue

        record = {
            "event_type": event_type,
            "source": event.get("source"),
            "source_file": event.get("source_file"),
            "timestamp": event.get("timestamp", event.get("observed_at")),
            "identity": None,
            "coverage": "UNKNOWN",
            "risk_assessed": False,
            "block_authorized": False,
        }

        if "observed_at" in event:
            record["observed_at"] = event["observed_at"]

        for field in ("journal_cursor", "journal_boot_id"):
            if field in item:
                record[field] = item[field]

        evidence.append(record)

    return {
        "auxiliary_evidence": evidence,
        "auxiliary_event_count": len(evidence),
        "rejected_records": rejected,
        "log_counts": {},
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "coverage": "UNKNOWN",
    }


def prepare_auxiliary_audit_batch(batch_path):
    """Valida lote MQTT e manifesto antes da normalização auxiliar.

    Integridade local não certifica autenticidade ou cobertura.
    """
    import hashlib
    import json
    import re
    from pathlib import Path

    batch = Path(batch_path)
    if not re.fullmatch(r"mqtt_v4_[0-9a-f]{64}\.json", batch.name):
        raise ValueError("Nome do lote MQTT inválido")

    manifest_path = batch.with_name(batch.stem + ".manifest.json")

    def canonical(value):
        return json.dumps(
            value, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")
        ).encode("utf-8")

    events_bytes = batch.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    events = json.loads(events_bytes)
    manifest = json.loads(manifest_bytes)

    if not isinstance(events, list) or not isinstance(manifest, dict):
        raise ValueError("Estrutura do lote ou manifesto inválida")

    digest = hashlib.sha256(canonical(events)).hexdigest()
    if hashlib.sha256(events_bytes).hexdigest() != digest:
        raise ValueError("Serialização do lote divergente")

    if manifest.get("schema_version") != "4.0":
        raise ValueError("Versão do manifesto incompatível")

    if digest != manifest.get("events_sha256"):
        raise ValueError("SHA-256 do lote divergente")

    if (
        type(manifest.get("audit_events_found")) is not int
        or manifest["audit_events_found"] != len(events)
    ):
        raise ValueError("Contagem de eventos divergente")

    for field in ("previous_cursor", "next_cursor"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ValueError("Cursor do manifesto inválido")

    records_read = manifest.get("journal_records_read")
    if type(records_read) is not int or records_read < len(events):
        raise ValueError("Quantidade de registros do journal inválida")

    expected_id = hashlib.sha256(canonical({
        "previous_cursor": manifest["previous_cursor"],
        "next_cursor": manifest["next_cursor"],
        "events_sha256": digest,
    })).hexdigest()

    if batch.name != f"mqtt_v4_{expected_id}.json":
        raise ValueError("Identificador do lote divergente")

    if not (
        manifest.get("coverage") == "UNKNOWN"
        and manifest.get("continuity_verified") is False
        and manifest.get("authorized_for_inference") is False
        and manifest.get("authorized_for_ips") is False
    ):
        raise ValueError("Manifesto fora do modo conservador")

    for index, item in enumerate(events):
        if not isinstance(item, dict) or not isinstance(item.get("event"), dict):
            raise ValueError(f"Envelope inválido: {index}")

        if item["event"].get("event_type") not in (
            "validation_failure", "duplicate_message"
        ):
            raise ValueError(f"Tipo de evento inválido: {index}")

        for field in ("journal_cursor", "journal_boot_id"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ValueError(f"Rastreabilidade ausente: {index}/{field}")

    result = prepare_auxiliary_audit(events)
    result["batch_integrity_verified"] = True
    result["batch_file"] = batch.name
    result["manifest_file"] = manifest_path.name
    result["batch_sha256"] = digest
    result["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    result["journal_records_read"] = records_read
    # Expose already-validated provenance, including for an empty batch. Do not
    # reread the manifest in the pipeline or infer continuity from its cursors.
    result["previous_cursor"] = manifest["previous_cursor"]
    result["next_cursor"] = manifest["next_cursor"]
    result["continuity_verified"] = False
    result["coverage"] = "UNKNOWN"
    result["authorized_for_inference"] = False
    result["authorized_for_ips"] = False
    result["log_counts"] = {}
    return result
