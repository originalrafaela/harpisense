"""Real native processes on disposable ports, NOT a clean-OS installation test.

No service registration, existing PostgreSQL connection, broker mutation or VM.
Outputs sanitized evidence; private state, TOTP and grant never leave .native-test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
for name in ('backend', 'backend/domain', 'genai', 'packaging/native'):
    sys.path.insert(0, str(ROOT/name))

import httpx
import psycopg
import pyotp
from playwright.sync_api import sync_playwright, expect
from provision import create_state, initialize_database, prepare_database, preflight, run
from native_server.runtime import probe_broker
from acceptance_first_use import prepare_first_use, authorize_browser


def wait_for(predicate, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if predicate():
                return
        except (OSError, httpx.TransportError, psycopg.OperationalError):
            pass
        time.sleep(.2)
    raise AssertionError('ACCEPTANCE_WAIT_TIMEOUT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', required=True, type=Path)
    parser.add_argument('--mosquitto', required=True, type=Path)
    parser.add_argument('--runtime', type=Path, help='Test frozen product runtime instead of Python source')
    args = parser.parse_args()
    if args.runtime:
        parser.error('Frozen clean-machine acceptance requires the installed IPC launcher; this script is an explicit source fixture')
    evidence = {'environment': 'Windows native disposable processes; existing workstation, not clean OS',
                'docker': False, 'service_registration': False, 'machine_reboot': False,
                'runtime': 'frozen_executable' if args.runtime else 'python_source', 'checks': []}
    def check(value, label):
        if not value:
            raise AssertionError(label)
        evidence['checks'].append(label)
    for port in (25432, 28080, 28883):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    private = ROOT/'.native-test'/str(uuid.uuid4())
    private.parent.mkdir(exist_ok=True)
    state = create_state(private)
    prepare_first_use(state, private)
    state['dsn'] = state['dsn'].replace(':15432/', ':25432/')
    state['panel_url'] = 'http://127.0.0.1:28080'
    state['mqtt']['port'] = 28883
    (private/'state.json').write_text(json.dumps(state), encoding='utf-8')
    config = private/'mosquitto.conf'
    config.write_text(config.read_text().replace('listener 8883 ', 'listener 28883 '), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('backend', 'backend/domain', 'genai')))
    processes, handles = [], []
    pg_started = False
    evidence_dir = ROOT/'docs/evidence/native-installers'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    api_command = [str(args.runtime)] if args.runtime else [sys.executable, str(ROOT/'packaging/native/entry.py')]
    def process(command, name):
        handle = (private/(name + '.log')).open('ab')
        handles.append(handle)
        proc = subprocess.Popen([str(x) for x in command], env=env, stdout=handle, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(proc)
        return proc
    try:
        run([args.postgres_bin/'initdb.exe', '-D', private/'postgres', '-U', 'native_installer',
             '--encoding=UTF8', '--auth=scram-sha-256', '--pwfile', private/'pg-init.secret'])
        with (private/'postgres/postgresql.conf').open('a') as stream:
            stream.write("\nlisten_addresses='127.0.0.1'\nport=25432\n")
        run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-l', private/'postgres.log', '-w', 'start'])
        pg_started = True
        initialize_database(state, private)
        if args.runtime:
            run(api_command + ['prepare', '--state', private/'state.json'])
        else:
            prepare_database(private/'state.json')
        check(not (private/'bootstrap.secret').exists(), 'fresh_migrations_without_manual_grant')
        process([args.mosquitto, '-c', config], 'broker')
        wait_for(lambda: probe_broker(state) == {'connected': True, 'subscribed': True})
        check(True, 'real_broker_tls_authentication_and_suback')
        original_broker_config = hashlib.sha256(config.read_bytes()).hexdigest()
        probe_broker(dict(state, mqtt=dict(state['mqtt'], mode='external')))
        check(hashlib.sha256(config.read_bytes()).hexdigest() == original_broker_config,
              'external_mode_validates_tls_and_suback_without_administering_broker')
        native_api_command = [sys.executable, str(ROOT/'packaging/native/acceptance_first_use.py')]
        api = process(native_api_command + ['api', '--state', str(private/'state.json')], 'api')
        consumer = process(api_command + ['consumer', '--state', str(private/'state.json')], 'consumer')
        base = state['panel_url']
        http = httpx.Client(base_url=base, timeout=10, trust_env=False, headers={'Origin': base})
        wait_for(lambda: http.get('/').status_code == 200)
        prefix = '/p11-api/api/v1'
        check(http.get(prefix + '/p11/telemetry').status_code == 401, 'anonymous_p11_denied')
        check(http.get(prefix + '/config/mqtt/status').status_code == 401, 'anonymous_mqtt_status_denied')
        check(http.get('/', headers={'Host': 'attacker.invalid'}).status_code == 403, 'dns_rebinding_denied')
        check(http.post(prefix + '/admin-auth/bootstrap', headers={'Origin': 'https://attacker.invalid'}, json={}).status_code == 403,
              'cross_origin_bootstrap_denied')
        username, password = 'native-owner', secrets.token_urlsafe(32)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            authorize_browser(page, state)
            page.goto(base)
            page.get_by_role('button', name='Autenticação inicial', exact=True).click()
            page.get_by_label('Usuário', exact=True).fill(username)
            page.get_by_label('Senha da conta administrativa', exact=True).fill(password)
            page.get_by_role('button', name='Criar conta e configurar MFA', exact=True).click()
            page.get_by_role('button', name='Mostrar QR e chave manual', exact=True).click()
            key = page.get_by_label('Chave manual', exact=True).input_value()
            invalid = '000000' if pyotp.TOTP(key).now() != '000000' else '111111'
            page.get_by_label('Código de 6 dígitos', exact=True).fill(invalid)
            page.get_by_role('button', name='Confirmar MFA', exact=True).click()
            expect(page.get_by_role('alert').first).to_be_visible()
            with psycopg.connect(state['dsn']) as conn:
                check(not conn.execute('SELECT 1 FROM hs_admin_mfa WHERE enabled_at IS NOT NULL').fetchone(), 'invalid_totp_does_not_activate')
            page.get_by_label('Código de 6 dígitos', exact=True).fill(pyotp.TOTP(key).now())
            page.get_by_role('button', name='Confirmar MFA', exact=True).click()
            expect(page.get_by_role('heading', name='Guarde seus 3 códigos de recuperação')).to_be_visible()
            check(page.locator('.recovery-codes li').count() == 3, 'three_password_recovery_codes_browser')
            page.get_by_role('button', name='Já guardei os códigos', exact=True).click()
            expect(page.get_by_role('button', name='Sair', exact=True)).to_be_visible()
            check(True, 'browser_bootstrap_totp_confirmation_dashboard')
            page.get_by_role('button', name='Iniciar assistente', exact=True).click()
            page.get_by_label('Nome da instalação', exact=True).fill('Central nativa — ensaio isolado')
            with page.expect_response(lambda r: r.url.endswith('/config/setup') and r.request.method == 'PUT') as saved:
                page.get_by_role('button', name='Salvar e continuar', exact=True).click()
            check(saved.value.status == 200, 'setup_save_http_' + str(saved.value.status))
            expect(page.get_by_label('Perfil de implantação', exact=False)).to_be_visible()
            with psycopg.connect(state['dsn']) as conn:
                account_before = conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone()
            check(True, 'browser_saved_setup_in_real_postgresql')
            # Full restart of own API/consumer/DB, not a machine reboot.
            for proc in (api, consumer):
                proc.terminate()
                proc.wait(15)
            run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-w', 'stop', '-m', 'fast'])
            pg_started = False
            run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-l', private/'postgres.log', '-w', 'start'])
            pg_started = True
            if args.runtime:
                run(api_command + ['prepare', '--state', private/'state.json'])
            else:
                prepare_database(private/'state.json')
            api = process(native_api_command + ['api', '--state', str(private/'state.json')], 'api-restarted')
            consumer = process(api_command + ['consumer', '--state', str(private/'state.json')], 'consumer-restarted')
            wait_for(lambda: http.get('/').status_code == 200)
            with psycopg.connect(state['dsn']) as conn:
                check(conn.execute('SELECT username,password_hash,credential_revision FROM hs_admin_account').fetchone() == account_before,
                      'repeated_preparation_preserves_account')
            browser.close()
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(base)
            page.get_by_label('Usuário', exact=True).fill(username)
            page.get_by_label('Senha', exact=True).fill(password)
            page.get_by_role('button', name='Entrar na central', exact=True).click()
            # PostgreSQL strictly prevents reuse of the enrollment time-step.
            old = pyotp.TOTP(key).now()
            wait_for(lambda: pyotp.TOTP(key).now() != old, timeout=35)
            with page.expect_response(lambda r: r.url.endswith('/mfa/verify') and r.status == 200) as verified:
                page.get_by_label('Código do aplicativo autenticador', exact=True).fill(pyotp.TOTP(key).now())
                page.get_by_role('button', name='Verificar código', exact=True).click()
            token = verified.value.json()['access_token']
            headers = {'Authorization': 'Bearer ' + token}
            expect(page.get_by_role('button', name='Sair', exact=True)).to_be_visible()
            check(True, 'new_browser_login_requires_real_totp_after_process_restart')
            setup = http.get(prefix + '/config/setup', headers=headers).json()
            check(setup['document']['parameters']['display_name'] == 'Central nativa — ensaio isolado', 'setup_preserved_after_process_restart')
            page.get_by_role('button', name='Retomar assistente', exact=True).click()
            expect(page.get_by_label('Perfil de implantação', exact=False)).to_be_visible()
            page.get_by_role('button', name='Abrir MQTT e dispositivos', exact=True).click()
            def observed():
                return http.get(prefix + '/config/mqtt/status', headers=headers).json()
            wait_for(lambda: observed()['consumer']['state'] == 'connected')
            before = observed()
            check(before['broker']['state'] == 'available' and before['devices'] == [] and before['reason_code'] == 'AWAITING_FIRST_MESSAGE',
                  'broker_active_consumer_subscribed_no_device_publication')
            evidence['mqtt_before'] = before
            page.get_by_role('button', name='Atualizar estados MQTT', exact=True).click()
            expect(page.get_by_text('Broker ativo, aguardando primeira mensagem', exact=True)).to_be_visible()
            page.screenshot(path=str(evidence_dir/'windows-broker-no-message.png'), full_page=True)
            device = json.loads((private/'device-poste2.json').read_text())
            from native_server.runtime import mqtt_client
            publisher = mqtt_client(dict(state, installation_id='publisher-' + uuid.uuid4().hex,
                                         mqtt=dict(state['mqtt'], username=device['username'], password=device['password'])))
            publisher.connect(state['mqtt']['host'], state['mqtt']['port'], 30)
            publisher.loop_start()
            message_id = 'native-acceptance-' + uuid.uuid4().hex
            raw = json.dumps({'device_id': 'poste2', 'message_id': message_id,
                              'observed_at': datetime.now(timezone.utc).isoformat(), 'purpose': 'installer_acceptance_no_sensor_claim'})
            pub = publisher.publish('harpisense/poste2/telemetry', raw, qos=1, retain=False)
            pub.wait_for_publish(10)
            publisher.disconnect()
            publisher.loop_stop()
            wait_for(lambda: any(x.get('message_id') == message_id for x in observed()['devices']))
            after = observed()
            telemetry = http.get(prefix + '/p11/telemetry', headers=headers).json()
            check(any(row['data'].get('message_id') == message_id for row in telemetry), 'authenticated_mqtt_publication_persisted_and_read_by_real_api')
            evidence['mqtt_after'] = after
            with psycopg.connect(state['dsn']) as conn:
                check(conn.execute("SELECT count(*) FROM projections WHERE kind='telemetry'").fetchone()[0] == 1, 'one_identifiable_postgresql_projection')
            page.get_by_role('button', name='Atualizar estados MQTT', exact=True).click()
            expect(page.get_by_text(message_id, exact=False)).to_be_visible()
            page.screenshot(path=str(evidence_dir/'windows-mqtt-received.png'), full_page=True)
            page.get_by_label('Modo do broker', exact=False).select_option('external')
            with page.expect_response(lambda r: r.url.endswith('/config/setup') and r.request.method == 'PUT') as mqtt_saved:
                page.get_by_role('button', name='Salvar rascunho MQTT', exact=True).click()
            check(mqtt_saved.value.status == 200, 'mqtt_mode_saved_as_draft_only')
            saved_setup = http.get(prefix + '/config/setup', headers=headers).json()
            current = http.get(prefix + '/config/current', headers=headers).json()
            check(saved_setup['document']['parameters']['mqtt_broker_mode'] == 'external' and
                  not current['effective_revision'] and current['operational'] is False,
                  'saving_broker_mode_does_not_apply_or_replace_active_local_broker')
            with psycopg.connect(state['dsn']) as conn:
                conn.execute("UPDATE hs_native_mqtt_observation SET observed_at=clock_timestamp()-interval '60 seconds'")
            stale = observed()
            check(stale['broker']['state'] == 'not_verified' and stale['consumer']['state'] == 'not_verified',
                  'stale_consumer_heartbeat_does_not_claim_current_connection')
            browser.close()
        try:
            preflight(private, ROOT/'.native-test/nonexistent-app', 'local_managed')
        except RuntimeError as error:
            check('EXISTING_INSTALLATION' in str(error), 'reinstallation_refused_before_changes_preserving_data')
        else:
            raise AssertionError('REINSTALLATION_NOT_REFUSED')
        check(http.get(prefix + '/config/current', headers=headers).json()['operational'] is False,
              'mqtt_observation_does_not_mark_configuration_operational')
        evidence['result'] = 'passed'
    except Exception as error:
        evidence['result'] = 'failed'
        evidence['first_failure'] = type(error).__name__
        # Stable assertions only; Playwright exception messages could include page contents.
        if isinstance(error, AssertionError) and str(error).replace('_', '').isalnum():
            evidence['first_failure'] = str(error)
        raise
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(15)
        if pg_started:
            run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-w', 'stop', '-m', 'fast'])
        for handle in handles:
            handle.close()
        (evidence_dir/'windows-native-result.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'result': evidence.get('result'), 'checks': len(evidence['checks']),
                          'evidence': str(evidence_dir/'windows-native-result.json')}))


if __name__ == '__main__':
    main()
