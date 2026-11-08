"""Explicit opt-in interoperability with Edge's real source and native DPAPI.

Selected by run_native_postgres.py --edge-backend PATH. Not an issuer fixture:
actual HTTPSIssuer -> TLS -> FastAPI license_issuer -> native PostgreSQL.
"""
import datetime
import importlib
import ipaddress
import os
from pathlib import Path
import socket
import sys
import threading
import time

import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from license_issuer import envelopes as wire
from license_issuer.api import create_issuer_app
from test_initial_auth import (issuer_and_machine, http_app, code_now, PASSWORD, PREFIX, query)


@pytest.fixture
def live_edge(dsn,tmp_path):
    sys.path.insert(0,os.environ['INITIAL_AUTH_EDGE_BACKEND'])
    from local_activation.client import ActivationClient, HTTPSIssuer
    from local_activation.protection import WindowsDPAPI, SystemdCredential
    from local_activation.envelopes import ActivationError
    issuer,_,_=issuer_and_machine(dsn)
    tls_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'issuer-fixture')])
    now=datetime.datetime.now(datetime.timezone.utc)
    certificate=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(tls_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .sign(tls_key,hashes.SHA256()))
    cert=tmp_path/'tls.pem'
    key=tmp_path/'tls.key'
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(tls_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    app=create_issuer_app(issuer,distributor_token='fixture-distributor-credential-32bytes')
    sock=socket.socket()
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,ssl_certfile=str(cert),ssl_keyfile=str(key),
        proxy_headers=False,access_log=False,log_config=None))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
    thread.start()
    deadline=time.monotonic()+8
    while not server.started and time.monotonic()<deadline:
        time.sleep(.02)
    assert server.started
    transport=HTTPSIssuer(f'https://127.0.0.1:{port}',ca_file=str(cert))
    keys={identifier:public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw) for identifier,public in issuer.keys.items()}
    if os.name=='nt':
        protector=WindowsDPAPI()
    else:
        # Fixture represents systemd-provided bytes; not evidence of encrypted
        # credential provisioning on a clean Ubuntu machine.
        credential=tmp_path/'credential'
        credential.write_bytes(os.urandom(32))
        credential.chmod(0o600)
        protector=SystemdCredential(credential)
    def machine(name):
        directory=tmp_path/name
        directory.mkdir(mode=0o700)
        return ActivationClient(directory,protector,keys,transport,'windows' if os.name=='nt' else 'ubuntu')
    try:
        yield issuer,transport,machine,ActivationError
    finally:
        server.should_exit=True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()


def test_real_edge_tls_commit_loss_replay_second_machine_and_offline(dsn,live_edge):
    issuer,transport,machine,ActivationError=live_edge
    issued=issuer.issue()
    first=machine('first')
    original_post=transport.post
    last={}
    def lose_once(path,body):
        response=original_post(path,body)
        if path.endswith('/activate'):
            last.update(body)
            raise ActivationError('connection_required')
        return response
    transport.post=lose_once
    with pytest.raises(ActivationError,match='connection_required'):
        first.activate(issued['activation_key'])
    assert first.status()=='activation_pending'
    committed=query(dsn,'SELECT receipt FROM hs_issuer_license')[0][0]
    transport.post=original_post
    document=first.activate(issued['activation_key'])
    assert first.status()=='activated'
    assert query(dsn,'SELECT receipt FROM hs_issuer_license')[0][0]==committed
    assert document['license_id']==issued['license_id']
    with pytest.raises(ActivationError,match='CHALLENGE_CONSUMED'):
        transport.post('/api/v1/licenses/activate',last)
    second=machine('second')
    second.receipt_path.write_bytes(first.receipt_path.read_bytes())
    assert second.status()=='invalid_local_identity'
    second.receipt_path.unlink()
    with pytest.raises(ActivationError,match='LICENSE_ALREADY_ACTIVATED'):
        second.activate(issued['activation_key'])
    first.issuer=None
    assert first.status()=='activated'  # offline startup validates possession


def test_real_initial_access_adapter_bootstrap_and_invalidation(dsn,live_edge):
    issuer,transport,machine,ActivationError=live_edge
    first=machine('first')
    first.activate(issuer.issue()['activation_key'])
    from local_activation.initial_access import create_initial_access
    account={'auth':None}
    adapter=create_initial_access(first,administrator_state=lambda:account['auth'].administrator_state(),
        retry_action=lambda:None,native_transport=lambda request:True,origin='http://127.0.0.1:18080')
    app,auth=http_app(dsn,adapter)
    account['auth']=auth
    # Test-only IPC handoff. Production uses Edge/Gerenciador's peer-authenticated
    # listener and NativeTransport, never this direct private method call.
    handoff=adapter._new_session('fixture-service-user',adapter._seal)
    headers={'origin':'http://127.0.0.1:18080','cookie':handoff['cookie_name']+'='+handoff['cookie_value']}
    # http_app has a strict test origin; use the same trusted native origin here.
    # Build another app with identical auth methods but an allowed local origin.
    from fastapi import FastAPI,Depends
    from admin_auth.candidate import install_candidate_admin_auth
    native=FastAPI()
    def old_admin():
        return 'fixture'
    @native.get('/api/v1/p11/health',dependencies=[Depends(old_admin)])
    def health():
        return {}
    from cryptography.fernet import Fernet
    auth=install_candidate_admin_auth(native,dsn,protection_key=Fernet.generate_key(),
        allowed_origins=['http://127.0.0.1:18080'],initial_access=adapter)
    account['auth']=auth
    with TestClient(native,base_url='http://127.0.0.1:18080') as client:
        assert client.get('/api/v1/activation/status',headers=headers).json()['first_use_authorized']
        challenge=client.post(PREFIX+'/bootstrap',headers=headers,json={'username':'owner','password':PASSWORD}).json()
        begin=client.post(PREFIX+'/mfa/enrollment/begin',headers=headers,json={'challenge_token':challenge['challenge_token']}).json()
        response=client.post(PREFIX+'/mfa/enrollment/confirm',headers=headers,json={'challenge_token':challenge['challenge_token'],'code':code_now(dsn,begin['manual_key'])})
        assert response.status_code==200
        assert not adapter._sessions
        status=client.get('/api/v1/activation/status',headers=headers).json()
        assert status['administrator']=='ready' and not status['first_use_authorized']
        assert client.post(PREFIX+'/bootstrap',headers=headers,json={'username':'owner','password':PASSWORD}).status_code==403
