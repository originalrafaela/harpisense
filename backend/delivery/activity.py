"""Producer adapter, not a second profile controller or a public ingestion API.

Only a worker owning complete coverage may publish a complete operational
snapshot. A projection, assessment, MQTT connection or synthetic trial cannot
attest it. Every write joins the existing controls transaction and lock.
"""
from copy import deepcopy

from psycopg.types.json import Jsonb
from harpisense_contracts import fingerprint, validate
from .controls import Controls, LOCK_ID
from .operational_queue import OperationalQueue, SOURCES, ACTIVE, CLOSED


def write_decision_snapshot(tx, bundle, current, *, decision_revision=1, origin):
    """Persist an admitted profile, never reconstruct history from today's mode."""
    if origin not in ('synthetic','trusted-service'):
        raise ValueError('UNKNOWN_DECISION_ORIGIN')
    tx.conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
    decision=bundle['decision']; validate(decision)
    if decision['autonomy_mode'] != current['value']['autonomy_mode']:
        raise ValueError('DECISION_PROFILE_CHANGED')
    profile=Controls.historical_profile(current)
    audit=bundle['audit']
    if audit['formula_version']!=decision['policy_version']:
        raise ValueError('POLICY_SNAPSHOT_MISMATCH')
    context=bundle.get('context')
    if context is not None and fingerprint(context)!=audit['context_fingerprint']:
        raise ValueError('CONTEXT_SNAPSHOT_MISMATCH')
    policy={'version':decision['policy_version'],'audit':audit}
    tx.conn.execute('INSERT INTO hs_decision_snapshot '
        '(decision_id,decision_revision,origin,historical_profile,policy,context) VALUES(%s,%s,%s,%s,%s,%s)',
        (decision['decision_id'],decision_revision,origin,Jsonb(profile),Jsonb(policy),
         None if context is None else Jsonb(context)))
    return profile


class ActivityProducer:
    def __init__(self, queue=None):
        self.queue=queue or OperationalQueue()

    def publish(self, tx, *, source, source_revision, items, origin, complete):
        """Internal service hook under Controls.decision_transaction.

        Each item has id/state and may supply record_revision and incident_ref.
        Lifecycle comes from the producer, never from human attack assessment.
        Synthetic reports are durable trial history only and do not refresh or
        overwrite operational coverage. Partial coverage carries UNKNOWN.
        """
        if (source not in SOURCES or type(source_revision) is not int or source_revision<1
                or origin not in ('synthetic','trusted-service') or type(complete) is not bool
                or not isinstance(items,list) or len(items)>9999):
            raise ValueError('INVALID_ACTIVITY_REPORT')
        prepared=[]; seen=set()
        for item in deepcopy(items):
            if (not isinstance(item,dict) or set(item)-{'id','state','record_revision','incident_ref'}
                    or not isinstance(item.get('id'),str) or not 1<=len(item['id'])<=128
                    or item['id'].startswith('__coverage__:') or item['id'] in seen
                    or item.get('state') not in ACTIVE|CLOSED):
                raise ValueError('INVALID_ACTIVITY_ITEM')
            if 'record_revision' in item and (type(item['record_revision']) is not int or item['record_revision']<1):
                raise ValueError('INVALID_RECORD_REVISION')
            ref=item.get('incident_ref')
            if ref is not None and (not isinstance(ref,dict) or set(ref)!={'id','revision'}
                    or not isinstance(ref['id'],str) or type(ref['revision']) is not int or ref['revision']<1):
                raise ValueError('INVALID_INCIDENT_REFERENCE')
            seen.add(item['id']);prepared.append(item)
        tx.conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
        for item in prepared:
            ref=item.get('incident_ref')
            if ref is not None:
                row=tx.conn.execute("SELECT source FROM projections WHERE kind='incident' AND id=%s AND revision=%s",
                                    (ref['id'],ref['revision'])).fetchone()
                if not row or row[0]!=origin:
                    raise ValueError('INCIDENT_ORIGIN_OR_REVISION_MISMATCH')
            tx.conn.execute('INSERT INTO hs_activity_event(source,source_revision,record_id,origin,data) '
                'VALUES(%s,%s,%s,%s,%s)',(source,source_revision,item['id'],origin,Jsonb(item)))
        if origin=='trusted-service':
            # Queue contract calls the producer record revision `revision`;
            # source_revision remains the independent full-snapshot generation.
            operational=[{**item,**({'revision':item['record_revision']}
                         if 'record_revision' in item else {})} for item in prepared]
            if not complete:
                operational.append({'id':'__coverage__:'+source,'state':'UNKNOWN'})
            else:
                previous=tx.conn.execute('SELECT items FROM hs_operational_authority WHERE source=%s',
                                         (source,)).fetchone()
                if previous and any(i.get('id')=='__coverage__:'+source for i in previous[0]):
                    operational.append({'id':'__coverage__:'+source,'state':'CLOSED'})
            self.queue.report(tx,source,source_revision,operational)
        tx.log('activity-producer','ACTIVITY_REPORTED',{'source':source,'source_revision':source_revision,
               'origin':origin,'complete':complete,'item_count':len(prepared)})
        return {'origin':origin,'operational_reported':origin=='trusted-service',
                'source':source,'source_revision':source_revision,'complete':complete}
