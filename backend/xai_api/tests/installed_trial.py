"""Isolated add-on trial on the identified installed Ubuntu VM, never production.

Uses installed venv, installed native runtime and a separate fixture database.
No checkout paths, model loading, broker call or existing service changes.
"""
import copy
import hashlib
import json
import os
import pwd
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

INSTALLED = Path('/opt/harpisense')
TRIAL = Path('/opt/harpisense-xai-trial')
DATABASE = 'xai_runtime_fixture_20261107'
URL = 'http://127.0.0.1:18089'
for directory in ('backend','backend/domain','genai','packaging/native'):
    sys.path.insert(0,str(INSTALLED/directory))
sys.path.insert(0,str(TRIAL/'site-packages'))

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from cryptography.fernet import Fernet
import pyotp
from admin_auth.mfa import MFAAdminAuth
from config_manager.store import ConfigStore, migrate
from config_manager.setup import migrate_setup
from native_server.runtime import build_native_app, capabilities
from delivery.postgres_store import PostgresStore
from types import SimpleNamespace
from xai_api import install_xai_api
from xai_api.native import install_on_native


def private(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')
    path.chmod(0o600)


def identity():
    if Path('/etc/hostname').read_text().strip()!='harpisense-ubuntu-reteste' or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!='2aab4d56-df4b-5ef3-ce71-f1fad2a99d21':
        raise RuntimeError('DISPOSABLE_INSTALLED_GUEST_NOT_CONFIRMED')
    if not Path(sys.executable).resolve().is_relative_to(INSTALLED):
        # A venv binary can be a symlink to /usr/bin; check the venv prefix instead.
        if not Path(sys.prefix).resolve().is_relative_to(INSTALLED):
            raise RuntimeError('INSTALLED_VENV_REQUIRED')


def prepare():
    identity()
    TRIAL.mkdir(mode=0o700,exist_ok=True)
    state_file=TRIAL/'state.json'
    if state_file.exists():
        return json.loads(state_file.read_text())
    original=json.loads(Path('/var/lib/harpisense/state.json').read_text())
    # The installed cluster's bootstrap credential is intentionally unavailable.
    # Start a distinct test cluster with the already installed PostgreSQL binary;
    # never weaken authentication or change the installed operational cluster.
    pgroot=Path('/var/lib/harpisense-xai-trial2')
    if pgroot.exists():
        raise RuntimeError('EXISTING_CLUSTER_WITHOUT_STATE_REFUSED')
    pgroot.mkdir(mode=0o700)
    owner=pwd.getpwnam('harpisense')
    os.chown(pgroot,owner.pw_uid,owner.pw_gid)
    password=secrets.token_urlsafe(32)
    password_file=pgroot/'init.secret'
    password_file.write_text(password); password_file.chmod(0o600)
    os.chown(password_file,owner.pw_uid,owner.pw_gid)
    def pg(arguments):
        result=subprocess.run(['runuser','-u','harpisense','--',*arguments],cwd='/tmp',capture_output=True)
        if result.returncode:
            raise RuntimeError('ISOLATED_POSTGRES_SETUP_FAILED')
    pg(['/usr/lib/postgresql/16/bin/initdb','-D',str(pgroot/'data'),'-U','xai_trial',
        '--pwfile='+str(password_file),'--auth=scram-sha-256'])
    password_file.unlink()
    pg(['/usr/lib/postgresql/16/bin/pg_ctl','-D',str(pgroot/'data'),'-l',str(pgroot/'server.log'),
        '-o','-h 127.0.0.1 -p 15439 -k '+str(pgroot),'-w','start'])
    parsed=dict(host='127.0.0.1',port='15439',user='xai_trial',password=password)
    with psycopg.connect(**dict(parsed,dbname='postgres'),autocommit=True) as conn:
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(DATABASE,)).fetchone():
            raise RuntimeError('EXISTING_FIXTURE_WITHOUT_MARKER_REFUSED')
        conn.execute('CREATE DATABASE xai_runtime_fixture_20261107 OWNER xai_trial')
    state=copy.deepcopy(original)
    state.update(dsn=make_conninfo(**dict(parsed,dbname=DATABASE)),installation_id=str(uuid.uuid4()),
                 key_file=str(TRIAL/'mfa.key'),panel_url=URL,technical_user='xai-trial-service',
                 technical_password=secrets.token_urlsafe(32),projection_token=secrets.token_urlsafe(32))
    state['mqtt'].update(username='xai-trial-unused',password=secrets.token_urlsafe(32))
    key=Fernet.generate_key(); (TRIAL/'mfa.key').write_bytes(key); (TRIAL/'mfa.key').chmod(0o600)
    with psycopg.connect(state['dsn']) as conn:
        if conn.info.dbname!=DATABASE:
            raise RuntimeError('FIXTURE_DATABASE_REQUIRED')
        for name in ('delivery/001_local.sql','delivery/002_operational_authority.sql',
                     'admin_auth/001_admin_auth.sql','admin_auth/002_admin_mfa.sql',
                     'admin_auth/003_password_reset.sql','native_server/001_mqtt_observer.sql'):
            path=INSTALLED/'backend'/name
            if path.is_file():
                conn.execute(path.read_text())
    connect=lambda:psycopg.connect(state['dsn'])
    migrate(connect); migrate_setup(connect)
    assets_migration=INSTALLED/'backend/config_manager/003_assets.sql'
    if assets_migration.is_file():
        with connect() as conn:
            conn.execute(assets_migration.read_text())
    config=ConfigStore(connect,capabilities(state)); config.provision_registry(state['installation_id'])
    store=PostgresStore(state['dsn'])
    for row in json.loads((TRIAL/'records.json').read_text()):
        store.insert(row['kind'],SimpleNamespace(id=row['id'],revision=row['revision'],source=row['source'],data=row['data']))
    store.insert('asset',SimpleNamespace(id='poste-1',revision=1,source='synthetic',data={
        'device_id':'poste-1','display_name':'Poste de ensaio XAI instalado'}))
    auth=MFAAdminAuth(state['dsn'],protection_key=key)
    password=secrets.token_urlsafe(32)
    token=auth.bootstrap(auth.issue_local_grant(),'xai-installed-owner',password)['challenge_token']
    enrollment=auth.begin_enrollment(token)
    full=auth.confirm_enrollment(token,pyotp.TOTP(enrollment['manual_key']).now())
    private(TRIAL/'access.json',{'username':'xai-installed-owner','password':password,
             'totp_key':enrollment['manual_key'],'access_token':full['access_token'],
             'url':URL+'/p11-api','fixture_only':True})
    private(state_file,state)
    return state


