"""Install on the approved P11 application and its EXISTING injected Store.

No database, inference, service credentials, writes or incident catalog are created here.
"""
from fastapi import HTTPException
from fastapi.routing import APIRoute

from .deterministic import XAI_FEATURES, fallback, identifier, number


def explain(store, incident_id):
    if not identifier(incident_id):
        raise HTTPException(422, 'Identificador inválido')
    records = store.history('incident', incident_id)
    if not records:
        raise HTTPException(404, 'Incidente não encontrado')
    latest = max(records, key=lambda r: r['revision'])
    revision, data = latest['revision'], latest['data']
    if type(revision) is not int or revision < 1 or not isinstance(data, dict):
        raise HTTPException(503, 'Projeção incompatível')
    if data.get('incident_id', incident_id) != incident_id or data.get('revision', revision) != revision:
        raise HTTPException(503, 'Identidade/revisão da projeção incompatível')
    facts = {k: data[k] for k in ('status', 'asset_id', 'scenario_id', 'target_ref') if k in data}
    risk = data.get('risk')
    if isinstance(risk, dict):
        facts.update(risk_status=risk.get('status'), risk_score=risk.get('score'), risk_level=risk.get('level'), risk_factors=risk.get('factors'))
    # Only exact references from this immutable incident revision, never an unrelated latest row.
    refs = data.get('detection_refs', [])
    if not isinstance(refs, list) or len(refs) > 16:
        raise HTTPException(422, 'Referências acima do limite ou inválidas')
    detections = []
    evidence_refs = data.get('evidence_refs', [])
    if isinstance(evidence_refs, list) and len(evidence_refs) <= 32 and all(identifier(v) for v in evidence_refs):
        facts['evidence_ref_count'] = len(evidence_refs)
    for ref in refs:
        if not identifier(ref):
            raise HTTPException(422, 'Referência inválida')
        rows = store.history('detection', ref)
        # Unpinned, mutable child revisions are ambiguous: do not silently pick one.
        if len(rows) == 1 and isinstance(rows[0].get('data'), dict):
            detections.append(rows[0]['data'])
    rf, anomaly = [], []
    window_values = {'start': set(), 'end': set()}
    for detection in detections:
        model = detection.get('model') or {}
        classification = detection.get('classification') or {}
        scoring = detection.get('anomaly') or {}
        if not all(isinstance(v, dict) for v in (model, classification, scoring)):
            continue
        window = detection.get('window') or {}
        if isinstance(window, dict):
            for name in ('start', 'end'):
                candidate = window.get(name)
                if isinstance(candidate, str):
                    window_values[name].add(candidate)
        if model.get('detector') == 'random_forest':
            value = number(classification.get('attack_probability'), 0, 1)
            if value is not None:
                rf.append(value)
        if model.get('detector') == 'isolation_forest':
            value = number(scoring.get('anomaly_score'))
            if value is not None:
                anomaly.append(value)
    if len(rf) == 1:
        facts['rf_attack_probability'] = rf[0]
    if len(anomaly) == 1:
        facts['if_anomaly_score'] = anomaly[0]
    for name, values in window_values.items():
        if len(values) == 1:
            facts['window_' + name] = next(iter(values))
    explanation_refs = data.get('explanation_refs', [])
    if isinstance(explanation_refs, list) and len(explanation_refs) <= 16:
        contributions = []
        for ref in explanation_refs:
            if not identifier(ref):
                continue
            rows = store.history('xai', ref)
            if len(rows) != 1 or not isinstance(rows[0].get('data'), dict):
                continue
            for item in rows[0]['data'].get('contributions', [])[:32]:
                if not isinstance(item, dict) or item.get('feature') not in XAI_FEATURES:
                    continue
                value = number(item.get('value'))
                contribution = number(item.get('contribution'))
                if value is not None and contribution is not None:
                    contributions.append({'feature': item['feature'], 'value': value, 'contribution': contribution})
        if contributions:
            facts['xai_contributions'] = sorted(contributions, key=lambda item: abs(item['contribution']), reverse=True)[:3]
    # Existing Store offers list/history, not a relational query. Bounded candidates
    # must match BOTH incident and revision; absence remains unknown, never "none".
    decision_id = identifier(data.get('decision_id'))
    if not decision_id:
        candidates = []
        for offset in range(0, 1000, 200):
            page = store.list('decision', limit=200, offset=offset)
            candidates.extend(r for r in page if r['data'].get('incident_id') == incident_id and r['data'].get('incident_revision') == revision)
            if len(page) < 200:
                break
        else:
            candidates = []  # Coverage cap reached: retain unknown rather than assume uniqueness.
        if len(candidates) == 1:
            decision_id = identifier(candidates[0]['id'])
    if decision_id:
        rows = store.history('decision', decision_id)
        matching = [r['data'] for r in rows if r['data'].get('incident_id') == incident_id
                    and r['data'].get('incident_revision') == revision]
        if len(matching) == 1:
            decision = matching[0]
            facts.update(decision_id=decision_id, decision_status=decision.get('status'))
            action = decision.get('action')
            if isinstance(action, dict):
                facts['decision_action'] = action.get('action_type')
            execution_id = identifier(decision.get('execution_id'))
            if not execution_id:
                candidates = []
                for offset in range(0, 1000, 200):
                    page = store.list('execution', limit=200, offset=offset)
                    candidates.extend(r for r in page if r['data'].get('decision_id') == decision_id)
                    if len(page) < 200:
                        break
                else:
                    candidates = []
                if len(candidates) == 1:
                    execution_id = identifier(candidates[0]['id'])
            if execution_id:
                executions = store.history('execution', execution_id)
                if executions:
                    execution = max(executions, key=lambda r: r['revision'])['data']
                    if execution.get('decision_id') == decision_id:
                        facts['execution_status'] = execution.get('status')
                        if isinstance(execution.get('verified_at'), str):
                            facts['execution_verified_at'] = execution['verified_at']
    result = fallback(dict(incident_id=incident_id, revision=revision, facts=facts))
    result['limitations'] = ['Cobertura limitada aos campos tipados e referências inequívocas desta revisão.',
                            'Busca de decisão/execução limitada aos 1.000 registros mais recentes; cobertura truncada permanece desconhecida.',
                            'Dados livres e contribuições XAI não são interpretados como fatos.']
    return result


def install_deterministic_harpia(app, store):
    """Preserve the approved routes' dependency trees, including Basic authentication.

    Pinned FastAPI 0.115 integration; fail closed if the expected authenticated routes
    are absent. Tested through HTTP, not by calling unprotected route functions.
    """
    if getattr(app.state, 'harpia_deterministic', False):
        raise RuntimeError('HarpIA already installed')
    routes = {r.path: r for r in app.routes if isinstance(r, APIRoute)}
    endpoint = routes.get('/api/v1/p11/explain/{incident_id}')
    health = routes.get('/api/v1/p11/health')
    if not endpoint or not health or not endpoint.dependant.dependencies or not health.dependant.dependencies:
        raise RuntimeError('Authenticated approved P11 routes required')
    original_health = health.dependant.call

    def deterministic(incident_id: str, **kwargs):
        return explain(store, incident_id)

    def capabilities(**kwargs):
        value = original_health(**kwargs)
        return {**value, 'harpia': {'mode': 'deterministic_only', 'contract_version': 1,
                                  'generation_enabled': False, 'model': 'bitnet'}}

    endpoint.dependant.call = deterministic
    health.dependant.call = capabilities
    app.state.harpia_deterministic = True
