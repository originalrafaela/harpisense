"""Adapt final execution control to canonical Policy and PostgreSQL transaction.

Retains IDS/SIMULATION semantics from Controle_Execucao_v1. No REAL branch or
adapter registration exists in this delivery. This is an isolated test executor,
not an operational worker or a new policy engine.
"""
from harpisense_engines import preflight
from harpisense_contracts import validate


def simulate(controls, bundle, context, *, expected_revision, now):
    with controls.decision_transaction(expected_revision) as (tx, state):
        value, decision = state['value'], bundle['decision']
        if state['emergency_stopped'] or value['operation'] != 'SIMULATION' or not value['execution_enabled']:
            return {'status': 'DENIED', 'reason': 'EXECUTION_DISABLED', 'executor': 'isolated_simulation'}
        validate(decision)
        preflight(bundle, context, now=now, current_mode=value['autonomy_mode'],
                  current_incident_revision=bundle['incident']['revision'])
        execution = dict(schema_version='1.0.0', record_type='execution',
                         execution_id='sim-'+decision['decision_id'], decision_id=decision['decision_id'],
                         action_fingerprint=decision['action_fingerprint'], status='SIMULATED',
                         requested_at=now, started_at=now, accepted_at=None, verified_at=None,
                         expires_at=None, reversed_at=None, attempt_count=1)
        validate(execution)
        # Replay prevention is durable in the same PostgreSQL transaction as controls.
        result = {'status': 'SIMULATED', 'decision_id': decision['decision_id'],
                  'control_revision': state['revision'], 'executor': 'isolated_simulation',
                  'mitigation_confirmed': False, 'simulated_at': now, 'execution': execution}
        return tx.simulation_once(decision['decision_id'], result)