def serve():
    identity()
    state=json.loads((TRIAL/'state.json').read_text())
    if conninfo_to_dict(state['dsn'])['dbname']!=DATABASE:
        raise RuntimeError('FIXTURE_DATABASE_REQUIRED')
    app=build_native_app(state,INSTALLED/'frontend/dist')
    install_on_native(app,state)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18089,access_log=False,log_level='critical')


def run():
    state=prepare()
    access=json.loads((TRIAL/'access.json').read_text())
    checks=[]
    pidfile=TRIAL/'server.pid'
    if not pidfile.exists():
        log=(TRIAL/'server.log').open('ab')
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'serve'],cwd=TRIAL,
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
            env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')})
        pidfile.write_text(str(child.pid)); pidfile.chmod(0o600)
    def request(path,token=None):
        headers={'Authorization':'Bearer '+token} if token else {}
        req=urllib.request.Request(URL+'/p11-api/api/v1/p11'+path,headers=headers)
        try:
            response=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as exc:
            response=exc
        return response.status,json.loads(response.read())
    examples=json.loads((TRIAL/'examples.json').read_text())
    access.update(example_incident_id=examples['available']['incident_ref']['id'],
                  absent_incident_id=examples['absent']['incident_ref']['id'])
    private(TRIAL/'access.json',access)
    incident=examples['available']['incident_ref']['id']
    path='/incidents/'+incident+'/explanations'
    deadline=time.monotonic()+15
    while True:
        try:
            code,_=request(path)
            break
        except urllib.error.URLError:
            if time.monotonic()>deadline:
                raise RuntimeError('INSTALLED_HTTP_STARTUP_FAILED') from None
            time.sleep(.05)
    assert code==401; checks.append('no_session_refused_401')
    code,body=request(path,access['access_token'])
    assert code==200 and body['state']=='available'; checks.append('installed_native_mount_and_real_session')
    assert {a['model']['detector'] for a in body['analyses']}=={'random_forest','isolation_forest'}
    checks.append('calibrated_rf_and_if_persisted_records')
    for analysis in body['analyses']:
        assert analysis['asset']['display_name']=='Poste de ensaio XAI instalado'
        for explanation in analysis['explanations']:
            assert explanation['record']['method']=='SHAPLEY_PERMUTATION'
            assert explanation['coherence']['absolute_error']<=1e-8
            assert explanation['risk_mapping']['matches_recorded_factor'] is True
    checks.extend(['numeric_coherence_with_residual','installed_asset_projection_friendly_name'])
    absent=examples['absent']['incident_ref']['id']
    code,body=request('/incidents/'+absent+'/explanations',access['access_token'])
    assert code==200 and all(a['state']=='absent' for a in body['analyses']); checks.append('absence_explicit_incident_readable')
    with psycopg.connect(state['dsn']) as conn:
        version=conn.execute('SHOW server_version').fetchone()[0]
    import xai_api, native_server.runtime
    origins={'reader':str(Path(xai_api.__file__).resolve()),'native_runtime':str(Path(native_server.runtime.__file__).resolve()),
             'python_prefix':sys.prefix}
    assert origins['reader'].startswith(str(TRIAL)) and origins['native_runtime'].startswith(str(INSTALLED))
    checks.append('no_checkout_import_paths')
    report={'environment':'installed Ubuntu native runtime + installed isolated reader wheel',
            'postgresql':version,'checks':checks,'success':True,'origins':origins,
            'url':URL+'/p11-api','main_native_service_changed':False,'production_database_changed':False,
            'numerical_inference_in_installed_runtime':False,
            'reader_source_sha256':{name:hashlib.sha256((TRIAL/'site-packages/xai_api'/name).read_bytes()).hexdigest()
                                    for name in ('api.py','store.py','schemas.py','native.py')},
            'installed_build':json.loads((INSTALLED/'backend/native_server/build_info.json').read_text())
                              if (INSTALLED/'backend/native_server/build_info.json').is_file() else None,
            'native_runtime_sha256':hashlib.sha256(Path(native_server.runtime.__file__).read_bytes()).hexdigest(),
            'limitation':'Records produced by real calibrated estimators in development; installed trial validates persisted reads, authentication and numerical coherence only.'}
    private(TRIAL/'result.json',report)
    print(json.dumps(report))


def restart():
    pidfile=TRIAL/'server.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text())
        command=Path('/proc')/str(pid)/'cmdline'
        if command.exists():
            args=command.read_bytes()
            if b'/opt/harpisense-xai-trial/installed_trial.py' not in args or b'serve' not in args:
                raise RuntimeError('UNEXPECTED_TRIAL_PROCESS_REFUSED')
            os.kill(pid,signal.SIGTERM)
            time.sleep(1)
        pidfile.unlink()
    run()


if __name__=='__main__':
    {'run':run,'serve':serve,'restart':restart}[sys.argv[1]]()
