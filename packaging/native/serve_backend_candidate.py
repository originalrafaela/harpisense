"""Development-only HTTP candidate backed by a new disposable native cluster.

No installation, service registration, Docker, containment or preview mutation.
Credentials stay in the private test directory and are never printed.
"""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/p) for p in ('backend','backend/domain','genai','backend/delivery_tests','packaging/native')]


def main():
    import httpx
    import uvicorn
    from native_server.runtime import build_native_api
    from provision import write_private
    from test_backend_integration import BackendIntegrationTests
    candidate=BackendIntegrationTests
    candidate.setUpClass()
    try:
        auth_headers=dict(candidate.client.headers)
        candidate.client.close()
        candidate.server.should_exit=True;candidate.thread.join(10);candidate.sock.close()
        port=int(os.environ.get('HARPISENSE_REVIEW_PORT','18081'))
        if port not in (18081,18082):raise ValueError('UNSUPPORTED_REVIEW_PORT')
        candidate.sock=socket.socket();candidate.sock.bind(('127.0.0.1',port))
        panel='http://127.0.0.1:'+str(port)
        candidate.state['panel_url']=panel
        (candidate.private/'state.json').write_text(json.dumps(candidate.state),encoding='utf-8')
        origins=[panel,'http://127.0.0.1:5175','http://127.0.0.1:5176']
        # The existing Vite proxy strips /p11-api and preserves the frontend Host.
        # Reuse the native API composition directly; do not weaken the installed
        # wrapper's Host/origin restrictions for a development proxy.
        app=build_native_api(candidate.state,allowed_origins=origins,runtime_kind='development_candidate')
        candidate.server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
        candidate.thread=threading.Thread(target=candidate.server.run,kwargs={'sockets':[candidate.sock]},daemon=True)
        candidate.thread.start()
        deadline=time.monotonic()+20
        while not candidate.server.started and time.monotonic()<deadline:time.sleep(.05)
        if not candidate.server.started:raise RuntimeError('CANDIDATE_HTTP_START_FAILED')
        candidate.url=panel
        candidate.client=httpx.Client(base_url=candidate.url,headers=auth_headers,trust_env=False)
        candidate('test_00_http_contract_examples_bitnet_off_and_no_residual_xai').test_00_http_contract_examples_bitnet_off_and_no_residual_xai()
        health=candidate.client.get('/api/v1/p11/health');health.raise_for_status()
        # Leave the candidate at real first access for browser E2E. The native
        # cluster is private and fresh; never truncate an installed database.
        with candidate.store._connect() as conn:
            conn.execute('TRUNCATE hs_admin_first_access,hs_admin_password_reset_code,hs_admin_mfa_challenge, '
                'hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant,hs_admin_session,hs_admin_account,hs_admin_audit')
            conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        grant=app.state.admin_auth.issue_local_grant(ttl_seconds=900)
        grantfile=candidate.private/'browser-bootstrap.secret'
        write_private(grantfile,grant)
        # Test the exact proxy-origin behavior without printing request secrets.
        approved=candidate.client.post('/api/v1/admin-auth/login',headers={'Origin':origins[2],
            'Host':'127.0.0.1:5176'},json={'username':'not-created','password':'not-a-real-password'})
        if approved.status_code!=401:raise RuntimeError('PROXY_ORIGIN_CHECK_FAILED')
        denied=candidate.client.post('/api/v1/admin-auth/login',headers={'Origin':'https://invalid.example'},
            json={'username':'not-created','password':'not-a-real-password'})
        if denied.status_code!=403:raise RuntimeError('FOREIGN_ORIGIN_NOT_REJECTED')
        result={'url':panel,'api_base':candidate.url,'health_http':health.status_code,
            'incident_with_explanation':candidate.ident,'incident_without_explanation':candidate.no_xai,
            'incident_revision':1,'fixture_origin':'synthetic','runtime':'native Windows development',
            'installed':False,'real_executor_available':False,
            'allowed_origins':origins,'bootstrap_handoff_file':str(grantfile),
            'proxy_target':panel,'proxy_origin_check':approved.status_code,'foreign_origin_check':denied.status_code}
        (candidate.evidence/'live-backend.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='bootstrap_handoff_file'}),flush=True)
        while candidate.thread.is_alive():time.sleep(1)
    finally:
        candidate.tearDownClass()


if __name__=='__main__':main()
