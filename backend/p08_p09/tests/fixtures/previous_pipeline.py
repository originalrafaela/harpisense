"""Orquestração experimental P08 -> P09 em modo fail-closed.

Não autentica vínculos, não certifica cobertura e não executa
inferência RF/IF ou ações IPS.
"""

from p08_artifact_validator import validate_p08_artifacts
from log_coverage_integration import prepare_verified_log_counts
from auxiliary_audit_adapter import prepare_auxiliary_audit


def run_pipeline(
    base_dir,
    session_name,
    events,
    windows,
    coverage_records,
    required_sources,
):
    result = {
        "session": session_name,
        "artifact_consistent": False,
        "coverage_diagnostic": None,
        "authorized_for_inference": False,
        "authorized_for_ips": False,
        "log_counts": {},
        "auxiliary_audit": None,
        "reasons": [],
    }

    try:
        result["auxiliary_audit"] = prepare_auxiliary_audit(events)
    except (TypeError, ValueError):
        result["reasons"].append(
            "Falha na preparação das evidências auxiliares"
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
        events=events,
        windows=windows,
        coverage_records=coverage_records,
        required_sources=required_sources,
    )

    result["coverage_diagnostic"] = coverage
    result["reasons"].extend(coverage["reasons"])

    return result
