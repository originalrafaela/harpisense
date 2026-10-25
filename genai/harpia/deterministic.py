"""Read-only operational explanation. Raw evidence never becomes narrative instructions."""
import math
import re
from datetime import datetime, timezone

ID = re.compile(r"[A-Za-z0-9_.:@/-]{1,128}\Z")
STATES = {'OPEN', 'OBSERVED', 'CORROBORATED', 'CLOSED', 'INCOMPLETE'}
DECISIONS = {'OBSERVE_ONLY', 'REQUEST_APPROVAL', 'AUTHORIZED', 'DENIED'}
EXECUTIONS = {'QUEUED', 'APPLYING', 'COMMAND_ACCEPTED', 'VERIFYING', 'MITIGATION_CONFIRMED',
              'SIMULATED', 'UNAVAILABLE', 'FAILED', 'UNKNOWN_OUTCOME', 'REVERSED', 'EXPIRED',
              'EXPIRING', 'REVERSING', 'REVERSAL_FAILED'}
XAI_FEATURES = {'packet_count', 'bytes_total', 'packets_per_second', 'connections_per_second',
                'syn_count', 'rst_count', 'unique_dst_ports', 'avg_packet_size', 'mean_interarrival_ms',
                'connection_failures', 'auth_failures', 'auth_successes', 'mqtt_publish_count',
                'mqtt_acl_denials', 'api_auth_failures', 'admin_auth_failures',
                'telemetry_identifier_conflicts', 'telemetry_stale_count'}


def identifier(value):
    return value if isinstance(value, str) and ID.fullmatch(value) else None


def number(value, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return value if (low is None or value >= low) and (high is None or value <= high) else None


def selected_facts(facts):
    """Explicit typed P11 fields only; free-form evidence is retained by the caller's store."""
    out = {}
    for key in ('asset_id', 'decision_id', 'scenario_id', 'target_ref'):
        if identifier(facts.get(key)):
            out[key] = facts[key]
    for key, allowed in [('status', STATES), ('decision_status', DECISIONS), ('execution_status', EXECUTIONS),
                         ('risk_level', {'LOW', 'MODERATE', 'HIGH', 'CRITICAL'}),
                         ('risk_status', {'COMPLETE', 'INCOMPLETE', 'NOT_EVALUATED'})]:
        if isinstance(facts.get(key), str) and facts[key] in allowed:
            out[key] = facts[key]
    for key, low, high in [('rf_attack_probability', 0, 1), ('if_anomaly_score', None, None), ('risk_score', 0, 100)]:
        value = number(facts.get(key), low, high)
        if value is not None:
            out[key] = value
    if type(facts.get('rf_calibrated')) is bool:
        out['rf_calibrated'] = facts['rf_calibrated']
    factors = facts.get('risk_factors')
    if isinstance(factors, dict):
        out['risk_factors'] = {k: number(factors.get(k), 0, 100) for k in
                               ('detection', 'corroboration', 'impact', 'anomaly', 'criticality')}
    for key in ('window_start', 'window_end'):
        value = facts.get(key)
        if isinstance(value, str) and len(value) <= 40:
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                out[key] = value
            except ValueError:
                pass
    verified = facts.get('execution_verified_at')
    if isinstance(verified, str) and len(verified) <= 40:
        try:
            datetime.fromisoformat(verified.replace('Z', '+00:00'))
            out['execution_verified_at'] = verified
        except ValueError:
            pass
    if facts.get('decision_action') in ('BLOCK_SOURCE_IP', 'RATE_LIMIT_SOURCE_IP', 'QUARANTINE_DEVICE', 'REVOKE_MQTT_CLIENT'):
        out['decision_action'] = facts['decision_action']
    count = facts.get('evidence_ref_count')
    if type(count) is int and 0 <= count <= 32:
        out['evidence_ref_count'] = count
    contributions = facts.get('xai_contributions')
    if isinstance(contributions, list) and len(contributions) <= 3:
        safe = []
        for item in contributions:
            if not isinstance(item, dict) or item.get('feature') not in XAI_FEATURES:
                continue
            value, contribution = number(item.get('value')), number(item.get('contribution'))
            if value is not None and contribution is not None:
                safe.append({'feature': item['feature'], 'value': value, 'contribution': contribution})
        if safe:
            out['xai_contributions'] = safe
    return out


def fallback(context):
    facts = selected_facts(context.get('facts', {}))
    parts = [f"Explicação determinística. Incidente {context['incident_id']}; revisão {context['revision']}."]
    if facts.get('asset_id'):
        parts.append(f"Ativo registrado: {facts['asset_id']}.")
    parts.append(f"Estado do incidente: {facts.get('status', 'não informado')}.")
    rf = facts.get('rf_attack_probability')
    parts.append('RF: resultado ausente.' if rf is None else f"RF: probabilidade de ataque registrada {rf}; calibração {'confirmada' if facts.get('rf_calibrated') is True else 'não confirmada neste resumo'}.")
    score = facts.get('if_anomaly_score')
    parts.append('IF: resultado ausente.' if score is None else f"IF: score operacional {score}; não é probabilidade de ataque e não determina sozinho o risco.")
    parts.append(f"Risk Engine: estado {facts.get('risk_status', 'não informado')}, score {facts.get('risk_score', 'não informado')}, nível {facts.get('risk_level', 'não informado')}; sem recálculo.")
    parts.append(f"Policy Engine: decisão {facts.get('decision_status', 'não informada')}.")
    if facts.get('decision_action'):
        parts.append(f"Ação na decisão: {facts['decision_action']}; proposta/autorização não comprova execução.")
    if 'risk_factors' in facts:
        parts.append('Fatores registrados do risco: ' + ', '.join(f'{k}={v if v is not None else "ausente"}' for k, v in facts['risk_factors'].items()) + '.')
    if facts.get('window_start') or facts.get('window_end'):
        parts.append(f"Intervalo: {facts.get('window_start', 'não informado')} a {facts.get('window_end', 'não informado')}.")
    if facts.get('xai_contributions'):
        parts.append('XAI (contribuições registradas; não demonstram causa): ' + '; '.join(
            f"{item['feature']} (valor {item['value']}, contribuição {item['contribution']})"
            for item in facts['xai_contributions']) + '.')
    if facts.get('scenario_id'):
        parts.append(f"Cenário associado: {facts['scenario_id']}.")
    if facts.get('target_ref'):
        parts.append(f"Alvo registrado: {facts['target_ref']}.")
    if facts.get('evidence_ref_count'):
        parts.append(f"Referências de evidência vinculadas: {facts['evidence_ref_count']}; os textos originais não são repetidos.")
    execution = facts.get('execution_status')
    if execution == 'MITIGATION_CONFIRMED' and facts.get('execution_verified_at'):
        parts.append(f"Estado registrado da execução: MITIGATION_CONFIRMED; verificação registrada em {facts['execution_verified_at']}.")
    elif execution:
        parts.append(f"Estado registrado da execução: {execution}; esse estado não equivale a mitigação confirmada.")
    else:
        parts.append('Execução: informação ausente; não permite concluir se a ação foi ou não executada.')
    parts.append('Causa e evidência de ataque não são inferidas por esta explicação. Textos livres de logs não são reproduzidos; evidências originais permanecem no armazenamento de origem.')
    return dict(source='deterministic_fallback', source_label='Explicação determinística',
                incident_id=context['incident_id'], revision=context['revision'],
                generated_at=datetime.now(timezone.utc).isoformat(), text=' '.join(parts),
                facts=facts, bitnet_status='disabled_for_quality', persisted=False)
