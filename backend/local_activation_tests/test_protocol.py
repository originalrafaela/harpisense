"""Contract fixture, explicitly NOT evidence of the production issuer or clean VM."""
import asyncio
import json
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.local_activation.client import ActivationClient, CHALLENGE, HTTPSIssuer
from backend.local_activation.envelopes import ActivationError, b64, key_id, parse, sign, unb64, verify
from backend.local_activation.identity import InstallationIdentity
from backend.local_activation.initial_access import create_initial_access, InitialAccessError
from backend.local_activation.protection import WindowsDPAPI
from backend.local_activation.transport import NativeTransport


class FixtureIssuer:
    def __init__(self):
        self.identity = InstallationIdentity(Ed25519PrivateKey.generate())
        self.keys = {key_id(self.identity.public_bytes()): self.identity.public_bytes()}
        self.license_id = str(uuid.uuid4())
        self.receipt = None
        self.consumed = set()
        self.expired = False
        self.lose_response = False
        self.last_request = None

    def post(self, path, body):
        if path.endswith('challenges'):
            public = unb64(body['installation_public_key'], 32)
            now = int(time.time()) - (121 if self.expired else 0)
            self.binding = dict(installation_id=body['installation_id'],
                                installation_key_id=key_id(public), platform=body['platform'])
            self.public = public
            return sign(self.identity, 'challenge', dict(version=1, challenge_id=str(uuid.uuid4()),
                nonce=b64(os.urandom(32)), license_id=self.license_id,
                issued_at=now, expires_at=now + 120, **self.binding))
        self.last_request = body
        challenge = verify(body['challenge'], 'challenge', self.keys, CHALLENGE)
        if challenge['challenge_id'] in self.consumed:
            raise ActivationError('CHALLENGE_CONSUMED')
        proof_fields = {k: type(v) for k, v in challenge.items() if k not in ('issued_at', 'expires_at')}
        proof = verify(body['proof'], 'activation-proof', {key_id(self.public): self.public}, proof_fields)
        if any(proof[k] != challenge[k] for k in proof):
            raise ActivationError('INVALID_PROOF')
        if self.receipt:
            existing = parse(unb64(self.receipt['payload']))
            if existing['installation_key_id'] != self.binding['installation_key_id']:
                raise ActivationError('LICENSE_ALREADY_ACTIVATED')
        else:
            self.receipt = sign(self.identity, 'receipt', dict(version=1, receipt_id=str(uuid.uuid4()),
                license_id=self.license_id, installation_public_key=b64(self.public),
                activated_at=int(time.time()), issuer_key_id=key_id(self.identity.public_bytes()), **self.binding))
        self.consumed.add(challenge['challenge_id'])
        if self.lose_response:
            self.lose_response = False
            raise ActivationError('connection_required')
        return dict(status='activated', receipt=self.receipt)


