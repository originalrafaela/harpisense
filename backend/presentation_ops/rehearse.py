"""Small real-HTTP compatibility rehearsal against the isolated restored database."""
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request
import urllib.error
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

from deploy import BASE, RELEASE, BACKUP, INSTALLATION, checked, config, migration_sql, sha


def main():
    os.umask(0o077)
    checked()
    if (RELEASE/'rehearsal.json').exists():
        (RELEASE/'rehearsal.json').rename(RELEASE/('rehearsal.previous-'+uuid4().hex+'.json'))
    sys.path[:0] = [str(RELEASE),str(RELEASE/'domain'),str(BASE)]
    from admin_auth.passwords import password_hash
    from config_manager.store import ConfigStore
    from config_manager.schema import Capabilities
    from deploy import CAPABILITY
    from snapshot import run, PG, receipt
    cluster, socket = BACKUP/'isolated-postgres', BACKUP/'socket'
    if subprocess.run([str(PG/'pg_ctl'),'-D',str(cluster),'status'],capture_output=True).returncode:
        run([PG/'pg_ctl','-D',cluster,'-l',BACKUP/'isolated-postgres.log',
             '-o',"-c listen_addresses='' -c unix_socket_directories="+str(socket)+' -p 55449','-w','start'])
    process = None
    try:
        admin = make_conninfo(host=str(socket),port=55449,user='harpiserver',dbname='postgres')
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute('DROP DATABASE presentation_restore WITH (FORCE)')
            conn.execute('CREATE DATABASE presentation_restore')
        run(['/usr/bin/pg_restore','--exit-on-error','--no-owner','--no-acl','--host',socket,
             '--port','55449','--username','harpiserver','--dbname','presentation_restore',BACKUP/'database.dump'],
            env={k:v for k,v in os.environ.items() if not k.startswith('PG')})
        dsn = make_conninfo(host=str(socket),port=55449,user='harpiserver',dbname='presentation_restore')
        with psycopg.connect(dsn) as conn:
            assert conn.info.host == str(socket) and conn.info.dbname == 'presentation_restore'
            before = receipt(conn)['public.projections']
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='presentation_runtime_probe'").fetchone():
                conn.execute("CREATE ROLE presentation_runtime_probe LOGIN")
            conn.execute('ALTER ROLE presentation_runtime_probe LOGIN')
            conn.execute('GRANT ALL ON ALL TABLES IN SCHEMA public TO presentation_runtime_probe')
            conn.execute('GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO presentation_runtime_probe')
            conn.execute(migration_sql('presentation_runtime_probe'))
            conn.execute('SET ROLE presentation_runtime_probe')
            assert not conn.execute("SELECT has_schema_privilege(current_user,'hs_config','CREATE')").fetchone()[0]
            conn.execute('RESET ROLE')
        password = secrets.token_urlsafe(28)
        with psycopg.connect(dsn) as conn:
            conn.execute('UPDATE hs_admin_account SET username=%s,password_hash=%s WHERE id=1',
                         ('rehearsal-admin',password_hash(password)))
            conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        dsn = make_conninfo(host=str(socket),port=55449,user='presentation_runtime_probe',dbname='presentation_restore')
        ConfigStore(lambda:psycopg.connect(dsn),Capabilities(revision=CAPABILITY)).provision_registry(INSTALLATION)
        os.environ.update(config())
        os.environ['HARPISENSE_DATABASE_URL'] = dsn
        source = (RELEASE/'app.candidate.py').read_text().replace(str(BASE/'presentation-state'),str(BACKUP/('rehearsal-state-'+uuid4().hex)))
        namespace = {'__name__':'candidate_rehearsal'}
        exec(compile(source,'candidate_rehearsal','exec'),namespace)
        app = namespace['app']
        import uvicorn
        def serve():
            uvicorn.run(app,host='127.0.0.1',port=18019,access_log=False,log_level='error')
        process = multiprocessing.get_context('fork').Process(target=serve)
        process.start()
        token = None
        def request(path,body=None,method=None,authenticated=True):
            headers={'Origin':'http://127.0.0.1:4174'}
            if authenticated and token: headers['Authorization']='Bearer '+token
            if body is not None: headers['Content-Type']='application/json'
            req=urllib.request.Request('http://127.0.0.1:18019/api/v1/'+path,
                data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
            try:
                with urllib.request.urlopen(req,timeout=15) as response:
                    raw=response.read(); return response.status,json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                return error.code,json.loads(error.read())
        for _ in range(40):
            try:
                status,_=request('p11/health',authenticated=False)
                break
            except urllib.error.URLError: time.sleep(.1)
        assert status==401
        status,login=request('admin-auth/login',{'username':'rehearsal-admin','password':password})
        assert status==200, ('login',status)
        token=login['access_token']
        checks=[]
        for path in ['p11/health','config/current','config/setup','config/catalog','config/presentation']:
            status,value=request(path); assert status==200,(path,status,value)
            checks.append(path)
        proposal={'schema_version':'1.0.0','record_type':'config.proposal','request_id':str(uuid4()),
            'idempotency_key':str(uuid4()),'expected_revision':0,'reason_code':'ADMIN_CHANGE',
            'document':{'schema_version':'1.0.0','record_type':'config.document',
                        'parameters':{'display_name':'Isolated compatibility rehearsal','timezone':'America/Sao_Paulo'}}}
        status,operation=request('config/proposals',proposal); assert status==200,(status,operation)
        path='config/proposals/'+operation['operation_id']
        status,value=request(path+'/validate',{'expected_revision':1}); assert status==200,(status,value)
        status,value=request(path+'/apply',{'expected_revision':1,'current_password':password})
        assert status==200 and value['status']=='APPLIED',(status,value)
        status,observed=request('config/presentation')
        assert observed['verified'] and observed['revision']==1 and observed['original_instant']=='2026-11-01T12:00:00Z'
        assert observed['displayed_instant']=='2026-11-01T09:00:00-03:00'
        status,value=request(path+'/apply',{'expected_revision':1,'current_password':password})
        assert status==200 and value['idempotent']
        status,current=request('config/current'); assert current['effective_revision']==1 and current['operational'] is False
        status,history=request('config/history'); assert [e['event'] for e in history]==['PROPOSED','VALIDATED','APPLYING','VERIFIED','APPLIED']
        status,_=request('admin-auth/logout',{},method='POST'); assert status==204
        status,_=request('config/presentation'); assert status==401
        with psycopg.connect(dsn) as conn:
            after=receipt(conn)['public.projections']
        assert before==after
        result=dict(candidate_sha256=sha(RELEASE/'app.candidate.py'),runtime='VM Python 3.14 / FastAPI 0.143.3',
            database='isolated restored presentation_restore',real_http=True,production_validation=False,
            checked_gets=checks,login_logout=True,unauthenticated_401=True,proposal_validation_apply=True,
            idempotency=True,consumption_verified=True,audit_verified=True,original_timestamps_preserved=True,
            projections_preserved=True,runtime_config_ddl=False)
        (RELEASE/'rehearsal.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:
        if process and process.pid:
            process.terminate(); process.join(10)
        run([PG/'pg_ctl','-D',cluster,'-m','fast','-w','stop'])


if __name__=='__main__':
    main()
