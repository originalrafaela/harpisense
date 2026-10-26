"""Experimental bridge from the existing P11 fact selector to the BitNet DTO."""
from .contracts import context_dto
from .deterministic import selected_facts


UNKNOWN_FIELDS = (
    "rf_attack_probability", "rf_calibrated", "if_anomaly_score",
    "risk_status", "risk_score", "risk_level", "risk_factors",
    "decision_status", "decision_action", "execution_status",
    "execution_verified_at", "observed_facts", "evidence_summary",
    "xai_contributions",
)


def context_from_p11(explanation):
    """Use facts already selected by p11.explain; never inspect raw evidence here."""
    if not isinstance(explanation, dict):
        raise ValueError("invalid P11 explanation")
    incident_id = explanation.get("incident_id")
    revision = explanation.get("revision")
    raw_facts = explanation.get("facts")
    if not isinstance(raw_facts, dict):
        raise ValueError("invalid P11 selected facts")

    facts = selected_facts(raw_facts)
    for key in UNKNOWN_FIELDS:
        facts.setdefault(key, None)
    facts["limitations"] = [
        "Campos ausentes ou null não estão disponíveis neste resumo.",
        "Causa e conectividade do ativo não foram fornecidas pelos campos selecionados.",
        "Textos livres de logs e evidências foram omitidos.",
    ]
    return context_dto({"incident_id": incident_id, "revision": revision, "facts": facts})
