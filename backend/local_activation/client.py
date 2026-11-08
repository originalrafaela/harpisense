"""HTTPS activator. Configuration and issuer trust come only from signed packaging."""
import contextlib
import http.client
import json
import os
import ssl
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .envelopes import (ActivationError, LIMIT, b64, exact, key_id, parse, sign,
                        unb64, verify)
from .identity import InstallationIdentity
from .protection import write_new

CHALLENGE = dict(version=int, challenge_id=str, nonce=str, license_id=str,
                 installation_id=str, installation_key_id=str, platform=str,
                 issued_at=int, expires_at=int)
RECEIPT = dict(version=int, receipt_id=str, license_id=str, installation_id=str,
               installation_key_id=str, installation_public_key=str, platform=str,
               activated_at=int, issuer_key_id=str)


def checked_uuid(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ActivationError('INVALID_ENVELOPE') from None


class HTTPSIssuer:
    def __init__(self, trusted_url, timeout=15, *, ca_file=None):
        url = urlsplit(trusted_url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ('', '/')):
            raise ActivationError('INVALID_ISSUER_CONFIGURATION')
        self.host, self.port, self.timeout = url.hostname, url.port or 443, timeout
        self.context = ssl.create_default_context(cafile=ca_file)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2

    def post(self, path, body):
        if path not in ('/api/v1/licenses/challenges', '/api/v1/licenses/activate'):
            raise ActivationError('INVALID_REQUEST')
        connection = http.client.HTTPSConnection(self.host, self.port,
                                                  timeout=self.timeout, context=self.context)
        try:
            connection.request('POST', path, json.dumps(body, separators=(',', ':')),
                               {'Content-Type': 'application/json', 'Accept': 'application/json'})
            response = connection.getresponse()
            raw = response.read(LIMIT + 1)
            if 300 <= response.status < 400:
                raise ActivationError('ISSUER_REDIRECT_REJECTED')
            if response.status != 200:
                # Never surface server-controlled bodies, URLs, nonce or keys in exceptions.
                codes = {400: 'INVALID_REQUEST', 401: 'INVALID_PROOF',
                         409: 'LICENSE_ALREADY_ACTIVATED', 410: 'CHALLENGE_EXPIRED',
                         429: 'RATE_LIMITED', 503: 'ISSUER_UNAVAILABLE'}
                code = codes.get(response.status, 'ISSUER_UNAVAILABLE')
                try:
                    error = parse(raw)
                    allowed = {'INVALID_ACTIVATION_KEY', 'INVALID_PROOF', 'CHALLENGE_CONSUMED',
                               'LICENSE_ALREADY_ACTIVATED', 'CHALLENGE_EXPIRED',
                               'RATE_LIMITED', 'ISSUER_UNAVAILABLE', 'INVALID_REQUEST'}
                    candidate = error['error']['code']
                    if candidate in allowed:
                        code = candidate
                except Exception:
                    pass
                raise ActivationError(code)
            return parse(raw)
        except (OSError, http.client.HTTPException):
            raise ActivationError('connection_required') from None
        finally:
            connection.close()


class ActivationClient:
    def __init__(self, directory, protector, issuer_keys, issuer, platform, *, clock=time.time):
        if platform not in ('windows', 'ubuntu'):
            raise ActivationError('INVALID_PLATFORM')
        self.directory = Path(directory)
        # The installer creates and ACLs this directory. Refuse implicit insecure creation.
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise ActivationError('PRIVATE_DIRECTORY_REQUIRED')
        if os.name == 'posix' and self.directory.stat().st_mode & 0o077:
            raise ActivationError('PRIVATE_DIRECTORY_REQUIRED')
        self.protector, self.keys, self.issuer = protector, dict(issuer_keys), issuer
        self.platform, self.clock = platform, clock
        self.identity_path = self.directory/'identity.protected'
        self.receipt_path = self.directory/'receipt.json'
        self._thread_lock = threading.Lock()

    @contextlib.contextmanager
    def _lock(self):
        with self._thread_lock:
            # OS lock also serializes separate installer/backend processes.
            fd = os.open(self.directory/'activation.lock', os.O_CREAT | os.O_RDWR, 0o600)
            try:
                if os.name == 'nt':
                    import msvcrt
                    if os.fstat(fd).st_size == 0:
                        os.write(fd, b'0')
                    os.lseek(fd, 0, 0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise ActivationError('ACTIVATION_BUSY') from None
            try:
                yield
            finally:
                os.close(fd)

    def _identity(self):
        return InstallationIdentity.load(self.identity_path, self.protector)

    def _installation_id(self, identity):
        # Random key gives stable per-installation UUID without a second mutable identity file.
        return str(uuid.UUID(bytes=bytes.fromhex(key_id(identity.public_bytes()))[:16], version=4))

    def _receipt(self, envelope, identity):
        doc = verify(envelope, 'receipt', self.keys, RECEIPT)
        for field in ('receipt_id', 'license_id', 'installation_id'):
            checked_uuid(doc[field])
        public = unb64(doc['installation_public_key'], 32)
        if (doc['issuer_key_id'] != envelope['key_id'] or
                doc['installation_key_id'] != key_id(public) or
                doc['installation_id'] != self._installation_id(identity) or
                doc['platform'] != self.platform or doc['activated_at'] < 0):
            raise ActivationError('INVALID_RECEIPT_BINDING')
        identity.prove_possession(public)
        return doc

    def verified_receipt(self):
        try:
            # Bound read prevents malicious oversized state from allocating unbounded memory.
            with self.receipt_path.open('rb') as stream:
                envelope = parse(stream.read(LIMIT + 1))
            return self._receipt(envelope, self._identity())
        except ActivationError:
            raise
        except Exception:
            raise ActivationError('invalid_local_identity') from None

    def status(self):
        if self.receipt_path.exists():
            try:
                self.verified_receipt()
                return 'activated'
            except Exception:
                return 'invalid_local_identity'
        if self.identity_path.exists():
            try:
                self._identity()
                return 'activation_pending'
            except Exception:
                return 'invalid_local_identity'
        return 'not_activated'

    def activate(self, activation_key):
        unb64(activation_key, 32)
        with self._lock():
            state = self.status()
            if state == 'activated':
                return self.verified_receipt()
            if state == 'invalid_local_identity':
                raise ActivationError(state)
            if not self.identity_path.exists():
                InstallationIdentity.provision(self.identity_path, self.protector)
            identity = self._identity()
            public = identity.public_bytes()
            installation_id = self._installation_id(identity)
            envelope = self.issuer.post('/api/v1/licenses/challenges', dict(
                activation_key=activation_key, installation_id=installation_id,
                installation_public_key=b64(public), platform=self.platform))
            challenge = verify(envelope, 'challenge', self.keys, CHALLENGE)
            for field in ('challenge_id', 'license_id', 'installation_id'):
                checked_uuid(challenge[field])
            unb64(challenge['nonce'], 32)
            if (challenge['installation_id'] != installation_id or
                    challenge['installation_key_id'] != key_id(public) or
                    challenge['platform'] != self.platform):
                raise ActivationError('INVALID_CHALLENGE_BINDING')
            now = int(self.clock())
            if (challenge['expires_at'] - challenge['issued_at'] != 120 or
                    challenge['issued_at'] > now or challenge['issued_at'] < 0 or
                    challenge['expires_at'] <= now):
                raise ActivationError('CHALLENGE_EXPIRED')
            proof_doc = {name: value for name, value in challenge.items()
                         if name not in ('issued_at', 'expires_at')}
            response = self.issuer.post('/api/v1/licenses/activate', dict(
                challenge=envelope, proof=sign(identity, 'activation-proof', proof_doc)))
            if type(response) is not dict or set(response) != {'status', 'receipt'} or response['status'] != 'activated':
                raise ActivationError('INVALID_RESPONSE')
            receipt = self._receipt(response['receipt'], identity)
            if receipt['license_id'] != challenge['license_id']:
                raise ActivationError('INVALID_RECEIPT_BINDING')
            # Identity was durably written BEFORE contacting issuer. Atomic receipt publication
            # is the only activation commit point; lost responses keep identity for retry.
            temp = self.directory/('receipt.' + uuid.uuid4().hex + '.tmp')
            try:
                write_new(temp, json.dumps(response['receipt'], separators=(',', ':')).encode('ascii'))
                os.replace(temp, self.receipt_path)
                if os.name == 'posix':
                    fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            finally:
                temp.unlink(missing_ok=True)
            return receipt
