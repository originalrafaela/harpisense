"""Distinct-case contracts on controlled service fixtures; no real attack claim."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/p) for p in ('backend','backend/domain','genai','backend/delivery_tests')]
import test_incident_dossier as fixture
from delivery.activity import ActivityProducer
from delivery.controls import Controls
from delivery.control_store import PostgresControls
from delivery.linked_cases import LinkedOperationalQueue
from delivery.operational_queue import SOURCES
from delivery.projections import Record


class LinkedCasesNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixture.IncidentDossierTests
        cls.fixture.setUpClass()
        cls.controls=Controls(PostgresControls(cls.fixture.state['dsn']),LinkedOperationalQueue())
        cls.producer=ActivityProducer()
        cls.output=ROOT/'docs/evidence/backend-integration-20261107/cases-v2'
        cls.output.mkdir(parents=True,exist_ok=True)

    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()

    def setUp(self):
        with self.controls.repository.transaction() as tx:
            tx.conn.execute('DELETE FROM hs_operational_authority')
            tx.conn.execute('DELETE FROM hs_activity_event')
        for source in SOURCES:self.report(source,[])

    def report(self,source,items,complete=True):
        with self.controls.repository.transaction() as tx:
            previous=tx.conn.execute('SELECT revision FROM hs_operational_authority WHERE source=%s',(source,)).fetchone()
            return self.producer.publish(tx,source=source,source_revision=1 if previous is None else previous[0]+1,
                items=items,origin='trusted-service',complete=complete)

    def case(self):
        # New IDs and trusted transport fixtures only. Never promote an existing
        # synthetic projection to another origin or claim observed real traffic.
        data=deepcopy(self.fixture.store.history('incident',self.fixture.ident)[0]['data'])
        data['incident_id']='fixture-linked-case-'+uuid.uuid4().hex
        self.fixture.store.insert('incident',Record(id=data['incident_id'],revision=1,source='trusted-service',data=data))
        return {'id':data['incident_id'],'revision':1}

    def activate(self,ref,attack=True):
        self.report('incident',[{'id':'fixture-lifecycle','state':'ACTIVE','record_revision':7,
            'incident_ref':ref,'activity_type':'attack' if attack else 'incident'}])
        self.report('anomaly',[{'id':'fixture-anomaly','state':'ACTIVE','record_revision':4,
            'incident_ref':ref,'activity_type':'anomaly'}])

    def http(self):
        response=self.fixture.client.get('/api/v1/security/settings/mode/default')
        self.assertEqual(response.status_code,200)
        return response.json()

    def evidence(self,name,body):
        (self.output/(name+'.json')).write_text(json.dumps({'fixture_notice':
            'Controlled trusted-service transport fixtures in a disposable native PostgreSQL cluster. '
            'No real traffic, real attack, approved model or containment is attested.',
            'response':body},indent=2,ensure_ascii=False),encoding='utf-8',newline='\n')

    def test_assessment_alone_does_not_create_activity_and_duplicate_sources_count_once(self):
        ref=self.case()
        self.fixture.interface.assess(ref['id'],1,'confirmed','Controlled fixture assessment; no real attack claim','dossier-owner')
        self.assertEqual(self.http()['cases']['status'],'none_active')
        self.activate(ref)
        state=self.http();cases=state['cases']
        self.assertEqual(cases['count_basis'],'distinct_incident_id')
        self.assertEqual(cases['known_active_count'],1)
        self.assertEqual(cases['total_active_count'],1)
        self.assertEqual(cases['classification_counts'],{'anomaly':1,'confirmed_attack':1,'incident':1})
        self.assertEqual(len(cases['items'][0]['items']),2)
        self.assertEqual(cases['items'][0]['incident_ref'],ref)
        self.assertEqual(cases['items'][0]['links'][0]['incident_ref'],ref)
        self.assertFalse(state['change_allowed'])
        self.evidence('current-sufficient-active',state)

    def test_confirmed_assessment_does_not_turn_anomaly_into_active_attack(self):
        ref=self.case()
        self.fixture.interface.assess(ref['id'],1,'confirmed','Controlled historical assessment','dossier-owner')
        self.report('anomaly',[{'id':'fixture-only-anomaly','state':'ACTIVE','incident_ref':ref,'activity_type':'anomaly'}])
        cases=self.http()['cases']
        self.assertEqual(cases['classification_counts'],{'anomaly':1,'confirmed_attack':0,'incident':0})
        self.assertEqual(cases['total_active_count'],1)

    def test_stale_known_attack_retained_and_total_not_claimed(self):
        ref=self.case()
        self.fixture.interface.assess(ref['id'],1,'confirmed','Controlled fixture assessment','dossier-owner')
        self.activate(ref)
        with self.controls.repository.transaction() as tx:
            tx.conn.execute("UPDATE hs_operational_authority SET observed_at=clock_timestamp()-interval '1 minute' "
                            "WHERE source IN ('incident','anomaly')")
        state=self.http();cases=state['cases']
        self.assertEqual(cases['status'],'active');self.assertEqual(cases['known_active_count'],1)
        self.assertEqual(cases['classification_counts']['confirmed_attack'],1)
        self.assertIsNone(cases['total_active_count']);self.assertFalse(cases['observation_sufficient'])
        self.assertTrue(all(not item['fresh'] for item in cases['items'][0]['items']))
        self.evidence('stale-known-attack',state)

    def test_unknown_state_retains_last_persisted_active_fact_until_closure(self):
        ref=self.case()
        self.fixture.interface.assess(ref['id'],1,'confirmed','Controlled fixture assessment','dossier-owner')
        self.activate(ref)
        self.report('incident',[{'id':'fixture-lifecycle','state':'UNKNOWN','incident_ref':ref}])
        cases=self.http()['cases']
        self.assertEqual(cases['known_active_count'],1)
        self.assertEqual(cases['classification_counts']['confirmed_attack'],1)
        self.assertIsNone(cases['total_active_count'])
        self.assertTrue(any(r['code']=='KNOWN_ACTIVE_RETAINED_AFTER_UNKNOWN' for r in cases['reason_codes']))
        self.evidence('communication-loss-known-attack',self.http())

    def test_unlinked_items_never_fabricate_distinct_total_or_navigation(self):
        self.report('incident',[{'id':'fixture-unlinked','state':'ACTIVE','record_revision':2}])
        state=self.http();cases=state['cases']
        self.assertEqual(cases['status'],'active');self.assertEqual(cases['coverage'],'partial')
        self.assertIsNone(cases['known_active_count']);self.assertIsNone(cases['total_active_count'])
        self.assertEqual(cases['items'],[]);self.assertEqual(cases['unlinked_active_item_count'],1)
        self.evidence('partial-unlinked',state)

    def test_never_observed_or_zero_stale_is_not_healthy_zero(self):
        with self.controls.repository.transaction() as tx:tx.conn.execute('DELETE FROM hs_operational_authority')
        state=self.http();self.assertEqual(state['cases']['status'],'unknown')
        self.assertFalse(state['cases']['observation_sufficient']);self.assertIsNone(state['cases']['total_active_count'])
        self.evidence('never-observed',state)
        self.report('incident',[])
        state=self.http();self.assertEqual(state['cases']['coverage'],'partial')
        self.assertNotEqual(state['cases']['status'],'none_active')
        self.evidence('partial-observation',state)

    def test_partial_coverage_marker_does_not_invent_an_active_case(self):
        self.report('incident',[],complete=False)
        state=self.http();cases=state['cases']
        self.assertEqual(cases['status'],'partial')
        self.assertEqual(cases['known_active_count'],0)
        self.assertEqual(cases['unlinked_active_item_count'],0)
        self.assertIsNone(cases['total_active_count'])
        self.assertFalse(state['change_allowed'])

    def test_unknown_without_prior_active_fact_does_not_claim_active_case(self):
        ref=self.case()
        self.report('incident',[{'id':'fixture-state-unknown','state':'UNKNOWN','incident_ref':ref}])
        state=self.http();cases=state['cases']
        self.assertEqual(cases['status'],'partial')
        self.assertIsNone(cases['known_active_count']);self.assertIsNone(cases['total_active_count'])
        self.assertFalse(state['change_allowed'])

    def test_emergency_keeps_v2_contract_without_querying_authority_or_erasing_cases(self):
        ref=self.case();self.activate(ref)
        controls=self.fixture.server.config.app.state.operational_controls
        original=controls.queue.snapshot
        def forbidden(tx):raise AssertionError('Emergency must not consult authority')
        controls.queue.snapshot=forbidden
        try:
            response=self.fixture.client.post('/api/v1/security/emergency-stop',json={'reason':'Controlled emergency contract test'})
        finally:controls.queue.snapshot=original
        self.assertEqual(response.status_code,200)
        body=response.json();self.assertTrue(body['emergency_stopped'])
        self.assertEqual(body['cases']['contract_version'],2)
        self.assertEqual(body['cases']['status'],'unknown')
        self.assertIsNone(body['cases']['total_active_count'])
        self.assertEqual(self.http()['cases']['known_active_count'],1)

    def test_adapter_failure_remains_v2_unknown_not_healthy_zero(self):
        controls=self.fixture.server.config.app.state.operational_controls
        original=controls.queue.snapshot
        def unavailable(tx):raise RuntimeError('Controlled adapter outage')
        controls.queue.snapshot=unavailable
        try:state=self.http()
        finally:controls.queue.snapshot=original
        self.assertEqual(state['cases']['contract_version'],2)
        self.assertEqual(state['cases']['status'],'unknown')
        self.assertIsNone(state['cases']['known_active_count'])
        self.assertIsNone(state['cases']['total_active_count'])
        self.assertFalse(state['change_allowed'])

    def test_new_revision_cannot_promote_synthetic_origin_to_service_origin(self):
        original=self.fixture.store.history('incident',self.fixture.ident)[0]['data']
        changed=deepcopy(original);changed['revision']=2
        with self.assertRaisesRegex(ValueError,'immutable origin conflict'):
            self.fixture.store.insert('incident',Record(id=self.fixture.ident,revision=2,source='trusted-service',data=changed))
        rows=self.fixture.store.history('incident',self.fixture.ident)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source'],'synthetic')
        same_origin=Record(id=self.fixture.ident,revision=2,source='synthetic',data=changed)
        self.assertTrue(self.fixture.store.insert('incident',same_origin))
        self.assertFalse(self.fixture.store.insert('incident',same_origin))

    def test_closed_history_and_closed_assessment_do_not_block_apply(self):
        ref=self.case()
        self.fixture.interface.assess(ref['id'],1,'confirmed','Controlled fixture assessment','dossier-owner')
        self.activate(ref)
        self.report('incident',[{'id':'fixture-lifecycle','state':'CLOSED','incident_ref':ref}])
        self.report('anomaly',[{'id':'fixture-anomaly','state':'CLOSED','incident_ref':ref}])
        state=self.http()
        self.assertEqual(state['cases']['status'],'none_active');self.assertEqual(state['cases']['total_active_count'],0)
        self.assertTrue(state['change_allowed'])
        mode=2 if state['value']['autonomy_mode']!=2 else 1
        applied=self.controls.change(value={**state['value'],'autonomy_mode':mode},expected_revision=state['revision'],
                                     reason='Explicit closed history does not block',actor='dossier-owner')
        self.assertEqual(applied['value']['autonomy_mode'],mode)
        self.evidence('current-sufficient-zero',state)

    def test_different_revisions_of_same_explicit_incident_are_one_case(self):
        ref=self.case()
        incident=deepcopy(self.fixture.store.history('incident',ref['id'])[0]['data']);incident['revision']=2
        self.fixture.store.insert('incident',Record(id=ref['id'],revision=2,source='trusted-service',data=incident))
        self.report('incident',[{'id':'fixture-revision-one','state':'ACTIVE','incident_ref':ref}])
        self.report('anomaly',[{'id':'fixture-revision-two','state':'ACTIVE','incident_ref':{'id':ref['id'],'revision':2}}])
        cases=self.http()['cases']
        self.assertEqual(cases['total_active_count'],1)
        self.assertIsNone(cases['items'][0]['incident_ref'])
        self.assertEqual(len(cases['items'][0]['incident_refs']),2)
        self.assertEqual(len(cases['items'][0]['links']),2)

    def test_concurrent_admission_revalidated_on_real_postgresql_connections(self):
        ref=self.case();before=self.http();admitted=threading.Event();release=threading.Event()
        def producer():
            with self.controls.decision_transaction(before['revision']) as (tx,current):
                previous=tx.conn.execute("SELECT revision FROM hs_operational_authority WHERE source='incident'").fetchone()[0]
                self.producer.publish(tx,source='incident',source_revision=previous+1,origin='trusted-service',complete=True,
                    items=[{'id':'fixture-concurrent','state':'ACTIVE','incident_ref':ref}])
                admitted.set()
                if not release.wait(10):raise RuntimeError('TEST_RELEASE_TIMEOUT')
        with ThreadPoolExecutor(2) as pool:
            writing=pool.submit(producer);self.assertTrue(admitted.wait(10))
            applying=pool.submit(self.fixture.client.put,'/api/v1/security/settings/mode/default',json={
                'value':{**before['value'],'autonomy_mode':3},'expected_revision':before['revision'],
                'reason':'Concurrent source admission must be revalidated'})
            release.set();writing.result();response=applying.result()
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['detail']['current_revision'],before['revision'])
        self.assertEqual(self.http()['value'],before['value'])
        self.evidence('profile-change-refused',response.json())


if __name__=='__main__':unittest.main()
