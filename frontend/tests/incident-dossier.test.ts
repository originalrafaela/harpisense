import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseDossier,methodName,outputName} from '../src/incident-dossier-data.ts';

const fixture=()=>({incident_ref:{id:'incident-1',revision:2},read_only:true,incident_card:{incident_id:'incident-1'},logs:[],missing_links:[],technical_cards:[{incident_ref:{id:'incident-1',revision:2},detection_id:'detection-1',method:'SHAP_TREE_EXPLAINER',output:{kind:'RAW_CLASS_PROBABILITY',class_label:'C01'},reference:{value:.4},result:{value:.7},explanation:{id:'explanation-1',record:{explanation_id:'explanation-1',detection_id:'detection-1',method:'SHAP_TREE_EXPLAINER',target:{output:'RAW_CLASS_PROBABILITY',class_label:'C01'},base_value:.4,output_value:.7}}}]});
test('dossier binds incident, revision and technical values to the exact explanation record',()=>{
 assert.ok(parseDossier(fixture(),'incident-1',2));
 assert.equal(parseDossier(fixture(),'incident-2',2),null);
 assert.equal(parseDossier(fixture(),'incident-1',3),null);
 const wrong=fixture();wrong.technical_cards[0].result.value=.9;
 assert.equal(parseDossier(wrong,'incident-1',2),null);
 const wrongLink=fixture();wrongLink.technical_cards[0].explanation.record.detection_id='another-detection';
 assert.equal(parseDossier(wrongLink,'incident-1',2),null);
});
test('library methods, historical method and RF raw output have distinct labels',()=>{
 assert.equal(methodName('SHAP_TREE_EXPLAINER'),'TreeExplainer');
 assert.equal(methodName('SHAP_PERMUTATION_EXPLAINER'),'PermutationExplainer');
 assert.match(methodName('SHAPLEY_PERMUTATION'),/SHAPLEY_PERMUTATION.*histórico/);
 assert.match(outputName('RAW_CLASS_PROBABILITY','C01'),/antes da calibração/);
 assert.equal(outputName('ANOMALY_SCORE',null),'Score operacional de anomalia');
});
