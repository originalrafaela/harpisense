"""Browser checks through a strict-host-key SSH tunnel to the disposable guest.

Read acceptance credentials into memory only; never print them or screenshot MFA.
Run after the installed guest acceptance phase; does not change installed source.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

import pyotp
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
ACCESS = ROOT / '.native-test/candidate2-clean-20261106'
SSH = ['ssh', '-i', str(ACCESS / 'trial_ed25519'),
       '-o', 'UserKnownHostsFile="' + (ACCESS / 'known_hosts').as_posix() + '"',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=10', '-o', 'ExitOnForwardFailure=yes']


def main():
    phase, host = sys.argv[1:3]
    evidence_dir = ROOT / 'docs/evidence/native-installers/ubuntu-candidate3-trial'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    private = json.loads(subprocess.check_output(SSH + ['trial@' + host,
        'sudo cat /home/trial/harpisense-trial/acceptance-private.json'], text=True))
    tunnel = subprocess.Popen(SSH + ['-N', '-L', '127.0.0.1:18080:127.0.0.1:18080',
                                      'trial@' + host],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    evidence = {'phase': phase, 'checks': [], 'transport': 'Chromium over strict SSH tunnel'}
    try:
        with sync_playwright() as pw:
            evidence['stage'] = 'launch_browser'
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            evidence['stage'] = 'load_login_page'
            for attempt in range(20):
                try:
                    page.goto('http://127.0.0.1:18080', timeout=5000)
                    break
                except Exception:
                    if attempt == 19:
                        raise
                    time.sleep(.5)
            page.screenshot(path=str(evidence_dir / (phase + '-login.png')), full_page=True)
            evidence['stage'] = 'enter_password'
            page.get_by_label('Usuário', exact=True).fill(private['username'])
            page.get_by_label('Senha', exact=True).fill(private['password'])
            page.get_by_role('button', name='Entrar na central', exact=True).click()
            evidence['stage'] = 'verify_totp'
            while int(time.time() // 30) <= private['last_totp_step']:
                time.sleep(.25)
            page.get_by_label('Código do aplicativo autenticador', exact=True).fill(
                pyotp.TOTP(private['totp_key']).now())
            page.get_by_role('button', name='Verificar código', exact=True).click()
            evidence['stage'] = 'wait_dashboard'
            expect(page.get_by_role('button', name='Sair', exact=True)).to_be_visible(timeout=15000)
            evidence['checks'].append('browser_password_totp_login_and_dashboard')
            page.get_by_role('button', name='Retomar assistente', exact=True).click()
            expect(page.get_by_label('Perfil de implantação', exact=False)).to_be_visible()
            evidence['checks'].append('browser_saved_configuration_resumed')
            page.screenshot(path=str(evidence_dir / (phase + '-dashboard.png')), full_page=True)
            browser.close()
        evidence['result'] = 'passed'
    except Exception as error:
        evidence.update(result='failed', failure_type=type(error).__name__)
        # Visible text contains no input values; redact known private values as well.
        try:
            visible = page.locator('body').inner_text(timeout=3000)
            for field in ('password', 'totp_key', 'username'):
                visible = visible.replace(private[field], '[REDACTED]')
            for code in private.get('recovery_codes', []):
                visible = visible.replace(code, '[REDACTED]')
            (evidence_dir / (phase + '-browser-failure.txt')).write_text(visible, encoding='utf-8')
        except Exception:
            pass
    finally:
        tunnel.terminate()
        tunnel.wait(timeout=15)
        output = evidence_dir / (phase + '-browser.json')
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps(evidence, indent=2))
    return 0 if evidence['result'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
