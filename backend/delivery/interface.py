"""Session-authorized incident reads and durable deterministic HarpIA history."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class InterfaceStore:
    def __init__(self, store):
        self.store = store

    def incident(self, incident_id):
        with self.store._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cur.execute("SELECT * FROM projections WHERE kind='incident' AND id=%s ORDER BY revision DESC LIMIT 1", (incident_id,))
            incident = cur.fetchone()
            if not incident:
                raise HTTPException(404, 'INCIDENT_NOT_FOUND')
            data = incident['data']
            result = {'incident': incident, 'related': {}, 'unresolved': [],
                      'commands': {'approval_available': False, 'execution_available': False}}
            # References are resolved only when immutable and unambiguous.
            for kind, field in [('detection', 'detection_refs'), ('xai', 'explanation_refs'),
                                ('evidence', 'evidence_refs'), ('network_event', 'network_event_refs')]:
                refs = data.get(field, [])
                if not isinstance(refs, list) or len(refs)>128 or any(not isinstance(x, str) for x in refs):
                    result['unresolved'].append({'kind': kind, 'reason': 'INVALID_REFERENCES'})
                    result['related'][kind] = []
                    continue
                cur.execute('SELECT * FROM projections WHERE kind=%s AND id=ANY(%s) ORDER BY id,revision', (kind, refs))
                rows = cur.fetchall()
                found = []
                for ref in refs:
                    matches = [row for row in rows if row['id']==ref]
                    if len(matches)==1:
                        found.extend(matches)
                    else:
                        result['unresolved'].append({'kind': kind, 'id': ref, 'reason': 'MISSING_OR_UNPINNED'})
                result['related'][kind] = found
            # Decisions must refer to this exact incident revision.
            cur.execute("WITH latest AS (SELECT DISTINCT ON(id) * FROM projections WHERE kind='decision' ORDER BY id,revision DESC) "
                        "SELECT * FROM latest WHERE data->>'incident_id'=%s AND data->>'incident_revision'=%s ORDER BY id",
                        (incident_id, str(incident['revision'])))
            decisions = cur.fetchall()
            result['related']['decision'] = decisions
            ids = [row['id'] for row in decisions]
            for kind in ('approval', 'execution'):
                cur.execute('WITH latest AS (SELECT DISTINCT ON(id) * FROM projections WHERE kind=%s ORDER BY id,revision DESC) '
                            'SELECT * FROM latest WHERE data->>\'decision_id\'=ANY(%s) ORDER BY id', (kind, ids))
                result['related'][kind] = cur.fetchall()
            execution_ids = [row['id'] for row in result['related']['execution']]
            cur.execute("WITH latest AS (SELECT DISTINCT ON(id) * FROM projections WHERE kind='verification' ORDER BY id,revision DESC) "
                        "SELECT * FROM latest WHERE data->>'execution_id'=ANY(%s) ORDER BY id", (execution_ids,))
            result['related']['verification'] = cur.fetchall()
            # source_ref is an evidence pointer, not proof of a readable log endpoint.
            result['log_references'] = [row['data']['source_ref'] for row in result['related']['evidence']
                                        if isinstance(row['data'].get('source_ref'), dict)]
            return result

    def remember(self, incident_id, revision, explanation):
        encoded = json.dumps(explanation, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.store._connect() as conn:
            conn.execute('INSERT INTO hs_harpia_explanation(incident_id,incident_revision,fingerprint,explanation) '
                         'VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                         (incident_id, revision, digest, Jsonb(explanation)))

    def history(self, incident_id, limit=100, before=None):
        with self.store._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT * FROM hs_harpia_explanation WHERE incident_id=%s AND (%s::bigint IS NULL OR id<%s) '
                        'ORDER BY id DESC LIMIT %s', (incident_id, before, before, limit))
            return cur.fetchall()


def install_interface_api(app, store):
    from fastapi import Response
    from fastapi.routing import APIRoute
    from admin_auth.api import PrivateRoute

    interface = InterfaceStore(store)
    def private(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/api/v1/interface', route_class=PrivateRoute,
                       dependencies=[Depends(app.state.require_admin_session), Depends(private)])

    @router.get('/incidents/{incident_id}')
    def incident(incident_id: str):
        return interface.incident(incident_id)

    @router.get('/incidents/{incident_id}/harpia')
    def history(incident_id: str, limit: int = Query(100, ge=1, le=200), before: int | None = Query(None, ge=1)):
        return {'history': interface.history(incident_id, limit, before),
                'latest_three': interface.history(incident_id, 3)}

    if not getattr(app.state, 'harpia_deterministic', False):
        raise RuntimeError('Existing deterministic HarpIA required')
    route = next(r for r in app.routes if isinstance(r, APIRoute) and r.path=='/api/v1/p11/explain/{incident_id}')
    original = route.dependant.call

    def recorded(incident_id: str, **kwargs):
        result = original(incident_id=incident_id, **kwargs)
        # Adapter returns the incident revision used in the explanation.
        revision = result.get('revision') or result.get('incident_revision')
        if type(revision) is not int:
            raise HTTPException(503, 'EXPLANATION_REVISION_UNAVAILABLE')
        interface.remember(incident_id, revision, result)
        return result

    route.dependant.call = recorded
    app.include_router(router)
    return interface
