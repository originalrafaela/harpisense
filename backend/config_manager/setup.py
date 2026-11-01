"""Resumable preparation, never an assertion of operational readiness."""
from pathlib import Path
from hashlib import sha256

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from harpisense_contracts.canonical import fingerprint

from .schema import ConfigError, IDENTIFIER, PARAMETER_SCHEMA, checked, obj, text
from .store import Conflict, identifier

STEPS = ['installation', 'deployment', 'devices', 'mqtt', 'capture', 'backup', 'review']
# Firmware is a distinct catalog namespace; Risk/Policy action catalog is unchanged.
FIRMWARE = [{
    'id': 'esp32-wroom32-lighting', 'version': '1.0.0',
    'compatible_board': 'ESP32-WROOM-32', 'application': 'lighting',
    'sensors': ['LDR'], 'actuators': ['LED'],
    'telemetry_contract': None, 'telemetry_status': 'confirmation_required',
    'required_connectivity': ['MQTT'], 'implementation': 'conditional_reference',
    'validation': 'physical_validation_pending', 'available': False,
    'source': 'versão_v2/05_Firmware_ESP32', 'selection_flashes_board': False,
}]
PARTIAL_PARAMETERS = {**PARAMETER_SCHEMA, 'minProperties': 0}
SETUP_SCHEMA = obj({
    'step': {'enum': STEPS},
    'deployment_profile': {'enum': ['esp32-lighting']},
    'devices': {'type': 'array', 'maxItems': 64, 'items': obj({
        'device_id': IDENTIFIER, 'firmware_id': {'const': FIRMWARE[0]['id']},
        'firmware_version': {'const': '1.0.0'}})},
    'parameters': PARTIAL_PARAMETERS,
    'backup': {'enum': ['deferred', 'external_reference']},
}, ['step', 'parameters'])
SAVE_SCHEMA = obj({
    'expected_version': {'type': 'integer', 'minimum': 0},
    'idempotency_key': text(128, r'^[A-Za-z0-9_.-]{8,128}$'),
    'document': SETUP_SCHEMA,
})


def migrate_setup(connect):
    """Explicit additive migration, same database and lock as stage 1."""
    sql = Path(__file__).with_name('002_setup.sql').read_text(encoding='utf-8')
    checksum = sha256(sql.encode()).hexdigest()
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(7261103101)')
        cur.execute("SELECT to_regclass('hs_config.setup_schema')")
        if cur.fetchone()[0]:
            cur.execute('SELECT version,checksum FROM hs_config.setup_schema')
            if cur.fetchall() != [(2, checksum)]:
                raise ConfigError('MIGRATION_CHECKSUM_MISMATCH')
            return
        cur.execute(sql)
        cur.execute('INSERT INTO hs_config.setup_schema VALUES(2,%s)', (checksum,))


class SetupStore:
    def __init__(self, config):
        self.config = config

    def get(self, installation):
        identifier(installation)
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            self.config._head(cur, installation)
            cur.execute('SELECT version,document,updated_at FROM hs_config.setup_progress WHERE installation_id=%s',
                        (installation,))
            result = cur.fetchone() or {'version': 0, 'document': None}
            result['state'] = 'draft_saved' if result['version'] else 'not_started'
            result['operational'] = False
            result['pending'] = self.pending(result['document'])
            return result

    @staticmethod
    def pending(document):
        """Review hints, not proof of validation or completion of a step."""
        document = document or {}
        parameters = document.get('parameters', {})
        missing = []
        for section, present in (
            ('installation', bool(parameters.get('display_name'))),
            ('deployment', bool(document.get('deployment_profile'))),
            ('devices', bool(document.get('devices'))),
            ('mqtt', bool(parameters.get('mqtt_broker_host'))),
            ('capture', bool(parameters.get('network_cidrs') and parameters.get('sensor_bindings'))),
            ('backup', document.get('backup') == 'external_reference' and bool(parameters.get('external_credential_ref'))),
        ):
            if not present:
                missing.append({'section': section, 'code': 'PREPARATION_PENDING'})
        missing.extend([
            {'section': 'devices', 'code': 'FIRMWARE_VALIDATION_PENDING'},
            {'section': 'review', 'code': 'PROPOSAL_VALIDATION_REQUIRED'},
            {'section': 'review', 'code': 'NO_REAL_APPLICATORS'},
            {'section': 'review', 'code': 'OPERATIONAL_VERIFICATION_PENDING'},
        ])
        return missing

    def save(self, installation, actor, request):
        identifier(installation)
        identifier(actor)
        req = checked(request, SAVE_SCHEMA)
        digest = fingerprint(req)
        with self.config.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            self.config._head(cur, installation)
            cur.execute('SELECT fingerprint,result FROM hs_config.setup_request WHERE installation_id=%s AND actor=%s AND idempotency_key=%s',
                        (installation, actor, req['idempotency_key']))
            old = cur.fetchone()
            if old:
                if old['fingerprint'] != digest:
                    raise Conflict('IDEMPOTENCY_CONFLICT')
                return old['result']
            cur.execute('SELECT version FROM hs_config.setup_progress WHERE installation_id=%s', (installation,))
            old = cur.fetchone()
            version = old['version'] if old else 0
            if req['expected_version'] != version:
                raise Conflict('SETUP_VERSION_CONFLICT', version)
            result = {'version': version + 1, 'document': req['document'],
                      'state': 'draft_saved', 'operational': False,
                      'pending': self.pending(req['document'])}
            cur.execute('''INSERT INTO hs_config.setup_progress(installation_id,version,document)
                VALUES(%s,%s,%s) ON CONFLICT(installation_id) DO UPDATE SET
                version=EXCLUDED.version,document=EXCLUDED.document,updated_at=clock_timestamp()''',
                        (installation, version + 1, Jsonb(req['document'])))
            cur.execute('INSERT INTO hs_config.setup_request VALUES(%s,%s,%s,%s,%s)',
                        (installation, actor, req['idempotency_key'], digest, Jsonb(result)))
            cur.execute('''INSERT INTO hs_config.setup_audit(installation_id,actor,version,event)
                VALUES(%s,%s,%s,'SETUP_SAVED')''', (installation, actor, version + 1))
            return result
