import copy
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

import httpx
import pandas as pd
import psycopg
import pyotp
import uvicorn
from cryptography.fernet import Fernet

from config_manager.schema import Capabilities
from config_manager.setup import migrate_setup
from config_manager.store import migrate, ConfigStore
from config_manager.assets import AssetStore
from delivery.app import build_candidate_app
from detection_composition.store import CompositionStore
from harpisense_contracts import validate_links
from harpisense_xai.core import explain, detection, VERSION
from fixtures import models, process, window, NOW

ROOT = Path(__file__).resolve().parents[3]


class XAIHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['DATABASE_URL']
        with psycopg.connect(cls.dsn) as conn:
            if conn.info.dbname!='detection_composition_test':
                raise RuntimeError('Disposable detection_composition_test only')
            conn.execute((ROOT/'backend/delivery/001_local.sql').read_text())
            if not conn.execute("SELECT to_regclass('hs_admin_schema_version')").fetchone()[0]:
                conn.execute((ROOT/'backend/admin_auth/001_admin_auth.sql').read_text())
            conn.execute((ROOT/'backend/admin_auth/002_admin_mfa.sql').read_text())
            conn.execute((ROOT/'backend/admin_auth/003_password_recovery.sql').read_text())
        cls.connect = staticmethod(lambda: psycopg.connect(cls.dsn))
        migrate(cls.connect); migrate_setup(cls.connect)
        with cls.connect() as conn:
            conn.execute((ROOT/'backend/config_manager/003_assets.sql').read_text())
            conn.execute('TRUNCATE projections,hs_admin_password_code,hs_admin_password_grant,hs_admin_session, '
                         'hs_admin_mfa_challenge,hs_admin_recovery_code,hs_admin_mfa,hs_admin_local_grant,hs_admin_account,hs_admin_audit')
            conn.execute("UPDATE hs_admin_throttle SET failures=0,blocked_until='-infinity'")
        cls.temp = tempfile.TemporaryDirectory()
        cls.args, cls.refs = models(Path(cls.temp.name))
        cls.store = CompositionStore(cls.dsn)
        cls.first = process(cls.store, cls.args, cls.refs)
        cls.second = process(cls.store, cls.args, cls.refs, 2)
        cls.without = process(cls.store, cls.args, {}, 3)
        cls.normal = process(cls.store, cls.args, cls.refs, 4, 'normal')
        os.environ['HARPISENSE_ADMIN_USER'] = 'fixture-service'
        os.environ['HARPISENSE_ADMIN_PASSWORD'] = 'fixture-technical-only'
        cls.key = Fernet.generate_key()
        cls.app = build_candidate_app(installation_id='xai-fixture', capabilities=Capabilities(revision='xai-fixture'),
             allowed_origins=['http://127.0.0.1:18089'], protection_key=cls.key)
        config = ConfigStore(cls.connect, Capabilities(revision='xai-fixture'))
        config.provision_registry('xai-fixture')
        cls.config = config
        with cls.connect() as conn:
            conn.execute("DELETE FROM hs_config.asset WHERE installation_id='xai-fixture'")
        AssetStore(config, {('device','lighting'):set()}).save('xai-fixture','poste-1',{'expected_revision':0,
            'document':dict(display_name='Poste de ensaio XAI',asset_type='device',profile='lighting',bindings={})})
        auth = cls.app.state.admin_auth
        grant = auth.issue_local_grant()
        challenge = auth.bootstrap(grant, 'xai-fixture-owner', 'isolated-xai-password-only')['challenge_token']
        enrollment = auth.begin_enrollment(challenge)
        cls.secret = enrollment['manual_key']
        cls.token = auth.confirm_enrollment(challenge, pyotp.TOTP(cls.secret).now())['access_token']
        cls.sock = socket.socket(); cls.sock.bind(('127.0.0.1',0))
        cls.url = f'http://127.0.0.1:{cls.sock.getsockname()[1]}'
        cls.server = uvicorn.Server(uvicorn.Config(cls.app, log_level='critical', access_log=False))
        cls.thread = threading.Thread(target=cls.server.run,kwargs={'sockets':[cls.sock]},daemon=True)
        cls.thread.start()
        deadline = time.monotonic()+10
        while not cls.server.started and time.monotonic()<deadline:
            time.sleep(.01)
        if not cls.server.started:
            raise RuntimeError('HTTP startup failed')
        cls.client = httpx.Client(base_url=cls.url, headers={'Authorization':'Bearer '+cls.token})

    @classmethod
    def tearDownClass(cls):
        cls.client.close(); cls.server.should_exit=True; cls.thread.join(10); cls.sock.close()
        cls.temp.cleanup()

    def get_incident(self, result):
        response = self.client.get('/api/v1/p11/incidents/'+result['incident']['incident_id']+'/explanations')
        self.assertEqual(response.status_code,200, response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
        from jsonschema import Draft202012Validator
        schema=self.client.get('/openapi.json').json()
        Draft202012Validator({'$ref':'#/components/schemas/XAIIncident','components':schema['components']}).validate(response.json())
        return response.json()

    def test_atomic_composition_rolls_back_xai_failure(self):
        with self.connect() as conn:
            before=conn.execute('SELECT count(*) FROM projections').fetchone()[0]
            conn.execute("CREATE FUNCTION hs_xai_fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ "
                         "BEGIN IF NEW.kind='xai' THEN RAISE EXCEPTION 'fixture XAI write failure'; END IF; RETURN NEW; END $$")
            conn.execute('CREATE TRIGGER hs_xai_fixture_fail BEFORE INSERT ON projections FOR EACH ROW EXECUTE FUNCTION hs_xai_fixture_fail()')
        try:
            with self.assertRaises(psycopg.Error):
                process(self.store,self.args,self.refs,99)
        finally:
            with self.connect() as conn:
                conn.execute('DROP TRIGGER hs_xai_fixture_fail ON projections')
                conn.execute('DROP FUNCTION hs_xai_fixture_fail()')
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM projections').fetchone()[0],before)

    def test_calibrated_rf_if_and_risk_transform_boundaries(self):
        view = self.get_incident(self.first)
        self.assertEqual(view['state'],'available')
        by_detector = {a['model']['detector']:a for a in view['analyses']}
        for name, analysis in by_detector.items():
            self.assertEqual(analysis['asset']['display_name'],'Poste de ensaio XAI')
            self.assertEqual(analysis['state'],'available')
            result = analysis['explanations'][0]
            e = result['record']
            self.assertEqual(e['method'],'SHAPLEY_PERMUTATION')
            self.assertEqual(e['explainer_version'],VERSION)
            self.assertAlmostEqual(e['base_value']+math.fsum(c['contribution'] for c in e['contributions'])+e['additivity_residual'],e['output_value'],delta=1e-8)
            self.assertTrue(result['risk_mapping']['matches_recorded_factor'])
            self.assertFalse(result['coherence']['causality_or_detector_accuracy_proven'])
            self.assertTrue(any(abs(c['contribution'])>1e-8 for c in e['contributions']))
        rf = by_detector['random_forest']['explanations'][0]
        label = rf['record']['target']['class_label']
        self.assertEqual(label,'C01')
        self.assertEqual(rf['record']['target']['output'],'CALIBRATED_CLASS_PROBABILITY')
        classification = by_detector['random_forest']['operational_outputs']['classification']
        self.assertAlmostEqual(rf['record']['output_value'],classification['probabilities'][label],delta=1e-6)
        from harpisense_xai.core import load_model
        bundle = load_model(self.args['rf_directory'])
        vector = pd.DataFrame([[self.first['detections'][0]['features'][f] for f in bundle['features']]],columns=bundle['features'])
        raw = float(bundle['raw_model'].predict_proba(vector)[0][list(bundle['raw_model'].classes_).index(label)])
        self.assertGreater(abs(raw-rf['record']['output_value']),1e-6)
        self.assertEqual(rf['risk_mapping']['scale'],100)
        isolation = by_detector['isolation_forest']['explanations'][0]
        self.assertEqual(isolation['record']['target'],{'output':'ANOMALY_SCORE','class_label':None})
        self.assertEqual(isolation['risk_mapping']['state'],'nonlinear_transform_not_additively_mapped')
        if_bundle=load_model(self.args['if_directory'])
        if_vector=pd.DataFrame([[self.first['detections'][1]['features'][f] for f in if_bundle['features']]],columns=if_bundle['features'])
        self.assertAlmostEqual(isolation['record']['output_value'],float(-if_bundle['model'].score_samples(if_vector)[0]),delta=1e-6)

    def test_same_asset_different_incidents_and_observations_never_cross(self):
        a,b = self.get_incident(self.first), self.get_incident(self.second)
        ids_a={v['detection_id'] for v in a['analyses']}; ids_b={v['detection_id'] for v in b['analyses']}
        self.assertFalse(ids_a & ids_b)
        self.assertEqual({e['record']['detection_id'] for v in a['analyses'] for e in v['explanations']},ids_a)
        detection = self.first['detections'][0]
        path='/api/v1/p11/detections/'+detection['detection_id']+'/explanations'
        wrong=self.client.get(path,params={'incident_id':self.second['incident']['incident_id'],'incident_revision':1})
        self.assertEqual(wrong.status_code,404)
        window=detection['window']
        observation=self.client.get('/api/v1/p11/observations/'+window['collection_session_id']+'/'+window['window_id']+'/explanations').json()
        self.assertEqual({v['detection_id'] for v in observation['analyses']},ids_a)

    def test_absence_does_not_prevent_incident_read_and_get_never_writes(self):
        with self.connect() as conn:
            before=conn.execute('SELECT count(*),md5(string_agg(data::text,\'\' ORDER BY kind,id,revision)) FROM projections').fetchone()
        response=self.get_incident(self.without)
        self.assertTrue(all(v['state']=='absent' and v['explanations']==[] for v in response['analyses']))
        self.assertEqual(self.client.get('/api/v1/p11/incident/'+self.without['incident']['incident_id']+'/history').status_code,200)
        self.get_incident(self.first)
        with self.connect() as conn:
            after=conn.execute('SELECT count(*),md5(string_agg(data::text,\'\' ORDER BY kind,id,revision)) FROM projections').fetchone()
        self.assertEqual(before,after)

    def test_unauthenticated_and_technical_accounts_are_refused(self):
        paths=['/api/v1/p11/incidents/'+self.first['incident']['incident_id']+'/explanations',
               '/api/v1/p11/detections/'+self.first['detections'][0]['detection_id']+'/explanations',
               '/api/v1/p11/observations/session/window/explanations']
        with httpx.Client(base_url=self.url) as client:
            for path in paths:
                self.assertEqual(client.get(path).status_code,401)
                self.assertEqual(client.get(path,auth=('fixture-service','fixture-technical-only')).status_code,401)

    def test_normal_class_complement_is_explicit_and_numerically_coherent(self):
        view=self.get_incident(self.normal)
        rf=next(a for a in view['analyses'] if a['model']['detector']=='random_forest')['explanations'][0]
        e=rf['record']; mapping=rf['risk_mapping']
        self.assertEqual(e['target']['class_label'],'normal')
        self.assertEqual(mapping['scale'],-100)
        transformed=100-100*e['base_value']+math.fsum(-100*c['contribution'] for c in e['contributions'])-100*e['additivity_residual']
        self.assertAlmostEqual(transformed,mapping['factor_value'],delta=1e-6)

    def test_tampered_explanation_is_rejected_without_guessing(self):
        bad=copy.deepcopy(self.first['explanations'][0]); bad['explanation_id']='exp-invalid-fixture'
        bad['detection_id']=self.without['detections'][0]['detection_id']
        self.store.insert('xai',SimpleNamespace(id=bad['explanation_id'],revision=1,source='synthetic',data=bad))
        try:
            view=self.get_incident(self.without)
            target=next(a for a in view['analyses'] if a['detection_id']==bad['detection_id'])
            self.assertEqual(target['state'],'invalid')
            self.assertEqual(target['explanations'],[])
        finally:
            with self.connect() as conn:
                conn.execute("DELETE FROM projections WHERE kind='xai' AND id=%s",(bad['explanation_id'],))

    def test_export_sanitized_examples_and_installed_fixture(self):
        destination=os.getenv('XAI_EVIDENCE_DIR')
        if not destination:
            self.skipTest('Explicit evidence directory not provided')
        out=Path(destination); out.mkdir(parents=True,exist_ok=True)
        examples={'input_origin':'synthetic','real_estimators':True,'statistical_validation':False,
                  'available':self.get_incident(self.first),'absent':self.get_incident(self.without),
                  'normal':self.get_incident(self.normal)}
        (out/'examples.json').write_text(json.dumps(examples,indent=2,ensure_ascii=False,allow_nan=False))
        with self.connect() as conn:
            rows=conn.execute('SELECT kind,id,revision,source,data FROM projections ORDER BY kind,id,revision').fetchall()
        (out/'records.json').write_text(json.dumps([dict(zip(('kind','id','revision','source','data'),r)) for r in rows],ensure_ascii=False,allow_nan=False))
        (out/'references.json').write_text(json.dumps(self.refs,ensure_ascii=False,allow_nan=False))
        manifest={'rf_sha256':self.args['rf_sha256'],'if_sha256':self.args['if_sha256'],
                  'references':{k:v['reference_id'] for k,v in self.refs.items()},
                  'core_sha256':hashlib.sha256((ROOT/'backend/domain/harpisense_xai/core.py').read_bytes()).hexdigest()}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2))


if __name__=='__main__':
    unittest.main()
