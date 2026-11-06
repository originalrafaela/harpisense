"""Actual installed-VM acceptance. Run with installed venv as root over SSH.

Credentials stay in a root-only file in the disposable guest; stdout is evidence only.
No migrations, SQL data edits, application source changes or service manipulation.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

APP = Path('/opt/harpisense')
for name in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, str(APP/name))
import psycopg
import pyotp
from native_server.runtime import mqtt_client

PRIVATE = Path('/home/trial/harpisense-trial/acceptance-private.json')
STATE = json.loads(Path('/var/lib/harpisense/state.json').read_text())
PREFIX = '/p11-api/api/v1'
evidence = {'phase': sys.argv[1], 'checks': [], 'transport': 'real installed HTTP API',
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def check(value, label):
    if not value:
        raise AssertionError(label)
    evidence['checks'].append(label)


def request(method, path, body=None, token=None, expected=200):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request('http://127.0.0.1:18080' + PREFIX + path,
        data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    blob = response.read()
    if response.code != expected:
        evidence['unexpected_http_status'] = response.code
        try:
            code = json.loads(blob).get('error', {}).get('code')
            if isinstance(code, str) and code.replace('_', '').isalnum():
                evidence['http_error_code'] = code
        except (ValueError, AttributeError):
            pass
    check(response.code == expected, 'http_' + method + '_' + path.replace('/', '_') + '_' + str(expected))
    return json.loads(blob) if blob else None


def account_digest():
    with psycopg.connect(STATE['dsn']) as conn:
        row = conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone()
    return hashlib.sha256(repr(row).encode()).hexdigest()


def login(private):
    first = request('POST', '/admin-auth/login',
        {'username': private['username'], 'password': private['password']})
    check('access_token' not in first and first['next_step'] == 'login', 'password_alone_does_not_issue_session')
    # Enrollment/login steps cannot be reused, even across machine reboot.
    while int(time.time() // 30) <= private['last_totp_step']:
        time.sleep(.25)
    result = request('POST', '/admin-auth/mfa/verify',
        {'challenge_token': first['challenge_token'], 'code': pyotp.TOTP(private['totp_key']).now()})
    private['last_totp_step'] = int(time.time() // 30)
    check(bool(result['access_token']), 'real_totp_login_succeeded')
    return result['access_token']


try:
    for service in ('harpisense-postgres', 'harpisense-broker', 'harpisense-api', 'harpisense-mqtt'):
        for action in ('is-active', 'is-enabled'):
            result = subprocess.run(['systemctl', action, service], capture_output=True, text=True)
            check(result.returncode == 0, service + '_' + action)
    request('GET', '/config/setup', expected=401)
    if sys.argv[1] == 'before-reboot':
        check(not PRIVATE.exists(), 'fresh_acceptance_account')
        private = {'username': 'ubuntu-trial-owner', 'password': secrets.token_urlsafe(32)}
        grant = Path('/var/lib/harpisense/bootstrap.secret').read_text().strip()
        first = request('POST', '/admin-auth/bootstrap', {'bootstrap_secret': grant,
            'username': private['username'], 'password': private['password']})
        enrollment = request('POST', '/admin-auth/mfa/enrollment/begin',
            {'challenge_token': first['challenge_token']})
        private['totp_key'] = enrollment['manual_key']
        valid = pyotp.TOTP(private['totp_key']).now()
        request('POST', '/admin-auth/mfa/enrollment/confirm',
            {'challenge_token': first['challenge_token'], 'code': '000000' if valid != '000000' else '111111'}, expected=401)
        session = request('POST', '/admin-auth/mfa/enrollment/confirm',
            {'challenge_token': first['challenge_token'], 'code': pyotp.TOTP(private['totp_key']).now()})
        check(len(session['recovery_codes']) == 10, 'mfa_enrollment_and_ten_recovery_codes')
        private['recovery_codes'] = session['recovery_codes']
        private['last_totp_step'] = int(time.time() // 30)
        token = session['access_token']
        setup = request('GET', '/config/setup', token=token)
        document = {'step': 'deployment', 'parameters': {'display_name': 'Ubuntu candidate2 clean reboot trial',
                     'timezone': 'America/Sao_Paulo'}}
        saved = request('PUT', '/config/setup', {'expected_version': setup['version'],
            'idempotency_key': 'ubuntu-trial-' + uuid.uuid4().hex, 'document': document}, token=token)
        check(saved['document'] == document, 'configuration_saved_via_api')
        private.update(setup=saved, account_digest=account_digest(), boot_id=evidence['boot_id'])
        PRIVATE.write_text(json.dumps(private))
        PRIVATE.chmod(0o600)
        token = login(private)
    else:
        private = json.loads(PRIVATE.read_text())
        check(evidence['boot_id'] != private['boot_id'], 'real_machine_reboot_confirmed')
        check(account_digest() == private['account_digest'], 'account_preserved_after_machine_reboot')
        token = login(private)
        saved = request('GET', '/config/setup', token=token)
        check(saved['document'] == private['setup']['document'] and saved['version'] == private['setup']['version'],
              'configuration_preserved_after_machine_reboot')
        status = request('GET', '/config/mqtt/status', token=token)
        check(status['consumer']['state'] == 'connected', 'automatic_mqtt_consumer_connected')
        device = json.loads(Path('/var/lib/harpisense/device-poste2.json').read_text())
        publisher_state = dict(STATE, installation_id='trial-publisher-' + uuid.uuid4().hex,
            mqtt=dict(STATE['mqtt'], username=device['username'], password=device['password']))
        publisher = mqtt_client(publisher_state)
        publisher.connect(STATE['mqtt']['host'], STATE['mqtt']['port'], 30)
        publisher.loop_start()
        message_id = 'ubuntu-candidate2-' + uuid.uuid4().hex
        try:
            raw = json.dumps({'device_id': 'poste2', 'message_id': message_id,
                'observed_at': datetime.now(timezone.utc).isoformat(), 'purpose': 'installer_acceptance_no_sensor_claim'})
            publication = publisher.publish('harpisense/poste2/telemetry', raw, qos=1, retain=False)
            publication.wait_for_publish(10)
            check(publication.is_published(), 'mqtt_tls_authenticated_qos1_published')
        finally:
            publisher.disconnect()
            publisher.loop_stop()
        end = time.monotonic() + 20
        found = False
        while time.monotonic() < end:
            rows = request('GET', '/p11/telemetry', token=token)
            found = any(row['data'].get('message_id') == message_id for row in rows)
            if found:
                break
            time.sleep(.5)
        check(found, 'identifiable_mqtt_message_returned_by_authenticated_api')
        with psycopg.connect(STATE['dsn']) as conn:
            count = conn.execute("SELECT count(*) FROM projections WHERE kind='telemetry' AND data->>'message_id'=%s",
                                 (message_id,)).fetchone()[0]
        check(count == 1, 'one_identifiable_postgresql_projection')
        observed = request('GET', '/config/mqtt/status', token=token)
        check(any(item.get('message_id') == message_id for item in observed['devices']), 'mqtt_observation_matches_message')
        evidence['message_id'] = message_id
    PRIVATE.write_text(json.dumps(private))
    PRIVATE.chmod(0o600)
    evidence['result'] = 'passed'
except Exception as error:
    evidence['result'] = 'failed'
    evidence['failure_type'] = type(error).__name__
    if isinstance(error, AssertionError):
        evidence['failure'] = str(error)
finally:
    print(json.dumps(evidence, indent=2), flush=True)
sys.exit(0 if evidence['result'] == 'passed' else 1)
