"""ASGI requests on the deployed FastAPI/P11 composition, without HTTPX or DB writes.

Set ADMIN_AUTH_RUNTIME_DIR to a read-only copy of deployed sources (or its cwd).
Fake identity and Store are explicit: this is compatibility, not a real login receipt.
"""
import asyncio
import base64
import json
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin_auth import AuthError, install_admin_auth


class IdentityFixture:
    def current(self, token):
        if token != 'a' * 43:
            raise AuthError(401, 'SESSION_INVALID')
        return dict(authenticated=True, username='fixture-owner', expires_at='2099-01-01T00:00:00Z',
                    idle_timeout_seconds=1800, mfa_available=False, email_recovery_available=False)

    def login(self, username, password):
        if (username, password) != ('fixture-owner', 'isolated fixture password'):
            raise AuthError(401, 'INVALID_CREDENTIALS')
        return dict(access_token='a'*43, token_type='Bearer', expires_at='2099-01-01T00:00:00Z',
                    idle_timeout_seconds=1800, username=username)

    def logout(self, token):
        self.current(token)


class ReadOnlyFixture:
    def list(self, kind, limit=50, offset=0):
        return []

    def history(self, kind, identifier):
        return []

    def insert(self, *_args):
        raise AssertionError('No ingestion writes permitted in compatibility test')


async def request(app, method, path, *, authorization=None, body=None, origin=None):
    sent = []
    headers = [(b'host', b'127.0.0.1')]
    if authorization:
        headers.append((b'authorization', authorization.encode()))
    if origin:
        headers.append((b'origin', origin.encode()))
    if body is not None:
        headers.append((b'content-type', b'application/json'))
    raw = json.dumps(body).encode() if body is not None else b''
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': raw, 'more_body': False}
        await asyncio.Event().wait()

    async def send(message):
        sent.append(message)

    parsed = urlsplit(path)
    scope = dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method=method,
                 scheme='http', path=parsed.path, raw_path=parsed.path.encode(), root_path='', query_string=parsed.query.encode(),
                 headers=headers, client=('127.0.0.1', 12345), server=('127.0.0.1', 8000))
    await app(scope, receive, send)
    status = next(m['status'] for m in sent if m['type'] == 'http.response.start')
    content = b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body')
    return status, json.loads(content) if content else None


@unittest.skipUnless(os.getenv('ADMIN_AUTH_RUNTIME_DIR'), 'Deployed source snapshot required')
class RuntimeRoutes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runtime = Path(os.environ['ADMIN_AUTH_RUNTIME_DIR'])
        sys.path.insert(0, str(runtime))
        from runtime_p11.service import create_app
        from harpia_deterministic.p11 import install_deterministic_harpia
        self.app = create_app(ReadOnlyFixture(), username='technical-fixture',
                              password='technical-password', service_token='fixture-service-token')
        install_deterministic_harpia(self.app, ReadOnlyFixture())
        install_admin_auth(self.app, IdentityFixture(), allowed_origins=['http://127.0.0.1:4174'])

    async def test_every_administrative_route_refuses_absent_basic_and_invalid_session(self):
        basic = 'Basic ' + base64.b64encode(b'technical-fixture:technical-password').decode()
        paths = ['/api/v1/p11/health', '/api/v1/p11/telemetry',
                 '/api/v1/p11/incident/fixture/history', '/api/v1/p11/explain/fixture']
        for path in paths:
            for header in [None, basic, 'Bearer ' + 'b' * 43]:
                with self.subTest(path=path, header_kind=(header or '').split(' ')[0]):
                    status, _ = await request(self.app, 'GET', path, authorization=header)
                    self.assertEqual(status, 401)
            status, _ = await request(self.app, 'GET', path, authorization='Bearer '+'a'*43)
            self.assertEqual(status, 404 if '/explain/' in path else 200)

    async def test_session_router_validation_and_origin(self):
        prefix = '/api/v1/admin-auth'
        status, body = await request(self.app, 'POST', prefix+'/login',
                                     body={'username':'fixture-owner','password':'isolated fixture password'})
        self.assertEqual(status, 200)
        self.assertEqual(body['token_type'], 'Bearer')
        status, _ = await request(self.app, 'GET', prefix+'/session', authorization='Bearer '+'a'*43)
        self.assertEqual(status, 200)
        status, _ = await request(self.app, 'POST', prefix+'/logout', authorization='Bearer '+'a'*43)
        self.assertEqual(status, 204)
        status, body = await request(self.app, 'POST', prefix+'/login', body={'password':'private-invalid-value'})
        self.assertEqual(status, 422)
        self.assertNotIn('private-invalid-value', str(body))
        status, _ = await request(self.app, 'POST', prefix+'/login', origin='https://foreign.example',
                                  body={'username':'fixture-owner','password':'isolated fixture password'})
        self.assertEqual(status, 403)

    async def test_technical_ingestion_still_requires_basic_and_service_token(self):
        for header in [None, 'Bearer '+'a'*43,
                       'Basic '+base64.b64encode(b'technical-fixture:technical-password').decode()]:
            status, _ = await request(self.app, 'POST', '/api/v1/p11/ingest/telemetry',
                                      authorization=header,
                                      body={'id':'fixture','source':'trusted-service','data':{}})
            self.assertEqual(status, 403 if header and header.startswith('Basic ') else 401)


if __name__ == '__main__':
    unittest.main()
