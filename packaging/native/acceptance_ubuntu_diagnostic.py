"""Post-reboot checks that remain possible when administrative login is broken."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

for item in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, '/opt/harpisense/' + item)
import psycopg
from native_server.runtime import mqtt_client

result = {'checks': [], 'authenticated_api': 'blocked_by_bootstrap_AUTH_UNAVAILABLE',
          'configuration_persistence': 'not_tested_bootstrap_failed',
          'login_mfa': 'failed_bootstrap_503', 'ui_login': 'not_tested'}


def check(value, name):
    if not value:
        raise AssertionError(name)
    result['checks'].append(name)


try:
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    result['boot_id'] = boot
    check(boot != sys.argv[1], 'real_machine_reboot_confirmed')
    for service in ('harpisense-postgres', 'harpisense-broker', 'harpisense-api', 'harpisense-mqtt'):
        for action in ('is-active', 'is-enabled'):
            response = subprocess.run(['systemctl', action, service], capture_output=True)
            check(response.returncode == 0, service + '_' + action + '_after_reboot')
    state = json.loads(Path('/var/lib/harpisense/state.json').read_text())
    with psycopg.connect(state['dsn']) as conn:
        result['postgres_version'] = conn.execute('SHOW server_version').fetchone()[0]
        result['account_count'] = conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0]
    try:
        urllib.request.urlopen('http://127.0.0.1:18080/p11-api/api/v1/p11/telemetry', timeout=10)
        raise AssertionError('anonymous_telemetry_must_be_denied')
    except urllib.error.HTTPError as error:
        check(error.code == 401, 'anonymous_telemetry_stays_denied_after_reboot')
    check(urllib.request.urlopen('http://127.0.0.1:18080', timeout=10).status == 200,
          'frontend_served_after_reboot')
    device = json.loads(Path('/var/lib/harpisense/device-poste2.json').read_text())
    publisher = mqtt_client(dict(state, installation_id='trial-publisher-' + uuid.uuid4().hex,
        mqtt=dict(state['mqtt'], username=device['username'], password=device['password'])))
    publisher.connect(state['mqtt']['host'], state['mqtt']['port'], 30)
    publisher.loop_start()
    message_id = 'ubuntu-candidate2-' + uuid.uuid4().hex
    try:
        message = json.dumps({'device_id': 'poste2', 'message_id': message_id,
            'observed_at': datetime.now(timezone.utc).isoformat(), 'purpose': 'installer_acceptance_no_sensor_claim'})
        publication = publisher.publish('harpisense/poste2/telemetry', message, qos=1, retain=False)
        publication.wait_for_publish(10)
        check(publication.is_published(), 'mqtt_tls_authenticated_qos1_published_after_reboot')
    finally:
        publisher.disconnect()
        publisher.loop_stop()
    end = time.monotonic() + 20
    count = 0
    while time.monotonic() < end:
        with psycopg.connect(state['dsn']) as conn:
            count = conn.execute("SELECT count(*) FROM projections WHERE kind='telemetry' AND data->>'message_id'=%s",
                                 (message_id,)).fetchone()[0]
        if count:
            break
        time.sleep(.5)
    check(count == 1, 'mqtt_consumer_persisted_one_identifiable_postgresql_projection_after_reboot')
    result['message_id'] = message_id
    result['result'] = 'partial_pass_with_authentication_blocker'
except Exception as error:
    result['result'] = 'failed'
    result['failure_type'] = type(error).__name__
    if isinstance(error, AssertionError):
        result['failure'] = str(error)
finally:
    print(json.dumps(result, indent=2), flush=True)
sys.exit(0 if result['result'] == 'partial_pass_with_authentication_blocker' else 1)
