"""Associação experimental de evidências a contexto externo.

Não autentica a origem dos vínculos, não certifica cobertura
e não autoriza inferência ou ações IPS.
"""


def attach_context(events, bindings):
    """Associa contexto para diagnóstico sem alterar as evidências originais."""

    if not isinstance(events, list) or not isinstance(bindings, list):
        raise ValueError("Eventos e vínculos devem ser listas")

    required = (
        "collection_session_id",
        "sensor_id",
        "target_ref",
    )

    event_ids = set()

    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Evidência inválida")

        evidence_id = event.get("evidence_id")

        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("Identificador de evidência inválido")

        if evidence_id in event_ids:
            raise ValueError("Evidência duplicada")

        event_ids.add(evidence_id)

        if any(field in event for field in required):
            raise ValueError("Evidência contém contexto reservado")

    binding_map = {}

    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError("Vínculo inválido")

        evidence_id = binding.get("evidence_id")

        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("Identificador de vínculo inválido")

        if evidence_id not in event_ids:
            raise ValueError("Vínculo sem evidência correspondente")

        if evidence_id in binding_map:
            raise ValueError("Vínculo duplicado ou ambíguo")

        if any(
            not isinstance(binding.get(field), str)
            or not binding[field].strip()
            for field in required
        ):
            raise ValueError("Contexto incompleto")

        binding_map[evidence_id] = binding

    if set(binding_map) != event_ids:
        raise ValueError("Existem evidências sem vínculo")

    result = []

    for event in events:
        binding = binding_map[event["evidence_id"]]

        enriched = dict(event)

        for field in required:
            enriched[field] = binding[field]

        result.append(enriched)

    return result
