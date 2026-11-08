"""Installer-owned composition. No browser input can configure trust or IPC peers."""
import json
import os
from pathlib import Path


class MigrationInitialAccess:
    """Existing accounts can log in; no new bootstrap or activation authorization."""
    def status(self, request):
        return dict(contract_version=1, status='not_activated',
                    administrator='migration_required', retry_allowed=False,
                    first_use_authorized=False, loss_of_authenticator_policy='not_approved')

    def require(self, request):
        from admin_auth.service import AuthError
        raise AuthError(403, 'ACTIVATION_REQUIRED')

    retry = require

    def invalidate(self):
        pass


def existing_administrator(state):
    import psycopg
    with psycopg.connect(state['dsn']) as conn:
        return conn.execute('SELECT 1 FROM hs_admin_account LIMIT 1').fetchone() is not None


def transport_for(state):
    from urllib.parse import urlsplit
    from local_activation.transport import NativeTransport
    url = urlsplit(state['panel_url'])
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port:
        raise RuntimeError('STRICT_LOOPBACK_REQUIRED')
    return NativeTransport('127.0.0.1', url.port)


def load_or_preserve_totp(state, directory, protector):
    from local_activation.identity import provision_totp_key, load_totp_key
    from local_activation.protection import write_new
    path = directory/'totp.protected'
    legacy = Path(state['key_file'])
    if not path.exists():
        if legacy.is_file():
            # Preserve the exact Fernet key already used by persisted secret_cipher.
            key = legacy.read_bytes().strip()
            from cryptography.fernet import Fernet
            Fernet(key)
            write_new(path, protector.protect(b'HS-TOTP-1\x00' + key))
        elif existing_administrator(state):
            raise RuntimeError('EXISTING_MFA_KEY_REQUIRED')
        else:
            provision_totp_key(path, protector)
    key = load_totp_key(path, protector)
    if legacy.is_file() and key != legacy.read_bytes().strip():
        raise RuntimeError('EXISTING_MFA_KEY_MISMATCH')
    return key


class NativeActivationRuntime:
    def __init__(self, state, root):
        self.state, self.root = state, Path(root)
        self.handoff = None

    def __enter__(self):
        self.transport = transport_for(self.state)
        configuration = self.root/'native-activation.json'
        if existing_administrator(self.state) and (
                not configuration.is_file() or not self.state.get('activation_directory')):
            self.totp_key = Path(self.state['key_file']).read_bytes().strip()
            self.adapter = MigrationInitialAccess()
            return self
        from local_activation.client import ActivationClient, HTTPSIssuer
        from local_activation.envelopes import unb64, key_id
        from local_activation.identity import provision_totp_key, load_totp_key
        from local_activation.initial_access import create_initial_access
        from local_activation.ipc import UnixHandoff, WindowsHandoff
        from local_activation.protection import SystemdCredential, WindowsDPAPI, write_new
        from local_activation.transport import NativeTransport
        cfg = json.loads(configuration.read_text())
        directory = Path(self.state['activation_directory'])
        if os.name == 'nt':
            protector = WindowsDPAPI()
        else:
            protector = SystemdCredential(Path(os.environ['CREDENTIALS_DIRECTORY'])/'activation-key')
        keys = {name: unb64(value, 32) for name, value in cfg['issuer_keys'].items()}
        if not keys or any(key_id(value) != name for name, value in keys.items()):
            raise RuntimeError('INVALID_PACKAGED_ISSUER_KEYS')
        self.client = ActivationClient(directory, protector, keys,
            HTTPSIssuer(cfg['issuer_url']), 'windows' if os.name == 'nt' else 'ubuntu')
        self.totp_key = load_or_preserve_totp(self.state, directory, protector)
        # The installer writes this only in the private service directory. Protection
        # happens under the API service identity, never the elevated GUI's DPAPI user.
        pending, license_file = directory/'activation.pending', directory/'license.protected'
        if pending.exists():
            if not license_file.exists():
                write_new(license_file, protector.protect(pending.read_bytes()))
            pending.unlink()

        def attempt_activation():
            self.client.activate(protector.unprotect(license_file.read_bytes()).decode('ascii'))

        def retry():
            from local_activation.envelopes import ActivationError
            from admin_auth.service import AuthError
            try:
                attempt_activation()
            except ActivationError as error:
                codes = {'LICENSE_ALREADY_ACTIVATED': 409, 'CHALLENGE_CONSUMED': 409,
                         'connection_required': 503, 'ISSUER_UNAVAILABLE': 503,
                         'CHALLENGE_EXPIRED': 410, 'RATE_LIMITED': 429,
                         'INVALID_ACTIVATION_KEY': 401, 'INVALID_PROOF': 401,
                         'INVALID_REQUEST': 400}
                raise AuthError(codes.get(error.code, 503),
                    error.code if error.code in codes else 'ISSUER_UNAVAILABLE') from None

        if not existing_administrator(self.state) and self.client.status() != 'activated':
            from local_activation.envelopes import ActivationError
            try:
                attempt_activation()  # Provision identity under API SID before IPC.
            except ActivationError as error:
                if error.code not in ('connection_required', 'ISSUER_UNAVAILABLE',
                                      'LICENSE_ALREADY_ACTIVATED'):
                    raise

        def administrator():
            import psycopg
            with psycopg.connect(self.state['dsn']) as conn:
                row = conn.execute('SELECT m.enabled_at FROM hs_admin_account a '
                    'LEFT JOIN hs_admin_mfa m ON m.account_id=a.id LIMIT 1').fetchone()
            if row is None:
                return 'absent'
            if self.client.status() != 'activated':
                return 'migration_required'
            return 'ready' if row[0] is not None else 'mfa_pending'

        def audit_hash(record):
            from local_activation.protection import write_new
            write_new(directory/('session-' + record['session_hash'] + '.json'),
                      json.dumps(record, separators=(',', ':')).encode('ascii'))

        self.adapter = create_initial_access(self.client, administrator_state=administrator,
            retry_action=retry, native_transport=self.transport.authorized,
            origin=self.state['panel_url'], audit_hash=audit_hash)
        if os.name == 'nt':
            self.handoff = WindowsHandoff(self.state['handoff_pipe'], self.adapter,
                self.state['api_service_sid'], self.state['installer_sids']).start()
        else:
            self.handoff = UnixHandoff(Path(self.state['handoff_directory'])/'first-use.sock',
                                       self.adapter, [0]).start()
        return self

    def __exit__(self, *error):
        if self.handoff:
            self.handoff.close()
        if hasattr(self, 'adapter'):
            self.adapter.invalidate()


