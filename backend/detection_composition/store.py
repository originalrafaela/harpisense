"""Atomic composition using the existing P11 store, table and revision rules."""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

from delivery.postgres_store import PostgresStore
from psycopg.conninfo import conninfo_to_dict


class _TransactionStore(PostgresStore):
    def __init__(self, connection):
        self.connection = connection

    def _connect(self):
        return nullcontext(self.connection)


class CompositionStore(PostgresStore):
    def commit_composition(self, run_id, request_hash, window, produce):
        if conninfo_to_dict(self.conninfo).get('dbname') != 'detection_composition_test':
            raise ValueError('Synthetic writer requires detection_composition_test database')
        with self._connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
                         ('detection-composition:' + run_id,))
            previous = conn.execute(
                "SELECT data FROM projections WHERE kind='window' AND id=%s AND revision=1",
                (run_id,)).fetchone()
            if previous:
                if previous[0].get('composition_request_sha256') != request_hash:
                    raise ValueError('Composition identifier conflict')
                return {**deepcopy(previous[0]['composition']), 'replayed': True}
            result = produce()
            rows = [('detection', d['detection_id'], d) for d in result['detections']]
            rows.extend(('xai', e['explanation_id'], e) for e in result.get('explanations', []))
            incident, decision = result['incident'], result['decision']
            rows.extend([
                ('incident', incident['incident_id'], incident),
                ('decision', decision['decision_id'], decision),
                ('risk', incident['incident_id'], dict(incident_id=incident['incident_id'],
                    incident_revision=incident['revision'], risk=incident['risk'], audit=result['audit'])),
                ('window', run_id, dict(window=window, composition_request_sha256=request_hash,
                                       composition=result)),
            ])
            writer = _TransactionStore(conn)
            for kind, identifier, data in sorted(rows, key=lambda row: (row[0], row[1])):
                writer.insert(kind, SimpleNamespace(id=identifier, revision=1,
                                                    source='synthetic', data=data))
            return {**result, 'replayed': False}
