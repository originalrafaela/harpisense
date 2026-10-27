"""Integração experimental P08: logs e cobertura temporal.

Modo fail-closed. Não autoriza inferência nem executa IPS.
"""

from coverage_gate import validate_coverage


def prepare_verified_log_counts(
    events, windows, coverage_records, required_sources,
    *, coverage_provenance_verified=False
):
    """Avalia cobertura sem liberar contagens não certificadas."""

    result = {
        "authorized_for_inference": False,
        "log_counts": {},
        "reasons": [],
        "coverage_provenance_verified": coverage_provenance_verified is True,
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

    proof_sources = {
        record.get("source")
        for record in coverage_records
        if isinstance(record, dict)
        and isinstance(record.get("source"), str)
        and record.get("verified") is True
        and record.get("verification_method") == "ed25519_signed_manifest_and_interval_chain"
        and isinstance(record.get("evidence_refs"), list)
        and record["evidence_refs"]
        and all(
            isinstance(ref, dict)
            and ref.get("signature_verified") is True
            and isinstance(ref.get("manifest_sha256"), str)
            and len(ref["manifest_sha256"]) == 64
            for ref in record["evidence_refs"]
        )
    }
    provenance_verified = (
        coverage_provenance_verified is True
        and set(required_sources) <= proof_sources
    )
    result["coverage_provenance_verified"] = provenance_verified

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
        if not provenance_verified
        else "Contagens permanecem bloqueadas nesta entrega, mesmo com a procedência verificada"
    )

    return result
