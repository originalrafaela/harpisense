"""Acceptance-only issuer fixture; real Ed25519/DPAPI, transport and authenticated IPC.

Never imported by the product entrypoint or distributed as an activation authority.
This is a workstation trial, not evidence of a clean Windows/Ubuntu installation.
"""
import json
import os
from pathlib import Path
import uuid


def prepare_first_use(state, private):
    if os.name != 'nt':
        raise RuntimeError('WINDOWS_ACCEPTANCE_FIXTURE_ONLY')
    import win32api
    import win32security
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from local_activation.client import ActivationClient, HTTPSIssuer
    from local_activation.envelopes import b64, key_id, sign
    from local_activation.identity import InstallationIdentity
    from local_activation.protection import WindowsDPAPI
    from provision import private_directory, write_private
    directory = Path(private)/'activation-fixture'
    private_directory(directory)
    protector = WindowsDPAPI()
    identity = InstallationIdentity.provision(directory/'identity.protected', protector)
    issuer = Ed25519PrivateKey.generate()
    public = issuer.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    issuer_id = key_id(public)
    client = ActivationClient(directory, protector, {issuer_id: public},
                              HTTPSIssuer('https://issuer.invalid'), 'windows')
    installation_id = client._installation_id(identity)
    receipt = sign(InstallationIdentity(issuer), 'receipt', dict(version=1,
        receipt_id=str(uuid.uuid4()), license_id=str(uuid.uuid4()),
        installation_id=installation_id, installation_key_id=key_id(identity.public_bytes()),
        installation_public_key=b64(identity.public_bytes()), platform='windows',
        activated_at=1, issuer_key_id=issuer_id))
    write_private(directory/'receipt.json', json.dumps(receipt))
    write_private(Path(private)/'native-activation.json', json.dumps(dict(
        issuer_url='https://issuer.invalid', issuer_keys={issuer_id: b64(public)})))
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    try:
        sid = win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token, win32security.TokenUser)[0])
    finally:
        token.Close()
    state.update(installation_id=installation_id, activation_directory=str(directory),
        api_service_sid=sid, installer_sids=[sid],
        handoff_pipe=r'\\.\pipe\HarpiSense-Acceptance-' + uuid.uuid4().hex)


def authorize_browser(page, state):
    from local_activation.ipc import request_windows_handoff
    handoff = request_windows_handoff(state['handoff_pipe'], expected_server_sid=state['api_service_sid'])
    from urllib.parse import urlsplit
    page.context.add_cookies([dict(name=handoff['cookie_name'], value=handoff['cookie_value'],
        domain=urlsplit(handoff['origin']).hostname, path=handoff['cookie_path'],
        httpOnly=True, secure=False, sameSite='Strict', expires=handoff['expires_at'])])
    page.goto(state['panel_url'])
    status = page.request.get(state['panel_url'] + '/p11-api/api/v1/activation/status')
    assert status.status == 200 and status.json()['first_use_authorized'], 'ipc_cookie_authorizes_initial_access'
    assert page.locator('input[name="bootstrap_secret"]').count() == 0, 'no_manual_grant_field'


if __name__ == '__main__':
    import sys
    root = Path(__file__).resolve().parents[2]
    for part in ('backend', 'backend/domain', 'genai', 'packaging/native'):
        sys.path.insert(0, str(root/part))
    if len(sys.argv) != 4 or sys.argv[1] != 'api' or sys.argv[2] != '--state':
        raise SystemExit('ACCEPTANCE_API_ONLY')
    from native_server.runtime import load_state, build_native_app
    from native_activation import NativeActivationRuntime
    import uvicorn
    from urllib.parse import urlsplit
    state = load_state(sys.argv[3])
    with NativeActivationRuntime(state, Path(sys.argv[3]).parent) as runtime:
        frontend = Path(os.environ.get('HARPISENSE_ACCEPTANCE_FRONTEND', root/'frontend/dist'))
        app = build_native_app(state, frontend, initial_access=runtime.adapter,
                               protection_key=runtime.totp_key)
        uvicorn.run(runtime.transport.wrap(app), host='127.0.0.1',
                    port=urlsplit(state['panel_url']).port, proxy_headers=False, access_log=False)
