"""Real SHAP and trained estimators on artificial windows; no performance claim."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend/domain'),str(ROOT/'backend')]

import numpy as np
import pandas as pd
import shap
from harpisense_contracts import validate_links
from harpisense_rf.demo_sintetico import make_session as rf_session
from harpisense_rf.random_forest import train_model as train_rf,save_bundle as save_rf
from harpisense_if.demo_sintetico import make_session as if_session
from harpisense_if.isolation_forest import train_model as train_if,save_bundle as save_if
from harpisense_xai.core import create_reference,detection,explain as historical
from harpisense_xai.shap_library import explain,TREE,PERMUTATION
from detection_composition.core import Composition

NOW='2026-11-07T03:00:11+00:00'


class MemoryStore:
    def commit_composition(self,run_id,request_hash,window,produce):
        return produce()


class SHAPLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.directory=Path(cls.temp.name)
        train=pd.concat([rf_session('train-'+str(i),12,i) for i in range(2)])
        cal=pd.concat([rf_session('cal-'+str(i),12,10+i) for i in range(2)])
        train,cal=[frame[frame.label.isin(['normal','C01'])] for frame in (train,cal)]
        cls.rf=train_rf(train,cal,features=None,classes=['normal','C01'],profile='demo_tcp_ingress',trees=20)
        normal=pd.concat([if_session('normal-'+str(i),150,20+i) for i in range(2)])
        normal_cal=pd.concat([if_session('normal-cal-'+str(i),150,30+i) for i in range(2)])
        cls.iforest=train_if(normal,normal_cal,profile='demo_tcp_ingress',n_estimators=20)
        csv=cls.directory/'normal.csv';normal.to_csv(csv,index=False)
        cls.iforest['dataset_sha256']={'train':hashlib.sha256(csv.read_bytes()).hexdigest()}
        cls.refs={'random_forest':create_reference(cls.rf,max_rows=8),
                  'isolation_forest':create_reference(cls.iforest,training=csv,max_rows=8)}
        source=rf_session('shap-library-fixture',1,91)
        row=source[source.label=='C01'].iloc[0].to_dict()
        cls.window={k:v for k,v in row.items() if k in cls.rf['features'] or k in (
            'window_id','collection_session_id','feature_schema_version','window_seconds','traffic_profile')}
        cls.window.update(sensor_id='shap-fixture',device_id='poste-shap',
            window_start='2026-11-07T03:00:00+00:00',window_end='2026-11-07T03:00:10+00:00')
        cls.detections=[detection(b,cls.window,created_at=NOW) for b in (cls.rf,cls.iforest)]
        with patch.object(shap,'TreeExplainer',wraps=shap.TreeExplainer) as tree:
            cls.tree,_=explain(cls.rf,cls.refs['random_forest'],cls.detections[0],method=TREE,
                               target_class='C01',created_at=NOW)
            if tree.call_count!=1:raise AssertionError('Real shap.TreeExplainer not invoked')
        with patch.object(shap,'PermutationExplainer',wraps=shap.PermutationExplainer) as permutation:
            cls.rf_perm,_=explain(cls.rf,cls.refs['random_forest'],cls.detections[0],method=PERMUTATION,
                                  target_class='C01',permutations=4,created_at=NOW)
            cls.if_perm,_=explain(cls.iforest,cls.refs['isolation_forest'],cls.detections[1],method=PERMUTATION,
                                  permutations=4,created_at=NOW)
            if permutation.call_count!=2:raise AssertionError('Real shap.PermutationExplainer not invoked')
        save_rf(cls.rf,cls.directory/'rf');save_if(cls.iforest,cls.directory/'if')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_tree_reconstructs_original_rf_not_calibrated_probability(self):
        x=pd.DataFrame([{f:self.window[f] for f in self.rf['features']}],dtype=np.float32)
        index=self.rf['classes'].index('C01')
        raw=float(self.rf['raw_model'].predict_proba(x)[0,index])
        calibrated=float(self.rf['model'].predict_proba(x)[0,index])
        self.assertEqual(self.tree['method'],TREE)
        self.assertEqual(self.tree['target']['output'],'RAW_CLASS_PROBABILITY')
        self.assertAlmostEqual(self.tree['output_value'],raw,places=8)
        self.assertGreater(abs(raw-calibrated),1e-3)
        self.assertEqual(self.tree['parameters']['output_space'],'raw_pre_calibration')

    def test_real_permutation_explains_calibrated_rf_and_operational_if(self):
        self.assertEqual(self.rf_perm['target']['output'],'CALIBRATED_CLASS_PROBABILITY')
        self.assertAlmostEqual(self.rf_perm['output_value'],self.detections[0]['classification']['probabilities']['C01'],places=8)
        self.assertEqual(self.if_perm['target'],{'output':'ANOMALY_SCORE','class_label':None})
        self.assertAlmostEqual(self.if_perm['output_value'],self.detections[1]['anomaly']['anomaly_score'],places=8)
        for record in (self.rf_perm,self.if_perm):
            self.assertEqual(record['parameters']['output_space'],'operational')
            self.assertEqual(record['parameters']['library_version'],shap.__version__)

    def test_all_records_reconstruct_and_bind_exact_window_input(self):
        self.assertTrue(validate_links(detections=self.detections,explanations=[self.tree,self.rf_perm,self.if_perm],incidents=[],decisions=[]))
        for record in (self.tree,self.rf_perm,self.if_perm):
            self.assertLess(abs(record['additivity_residual']),1e-5)
            self.assertAlmostEqual(record['base_value']+sum(c['contribution'] for c in record['contributions'])+record['additivity_residual'],record['output_value'],places=8)
        invalid=deepcopy(self.tree);invalid['parameters']['operational_output_value']+=.1
        with self.assertRaises(ValueError):
            validate_links(detections=self.detections,explanations=[invalid],incidents=[],decisions=[])
        invalid=deepcopy(self.tree);invalid['method']=PERMUTATION
        with self.assertRaises(ValueError):
            validate_links(detections=self.detections,explanations=[invalid],incidents=[],decisions=[])

    def test_tree_if_refused_instead_of_relabeling_path_length(self):
        with self.assertRaisesRegex(ValueError,'TREE_IF_OUTPUT_NOT_OPERATIONAL'):
            explain(self.iforest,self.refs['isolation_forest'],self.detections[1],method=TREE,created_at=NOW)

    def test_historical_record_keeps_original_name_and_numerics(self):
        record,_=historical(self.rf,self.refs['random_forest'],self.detections[0],target_class='C01',permutations=2,created_at=NOW)
        self.assertEqual(record['method'],'SHAPLEY_PERMUTATION')
        self.assertEqual(record['explainer_version'],'harpisense.xai.permutation.v1')
        self.assertNotIn('library_version',record['parameters'])
        self.assertAlmostEqual(record['output_value'],self.rf_perm['output_value'],places=8)

    def test_cli_runs_both_library_methods_and_writes_the_same_contribution_records(self):
        from harpisense_xai.__main__ import main
        reference=self.directory/'reference.json'
        reference.write_text(json.dumps(self.refs['random_forest']),encoding='utf-8')
        detection_file=self.directory/'detection.json'
        detection_file.write_text(json.dumps(self.detections[0]),encoding='utf-8')
        for method in (TREE,PERMUTATION):
            out=self.directory/('cli-'+method)
            main(['explain','--model',str(self.directory/'rf'),'--background',str(reference),
                  '--detection',str(detection_file),'--target-class','C01','--method',method,
                  '--permutations','2','--out',str(out)])
            result=json.loads((out/'explanation.json').read_text(encoding='utf-8'))
            self.assertEqual(result['method'],method)
            self.assertTrue(validate_links(detections=self.detections,explanations=[result],incidents=[],decisions=[]))
            self.assertEqual(len((out/'contributions.csv').read_text().splitlines()),len(result['contributions'])+1)

    def test_library_composition_emits_separate_records_without_execution(self):
        paths={name:self.directory/name for name in ('rf','if')}
        composition=Composition(MemoryStore(),rf_directory=paths['rf'],if_directory=paths['if'],
            rf_sha256=hashlib.sha256((paths['rf']/'model.joblib').read_bytes()).hexdigest(),
            if_sha256=hashlib.sha256((paths['if']/'model.joblib').read_bytes()).hexdigest(),
            xai_references=self.refs,xai_permutations=4,xai_methods={
                'random_forest':[TREE,PERMUTATION],'isolation_forest':[PERMUTATION]})
        result=composition.process_synthetic(self.window,now=NOW,mode=1)
        self.assertEqual(len(result['explanations']),3)
        self.assertEqual(len({e['explanation_id'] for e in result['explanations']}),3)
        self.assertEqual(result['incident']['explanation_refs'],sorted(e['explanation_id'] for e in result['explanations']))
        self.assertFalse(result['execution_performed'])
        self.assertTrue(validate_links(detections=result['detections'],explanations=result['explanations'],
            incidents=[result['incident']],decisions=[result['decision']]))
        destination=os.getenv('HARPISENSE_SHAP_EVIDENCE_DIR')
        if destination:
            out=Path(destination);out.mkdir(parents=True,exist_ok=True)
            rows=[dict(kind='detection',id=d['detection_id'],revision=1,source='synthetic-shap-library',data=d) for d in result['detections']]
            rows.extend(dict(kind='xai',id=e['explanation_id'],revision=1,source='synthetic-shap-library',data=e) for e in result['explanations'])
            for kind,idkey in (('incident','incident_id'),('decision','decision_id')):
                rows.append(dict(kind=kind,id=result[kind][idkey],revision=1,source='synthetic-shap-library',data=result[kind]))
            (out/'synthetic-records.json').write_text(json.dumps(rows,indent=2,allow_nan=False),encoding='utf-8')
            (out/'result.json').write_text(json.dumps(dict(input_origin='synthetic',real_estimators=True,
                real_library=shap.__version__,statistical_validation=False,execution_performed=False,
                methods=[TREE,PERMUTATION],rf_raw_output=self.tree['output_value'],
                rf_calibrated_output=self.rf_perm['output_value'],if_operational_score=self.if_perm['output_value']),indent=2),encoding='utf-8')


if __name__=='__main__':unittest.main()
