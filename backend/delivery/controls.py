"""Versioned controls. The queue authority must join the SAME transaction/lock.

P11 projections are deliberately never used to attest an empty operational queue.
No dispatcher, collector, shell command or model generation is called here.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

from harpisense_contracts.compatibility import canonical_operation

LOCK_ID = 72611027
QUEUE_DEPENDENCY = ('A fila de aprovações, decisões, execuções e reversões ainda precisa ser integrada '
                    'para verificar todas as pendências com confiança. A troca de perfil permanece bloqueada.')


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Rejected(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(detail['message'])


class UnknownQueue:
    def snapshot(self, tx):
        return {'reliable': False, 'blockers': [], 'dependency': QUEUE_DEPENDENCY}


class Controls:
    def __init__(self, repository, queue=None):
        self.repository, self.queue = repository, queue or UnknownQueue()

    def pending(self, tx):
        try:
            result = self.queue.snapshot(tx)
            if (not isinstance(result, dict) or type(result.get('reliable')) is not bool
                    or not isinstance(result.get('blockers'), list)
                    or any(not isinstance(b, dict) or not b.get('id') or not b.get('state') for b in result['blockers'])):
                raise ValueError('Invalid queue snapshot')
            return result
        except Exception:
            return UnknownQueue().snapshot(tx)

    def view(self, tx):
        current = tx.read()
        pending = self.pending(tx)
        return {**current, 'pending': pending, 'observed_at': stamp(),
                'real_execution_blocked': True,
                'executor': 'isolated_simulation_only',
                'change_allowed': pending['reliable'] and not pending['blockers']}

    def get(self):
        with self.repository.transaction() as tx:
            return self.view(tx)

    def change(self, *, value, expected_revision, reason, actor):
        value = canonical_operation(value)
        if 'revision' in value or type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('Use expected_revision fora do valor canônico')
        failure = None
        with self.repository.transaction() as tx:
            before = tx.read()
            pending = self.pending(tx)
            code, message = None, None
            if expected_revision != before['revision']:
                code, message = 'REVISION_CONFLICT', 'Configuração alterada por outra operação. Consulte novamente.'
            elif value['operation'] == 'REAL':
                code, message = 'REAL_EXECUTION_BLOCKED', 'Execução REAL bloqueada nesta entrega.'
            elif before['emergency_stopped'] and value['execution_enabled']:
                code, message = 'EMERGENCY_STOPPED', 'Parada de emergência ativa; retomada exige procedimento próprio.'
            elif not pending['reliable']:
                code, message = 'QUEUE_UNVERIFIED', 'Estado das pendências operacionais não verificado.'
            elif pending['blockers']:
                code, message = 'OPERATIONAL_PENDING', 'Há pendências operacionais que impedem a transição.'
            if code:
                detail = {'code': code, 'message': message, 'pending': pending,
                          'current_revision': before['revision']}
                tx.log(actor, 'CONTROL_CHANGE_REJECTED', {'code': code, 'reason': reason,
                       'expected_revision': expected_revision, 'pending': pending})
                failure = Rejected(409, detail)
            elif value == before['value']:
                tx.log(actor, 'CONTROL_CHANGE_NOOP', {'reason': reason, 'revision': before['revision']})
            else:
                # No historical decision is replayed or reclassified. No dispatch on change.
                tx.save(value, before['revision'] + 1, before['emergency_stopped'])
                tx.log(actor, 'CONTROL_CHANGED', {'before': before, 'value': value,
                       'revision': before['revision'] + 1, 'reason': reason})
            result = self.view(tx)
        # Audit refusals commit too; exceptions inside the transaction would erase them.
        if failure:
            raise failure
        return result

    def stop(self, *, actor, reason):
        with self.repository.transaction() as tx:
            before = tx.read()
            value = {**before['value'], 'execution_enabled': False}
            tx.save(value, before['revision'] + 1, True)
            tx.log(actor, 'EMERGENCY_STOP', {'reason': reason, 'revision': before['revision'] + 1})
            # Do not consult a queue adapter at all on the emergency path.
            return {**tx.read(), 'pending': UnknownQueue().snapshot(tx), 'observed_at': stamp(),
                    'real_execution_blocked': True, 'executor': 'isolated_simulation_only',
                    'change_allowed': False}

    @contextmanager
    def decision_transaction(self, expected_revision):
        """Trusted producer hook. Never expose this as a client-supplied attestation.

        All admission, review, claims, results and reversals must use this lock and
        the yielded connection; external queues need a coordinated adapter first.
        A producer holding an old configuration must reevaluate, never auto-replay.
        """
        with self.repository.transaction() as tx:
            current = tx.read()
            if current['revision'] != expected_revision:
                raise Rejected(409, {'code': 'REVISION_CONFLICT', 'message': 'Reavaliar sob o perfil atual.'})
            yield tx, current
