"""Authenticated HTTP and native PostgreSQL; fixtures are explicitly synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/domain'),str(ROOT/'genai'),str(Path(__file__).parent)]
import test_incident_dossier as fixture
from delivery.activity import ActivityProducer,write_decision_snapshot
from delivery.projections import Record
from delivery.operational_queue import SOURCES
from harpisense_contracts import fingerprint


class BackendIntegrationTests(fixture.IncidentDossierTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evidence=ROOT/'docs/evidence/backend-integration-20261107'
        cls.evidence.mkdir(parents=True,exist_ok=True)
        original=cls.store.history('incident',cls.ident)[0]['data']
        no_xai=deepcopy(original);no_xai['incident_id']='inc-development-without-xai'
        no_xai['explanation_refs']=[]
        cls.store.insert('incident',Record(id=no_xai['incident_id'],revision=1,source='synthetic',data=no_xai))
        cls.no_xai=no_xai['incident_id']

    def refresh(self,source,items):
        with self.controls.repository.transaction() as tx:
            previous=tx.conn.execute('SELECT revision FROM hs_operational_authority WHERE source=%s',(source,)).fetchone()
            return ActivityProducer().publish(tx,source=source,source_revision=1 if previous is None else previous[0]+1,
                    items=items,origin='trusted-service',complete=True)

    def test_00_http_contract_examples_bitnet_off_and_no_residual_xai(self):
        full=self.client.get(self.path+'/dossier?incident_revision=1')
        self.assertEqual(full.status_code,200,full.text)
        value=full.json();self.assertEqual(value['incident_card']['origin']['value'],'synthetic')
        methods={card['method'] for card in value['technical_cards']}
        self.assertEqual(methods,{'SHAP_TREE_EXPLAINER','SHAP_PERMUTATION_EXPLAINER'})
        for card in value['technical_cards']:
            record=card['explanation']['record']
            self.assertTrue(card['explanation']['in_incident_explanation_refs'])
            self.assertEqual(record['output_value'],card['result']['value'])
            self.assertEqual(record['base_value'],card['reference']['value'])
            self.assertEqual({c['feature']:c['value'] for c in record['contributions']},
                next(r['data']['features'] for r in value['records']['detection'] if r['id']==card['detection_id']))
        empty=self.client.get('/api/v1/p11/incidents/'+self.no_xai+'/dossier?incident_revision=1')
        self.assertEqual(empty.status_code,200,empty.text)
        self.assertEqual(empty.json()['technical_cards'],[])
        self.assertEqual(empty.json()['latest_explanations'],[])
        self.assertTrue(any(m['reason']=='EXPLANATION_NOT_AVAILABLE' for m in empty.json()['missing_links']))
        settings=self.client.get('/api/v1/security/settings/mode/default').json()
        refused=self.client.put('/api/v1/security/settings/mode/default',json={
            'value':{**settings['value'],'autonomy_mode':2},'expected_revision':settings['revision'],
            'reason':'Ensaio explícito de recusa por cobertura desconhecida'})
        self.assertEqual(refused.status_code,409,refused.text)
        self.assertEqual(refused.json()['detail']['current']['value'],settings['value'])
        for name,response in [('incident-with-explanation',full),('incident-without-explanation',empty),
                              ('profile-change-refused',refused)]:
            (self.evidence/(name+'.json')).write_text(json.dumps(response.json(),indent=2,ensure_ascii=False),encoding='utf-8')
        (self.evidence/'http-check.json').write_text(json.dumps({'runtime':'native Windows development',
            'url_tested':self.url,'authenticated_http':True,'database':'native PostgreSQL',
            'bitnet_called':False,'fixture_origin':'synthetic','installed_acceptance':False,
            'server_lifetime':'test only; stopped after tests','cases':[200,200,409]},indent=2),encoding='utf-8')

    def test_01_trial_does_not_refresh_operational_authority(self):
        with self.controls.repository.transaction() as tx:
            before=tx.conn.execute('SELECT source,revision,items FROM hs_operational_authority ORDER BY source').fetchall()
            result=ActivityProducer().publish(tx,source='incident',source_revision=1,
                items=[{'id':'trial-active','state':'ACTIVE','record_revision':1,
                        'incident_ref':{'id':self.ident,'revision':1}}],origin='synthetic',complete=True)
            after=tx.conn.execute('SELECT source,revision,items FROM hs_operational_authority ORDER BY source').fetchall()
            self.assertEqual(before,after);self.assertFalse(result['operational_reported'])

    def test_02_native_activity_revalidation_closure_unknown_and_stale(self):
        for source in SOURCES:self.refresh(source,[])
        self.assertTrue(self.controls.get()['change_allowed'])
        self.refresh('incident',[{'id':'producer-native-case','state':'ACTIVE','record_revision':7}])
        before=self.controls.get()
        self.assertEqual(before['pending']['cases']['status'],'active')
        case=before['pending']['cases']['items'][0];self.assertEqual(case['record_revision'],7)
        with self.assertRaises(fixture.Rejected):
            self.controls.change(value={**before['value'],'autonomy_mode':3},expected_revision=before['revision'],
                                 reason='Active lifecycle blocks Apply',actor='dossier-owner')
        self.assertEqual(self.controls.get()['revision'],before['revision'])
        with self.assertRaisesRegex(ValueError,'ACTIVE_ITEM_REQUIRES_CLOSURE'):self.refresh('incident',[])
        self.refresh('incident',[{'id':'producer-native-case','state':'CLOSED','record_revision':8}])
        self.assertTrue(self.controls.get()['change_allowed'])
        self.refresh('incident',[{'id':'unknown-case','state':'UNKNOWN'}])
        self.assertFalse(self.controls.get()['change_allowed'])
        self.refresh('incident',[{'id':'unknown-case','state':'CLOSED'}])
        self.refresh('incident',[])
        with self.controls.repository.transaction() as tx:
            tx.conn.execute("UPDATE hs_operational_authority SET observed_at=clock_timestamp()-interval '1 minute' WHERE source='incident'")
        state=self.controls.get()
        self.assertNotEqual(state['pending']['cases']['status'],'none_active')
        self.assertFalse(state['change_allowed'])


if __name__=='__main__':unittest.main()
