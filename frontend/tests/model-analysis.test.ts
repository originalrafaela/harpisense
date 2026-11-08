import {test} from 'node:test';
import assert from 'node:assert/strict';
import {contributionDirection,formatModelValue,incidentIdentity,methodLabel,parseIncidentModelResponse} from '../src/model-analysis-data.ts';
import type {Row} from '../src/api.ts';

const makeAnalysis=(detector:'random_forest'|'isolation_forest',id:string,state:'available'|'absent'='available')=>{
 const output=detector==='random_forest'?'CALIBRATED_CLASS_PROBABILITY':'ANOMALY_SCORE';
 const explanation={id:`xai-${id}`,projection_revision:2,in_incident_explanation_refs:true,coherence:{absolute_error:0,reconstruction_tolerance:1e-8,causality_or_detector_accuracy_proven:false},record:{record_type:'explanation',explanation_id:`xai-${id}`,detection_id:id,
  model_version:`${detector}-v1`,method:'SHAPLEY_PERMUTATION',target:{output,class_label:detector==='random_forest'?'C01':null},
  base_value:detector==='random_forest'?.4:-.2,output_value:detector==='random_forest'?.7:-.6,
  contributions:[{feature:'mqtt_rate',value:12,contribution:detector==='random_forest'?.2:-.3},{feature:'flow_count',value:4,contribution:-.1}],
  limitations:['Synthetic test input'],created_at:'2026-11-07T12:00:00Z'},
  output_direction:detector==='random_forest'?'positive_increases_class_probability':'positive_increases_anomaly_score'};
 return {detection_id:id,detection_revision:1,state,reason_code:state==='absent'?'EXPLANATION_NOT_PERSISTED':null,
  model:{detector,model_version:`${detector}-v1`},window:{window_id:`window-${id}`,start:'2026-11-07T11:59:00Z',end:'2026-11-07T12:00:00Z'},
  incident_ref:{id:'incident-1',revision:4},asset:{technical_id:'device-7',display_name:'Ativo de ensaio',name_state:'available'},
  operational_outputs:{classification:detector==='random_forest'?{predicted_class:'C01',probabilities:{normal:.3,C01:.7}}:null,
   anomaly:detector==='isolation_forest'?{anomaly_score:-.6,anomaly_threshold:-.3,is_anomaly:true}:null},
  explanations:state==='available'?[explanation]:[]};
};
const response=(analyses:unknown[],state='available')=>({incident_ref:{id:'incident-1',revision:4},state,analyses,read_only:true});

test('TreeExplainer RF is explicit raw output and cannot masquerade as calibrated RF or IF score',()=>{
 const raw=makeAnalysis('random_forest','detect-raw');
 raw.explanations[0].record.method='SHAP_TREE_EXPLAINER';
 raw.explanations[0].record.target.output='RAW_CLASS_PROBABILITY';
 raw.explanations[0].output_direction='positive_increases_raw_class_probability';
 assert.equal(parseIncidentModelResponse(response([raw]),'incident-1',4)?.analyses[0].explanations[0].output,'RAW_CLASS_PROBABILITY');
 raw.explanations[0].record.target.output='CALIBRATED_CLASS_PROBABILITY';
 assert.equal(parseIncidentModelResponse(response([raw]),'incident-1',4),null);
 const operational=makeAnalysis('isolation_forest','detect-if-permutation');
 operational.explanations[0].record.method='SHAP_PERMUTATION_EXPLAINER';
 assert.equal(parseIncidentModelResponse(response([operational]),'incident-1',4)?.analyses[0].explanations[0].method,'SHAP_PERMUTATION_EXPLAINER');
});

test('vincula explicações RF e IF ao incidente, revisão, modelo e detecção',()=>{
 const parsed=parseIncidentModelResponse(response([makeAnalysis('random_forest','detect-rf'),makeAnalysis('isolation_forest','detect-if')]),'incident-1',4);
 assert.ok(parsed);assert.equal(parsed.analyses.length,2);
 assert.equal(parsed.analyses[0].explanations[0].output,'CALIBRATED_CLASS_PROBABILITY');
 assert.equal(parsed.analyses[1].explanations[0].output,'ANOMALY_SCORE');
 assert.equal(parsed.analyses[1].explanations[0].detectionId,'detect-if');
});

