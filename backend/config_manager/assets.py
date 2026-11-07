"""Permanent installation-owned asset registry; registration never attests liveness."""
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .schema import ConfigError, checked, obj, text, ID_PATTERN
from .setup import FIRMWARE
from .store import Conflict, identifier

DOCUMENT = obj({'name': text(100, r'.*\S.*'),
                'firmware_id': {'enum': [item['id'] for item in FIRMWARE]},
                'mqtt_topic': text(256), 'enabled': {'type': 'boolean'}})
SAVE = obj({'device_id': text(64, ID_PATTERN), 'expected_revision': {'type': 'integer', 'minimum': 0},
            'document': DOCUMENT})


class AssetStore:
    def __init__(self, config):
        self.config = config

    def list(self, installation):
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            self.config._head(cur, installation)
            cur.execute('SELECT device_id,revision,document,updated_at FROM hs_config.asset '
                        'WHERE installation_id=%s ORDER BY device_id', (installation,))
            return [dict(row, updated_at=row['updated_at'].isoformat(), connection_state='not_verified')
                    for row in cur.fetchall()]

    def save(self, installation, actor, request):
        req = checked(request, SAVE)
        identifier(req['device_id'])
        if req['document']['mqtt_topic'] not in self.config.capabilities.mqtt_topics:
            raise ConfigError('MQTT_TOPIC_NOT_ALLOWED')
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            self.config._head(cur, installation)
            cur.execute('SELECT revision FROM hs_config.asset WHERE installation_id=%s AND device_id=%s FOR UPDATE',
                        (installation, req['device_id']))
            row = cur.fetchone()
            version = row['revision'] if row else 0
            if req['expected_revision'] != version:
                raise Conflict('REVISION_CONFLICT', version)
            if not row:
                cur.execute('SELECT count(*) AS count FROM hs_config.asset WHERE installation_id=%s', (installation,))
                if cur.fetchone()['count'] >= 256:
                    raise ConfigError('ASSET_LIMIT_REACHED')
            revision = version + 1
            cur.execute('INSERT INTO hs_config.asset(installation_id,device_id,revision,document) VALUES(%s,%s,%s,%s) '
                        'ON CONFLICT(installation_id,device_id) DO UPDATE SET revision=excluded.revision,'
                        'document=excluded.document,updated_at=clock_timestamp()',
                        (installation, req['device_id'], revision, Jsonb(req['document'])))
            cur.execute('INSERT INTO hs_config.asset_audit(installation_id,device_id,revision,actor,document) '
                        'VALUES(%s,%s,%s,%s,%s)',
                        (installation, req['device_id'], revision, actor, Jsonb(req['document'])))
        return {'device_id': req['device_id'], 'revision': revision, 'document': req['document'],
                'connection_state': 'not_verified'}
