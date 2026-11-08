"""Real native auth/PG/Chromium/IPC trial with explicitly fixture-issued receipt."""
import argparse
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
sys.path[:0] = [str(ROOT/p) for p in ('backend', 'backend/domain', 'genai', 'packaging/native')]
import httpx
import pyotp
from playwright.sync_api import sync_playwright, expect
from acceptance_first_use import prepare_first_use, authorize_browser
from provision import create_state, initialize_database, prepare_database, run
from native_activation import launcher_administrator_state


def wait(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except httpx.TransportError:
            pass
        time.sleep(.2)
    raise AssertionError('WAIT_TIMEOUT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', required=True, type=Path)
    parser.add_argument('--frontend-dist', required=True, type=Path)
    args = parser.parse_args()
    private = ROOT/'.native-test'/('initial-auth-' + uuid.uuid4().hex)
    state = create_state(private)
    prepare_first_use(state, private)
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            ports.append(sock.getsockname()[1])
    state['dsn'] = state['dsn'].replace(':15432/', ':' + str(ports[0]) + '/')
    state['panel_url'] = 'http://127.0.0.1:' + str(ports[1])
    (private/'state.json').write_text(json.dumps(state))
    result = dict(environment='existing Windows workstation, disposable native processes',
                  issuer='signed receipt fixture; human authentication Backend is real',
                  clean_machine=False, checks=[])
    def check(value, label):
        if not value:
            raise AssertionError(label)
        result['checks'].append(label)
    pg = args.postgres_bin
    started, api, logfile = False, None, None
    http = httpx.Client(base_url=state['panel_url'], trust_env=False, timeout=5,
                        headers={'Origin': state['panel_url']})
    def start_api():
        nonlocal api, logfile
        logfile = (private/'api.log').open('ab')
        api = subprocess.Popen([sys.executable, str(ROOT/'packaging/native/acceptance_first_use.py'),
            'api', '--state', str(private/'state.json')], cwd=ROOT,
            env=dict(os.environ, HARPISENSE_ACCEPTANCE_FRONTEND=str(args.frontend_dist.resolve())),
            stdout=logfile, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        wait(lambda: http.get('/').status_code == 200)
    def stop_api():
        nonlocal api, logfile
        if api and api.poll() is None:
            api.terminate()
            api.wait(15)
        if logfile:
            logfile.close()
        api, logfile = None, None
    try:
        run([pg/'initdb.exe', '-D', private/'postgres', '-U', 'native_installer',
             '--encoding=UTF8', '--auth=scram-sha-256', '--pwfile', private/'pg-init.secret'])
        with (private/'postgres/postgresql.conf').open('a') as stream:
            stream.write("\nlisten_addresses='127.0.0.1'\nport=" + str(ports[0]) + '\n')
        run([pg/'pg_ctl.exe', '-D', private/'postgres', '-l', private/'postgres.log', '-w', 'start'])
        started = True
        initialize_database(state, private)
        prepare_database(private/'state.json')
        prepare_database(private/'state.json')
        check(not (private/'bootstrap.secret').exists(), 'migrations_idempotent_no_manual_grant')
        start_api()
        prefix = '/p11-api/api/v1'
        username, password = 'native-initial-owner', secrets.token_urlsafe(32)
        denied = http.post(prefix+'/admin-auth/bootstrap', json=dict(username=username, password=password))
        check(denied.status_code == 403, 'bootstrap_without_ipc_cookie_denied')
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                authorize_browser(page, state)
                check(True, 'real_named_pipe_peer_identity_and_cookie_handoff')
                initial = page.get_by_role('button', name='Autenticação inicial', exact=True)
                if initial.is_visible():
                    initial.click()
                expect(page.get_by_label('Senha da conta administrativa', exact=True)).to_be_visible()
                check(page.locator('input').count() == 2, 'bootstrap_only_username_password')
                page.get_by_label('Usuário', exact=True).fill(username)
                page.get_by_label('Senha da conta administrativa', exact=True).fill(password)
                page.get_by_role('button', name='Criar conta e configurar MFA', exact=True).click()
                page.get_by_role('button', name='Mostrar QR e chave manual', exact=True).click()
                key = page.get_by_label('Chave manual', exact=True).input_value()
                page.get_by_label('Código de 6 dígitos', exact=True).fill(pyotp.TOTP(key).now())
                page.get_by_role('button', name='Confirmar MFA', exact=True).click()
                expect(page.get_by_role('dialog')).to_be_visible()
                expect(page.locator('.recovery-codes li')).to_have_count(3)
                page.get_by_role('button', name='Já guardei os códigos', exact=True).click()
                expect(page.get_by_role('dialog')).to_have_count(0)
                check(True, 'real_ui_bootstrap_totp_three_codes_and_completed')
                check(launcher_administrator_state(state) == 'ready', 'launcher_ready_after_completed')
            finally:
                browser.close()
            for migration in (False, True):
                stop_api()
                if migration:
                    (private/'native-activation.json').rename(private/'native-activation.disabled')
                start_api()
                expected = 'migration_required' if migration else 'ready'
                check(launcher_administrator_state(state) == expected, 'restart_launcher_' + expected)
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page()  # No IPC or first-use cookie on login.
                    page.goto(state['panel_url'])
                    page.get_by_label('Usuário', exact=True).fill(username)
                    page.get_by_label('Senha', exact=True).fill(password)
                    page.get_by_role('button', name='Entrar na central', exact=True).click()
                    expect(page.get_by_label('Código do aplicativo autenticador', exact=True)).to_be_visible()
                    previous = pyotp.TOTP(key).now()
                    wait(lambda: pyotp.TOTP(key).now() != previous)
                    page.get_by_label('Código do aplicativo autenticador', exact=True).fill(pyotp.TOTP(key).now())
                    page.get_by_role('button', name='Verificar código', exact=True).click()
                    expect(page.get_by_role('button', name='Sair', exact=True)).to_be_visible()
                    expect(page.get_by_role('dialog')).to_have_count(0)
                    check(True, 'real_login_no_cookie_no_welcome_' + expected)
                finally:
                    browser.close()
        result['result'] = 'passed'
    except Exception as error:
        result.update(result='failed', failure_type=type(error).__name__)
        if isinstance(error, AssertionError) and str(error).replace('_', '').isalnum():
            result['failure'] = str(error)
    finally:
        stop_api()
        http.close()
        if started:
            run([pg/'pg_ctl.exe', '-D', private/'postgres', '-m', 'fast', '-w', 'stop'])
        output = ROOT/'docs/evidence/native-initial-auth'
        output.mkdir(parents=True, exist_ok=True)
        (output/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    return 0 if result['result'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