@unittest.skipUnless(os.name == 'nt', 'uses real native DPAPI')
class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.issuer = FixtureIssuer()
        self.key = b64(os.urandom(32))
        self.client = self.make_client('first')

    def tearDown(self):
        self.temp.cleanup()

    def make_client(self, name):
        directory = self.root/name
        directory.mkdir(exist_ok=True)
        return ActivationClient(directory, WindowsDPAPI(), self.issuer.keys, self.issuer, 'windows')

    def test_offline_restart_and_copy_receipt_and_second_installation(self):
        self.client.activate(self.key)
        restarted = self.make_client('first')
        restarted.issuer = None
        self.assertEqual(restarted.status(), 'activated')
        second = self.make_client('second')
        second.receipt_path.write_bytes(self.client.receipt_path.read_bytes())
        self.assertEqual(second.status(), 'invalid_local_identity')
        second.receipt_path.unlink()
        with self.assertRaisesRegex(ActivationError, 'LICENSE_ALREADY_ACTIVATED'):
            second.activate(self.key)

    def test_expired_never_signs_and_replay_rejected_by_fixture(self):
        self.issuer.expired = True
        with self.assertRaisesRegex(ActivationError, 'CHALLENGE_EXPIRED'):
            self.client.activate(self.key)
        self.assertIsNone(self.issuer.last_request)
        self.issuer.expired = False
        self.client.activate(self.key)
        with self.assertRaisesRegex(ActivationError, 'CHALLENGE_CONSUMED'):
            self.issuer.post('/api/v1/licenses/activate', self.issuer.last_request)

    def test_lost_response_resumes_same_identity_same_receipt(self):
        self.issuer.lose_response = True
        with self.assertRaisesRegex(ActivationError, 'connection_required'):
            self.client.activate(self.key)
        protected_key = self.client.identity_path.read_bytes()
        self.assertEqual(self.client.status(), 'activation_pending')
        first_receipt = self.issuer.receipt
        self.client.activate(self.key)
        self.assertEqual(protected_key, self.client.identity_path.read_bytes())
        self.assertEqual(json.loads(self.client.receipt_path.read_text()), first_receipt)

    def test_altered_receipt_and_unknown_issuer(self):
        self.client.activate(self.key)
        envelope = json.loads(self.client.receipt_path.read_text())
        envelope['payload'] = b64(b'{}')
        self.client.receipt_path.write_text(json.dumps(envelope))
        self.assertEqual(self.client.status(), 'invalid_local_identity')
        self.client.keys = {}
        self.assertEqual(self.client.status(), 'invalid_local_identity')

    def test_cookie_transport_origin_expiry_restart_and_mfa_boundaries(self):
        self.client.activate(self.key)
        account = ['absent']
        now = [time.time()]
        attestation = object()
        adapter = create_initial_access(self.client, administrator_state=lambda: account[0],
            retry_action=lambda: None, native_transport=lambda r: r.scope.get('attest') is attestation,
            clock=lambda: now[0])
        session = adapter._new_session('sid:fixture-installer', adapter._seal)
        request = SimpleNamespace(method='POST', scope={'attest': attestation}, headers={
            'host': '127.0.0.1:18080', 'origin': 'http://127.0.0.1:18080',
            'cookie': 'hs_initial_access=' + session['cookie_value']})
        self.assertEqual(adapter.require(request)['license_id'], self.issuer.license_id)
        for change in ('remote', 'foreign-origin', 'no-origin', 'no-cookie', 'foreign-host'):
            saved_headers, saved_scope = dict(request.headers), dict(request.scope)
            if change == 'remote':
                request.scope = {}
                request.headers['x-native-installer'] = 'true'
            elif change == 'foreign-origin':
                request.headers['origin'] = 'http://attacker.invalid'
            elif change == 'no-origin':
                request.headers.pop('origin')
            elif change == 'no-cookie':
                request.headers.pop('cookie')
            else:
                request.headers['host'] = 'attacker.invalid'
            with self.subTest(change=change), self.assertRaises(InitialAccessError):
                adapter.require(request)
            request.headers, request.scope = saved_headers, saved_scope
        now[0] += 901
        with self.assertRaises(InitialAccessError):
            adapter.require(request)
        now[0] -= 901
        adapter.invalidate()
        with self.assertRaises(InitialAccessError):
            adapter.require(request)
        account[0] = 'ready'
        with self.assertRaises(InitialAccessError):
            adapter._new_session('sid:fixture-installer', adapter._seal)
        # Full administrative access is backend-owned; adapter grants only public binding.
        self.assertNotIn('access_token', session)


class EnvelopeTests(unittest.TestCase):
    def test_duplicates_noncanonical_base64_types_and_limit(self):
        for value in (b'{"a":1,"a":2}', b'{"a":NaN}', b'x' * 16385):
            with self.assertRaises(ActivationError):
                parse(value)
        for value in ('YQ==', 'YR', '!!'):
            with self.assertRaises(ActivationError):
                unb64(value)
        issuer = FixtureIssuer()
        envelope = sign(issuer.identity, 'challenge', {'version': True})
        with self.assertRaises(ActivationError):
            verify(envelope, 'challenge', issuer.keys, {'version': int})
        with self.assertRaises(ActivationError):
            verify(envelope, 'receipt', issuer.keys, {'version': int})

    def test_https_configuration_and_cert_verification(self):
        for url in ('http://issuer.test', 'https://user:password@issuer.test',
                    'https://issuer.test/?secret=x', 'https://issuer.test/redirect'):
            with self.assertRaises(ActivationError):
                HTTPSIssuer(url)
        client = HTTPSIssuer('https://issuer.test')
        self.assertTrue(client.context.check_hostname)
        import ssl
        self.assertEqual(client.context.verify_mode, ssl.CERT_REQUIRED)

    def test_native_scope_attestation_and_proxy_refusal(self):
        transport = NativeTransport()
        scopes, responses = [], []
        async def app(scope, receive, send):
            scopes.append(scope)
        async def send(value):
            responses.append(value)
        wrapper = transport.wrap(app)
        base = dict(type='http', client=('127.0.0.1', 51234), server=('127.0.0.1', 18080), headers=[])
        asyncio.run(wrapper(base, None, send))
        self.assertTrue(transport.authorized(SimpleNamespace(scope=scopes[0])))
        self.assertFalse(transport.authorized(SimpleNamespace(scope={'harpisense.native_transport': True})))
        for change in (dict(client=('192.0.2.1', 50)),
                       dict(headers=[(b'x-forwarded-for', b'127.0.0.1')]),
                       dict(server=('0.0.0.0', 18080))):
            responses.clear()
            asyncio.run(wrapper(base | change, None, send))
            self.assertEqual(responses[0]['status'], 403)


if __name__ == '__main__':
    unittest.main()
