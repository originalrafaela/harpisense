"""Persistent administrative labels; trusted manifest validates compatibility.

No device identity, telemetry, broker or operational state is mutated here.
"""
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .schema import ConfigError, IDENTIFIER, checked, obj, text
from .store import Conflict, identifier

ASSET_DOCUMENT = obj({
    'display_name': text(100, r'^[^\x00-\x1f\x7f]+$'),
    'asset_type': {'enum': ['device', 'sensor', 'gateway']},
    'profile': IDENTIFIER,
    'location': text(100, r'^[^\x00-\x1f\x7f]+$'),
    'group': text(100, r'^[^\x00-\x1f\x7f]+$'),
    'bindings': obj({'connection': IDENTIFIER, 'sensor': IDENTIFIER, 'gateway': IDENTIFIER}, []),
}, ['display_name', 'asset_type', 'profile', 'bindings'])
ASSET_REQUEST = obj({'expected_revision': {'type': 'integer', 'minimum': 0}, 'document': ASSET_DOCUMENT})


class AssetStore:
    def __init__(self, config, catalog):
        self.config = config
        # Server-owned mapping (asset_type, profile) -> permitted (role, id) pairs.
        self.catalog = {key: frozenset(value) for key, value in catalog.items()}

    @staticmethod
    def present(row):
        return {**row, 'registered': True, 'connectivity': 'unknown',
                'capture': 'unknown', 'defense': 'unknown'}

    def save(self, installation, technical_id, request):
        identifier(installation); identifier(technical_id)
        req = checked(request, ASSET_REQUEST)
        doc = req['document']
        allowed = self.catalog.get((doc['asset_type'], doc['profile']))
        if allowed is None or any(pair not in allowed for pair in doc['bindings'].items()):
            raise ConfigError('INCOMPATIBLE_ASSET')
        if not doc['display_name'].strip():
            raise ConfigError('INVALID_ASSET_NAME')
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            self.config._head(cur, installation)
            cur.execute('SELECT * FROM hs_config.asset WHERE installation_id=%s AND technical_id=%s',
                        (installation, technical_id))
            old = cur.fetchone()
            revision = old['revision'] if old else 0
            if revision != req['expected_revision']:
                raise Conflict('REVISION_CONFLICT', revision)
            if old and (old['document']['asset_type'], old['document']['profile']) != (doc['asset_type'], doc['profile']):
                raise ConfigError('ASSET_IDENTITY_IMMUTABLE')
            cur.execute('INSERT INTO hs_config.asset(installation_id,technical_id,revision,document) VALUES(%s,%s,%s,%s) '
                        'ON CONFLICT(installation_id,technical_id) DO UPDATE SET revision=excluded.revision, '
                        'document=excluded.document,updated_at=clock_timestamp() RETURNING *',
                        (installation, technical_id, revision+1, Jsonb(doc)))
            result = cur.fetchone()
            cur.execute('INSERT INTO hs_config.asset_audit(installation_id,technical_id,revision,actor,event) '
                        "VALUES(%s,%s,%s,'admin-account-1',%s)",
                        (installation, technical_id, revision+1, 'UPDATED' if old else 'CREATED'))
            return self.present(result)

    def list(self, installation, limit=100, offset=0):
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT * FROM hs_config.asset WHERE installation_id=%s ORDER BY technical_id LIMIT %s OFFSET %s',
                        (installation, limit, offset))
            return [self.present(row) for row in cur.fetchall()]

    def audit(self, installation, after=0, limit=100):
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT * FROM hs_config.asset_audit WHERE installation_id=%s AND id>%s ORDER BY id LIMIT %s',
                        (installation, after, limit))
            return cur.fetchall()


def install_assets_api(app, config, installation_id, catalog):
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import JSONResponse
    from .api import SafeRoute, body

    store = AssetStore(config, catalog)
    router = APIRouter(prefix='/api/v1/config/assets', route_class=SafeRoute,
                       dependencies=[Depends(app.state.require_admin_session)])

    @router.get('')
    def listing(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return store.list(installation_id, limit, offset)

    @router.get('/audit')
    def audit(after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
        return store.audit(installation_id, after, limit)

    @router.put('/{technical_id}', openapi_extra={'requestBody': {'required': True,
        'content': {'application/json': {'schema': ASSET_REQUEST}}}})
    async def save(technical_id: str, request: Request):
        value = await body(request, ASSET_REQUEST)
        if isinstance(value, JSONResponse):
            return value
        return store.save(installation_id, technical_id, value)

    app.include_router(router)
    return store
