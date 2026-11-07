"""Exact PostgreSQL resolver and projection adapter for the owned action hook.

No inference, client context, mode controller or real executor is introduced.
"""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from types import SimpleNamespace

from harpisense_contracts import fingerprint, validate_links
from .activity import write_decision_snapshot
from .postgres_store import PostgresStore


class TransactionWriter(PostgresStore):
    def __init__(self,connection):self.connection=connection
    def _connect(self):return nullcontext(self.connection)


def exact(tx,kind,identifier,revision=None):
    rows=tx.conn.execute('SELECT revision,source,data FROM projections WHERE kind=%s AND id=%s '
                         'AND (%s::integer IS NULL OR revision=%s) ORDER BY revision',
                         (kind,identifier,revision,revision)).fetchall()
    if len(rows)!=1:raise ValueError('MISSING_OR_UNPINNED_'+kind.upper())
    return rows[0]


class PersistentActionResolver:
    def __init__(self,*,incident_id=None,incident_revision=None,decision_revision=None):
        self.incident_id=incident_id;self.incident_revision=incident_revision
        self.decision_revision=decision_revision

    def __call__(self,tx,decision_id):
        revision,origin,decision=exact(tx,'decision',decision_id,self.decision_revision)
        if (self.incident_id is not None and decision['incident_id']!=self.incident_id
                or self.incident_revision is not None and decision['incident_revision']!=self.incident_revision):
            raise ValueError('DECISION_NOT_IN_INCIDENT_REVISION')
        snapshot=tx.conn.execute('SELECT origin,historical_profile,policy,context FROM hs_decision_snapshot '
                                'WHERE decision_id=%s AND decision_revision=%s',(decision_id,revision)).fetchone()
        if not snapshot or snapshot[0]!=origin or snapshot[3] is None:
            raise ValueError('DECISION_CONTEXT_NOT_PERSISTED')
        _,incident_origin,incident=exact(tx,'incident',decision['incident_id'],decision['incident_revision'])
        latest=tx.conn.execute("SELECT revision,source FROM projections WHERE kind='incident' AND id=%s "
                               'ORDER BY revision DESC LIMIT 1',(decision['incident_id'],)).fetchone()
        if incident_origin!=origin or latest[1]!=origin:
            raise ValueError('INCIDENT_ORIGIN_MISMATCH')
        context=snapshot[3];audit=snapshot[2]['audit']
        if (snapshot[1]['autonomy_mode']!=decision['autonomy_mode']
                or snapshot[2]['version']!=decision['policy_version']
                or fingerprint(context)!=audit['context_fingerprint']):
            raise ValueError('DECISION_SNAPSHOT_MISMATCH')
        for kind,key,idkey in (('detection','detections','detection_id'),('xai','explanations','explanation_id')):
            for record in context[key]:
                _,record_origin,persisted=exact(tx,kind,record[idkey])
                if record_origin!=origin or persisted!=record:
                    raise ValueError('CONTEXT_RECORD_MISMATCH')
        valid=tx.conn.execute('SELECT %s::timestamptz>clock_timestamp()',
                             (decision['valid_until'],)).fetchone()[0]
        if not valid:raise ValueError('DECISION_EXPIRED')
        validate_links(detections=context['detections'],explanations=context['explanations'],
                       incidents=[incident],decisions=[decision])
        return {'incident':incident,'decision':decision,'audit':audit},context,origin,latest[0]


class ProjectionTransaction:
    def __init__(self,tx):self.tx=tx;self.conn=tx.conn
    def __getattr__(self,name):return getattr(self.tx,name)

    def review_put(self,kind,decision_id,result,actor):
        self.tx.review_put(kind,decision_id,result,actor)
        origin=result['origin'];writer=TransactionWriter(self.conn)
        def insert(record_kind,identifier,data):
            writer.insert(record_kind,SimpleNamespace(id=identifier,revision=1,source=origin,data=data))
        if kind=='approval':
            bundle=result['bundle'];decision=bundle['decision']
            insert('decision',decision['decision_id'],decision)
            insert('approval',decision['approval']['approval_id'],decision['approval'])
            # The new decision keeps the original admitted context and policy;
            # this sidecar records the controls at this specific approval.
            _,context,_,_=PersistentActionResolver()(self,decision_id)
            write_decision_snapshot(self,{**bundle,'context':context},self.read(),origin=origin)
        elif kind=='result':
            execution=result['execution']
            insert('execution',execution['execution_id'],execution)
        elif kind=='verification':
            insert('verification','verification-'+result['execution_id'],deepcopy(result))


class ProjectionRepository:
    def __init__(self,repository):self.repository=repository
    @contextmanager
    def transaction(self):
        with self.repository.transaction() as tx:yield ProjectionTransaction(tx)
