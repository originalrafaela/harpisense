"""Orquestração experimental P08 -> P09 em modo fail-closed.

Não autentica vínculos, não certifica cobertura e não executa
inferência RF/IF ou ações IPS.
"""

from p08_artifact_validator import validate_p08_artifacts
from log_coverage_integration import prepare_verified_log_counts
from auxiliary_audit_adapter import prepare_auxiliary_audit, prepare_auxiliary_audit_batch


def run_pipeline(
    base_dir,
    session_name,
    events,
    windows,
    coverage_records,
    required_sources,
    *,
    batch_path=None,
):
    """Select exactly one input: events list, or events=None with batch_path.

    Batch integrity is local consistency only. Auxiliary events never become
    feature counts or proof of coverage, including when the batch is empty.
    """
    result = {
        "session": session_name,
        "artifact_consistent": False,
        "coverage_diagnostic": None,
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "log_counts": {},
        "auxiliary_audit": None,
        "reasons": [],
        "input_mode": "batch" if batch_path is not None else "events",
        "batch_reference": str(batch_path) if batch_path is not None else None,
        "batch_integrity_verified": False,
        "limitations": [
            "Integridade local não comprova autenticidade, continuidade ou cobertura.",
            "Evidências auxiliares não habilitam contagens, inferência ou IPS.",
        ],
    }

    # Even [] supplied alongside a batch is ambiguous: never merge or silently
    # prefer one input. Reject before opening the batch or evaluating the gates.
    if batch_path is not None and events is not None:
        result["input_mode"] = "conflict"
        result["reasons"].append("Forneça events ou batch_path, nunca ambos")
        return result

    try:
        if batch_path is not None:
            result["auxiliary_audit"] = prepare_auxiliary_audit_batch(batch_path)
            result["batch_integrity_verified"] = True
            # No reread/re-normalization; these unbound auxiliary records are
            # retained in auxiliary_audit, not passed to a feature-count path.
            coverage_events = []
        else:
            result["auxiliary_audit"] = prepare_auxiliary_audit(events)
            coverage_events = events
    except (OSError, TypeError, ValueError) as exc:
        result["reasons"].append(
            ("Falha na preparação das evidências auxiliares"
             if batch_path is None else
             f"Falha na preparação do lote auxiliar: {type(exc).__name__}")
        )
        return result

    try:
        artifact = validate_p08_artifacts(base_dir, session_name)
    except (OSError, ValueError, TypeError) as exc:
        result["reasons"].append(
            f"Falha na validação dos artefatos: {type(exc).__name__}"
        )
        return result

    result["artifact_consistent"] = artifact["consistent"]

    if not artifact["consistent"]:
        failed = [
            name for name, passed in artifact["checks"].items()
            if not passed
        ]
        result["reasons"].append(
            "Inconsistências nos artefatos P08: " + ", ".join(failed)
        )
        return result

    coverage = prepare_verified_log_counts(
        events=coverage_events,
        windows=windows,
        coverage_records=coverage_records,
        required_sources=required_sources,
    )

    result["coverage_diagnostic"] = coverage
    result["reasons"].extend(coverage["reasons"])

    return result
