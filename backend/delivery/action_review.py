"""Trusted internal action review; no HTTP admission, model or OS executor.

The resolver must load exact persisted bundle/context/origin under the supplied
transaction and return the CURRENT incident revision. Never bind it to request
JSON. Authentication of actor is the composition's responsibility.
"""
from copy import deepcopy

from harpisense_contracts import fingerprint, validate
from harpisense_contracts.validation import timestamp
from harpisense_engines import preflight


def authorize_specific(bundle, context, *, actor, now, expected_action,
                       current_mode, current_incident_revision):
    """Create a new authorized snapshot, preserving the pending decision."""
    original = bundle['decision']
    validate(original)
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError('AUTHENTICATED_ACTOR_REQUIRED')
    if original['status'] != 'REQUEST_APPROVAL':
        raise ValueError('SPECIFIC_APPROVAL_NOT_PENDING')
    if original['action_fingerprint'] != expected_action:
        raise ValueError('ACTION_FINGERPRINT_CONFLICT')
    if not timestamp(original['created_at']) <= timestamp(now) < timestamp(original['valid_until']):
        raise ValueError('DECISION_EXPIRED')
    authorized = deepcopy(bundle)
    decision = authorized['decision']
    decision.update(
        decision_id='dec-approved-' + fingerprint([original['decision_id'], actor, now]),
        supersedes_decision_id=original['decision_id'], created_at=now,
        status='AUTHORIZED', reason_codes=['SPECIFIC_MANUAL_APPROVAL'],
    )
    decision['approval'] = dict(
        approval_id='approval-' + fingerprint([decision['decision_id'], expected_action]),
        decision_id=decision['decision_id'], action_fingerprint=expected_action,
        policy_version=decision['policy_version'], approved_by=actor,
        approved_at=now, expires_at=decision['valid_until'],
    )
    # Reuse all evidence/target/scope/protected/freshness/executor gates.
    preflight(authorized, context, now=now, current_mode=current_mode,
              current_incident_revision=current_incident_revision,
              config=bundle['audit']['config'])
    return authorized


class ActionReview:
    """Explicit approval and simulated result are independent transactions.

    controls must use PostgresControls for persistence. resolver(tx, decision_id)
    returns (bundle, context, immutable_origin, current_incident_revision).
    Unknown origins are never promoted. Evaluation remains Backend's assessment.
    """
    def __init__(self, controls, resolver):
        self.controls, self.resolver = controls, resolver

    @staticmethod
    def origin(value):
        if value not in ('synthetic', 'trusted-service'):
            raise ValueError('ORIGIN_UNVERIFIED')
        return value

    def approve(self, decision_id, *, expected_action, expected_revision, actor, now):
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('AUTHENTICATED_ACTOR_REQUIRED')
        with self.controls.decision_transaction(expected_revision) as (tx, state):
            if state['emergency_stopped']:
                raise ValueError('EMERGENCY_STOPPED')
            bundle, context, origin, revision = self.resolver(tx, decision_id)
            if bundle['decision']['decision_id'] != decision_id:
                raise ValueError('DECISION_ID_CONFLICT')
            origin = self.origin(origin)
            # One approval per immutable pending decision; retries return it.
            previous = tx.review_get('approval', decision_id)
            if previous is not None:
                if previous['bundle']['decision']['action_fingerprint'] != expected_action:
                    raise ValueError('ACTION_FINGERPRINT_CONFLICT')
                preflight(previous['bundle'], context, now=now,
                          current_mode=state['value']['autonomy_mode'],
                          current_incident_revision=revision,
                          config=previous['bundle']['audit']['config'])
                if previous['origin'] != origin:
                    raise ValueError('ORIGIN_CONFLICT')
                return previous
            authorized = authorize_specific(bundle, context, actor=actor, now=now,
                expected_action=expected_action, current_mode=state['value']['autonomy_mode'],
                current_incident_revision=revision)
            result = dict(bundle=authorized, origin=origin,
                          historical_profile=authorized['decision']['autonomy_mode'],
                          control_revision=state['revision'], dispatched=False)
            tx.review_put('approval', decision_id, result, actor)
            return result

    def simulate(self, decision_id, *, expected_revision, actor, now):
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('AUTHENTICATED_ACTOR_REQUIRED')
        with self.controls.decision_transaction(expected_revision) as (tx, state):
            if (state['emergency_stopped'] or state['value']['operation'] != 'SIMULATION'
                    or not state['value']['execution_enabled']):
                raise ValueError('SIMULATION_DISABLED')
            bundle, context, origin, revision = self.resolver(tx, decision_id)
            if bundle['decision']['decision_id'] != decision_id:
                raise ValueError('DECISION_ID_CONFLICT')
            origin = self.origin(origin)
            approval = tx.review_get('approval', decision_id)
            if approval is not None:
                if approval['origin'] != origin:
                    raise ValueError('ORIGIN_CONFLICT')
                bundle = approval['bundle']
            preflight(bundle, context, now=now, current_mode=state['value']['autonomy_mode'],
                      current_incident_revision=revision, config=bundle['audit']['config'])
            previous = tx.review_get('result', decision_id)
            if previous is not None:
                if previous['origin'] != origin:
                    raise ValueError('ORIGIN_CONFLICT')
                return previous
            decision = bundle['decision']
            execution = dict(schema_version='1.0.0', record_type='execution',
                execution_id='sim-'+decision['decision_id'], decision_id=decision['decision_id'],
                action_fingerprint=decision['action_fingerprint'], status='SIMULATED',
                requested_at=now, started_at=now, accepted_at=None, verified_at=None,
                expires_at=None, reversed_at=None, attempt_count=1)
            validate(execution)
            result = dict(execution=execution, origin=origin, simulated=True,
                historical_profile=decision['autonomy_mode'], control_revision=state['revision'],
                mitigation_confirmed=False, real_executor='not_available')
            tx.review_put('result', decision_id, result, actor)
            # Simulation is not verification of a defense in the operating system.
            tx.review_put('verification', decision_id, dict(
                execution_id=execution['execution_id'], origin=origin,
                historical_profile=decision['autonomy_mode'], status='NOT_PERFORMED',
                reason='SIMULATION_NO_REAL_CONTAINMENT', mitigation_confirmed=False), actor)
            return result
