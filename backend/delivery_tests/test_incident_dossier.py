"""Real HTTP/session/MFA/PostgreSQL in a new native disposable cluster. No Docker."""
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[2]
for directory in ('backend','backend/domain','genai','packaging/native'):
    sys.path.insert(0,str(ROOT/directory))
import httpx
import pyotp
import uvicorn
from provision import create_state,initialize_database,prepare_database,run
from delivery.postgres_store import PostgresStore
from delivery.projections import Record
from delivery.app import build_app
from delivery.control_store import PostgresControls
from delivery.controls import Controls,Rejected
from delivery.operational_queue import OperationalQueue,SOURCES
from delivery.incident_dossier import install_incident_api
from admin_auth.candidate import install_candidate_admin_auth


class IncidentDossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg=Path(os.environ.get('HARPISENSE_NATIVE_PG_BIN','D:/Programas/PostgreSQL/bin'))
        if not (cls.pg/'initdb.exe').is_file():raise RuntimeError('Native PostgreSQL binaries required')
        cls.private=ROOT/'.native-test'/('incident-dossier-'+uuid.uuid4().hex)
        cls.state=create_state(cls.private)
        probe=socket.socket();probe.bind(('127.0.0.1',0));pgport=probe.getsockname()[1];probe.close()
        cls.state['dsn']=cls.state['dsn'].replace(':15432/',':'+str(pgport)+'/')
        (cls.private/'state.json').write_text(json.dumps(cls.state))
        run([cls.pg/'initdb.exe','-D',cls.private/'postgres','-U','native_installer','--encoding=UTF8',
             '--auth=scram-sha-256','--pwfile',cls.private/'pg-init.secret'])
        with (cls.private/'postgres/postgresql.conf').open('a') as out:
            out.write(f"\nlisten_addresses='127.0.0.1'\nport={pgport}\n")
        run([cls.pg/'pg_ctl.exe','-D',cls.private/'postgres','-l',cls.private/'postgres.log','-w','start'])
        try:
            initialize_database(cls.state,cls.private);prepare_database(cls.private/'state.json')
            cls.store=PostgresStore(cls.state['dsn'])
            with cls.store._connect() as conn:
                conn.execute((ROOT/'backend/delivery/003_incident_assessment.sql').read_text())
            records=json.loads((ROOT/'docs/evidence/shap-library-20261107/synthetic-records.json').read_text())
            # Development fixtures contain real library outputs on artificial
            # inputs. Their origin remains explicitly synthetic in P11.
            for row in records:row['source']='synthetic'
            for row in records:cls.store.insert(row['kind'],Record(**{k:row[k] for k in ('id','revision','source','data')}))
            cls.ident=next(r['id'] for r in records if r['kind']=='incident')
            cls.sock=socket.socket();cls.sock.bind(('127.0.0.1',0))
            cls.url='http://127.0.0.1:'+str(cls.sock.getsockname()[1])
            os.environ.update(DATABASE_URL=cls.state['dsn'],HARPISENSE_ADMIN_USER=cls.state['technical_user'],
                              HARPISENSE_ADMIN_PASSWORD=cls.state['technical_password'])
            app=build_app()
            install_candidate_admin_auth(app,cls.state['dsn'],protection_key=Path(cls.state['key_file']).read_bytes(),
                                         allowed_origins=[cls.url])
            cls.interface=install_incident_api(app,cls.store,cls.state['installation_id'])
            auth=app.state.admin_auth
            challenge=auth.bootstrap(auth.issue_local_grant(),'dossier-owner',secrets.token_urlsafe(32))['challenge_token']
            enrollment=auth.begin_enrollment(challenge)
            token=auth.confirm_enrollment(challenge,pyotp.TOTP(enrollment['manual_key']).now())['access_token']
            cls.server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
            cls.thread=threading.Thread(target=cls.server.run,kwargs={'sockets':[cls.sock]},daemon=True)
            cls.thread.start()
            deadline=time.monotonic()+15
            while not cls.server.started and time.monotonic()<deadline:time.sleep(.05)
            if not cls.server.started:raise RuntimeError('HTTP startup failed')
            cls.client=httpx.Client(base_url=cls.url,headers={'Authorization':'Bearer '+token},trust_env=False)
            cls.path='/api/v1/p11/incidents/'+cls.ident
            cls.controls=Controls(PostgresControls(cls.state['dsn']),OperationalQueue())
        except Exception:
            run([cls.pg/'pg_ctl.exe','-D',cls.private/'postgres','-w','stop','-m','fast'])
            raise

    @classmethod
    def tearDownClass(cls):
        cls.client.close();cls.server.should_exit=True;cls.thread.join(10);cls.sock.close()
        run([cls.pg/'pg_ctl.exe','-D',cls.private/'postgres','-w','stop','-m','fast'])

    def test_read_exact_linked_dossier_without_bitnet(self):
        response=self.client.get(self.path+'/dossier?incident_revision=1')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
        body=response.json();self.assertEqual(body['incident_ref'],{'id':self.ident,'revision':1})
        self.assertEqual(body['incident_card']['defense_execution']['state'],'missing')
        self.assertTrue(body['technical_cards'])
        self.assertEqual(body['incident_card']['operational_mode']['value'],'M1')
        for card in body['technical_cards']:
            self.assertEqual(card['explanation']['record']['output_value'],card['result']['value'])
            self.assertEqual(card['source'],'persisted_xai')
        self.assertEqual(self.client.get(self.path+'/dossier?incident_revision=999').status_code,404)
        self.assertEqual(httpx.get(self.url+self.path+'/dossier',trust_env=False).status_code,401)

    def test_assessment_is_separate_from_profile_approval_execution(self):
        before=self.controls.get()
        original=self.store.history('incident',self.ident)
        payload={'incident_revision':1,'assessment':'confirmed','reason':'Evidências do ensaio sintético revisadas'}
        response=self.client.post(self.path+'/assessments',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json();event=result['assessment']
        self.assertEqual(event['actor'],'dossier-owner');self.assertEqual(event['origin'],'synthetic')
        self.assertFalse(any(result['side_effects'].values()))
        self.assertEqual(self.controls.get()['value'],before['value'])
        self.assertEqual(self.store.history('incident',self.ident),original)
        self.assertEqual(self.client.post(self.path+'/assessments',json={**payload,'actor':'forged'}).status_code,422)
        self.assertEqual(self.client.post(self.path+'/assessments',json={**payload,'incident_revision':99}).status_code,409)
        with self.controls.repository.transaction() as tx:
            for source in SOURCES:
                current=tx.conn.execute('SELECT revision FROM hs_operational_authority WHERE source=%s',(source,)).fetchone()
                OperationalQueue().report(tx,source,(current[0]+1) if current else 1,[])
        self.assertFalse(self.controls.get()['pending']['blockers'])
        # Assessment is a historical administrative fact, not a live attack.
        self.assertTrue(self.controls.get()['change_allowed'])
        dossier=self.client.get(self.path+'/dossier?incident_revision=1').json()
        self.assertEqual(dossier['incident_card']['attack_assessment']['state'],'confirmed')
        self.assertEqual(dossier['incident_card']['defense_execution']['state'],'missing')
        with self.store._connect() as conn:
            self.assertGreater(conn.execute("SELECT count(*) FROM hs_control_audit WHERE operation='INCIDENT_ASSESSED'").fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM hs_simulation').fetchone()[0],0)

    def test_visibility_loss_retains_known_active_cases(self):
        with self.controls.repository.transaction() as tx:
            current=tx.conn.execute("SELECT revision FROM hs_operational_authority WHERE source='anomaly'").fetchone()
            OperationalQueue().report(tx,'anomaly',(current[0]+1) if current else 1,[{'id':'still-active','state':'ACTIVE'}])
            tx.conn.execute("UPDATE hs_operational_authority SET observed_at=clock_timestamp()-interval '1 hour' WHERE source='anomaly'")
        pending=self.controls.get()['pending']
        self.assertFalse(pending['reliable'])
        case=next(b for b in pending['blockers'] if b['id']=='anomaly:still-active')
        self.assertFalse(case['fresh']);self.assertEqual(pending['cases']['known_active_count'],1)


if __name__=='__main__':unittest.main()
