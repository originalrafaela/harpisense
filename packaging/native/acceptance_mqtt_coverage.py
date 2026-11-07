"""Isolated real TLS broker/consumer/PostgreSQL; no service or device mutation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
for folder in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, str(ROOT/folder))
import psycopg
from native_server.observation import mqtt_observation, message_received
from native_server.runtime import mqtt_client, probe_broker
from provision import create_state, initialize_database, prepare_database, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', type=Path, required=True)
    parser.add_argument('--mosquitto', type=Path, required=True)
    args = parser.parse_args()
    suffix = '.exe' if os.name == 'nt' else ''
    def port():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]
    pg_port, mqtt_port = port(), port()
    private = ROOT/'.native-test'/('mqtt-coverage-' + uuid.uuid4().hex)
    private.parent.mkdir(exist_ok=True)
    state = create_state(private)
    state['dsn'] = state['dsn'].replace(':15432/', f':{pg_port}/')
    state['mqtt']['port'] = mqtt_port
    state_file = private/'state.json'
    state_file.write_text(json.dumps(state), encoding='utf-8')
    config = private/'mosquitto.conf'
    config.write_text(config.read_text().replace('listener 8883 ', f'listener {mqtt_port} '), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('backend', 'backend/domain', 'genai')))
    processes, logs, checks = [], [], []
    started = False
    evidence = dict(platform=sys.platform, docker=False, clean_os=False, reboot=False,
                    services_autostart='not_tested', admin_login='not_tested',
                    new_dependencies=[], checks=checks)
    def spawn(command, name):
        log = (private/(name+'.log')).open('ab')
        logs.append(log)
        proc = subprocess.Popen(list(map(str, command)), env=env, stdout=log, stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        processes.append(proc)
        return proc
    def wait(predicate, timeout=30):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            try:
                if predicate(): return
            except (OSError, psycopg.OperationalError): pass
            time.sleep(.2)
        raise AssertionError('WAIT_TIMEOUT')
    def check(condition, label):
        if not condition: raise AssertionError(label)
        checks.append(label)
    try:
        run([args.postgres_bin/('initdb'+suffix), '-D', private/'postgres', '-U', 'native_installer',
             '--encoding=UTF8', '--auth=scram-sha-256', '--pwfile', private/'pg-init.secret'])
        with (private/'postgres/postgresql.conf').open('a') as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={pg_port}\n")
        run([args.postgres_bin/('pg_ctl'+suffix), '-D', private/'postgres', '-l', private/'postgres.log', '-w', 'start'])
        started = True
        initialize_database(state, private)
        prepare_database(state_file)
        broker = spawn([args.mosquitto, '-c', config], 'broker')
        wait(lambda: probe_broker(state) == dict(connected=True, subscribed=True))
        spawn([sys.executable, ROOT/'packaging/native/entry.py', 'consumer', '--state', state_file], 'consumer')
        wait(lambda: mqtt_observation(state)['consumer']['state'] == 'connected')
        check(mqtt_observation(state)['device_observation'] == 'not_verified', 'suback_without_message_unknown')
        device = json.loads((private/'device-poste2.json').read_text())
        raw = json.dumps(dict(device_id='poste2', message_id='coverage-'+uuid.uuid4().hex,
                              observed_at=datetime.now(timezone.utc).isoformat(),
                              status=dict(origin_type='SIMULATED'), purpose='isolated_acceptance')).encode()
        projection = 'poste2-'+hashlib.sha256(b'harpisense/poste2/telemetry\0'+raw).hexdigest()
        def publish():
            publisher = mqtt_client(dict(state, installation_id='pub-'+uuid.uuid4().hex,
                mqtt=dict(state['mqtt'], username=device['username'], password=device['password'])))
            try:
                publisher.connect(state['mqtt']['host'], mqtt_port, 30)
                publisher.loop_start()
                publisher.publish('harpisense/poste2/telemetry', raw, qos=1).wait_for_publish(10)
            finally:
                publisher.disconnect()
                publisher.loop_stop()
        publish()
        wait(lambda: mqtt_observation(state)['device_observation'] == 'observed')
        before = mqtt_observation(state)['devices'][0]
        check(before['projection_id'] == projection, 'mqtt_to_exact_persisted_projection')
        with psycopg.connect(state['dsn']) as conn:
            data, created = conn.execute("SELECT data,created_at FROM projections WHERE kind='telemetry' AND id=%s AND revision=1", (projection,)).fetchone()
        check(data['status']['origin_type'] == 'SIMULATED', 'simulated_origin_preserved_in_postgresql')
        publish()
        time.sleep(.5)
        check(mqtt_observation(state)['devices'][0]['observed_at'] == before['observed_at'], 'duplicate_does_not_renew_sample_time')
        broker.terminate()
        broker.wait(15)
        wait(lambda: mqtt_observation(state)['consumer']['state'] == 'not_verified')
        lost = mqtt_observation(state)
        check(lost['devices'][0]['projection_id'] == projection and lost['coverage']['state'] == 'partial', 'disconnect_preserves_evidence')
        spawn([args.mosquitto, '-c', config], 'broker-restarted')
        wait(lambda: mqtt_observation(state)['consumer']['state'] == 'connected', timeout=75)
        publish()
        check(mqtt_observation(state)['devices'][0]['projection_id'] == projection, 'automatic_tls_reconnect_resubscribe')
        with psycopg.connect(state['dsn']) as conn:
            check(conn.execute("SELECT count(*) FROM projections WHERE kind='telemetry'").fetchone()[0] == 1, 'qos_retries_one_revision')
            conn.execute("UPDATE projections SET created_at=clock_timestamp()-interval '121 seconds' WHERE id=%s", (projection,))
            conn.execute("UPDATE hs_native_mqtt_observation SET last_message_at=NULL")
        # Deliberately age only disposable fixture data; never product evidence.
        message_received(state, json.loads(raw)['message_id'], projection)
        check(mqtt_observation(state)['reason_code'] == 'TELEMETRY_STALE', 'old_revision_retry_cannot_claim_freshness')
        evidence['result'] = 'passed'
    except Exception as error:
        evidence['result'] = 'failed'
        evidence['failure'] = type(error).__name__
        raise
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
                proc.wait(15)
        if started:
            run([args.postgres_bin/('pg_ctl'+suffix), '-D', private/'postgres', '-m', 'fast', '-w', 'stop'])
        for log in logs: log.close()
        evidence['source_sha256'] = hashlib.sha256((ROOT/'backend/native_server/observation.py').read_bytes()).hexdigest()
        dest = ROOT/'docs/evidence/mqtt-coverage'
        dest.mkdir(parents=True, exist_ok=True)
        (dest/(sys.platform+'.json')).write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(evidence))


if __name__ == '__main__': main()
