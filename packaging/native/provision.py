"""Explicit product provisioning; never imported on API/service startup."""
import base64
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import uuid


def run(args, **kwargs):
    # Child output can contain DSNs/passwords: capture, report stable code only.
    # Windows PostgreSQL children can inherit pipe handles after pg_ctl exits.
    # DEVNULL avoids waiting forever for pipe EOF from a running database server.
    options = {'check': True, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL,
               'timeout': 180}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.run([str(x) for x in args], **(options | kwargs))
    except subprocess.CalledProcessError:
        raise RuntimeError('INSTALLER_SUBPROCESS_FAILED:' + Path(str(args[0])).name) from None


def private_directory(path):
    path.mkdir(parents=True, mode=0o700, exist_ok=False)
    if os.name == 'nt':
        run(['icacls', path, '/inheritance:r', '/grant:r',
             '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F', '*S-1-5-19:(OI)(CI)M'])


def write_private(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def preflight(data, app, mode):
    """Read-only and complete before making any filesystem/service mutation."""
    conflicts = []
    for path in (Path(data), Path(app)):
        if path.exists():
            conflicts.append('EXISTING_INSTALLATION:' + str(path))
    ports = [18080, 15432] + ([8883, 1883] if mode == 'local_managed' else [])
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(('0.0.0.0', port))
            except OSError:
                conflicts.append('PORT_IN_USE:' + str(port))
    if os.name == 'nt':
        for service in ('HarpiSenseApi', 'HarpiSenseMqtt', 'HarpiSenseBroker',
                        'HarpiSensePostgres', 'postgresql-x64-18') + (('mosquitto',) if mode == 'local_managed' else ()):
            result = subprocess.run(['sc.exe', 'query', service], capture_output=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                conflicts.append('SERVICE_EXISTS:' + service)
        # Catch every PostgreSQL service version, not only the known local one.
        result = subprocess.run(['sc.exe', 'query', 'state=', 'all'], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if b'postgres' in result.stdout.lower():
            conflicts.append('POSTGRES_SERVICE_EXISTS')
    else:
        for prefix in ('/etc/systemd/system', '/usr/lib/systemd/system', '/lib/systemd/system'):
            for service in ('postgresql.service',) + (('mosquitto.service',) if mode == 'local_managed' else ()):
                if (Path(prefix)/service).exists():
                    conflicts.append('SERVICE_EXISTS:' + service)
        if Path('/etc/postgresql').exists() and list(Path('/etc/postgresql').glob('*/*/postgresql.conf')):
            conflicts.append('EXISTING_POSTGRES_CLUSTER')
        if mode == 'local_managed' and Path('/etc/mosquitto/mosquitto.conf').exists():
            conflicts.append('EXISTING_BROKER_CONFIG')
        for service in ('harpisense-api', 'harpisense-mqtt', 'harpisense-broker', 'harpisense-postgres'):
            if Path('/etc/systemd/system/' + service + '.service').exists():
                conflicts.append('SERVICE_EXISTS:' + service)
    if conflicts:
        raise RuntimeError('\n'.join(conflicts))


def broker_files(data, consumer_password, device_password):
    """TLS and ACLs for the privately owned loopback broker only."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    now = datetime.datetime.now(datetime.timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'HarpiSense local broker')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
                                                       x509.DNSName('localhost')]), critical=False)
            .sign(key, hashes.SHA256()))
    write_private(data/'mqtt.key', key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
    write_private(data/'mqtt-ca.crt', cert.public_bytes(serialization.Encoding.PEM).decode())
    lines = []
    for username, password in [('harpisense-consumer', consumer_password), ('poste2', device_password)]:
        salt = secrets.token_bytes(12)
        iterations = 210000
        digest = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, iterations, dklen=64)
        lines.append(f'{username}:$7${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}')
    write_private(data/'mqtt.passwords', '\n'.join(lines) + '\n')
    write_private(data/'mqtt.acl', 'user harpisense-consumer\ntopic read harpisense/poste2/telemetry\n\nuser poste2\ntopic write harpisense/poste2/telemetry\n')
    def p(name):
        return (data/name).as_posix()
    write_private(data/'mosquitto.conf', '\n'.join([
        'listener 8883 127.0.0.1', 'allow_anonymous false',
        'password_file ' + p('mqtt.passwords'), 'acl_file ' + p('mqtt.acl'),
        'certfile ' + p('mqtt-ca.crt'), 'keyfile ' + p('mqtt.key'),
        'tls_version tlsv1.2', 'persistence false', 'log_type error', 'log_type warning', '']))


def create_state(data, *, mode='local_managed', external=None):
    from cryptography.fernet import Fernet
    data = Path(data).resolve()
    private_directory(data)
    write_private(data/'admin-mfa.key', Fernet.generate_key().decode())
    password, consumer, device = [secrets.token_urlsafe(32) for _ in range(3)]
    if mode == 'local_managed':
        broker_files(data, consumer, device)
        mqtt = {'mode': 'local_managed', 'host': '127.0.0.1', 'port': 8883,
                'username': 'harpisense-consumer', 'password': consumer,
                'ca_file': str(data/'mqtt-ca.crt'), 'topics': ['harpisense/poste2/telemetry']}
        write_private(data/'device-poste2.json', json.dumps({
            'username': 'poste2', 'password': device, 'topic': 'harpisense/poste2/telemetry',
            'host': '127.0.0.1', 'port': 8883, 'ca_file': str(data/'mqtt-ca.crt')}))
    else:
        if not external or set(external) != {'host', 'port', 'username', 'password', 'ca_file'}:
            raise ValueError('EXTERNAL_BROKER_CONFIGURATION_REQUIRED')
        if not isinstance(external['port'], int) or not 1 <= external['port'] <= 65535:
            raise ValueError('EXTERNAL_BROKER_PORT_INVALID')
        shutil.copyfile(external['ca_file'], data/'external-ca.crt')
        os.chmod(data/'external-ca.crt', 0o600)
        mqtt = dict(external, mode='external', ca_file=str(data/'external-ca.crt'),
                    topics=['harpisense/poste2/telemetry'])
    state = {'schema': 1, 'installation_id': str(uuid.uuid4()),
        'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'dsn': f'postgresql://harpisense:{password}@127.0.0.1:15432/harpisense',
        'key_file': str(data/'admin-mfa.key'), 'panel_url': 'http://127.0.0.1:18080',
        'technical_user': 'native-projection-service', 'technical_password': secrets.token_urlsafe(32),
        'projection_token': secrets.token_urlsafe(32), 'mqtt': mqtt}
    write_private(data/'state.json', json.dumps(state))
    write_private(data/'pg-init.secret', secrets.token_urlsafe(32))
    return state


def initialize_database(state, data):
    """Application owns only its database; it is not a PostgreSQL superuser."""
    import psycopg
    from psycopg import sql
    from urllib.parse import urlparse
    dsn = urlparse(state['dsn'])
    with psycopg.connect(host='127.0.0.1', port=dsn.port, dbname='postgres',
                         user='native_installer', password=(Path(data)/'pg-init.secret').read_text(),
                         autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE ROLE harpisense LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Literal(dsn.password)))
        conn.execute('CREATE DATABASE harpisense OWNER harpisense')


def prepare_database(state_file):
    import psycopg
    from admin_auth.mfa import MFAAdminAuth
    from config_manager.setup import migrate_setup
    from config_manager.store import ConfigStore, migrate
    from native_server.runtime import capabilities, load_state
    state = load_state(state_file)
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    with psycopg.connect(state['dsn'], autocommit=True) as conn:
        if conn.info.dbname != 'harpisense':
            raise RuntimeError('PRODUCT_DATABASE_NAME_REQUIRED')
        conn.execute((root/'backend/delivery/001_local.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/delivery/002_operational_authority.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/delivery/003_incident_assessment.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/delivery/004_activity_decision_snapshot.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/delivery/006_action_review.sql').read_text(encoding='utf-8'))
        if not conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
            conn.execute((root/'backend/admin_auth/001_admin_auth.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/admin_auth/002_admin_mfa.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/admin_auth/003_password_reset.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/admin_auth/004_first_access.sql').read_text(encoding='utf-8'))
        conn.execute((root/'backend/native_server/001_mqtt_observer.sql').read_text(encoding='utf-8'))
        present = conn.execute('SELECT 1 FROM hs_admin_account').fetchone()
    connect = lambda: psycopg.connect(state['dsn'])
    migrate(connect)
    migrate_setup(connect)
    with connect() as conn:
        conn.execute((root/'backend/config_manager/003_assets.sql').read_text(encoding='utf-8'))
    ConfigStore(connect, capabilities(state)).provision_registry(state['installation_id'])
    # No human identity reset, no grant issuance on API startup or existing account.
    grantfile = Path(state_file).parent/'bootstrap.secret'
    if not present and not grantfile.exists():
        grant = MFAAdminAuth(state['dsn'], protection_key=Path(state['key_file']).read_bytes()).issue_local_grant()
        write_private(grantfile, grant)
