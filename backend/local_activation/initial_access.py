"""Fail-closed first-use adapter. Browser headers can never attest native transport."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from .envelopes import ActivationError, b64
from .protection import write_new

COOKIE_NAME = 'hs_initial_access'
COOKIE_PATH = '/p11-api/api/v1/'


class InitialAccessError(RuntimeError):
    status = 403

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class InitialAccess:
    def __init__(self, activation, *, administrator_state, retry_action,
                 native_transport, origin, clock=time.time, audit_hash=None):
        url = urlsplit(origin)
        if (url.scheme not in ('http', 'https') or url.hostname not in ('127.0.0.1', '::1')
                or url.path or url.query or url.fragment or url.username or url.password):
            raise ValueError('INVALID_NATIVE_ORIGIN')
        self.activation = activation
        self.administrator_state = administrator_state
        self.retry_action = retry_action
        self.native_transport = native_transport
        self.origin, self.clock = origin, clock
        self.audit_hash = audit_hash or self._persist_hash
        self.instance_nonce = secrets.token_bytes(32)
        self._sessions = {}
        self._lock = threading.RLock()
        self._seal = object()

    def _persist_hash(self, record):
        # Persist no bearer material. Restart intentionally refuses these old hashes.
        path = self.activation.directory/'first-use-session.protected'
        temp = path.with_name('session.' + secrets.token_hex(16) + '.tmp')
        try:
            write_new(temp, self.activation.protector.protect(
                json.dumps(record, sort_keys=True, separators=(',', ':')).encode('ascii')))
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _account(self):
        state = self.administrator_state()
        if state not in ('absent', 'mfa_pending', 'ready', 'migration_required'):
            raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
        return state

    def _new_session(self, local_user, capability):
        """Called solely by authenticated IPC endpoint with unforgeable in-process seal."""
        if capability is not self._seal or not local_user:
            raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
        with self._lock:
            if self._account() not in ('absent', 'mfa_pending'):
                self._sessions.clear()
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            if self.activation.status() == 'activated':
                receipt = self.activation.verified_receipt()
            else:
                # Network failures preserve identity. IPC may authorize retry, never bootstrap.
                identity = self.activation._identity()
                receipt = dict(installation_id=self.activation._installation_id(identity),
                               license_id=None, receipt_id=None)
            token = b64(secrets.token_bytes(32))
            digest = hashlib.sha256(token.encode('ascii')).hexdigest()
            expires = int(self.clock()) + 900
            self._sessions[digest] = dict(installation_id=receipt['installation_id'],
                license_id=receipt['license_id'], receipt_id=receipt['receipt_id'],
                local_user=local_user, instance=self.instance_nonce, expires=expires)
            if self.audit_hash:
                # Consumer persists only this hash and public binding in private state.
                self.audit_hash(dict(session_hash=digest, installation_id=receipt['installation_id'],
                                     local_user=local_user, expires_at=expires,
                                     service_instance_hash=hashlib.sha256(self.instance_nonce).hexdigest()))
            return dict(cookie_name=COOKIE_NAME, cookie_value=token, cookie_path=COOKIE_PATH,
                        origin=self.origin, expires_at=expires)

    def _authorize(self, request, *, activation_required=True):
        with self._lock:
            if self._account() not in ('absent', 'mfa_pending'):
                self._sessions.clear()
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            # Must be a runtime-owned predicate, NEVER derived from an HTTP header.
            if not self.native_transport(request):
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            expected_host = urlsplit(self.origin).netloc
            if request.headers.get('host') != expected_host:
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            origin = request.headers.get('origin')
            if (origin is not None and origin != self.origin) or (
                    request.method.upper() not in ('GET', 'HEAD') and origin != self.origin):
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            try:
                cookie = SimpleCookie()
                cookie.load(request.headers.get('cookie', ''))
                token = cookie[COOKIE_NAME].value
                if len(token) != 43:
                    raise ValueError()
                digest = hashlib.sha256(token.encode('ascii')).hexdigest()
                session = self._sessions[digest]
            except (KeyError, ValueError, UnicodeError):
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED') from None
            if session['expires'] <= self.clock() or not hmac.compare_digest(
                    session['instance'], self.instance_nonce):
                self._sessions.pop(digest, None)
                raise InitialAccessError('INITIAL_ACCESS_REQUIRED')
            if not activation_required:
                return session
            try:
                receipt = self.activation.verified_receipt()
            except Exception:
                raise InitialAccessError('ACTIVATION_REQUIRED') from None
            if session['installation_id'] != receipt['installation_id']:
                raise InitialAccessError('ACTIVATION_REQUIRED')
            for name in ('license_id', 'receipt_id'):
                if session[name] is not None and session[name] != receipt[name]:
                    raise InitialAccessError('ACTIVATION_REQUIRED')
                session[name] = receipt[name]
            return {name: receipt[name] for name in ('license_id', 'installation_id')}

    def require(self, request):
        try:
            return self._authorize(request)
        except InitialAccessError as exc:
            # Backend's actual AuthError when composed with the installed auth library.
            try:
                from admin_auth.service import AuthError
            except ImportError:
                raise exc
            raise AuthError(403, exc.code) from None

    def status(self, request):
        authorized = False
        retry_authorized = False
        try:
            self._authorize(request, activation_required=False)
            retry_authorized = True
            self._authorize(request)
            authorized = True
        except InitialAccessError:
            pass
        state = self.activation.status()
        account = self._account()
        return dict(contract_version=1, status=state, administrator=account,
                    retry_allowed=retry_authorized and state in ('not_activated', 'activation_pending'),
                    first_use_authorized=authorized,
                    loss_of_authenticator_policy='not_approved')

    def retry(self, request):
        try:
            self._authorize(request, activation_required=False)
        except InitialAccessError as exc:
            try:
                from admin_auth.service import AuthError
            except ImportError:
                raise exc
            raise AuthError(403, exc.code) from None
        self.retry_action()
        return self.status(request)

    def invalidate(self):
        """Call after successful MFA enrollment; ready account also fails closed."""
        with self._lock:
            self._sessions.clear()


def create_initial_access(activation, *, administrator_state, retry_action,
                          native_transport=None, origin='http://127.0.0.1:18080',
                          clock=time.time, audit_hash=None):
    return InitialAccess(activation, administrator_state=administrator_state,
                         retry_action=retry_action,
                         native_transport=native_transport or (lambda request: False),
                         origin=origin, clock=clock, audit_hash=audit_hash)
