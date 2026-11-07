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
    evidence = {'environment': 'Product integration: isolated native PostgreSQL/Mosquitto/HTTP/Chromium; not clean OS',
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
    state['dsn'] = state['dsn'].replace(':15432/', ':25432/')
    state['panel_url'] = 'http://127.0.0.1:28080'
    state['mqtt']['port'] = 28883
    (private/'state.json').write_text(json.dumps(state), encoding='utf-8')
    config = private/'mosquitto.conf'
    config.write_text(config.read_text().replace('listener 8883 ', 'listener 28883 '), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('backend', 'backend/domain', 'genai')))
    processes, handles = [], []
    pg_started = False
    evidence_dir = ROOT/'docs/evidence/product-consolidation'
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
        check(True, 'fresh_product_migrations_and_protected_grant')
        process([args.mosquitto, '-c', config], 'broker')
        wait_for(lambda: probe_broker(state) == {'connected': True, 'subscribed': True})
        check(True, 'real_broker_tls_authentication_and_suback')
        original_broker_config = hashlib.sha256(config.read_bytes()).hexdigest()
        probe_broker(dict(state, mqtt=dict(state['mqtt'], mode='external')))
        check(hashlib.sha256(config.read_bytes()).hexdigest() == original_broker_config,
              'external_mode_validates_tls_and_suback_without_administering_broker')
        api = process(api_command + ['api', '--state', str(private/'state.json')], 'api')
        consumer = process(api_command + ['consumer', '--state', str(private/'state.json')], 'consumer')
        base = state['panel_url']
        http = httpx.Client(base_url=base, timeout=10, trust_env=False)
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
            page.goto(base)
            page.get_by_role('button', name='Primeira configuração', exact=True).click()
            page.get_by_label('Grant local de uso único', exact=True).fill((private/'bootstrap.secret').read_text())
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
            with page.expect_response(lambda r: r.url.endswith('/mfa/enrollment/confirm') and r.status == 200) as enrollment_confirmed:
                page.get_by_role('button', name='Confirmar MFA', exact=True).click()
            enrolled_headers = {'Authorization':'Bearer '+enrollment_confirmed.value.json()['access_token']}
            expect(page.get_by_role('heading', name='Guarde seus códigos de recuperação')).to_be_visible()
            check(page.locator('.recovery-codes li').count() == 10, 'ten_recovery_codes_browser')
            reset_codes = page.locator('.password-reset-codes li').all_text_contents()
            mfa_codes = page.locator('.recovery-codes li').all_text_contents()
            check(len(reset_codes) == 10 and not set(reset_codes) & set(mfa_codes), 'separate_password_reset_codes_browser')
            page.get_by_label('Guardei os códigos em local seguro.').check()
            page.get_by_role('button', name='Concluir e continuar', exact=True).click()
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
            page.get_by_label('Identificador do ativo', exact=True).fill('poste-extra')
            page.get_by_label('Nome do ativo', exact=True).fill('Ativo cadastrado no produto')
            page.get_by_label('Tópico MQTT do ativo', exact=True).fill('harpisense/poste2/telemetry')
            with page.expect_response(lambda r: r.url.endswith('/config/assets') and r.request.method == 'POST') as asset_saved:
                page.get_by_role('button', name='Salvar ativo', exact=True).click()
            check(asset_saved.value.status == 200, 'browser_asset_saved_real_http')
            expect(page.get_by_text('Ativo salvo e consultado novamente no servidor.', exact=True)).to_be_visible()
            with psycopg.connect(state['dsn']) as conn:
                check(conn.execute('SELECT count(*) FROM hs_config.asset').fetchone()[0] == 1, 'registered_asset_persisted_postgresql')
            proposal = http.post(prefix+'/config/proposals',headers=enrolled_headers,json={
                'schema_version':'1.0.0','record_type':'config.proposal','request_id':str(uuid.uuid4()),
                'idempotency_key':'presentation-'+uuid.uuid4().hex,'expected_revision':0,'reason_code':'INITIAL_IMPORT',
                'document':{'schema_version':'1.0.0','record_type':'config.document',
                            'parameters':{'display_name':'Central reutilizável','timezone':'America/Sao_Paulo'}}})
            check(proposal.status_code in (200,201),'permanent_presentation_proposal_created')
            operation = proposal.json()
            validated = http.post(prefix+'/config/proposals/'+operation['operation_id']+'/validate',
                headers=enrolled_headers,json={'expected_revision':operation['revision']})
            check(validated.status_code==200 and validated.json()['status']=='VALIDATED','presentation_validated_by_backend')
            applied = http.post(prefix+'/config/proposals/'+operation['operation_id']+'/apply',headers=enrolled_headers,
                json={'expected_revision':operation['revision'],'current_password':password})
            check(applied.status_code==200,'presentation_applied_with_reauthentication')
            # Full restart of own API/consumer/DB, not a machine reboot.
            for proc in (api, consumer):
                proc.terminate()
                proc.wait(15)
            page.get_by_role('button',name='Consultar ativos cadastrados',exact=True).click()
            expect(page.get_by_text('Falha de rede/configuração.',exact=False).first).to_be_visible(timeout=15000)
            check(True,'real_api_unavailability_visible_no_fake_success')
            run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-w', 'stop', '-m', 'fast'])
            pg_started = False
            run([args.postgres_bin/'pg_ctl.exe', '-D', private/'postgres', '-l', private/'postgres.log', '-w', 'start'])
            pg_started = True
            if args.runtime:
                run(api_command + ['prepare', '--state', private/'state.json'])
            else:
                prepare_database(private/'state.json')
            api = process(api_command + ['api', '--state', str(private/'state.json')], 'api-restarted')
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
            installed_status = http.get(prefix+'/native/status',headers=headers).json()
            check('package_version' in installed_status['build'] and installed_status['containment']=='not_available',
                  'installed_build_identity_and_real_containment_blocked')
            expect(page.get_by_role('button', name='Sair', exact=True)).to_be_visible()
            check(True, 'new_browser_login_requires_real_totp_after_process_restart')
            presented = http.get(prefix+'/config/presentation',headers=headers).json()
            check(presented['verified'] and presented['parameters']['display_name']=='Central reutilizável',
                  'permanent_presentation_preserved_after_process_restart')
            setup = http.get(prefix + '/config/setup', headers=headers).json()
            check(setup['document']['parameters']['display_name'] == 'Central nativa — ensaio isolado', 'setup_preserved_after_process_restart')
            page.get_by_role('button', name='Retomar assistente', exact=True).click()
            expect(page.get_by_label('Perfil de implantação', exact=False)).to_be_visible()
            expect(page.get_by_text('Ativo cadastrado no produto', exact=True)).to_be_visible()
            assets = http.get(prefix + '/config/assets', headers=headers).json()
            check(len(assets) == 1 and assets[0]['device_id'] == 'poste-extra', 'asset_preserved_after_reload_and_process_restart')
            duplicate = dict(device_id='poste-extra',expected_revision=0,document=assets[0]['document'])
            check(http.post(prefix + '/config/assets', headers=headers,json=duplicate).status_code == 409, 'asset_stale_revision_refused')
            controls = http.get(prefix + '/security/settings/mode/default', headers=headers).json()
            check(not controls['pending']['reliable'] and not controls['change_allowed'], 'unknown_operational_authority_blocks_change')
            change = dict(value=dict(controls['value'],autonomy_mode=2),expected_revision=controls['revision'],reason='isolated product verification')
            check(http.put(prefix + '/security/settings/mode/default',headers=headers,json=change).status_code == 409,'operational_change_refused_real_http')
            page.get_by_role('button', name='Selecionar M2', exact=True).click()
            expect(page.get_by_text('Selecionado M2.',exact=False)).to_be_visible()
            expect(page.get_by_role('button',name='Aplicar perfil selecionado',exact=True)).to_be_disabled()
            check(True,'profile_selection_local_effective_state_not_changed')
            page.get_by_role('button', name='Cancelar seleção',exact=True).click()
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
                  current['effective']['parameters'] == {'display_name':'Central reutilizável','timezone':'America/Sao_Paulo'} and current['operational'] is False,
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
        # Password reset through actual browser; code purpose and session boundaries in HTTP/DB.
        with psycopg.connect(state['dsn']) as conn:
            mfa_before = conn.execute('SELECT secret_cipher,enabled_at FROM hs_admin_mfa').fetchone()
        replacement = secrets.token_urlsafe(32)
        with sync_playwright() as pw:
            recovery_browser = pw.chromium.launch()
            recovery_page = recovery_browser.new_page()
            recovery_page.goto(base)
            recovery_page.get_by_role('button',name='Esqueci minha senha',exact=True).click()
            recovery_page.get_by_label('Usuário',exact=True).fill(username)
            recovery_page.get_by_label('Código de redefinição de senha',exact=True).fill(reset_codes[0])
            recovery_page.get_by_label('Nova senha',exact=True).fill(replacement)
            recovery_page.get_by_role('button',name='Redefinir senha',exact=True).click()
            expect(recovery_page.get_by_role('status')).to_contain_text('Senha redefinida')
            check(True,'browser_password_reset_without_administrative_session')
            recovery_browser.close()
        check(http.get(prefix + '/config/setup', headers=headers).status_code == 401, 'reset_revokes_existing_session')
        retry = http.post(prefix + '/admin-auth/password-reset/confirm',json=dict(username=username,code=reset_codes[0],new_password=replacement))
        check(retry.status_code == 401, 'password_reset_code_one_use')
        wrong_purpose = http.post(prefix + '/admin-auth/password-reset/confirm',json=dict(username=username,code=mfa_codes[0],new_password=replacement))
        check(wrong_purpose.status_code == 401, 'mfa_recovery_code_cannot_reset_password')
        with psycopg.connect(state['dsn']) as conn:
            check(conn.execute('SELECT secret_cipher,enabled_at FROM hs_admin_mfa').fetchone() == mfa_before, 'password_reset_preserves_totp_secret_and_enabled_state')
            check(conn.execute('SELECT count(*) FROM hs_admin_recovery_code WHERE used_at IS NULL').fetchone()[0] == 10, 'password_reset_preserves_mfa_recovery_codes')
        next_login = http.post(prefix + '/admin-auth/login',json=dict(username=username,password=replacement)).json()
        check(next_login.get('next_step') == 'login' and 'access_token' not in next_login,'new_password_still_requires_totp')
        old_step = pyotp.TOTP(key).now()
        wait_for(lambda: pyotp.TOTP(key).now() != old_step,timeout=35)
        verified_reset = http.post(prefix + '/admin-auth/mfa/verify',json=dict(challenge_token=next_login['challenge_token'],code=pyotp.TOTP(key).now()))
        check(verified_reset.status_code == 200,'new_password_totp_session_confirmed')
        recovered_headers = {'Authorization':'Bearer '+verified_reset.json()['access_token']}
        check(http.get(prefix+'/config/assets',headers=recovered_headers).json()[0]['device_id']=='poste-extra','assets_preserved_after_password_reset')
        # Existing MFA recovery continues to issue enrollment only.
        recovery_login = http.post(prefix+'/admin-auth/login',json=dict(username=username,password=replacement)).json()
        wrong_mfa_purpose = http.post(prefix+'/admin-auth/mfa/recover',json=dict(challenge_token=recovery_login['challenge_token'],code=reset_codes[1]))
        check(wrong_mfa_purpose.status_code==401,'password_reset_code_cannot_recover_mfa')
        mfa_recover = http.post(prefix+'/admin-auth/mfa/recover',json=dict(challenge_token=recovery_login['challenge_token'],code=mfa_codes[0]))
        check(mfa_recover.status_code==200 and mfa_recover.json().get('next_step')=='enroll' and 'access_token' not in mfa_recover.json(),'mfa_recovery_remains_separate_enrollment_only')
        recovered_challenge = mfa_recover.json()['challenge_token']
        enrollment = http.post(prefix+'/admin-auth/mfa/enrollment/begin',json=dict(challenge_token=recovered_challenge)).json()
        confirmed = http.post(prefix+'/admin-auth/mfa/enrollment/confirm',json=dict(challenge_token=recovered_challenge,code=pyotp.TOTP(enrollment['manual_key']).now()))
        check(confirmed.status_code == 200, 'lost_authenticator_replacement_confirmed')
        recovered_headers = {'Authorization':'Bearer '+confirmed.json()['access_token']}
        check(http.get(prefix+'/config/assets',headers=recovered_headers).status_code == 200,'replacement_authenticator_issues_full_session_only_after_totp')
        new_key = enrollment['manual_key']
        old_step = pyotp.TOTP(new_key).now()
        wait_for(lambda: pyotp.TOTP(new_key).now()!=old_step,timeout=35)
        regenerated = http.post(prefix+'/admin-auth/password-reset/codes',headers=recovered_headers,
                               json={'current_password':replacement,'code':pyotp.TOTP(new_key).now()})
        check(regenerated.status_code==200 and len(regenerated.json()['password_reset_codes'])==10,
              'password_reset_codes_regenerated_with_password_and_totp')
        # Trusted worker hook exercises authoritative state on isolated real DB.
        from delivery.operational_queue import OperationalQueue,SOURCES
        from delivery.control_store import PostgresControls
        from delivery.controls import Controls
        repo = PostgresControls(state['dsn'])
        authority = OperationalQueue()
        for source in SOURCES:
            with repo.transaction() as tx:
                authority.report(tx,source,1,[{'id':'closed-history','state':'CLOSED'}])
        control_state = http.get(prefix+'/security/settings/mode/default',headers=recovered_headers).json()
        check(control_state['change_allowed'] and control_state['pending']['blockers']==[], 'closed_authoritative_history_does_not_block')
        changed = http.put(prefix+'/security/settings/mode/default',headers=recovered_headers,json=dict(
            value=dict(autonomy_mode=2,operation='SIMULATION',execution_enabled=False),
            expected_revision=control_state['revision'],reason='isolated trusted authority verification'))
        check(changed.status_code==200 and changed.json()['value']['execution_enabled'] is True,'executor_derived_from_mode_backend')
        for source in SOURCES:
            with repo.transaction() as tx:
                authority.report(tx,source,2,[{'id':'active-case','state':'ACTIVE'}])
            blocked = http.get(prefix+'/security/settings/mode/default',headers=recovered_headers).json()
            check(not blocked['change_allowed'] and bool(blocked['pending']['blockers']), 'active_'+source+'_blocks_mode_change')
            refusal = http.put(prefix+'/security/settings/mode/default',headers=recovered_headers,json=dict(
                value=dict(blocked['value'],autonomy_mode=3),expected_revision=blocked['revision'],reason='isolated blocked transition'))
            check(refusal.status_code==409,'authoritative_'+source+'_transition_refused')
            with repo.transaction() as tx:
                authority.report(tx,source,3,[{'id':'active-case','state':'RESOLVED'}])
        with psycopg.connect(state['dsn']) as conn:
            conn.execute("UPDATE hs_operational_authority SET observed_at=clock_timestamp()-interval '60 seconds'")
        stale_controls = http.get(prefix+'/security/settings/mode/default',headers=recovered_headers).json()
        check(not stale_controls['pending']['reliable'] and not stale_controls['change_allowed'],'stale_authority_blocks_effective_change')
        stop = http.post(prefix+'/security/emergency-stop',headers=recovered_headers,json={'reason':'isolated product emergency verification'})
        check(stop.status_code==200 and stop.json()['emergency_stopped'] and not stop.json()['value']['execution_enabled'],'emergency_stop_persisted_disables_executor')
        check(http.get(prefix+'/p11/health',headers=recovered_headers).status_code==200,'emergency_stop_preserves_api_consultation')
        check(http.post(prefix+'/config/assets',json={}).status_code==401,'anonymous_asset_mutation_denied')
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
        (evidence_dir/'product-native-result.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'result': evidence.get('result'), 'checks': len(evidence['checks']),
                          'evidence': str(evidence_dir/'product-native-result.json')}))


if __name__ == '__main__':
    main()