test('ausência persistida é válida e distinta de resposta incompatível',()=>{
 const parsed=parseIncidentModelResponse(response([makeAnalysis('random_forest','detect-rf','absent')],'absent_or_unavailable'),'incident-1',4);
 assert.equal(parsed?.analyses[0].state,'absent');assert.deepEqual(parsed?.analyses[0].explanations,[]);
 assert.equal(parseIncidentModelResponse(response([makeAnalysis('random_forest','detect-rf')]),'other-incident',4),null);
 assert.equal(parseIncidentModelResponse(response([makeAnalysis('random_forest','detect-rf')]),'incident-1',5),null);
});

test('aceita o envelope indisponível do leitor sem inventar revisão ou modelo',()=>{
 const unavailable={detection_id:'detect-missing',state:'unavailable',reason_code:'DETECTION_NOT_FOUND',
  explanations:[],rejected_explanations:[],has_more:false};
 const parsed=parseIncidentModelResponse(response([unavailable],'absent_or_unavailable'),'incident-1',4);
 assert.equal(parsed?.analyses[0].state,'unavailable');
 assert.equal(parsed?.analyses[0].detectionRevision,null);
 assert.equal(parsed?.analyses[0].detector,null);
 const partial={...makeAnalysis('random_forest','detect-unavailable','absent'),state:'unavailable',incident_ref:null,explanations:[]};
 const partialParsed=parseIncidentModelResponse(response([partial],'absent_or_unavailable'),'incident-1',4);
 assert.equal(partialParsed?.analyses[0].state,'unavailable');
});

test('não apresenta explicação persistida que não esteja vinculada ao incidente',()=>{
 const analysis=makeAnalysis('random_forest','detect-rf');analysis.explanations[0].in_incident_explanation_refs=false;
 const parsed=parseIncidentModelResponse(response([analysis]),'incident-1',4);
 assert.equal(parsed?.analyses[0].state,'absent');
 assert.equal(parsed?.analyses[0].reasonCode,'EXPLANATION_NOT_LINKED_TO_INCIDENT');
 assert.deepEqual(parsed?.analyses[0].explanations,[]);
});

test('rejeita projeção sem coerência numérica confirmada pela API',()=>{
 const invalid=makeAnalysis('random_forest','detect-rf');
 invalid.explanations[0].coherence.absolute_error=1;
 assert.equal(parseIncidentModelResponse(response([invalid]),'incident-1',4),null);
});

test('rejeita mistura de incidente, detector ou saída explicada',()=>{
 const wrong=makeAnalysis('random_forest','detect-rf');wrong.explanations[0].record.detection_id='foreign-detection';
 assert.equal(parseIncidentModelResponse(response([wrong]),'incident-1',4),null);
 const mismatch=makeAnalysis('random_forest','detect-rf');mismatch.explanations[0].record.target.output='ANOMALY_SCORE';
 assert.equal(parseIncidentModelResponse(response([mismatch]),'incident-1',4),null);
 const missing=[];assert.equal(parseIncidentModelResponse(response(missing,'absent_or_unavailable'),'incident-1',4)?.analyses.length,0);
});

test('RF é exibido como probabilidade calibrada e IF como score sem porcentagem',()=>{
 assert.equal(formatModelValue(.75,'CALIBRATED_CLASS_PROBABILITY'),'75%');
 assert.equal(formatModelValue(-.25,'ANOMALY_SCORE'),'-0,25');
 assert.equal(methodLabel('SHAPLEY_PERMUTATION'),'SHAPLEY_PERMUTATION · implementação histórica');
 assert.equal(contributionDirection(.2,'positive_increases_class_probability'),'Aumentou probabilidade da classe');
 assert.equal(contributionDirection(-.2,'positive_increases_anomaly_score'),'Reduziu score de anomalia');
 assert.equal(contributionDirection(.1,'positive_increases_class_probability').includes('ataque'),false);
});

test('usa nome amigável e mantém ID técnico nos metadados do ativo',()=>{
 const row:Row={id:'projection-id',revision:9,data:{incident_id:'incident-1',revision:4}};
 assert.deepEqual(incidentIdentity(row),{id:'incident-1',revision:4});
 assert.equal(incidentIdentity({id:'incident-1',data:{revision:0}}),null);
});
