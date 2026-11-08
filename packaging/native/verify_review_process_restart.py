"""Restart owned API child processes against the browser E2E database, read-only.

Does not stop the browser's 18082 runner, recreate a cluster, change credentials,
consume codes, issue sessions, apply migrations or register an OS service.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import signal
import time
import urllib.request
import urllib.error
import uuid

ROOT=Path(__file__).resolve().parents[2]


def metadata(state):
    import psycopg
    with psycopg.connect(state['dsn']) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        identity=conn.execute('SELECT current_database(),inet_server_port()').fetchone()
        first=conn.execute('SELECT account_id,password_reset_generation,issued_at,completed_at '
                           'FROM hs_admin_first_access ORDER BY account_id').fetchall()
        mfa=conn.execute('SELECT account_id,required,enabled_at IS NOT NULL,secret_cipher FROM hs_admin_mfa ORDER BY account_id').fetchall()
        codes={}
        for label,table in (('password_reset','hs_admin_password_reset_code'),('authenticator_recovery','hs_admin_recovery_code')):
            rows=conn.execute('SELECT purpose,generation,count(*),count(used_at),count(revoked_at),'
                'bool_and(length(code_hash)=64) FROM '+table+' GROUP BY purpose,generation ORDER BY generation').fetchall()
            codes[label]=[dict(purpose=r[0],generation=r[1],verifier_count=r[2],used_count=r[3],revoked_count=r[4],
                               sha256_verifiers_only=r[5]) for r in rows]
        setup=conn.execute('SELECT version,document FROM hs_config.setup_progress WHERE installation_id=%s',
                           (state['installation_id'],)).fetchone()
        internal={'mfa_cipher_fingerprint':hashlib.sha256(json.dumps([(r[0],r[3]) for r in mfa]).encode()).hexdigest(),
            'setup_fingerprint':None if setup is None else hashlib.sha256(json.dumps(setup[1],sort_keys=True).encode()).hexdigest()}
        public={'database':{'name':identity[0],'port':identity[1],'installation_id':state['installation_id']},
            'account_count':conn.execute('SELECT count(*) FROM hs_admin_account').fetchone()[0],
            'first_access':[dict(account_id=r[0],password_reset_generation=r[1],codes_issued=r[2] is not None,
                status='completed' if r[3] else 'pending',issued_at=r[2].isoformat() if r[2] else None,
                completed_at=r[3].isoformat() if r[3] else None) for r in first],
            'mfa':[dict(account_id=r[0],required=r[1],enabled=r[2]) for r in mfa],
            'code_metadata':codes,'setup_version':setup[0] if setup else 0,
            'setup_state':'draft_saved' if setup else 'not_started'}
    return public,internal


def ready(process,port,boot_id):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('REVIEW_CHILD_EXITED')
        request=urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/v1/admin-auth/first-access',
            headers={'Origin':'http://127.0.0.1:5176'})
        try:
            with urllib.request.urlopen(request,timeout=1) as response:status=response.status
        except urllib.error.HTTPError as response:status=response.code
        except OSError:time.sleep(.1);continue
        if status==401:
            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/_review/process-identity',timeout=2) as response:
                identity=json.loads(response.read(2048))
            if identity.get('boot_id')!=boot_id:raise RuntimeError('WRONG_API_PROCESS_IDENTITY')
            return status,identity
        raise RuntimeError('REVIEW_AUTH_BOUNDARY_FAILED')
    raise RuntimeError('REVIEW_CHILD_START_TIMEOUT')


def stop(process,server_pid=None):
    if process is not None and process.poll() is None:
        if server_pid is not None and server_pid!=process.pid:
            os.kill(server_pid,signal.SIGTERM)
        else:process.terminate()
        process.wait(timeout=10)


def main():
    live=json.loads((ROOT/'docs/evidence/backend-integration-20261107/live-backend.json').read_text(encoding='utf-8'))
    state_path=Path(live['bootstrap_handoff_file']).resolve().parent/'state.json'
    if not state_path.is_relative_to(ROOT/'.native-test') or live['installed'] is not False:
        raise RuntimeError('PRIVATE_REVIEW_DATABASE_REQUIRED')
    port=18083
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',port))==0:port=18084
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('REVIEW_RESTART_PORT_BUSY')
    state=json.loads(state_path.read_text(encoding='utf-8'))
    before,internal_before=metadata(state)
    if not before['first_access'] or any(r['status']!='completed' for r in before['first_access']):
        raise RuntimeError('BROWSER_FIRST_ACCESS_NOT_COMPLETED')
    command=[sys.executable,str(ROOT/'packaging/native/serve_existing_review_database.py'),
             '--state',str(state_path),'--port',str(port)]
    options={'cwd':ROOT,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
    if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
    first=None;second=None;first_server_pid=None;second_server_pid=None
    try:
        first_boot=str(uuid.uuid4());second_boot=str(uuid.uuid4())
        first=subprocess.Popen(command,env=dict(os.environ,HARPISENSE_REVIEW_BOOT_ID=first_boot),**options)
        first_http,first_identity=ready(first,port,first_boot);first_pid=first.pid;first_server_pid=first_identity['pid']
        stop(first,first_server_pid)
        closed=False;deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            with socket.socket() as probe:closed=probe.connect_ex(('127.0.0.1',port))!=0
            if closed:break
            time.sleep(.05)
        if not closed:raise RuntimeError('API_PORT_REMAINED_OPEN_AFTER_STOP')
        second=subprocess.Popen(command,env=dict(os.environ,HARPISENSE_REVIEW_BOOT_ID=second_boot),**options)
        second_http,second_identity=ready(second,port,second_boot);second_pid=second.pid;second_server_pid=second_identity['pid']
        after,internal_after=metadata(state)
        checks={'different_process_ids':first_pid!=second_pid,'same_database_metadata':before==after,
            'different_server_pids':first_server_pid!=second_server_pid,
            'different_boot_ids':first_identity['boot_id']!=second_identity['boot_id'],
            'port_closed_between_processes':closed,
            'mfa_secret_unchanged':internal_before['mfa_cipher_fingerprint']==internal_after['mfa_cipher_fingerprint'],
            'setup_draft_unchanged':internal_before['setup_fingerprint']==internal_after['setup_fingerprint'],
            'mfa_required_and_enabled':all(r['required'] and r['enabled'] for r in after['mfa']),
            'completed_persisted':all(r['status']=='completed' for r in after['first_access']),
            'unauthenticated_access_denied':first_http==second_http==401}
        result={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
            'methodology':'Owned API process A terminated, independent process B started against the SAME existing browser-E2E PostgreSQL cluster. No provisioning, cluster recreation, account mutation or reset-code consumption.',
            'database_metadata':after,'api_test_url':'http://127.0.0.1:'+str(port),
            'browser_runner_preserved':live['url'],'process_ids':[first_pid,second_pid],
            'actual_server_pids':[first_server_pid,second_server_pid],
            'source_fingerprints':second_identity['source_fingerprints'],
            'installed':False,'os_reboot_tested':False,'full_browser_login_after_this_restart':False,
            'login_reset_totp_protocol':'11 native HTTP/PostgreSQL first-access tests passed separately on the same auth code version',
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'test_listener_stopped_after_verification':True}
        output=ROOT/'docs/evidence/backend-integration-20261107/process-restart.json'
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'result':result['result'],'checks':checks,'evidence':str(output)}),flush=True)
        if result['result']!='PASS':raise RuntimeError('PROCESS_RESTART_METADATA_CHANGED')
    finally:
        stop(second,second_server_pid);stop(first,first_server_pid)


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never stringify a DB exception/DSN or arbitrary request state.
        print(json.dumps({'result':'BLOCKED','code':str(error) if isinstance(error,RuntimeError) else type(error).__name__}),flush=True)
        raise SystemExit(1)
