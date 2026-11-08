import React from 'react';
import {createRoot} from 'react-dom/client';
import type {Client,Row} from '../src/api';
import {ModelAnalysis} from '../src/model-analysis';
import '../src/style.css';

const incidents:Row[]=[
 {id:'incident-rf-if',revision:1,source:'fixture',data:{incident_id:'incident-rf-if',revision:4,status:'OBSERVED'}},
 {id:'incident-empty',revision:1,source:'fixture',data:{incident_id:'incident-empty',revision:1,status:'OBSERVED'}},
 {id:'incident-error',revision:1,source:'fixture',data:{incident_id:'incident-error',revision:1,status:'OBSERVED'}},
 {id:'incident-slow',revision:1,source:'fixture',data:{incident_id:'incident-slow',revision:1,status:'OBSERVED'}},
 {id:'incident-fast',revision:1,source:'fixture',data:{incident_id:'incident-fast',revision:1,status:'OBSERVED'}},
];
function analysis(incidentId:string,revision:number,detector:'random_forest'|'isolation_forest',detectionId:string,assetName:string,state:'available'|'absent'='available'){
 const output=detector==='random_forest'?'CALIBRATED_CLASS_PROBABILITY':'ANOMALY_SCORE';
 const explanations=state==='available'?[{id:`xai-${detectionId}`,projection_revision:1,in_incident_explanation_refs:true,coherence:{absolute_error:0,reconstruction_tolerance:1e-8,causality_or_detector_accuracy_proven:false},record:{record_type:'explanation',explanation_id:`xai-${detectionId}`,detection_id:detectionId,model_version:`${detector}-fixture-v1`,method:'SHAPLEY_PERMUTATION',target:{output,class_label:detector==='random_forest'?'C01':null},base_value:detector==='random_forest'?.2:-.15,output_value:detector==='random_forest'?.8:-.55,contributions:[{feature:'mqtt_rate',value:4,contribution:detector==='random_forest'?.5:-.3},{feature:'packet_count',value:12,contribution:.1}],limitations:['Dados sintéticos de navegação']},output_direction:detector==='random_forest'?'positive_increases_class_probability':'positive_increases_anomaly_score'}]:[];
 return {detection_id:detectionId,detection_revision:1,state,reason_code:state==='absent'?'EXPLANATION_NOT_PERSISTED':null,model:{detector,model_version:`${detector}-fixture-v1`},window:{window_id:`window-${detectionId}`,start:'2026-11-07T11:00:00Z',end:'2026-11-07T11:01:00Z'},incident_ref:{id:incidentId,revision},asset:{technical_id:`device-${detectionId}`,display_name:assetName,name_state:'available'},operational_outputs:{classification:detector==='random_forest'?{predicted_class:'C01',probabilities:{C01:.8,normal:.2}}:null,anomaly:detector==='isolation_forest'?{anomaly_score:-.55,anomaly_threshold:-.2,is_anomaly:true}:null},explanations};
}
const responses:Record<string,unknown>={
 'incident-rf-if':{incident_ref:{id:'incident-rf-if',revision:4},state:'available',read_only:true,analyses:[analysis('incident-rf-if',4,'random_forest','detect-rf','Ativo RF'),analysis('incident-rf-if',4,'isolation_forest','detect-if','Ativo IF')]},
 'incident-empty':{incident_ref:{id:'incident-empty',revision:1},state:'absent_or_unavailable',read_only:true,analyses:[analysis('incident-empty',1,'random_forest','detect-empty','Ativo sem XAI','absent')]},
 'incident-slow':{incident_ref:{id:'incident-slow',revision:1},state:'available',read_only:true,analyses:[analysis('incident-slow',1,'random_forest','detect-slow','Ativo Lento')]},
 'incident-fast':{incident_ref:{id:'incident-fast',revision:1},state:'available',read_only:true,analyses:[analysis('incident-fast',1,'random_forest','detect-fast','Ativo Rápido')]},
};
const client={get:(path:string)=>new Promise<unknown>((resolve,reject)=>{
 const match=path.match(/\/incidents\/([^/?]+)\/explanations\?incident_revision=(\d+)/);if(!match)return reject(new Error('Rota de fixture inválida'));
 const id=decodeURIComponent(match[1]);if(id==='incident-error')return reject(new Error('API fixture indisponível'));
 setTimeout(()=>resolve(responses[id]),id==='incident-slow'?350:20);
})} as Pick<Client,'get'>;

createRoot(document.getElementById('root')!).render(<main style={{maxWidth:980,margin:'24px auto',padding:'0 16px'}}><ModelAnalysis incidents={incidents} client={client}/></main>);