def launcher_administrator_state(state):
    from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
    transport_for(state)  # Literal loopback only; never use proxy environment.

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(state['panel_url'] + '/p11-api/api/v1/activation/status')
    with opener.open(request, timeout=5) as response:
        result = json.loads(response.read(16385))
    status = result.get('administrator')
    if status not in ('ready', 'migration_required', 'absent', 'mfa_pending'):
        raise RuntimeError('INVALID_ACTIVATION_STATUS')
    return status


def open_browser(state, executable, handoff):
    if handoff is not None:
        from local_activation.ipc import launch_first_use
        return launch_first_use(handoff, chromium_executable=executable)
    # Login never requires an initial-access cookie or contact with the issuer.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(executable), headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(state['panel_url'])
            while context.pages:
                page.wait_for_timeout(250)
        finally:
            browser.close()


def launch_installer_browser(state, root):
    """Run in the interactive desktop; only the local trusted launcher calls this."""
    from local_activation.ipc import request_unix_handoff, request_windows_handoff
    needs_handoff = launcher_administrator_state(state) in ('absent', 'mfa_pending')
    handoff = None
    if os.name == 'nt':
        if needs_handoff:
            handoff = request_windows_handoff(state['handoff_pipe'],
                                              expected_server_sid=state['api_service_sid'])
        executable = Path(root)/'browser/chrome.exe'
    else:
        import pwd
        if needs_handoff:
            handoff = request_unix_handoff(Path(state['handoff_directory'])/'first-use.sock',
                expected_server_uid=pwd.getpwnam('harpisense-api').pw_uid)
        executable = Path(root)/'browser/chrome'
        if os.geteuid() == 0:
            uid = int(os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID') or '0')
            if uid == 0:
                raise RuntimeError('INTERACTIVE_NON_ROOT_USER_REQUIRED')
            user = pwd.getpwuid(uid)
            child = os.fork()
            if child:
                _, result = os.waitpid(child, 0)
                if result:
                    raise RuntimeError('FIRST_USE_BROWSER_FAILED')
                return
            try:
                os.initgroups(user.pw_name, user.pw_gid)
                os.setgid(user.pw_gid)
                os.setuid(uid)
                os.environ.update(HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name)
                open_browser(state, executable, handoff)
                os._exit(0)
            except Exception:
                os._exit(1)
    open_browser(state, executable, handoff)
