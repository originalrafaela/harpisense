import {object,type Row} from './api.ts';

export type Detector='random_forest'|'isolation_forest';
export type AnalysisState='available'|'absent'|'invalid'|'unavailable';
export type ModelExplanation={
 id:string; projectionRevision:number; detectionId:string; modelVersion:string;
 linkedToIncident:boolean;
 method:string; output:'CALIBRATED_CLASS_PROBABILITY'|'ANOMALY_SCORE'; classLabel:string|null;
 baseValue:number; outputValue:number; contributions:{feature:string;value:number;contribution:number}[];
 outputDirection:string; createdAt:string|null; limitations:string[];
};
export type ModelAnalysis={
 detectionId:string; detectionRevision:number|null; state:AnalysisState; reasonCode:string|null;
 detector:Detector|null; modelVersion:string|null; windowId:string|null; windowStart:string|null; windowEnd:string|null;
 incidentId:string; incidentRevision:number; technicalAssetId:string|null; assetName:string|null;
 classification:Record<string,unknown>|null; anomaly:Record<string,unknown>|null;
 explanations:ModelExplanation[];
};
export type IncidentModelResponse={incidentId:string;incidentRevision:number;state:'available'|'absent_or_unavailable';analyses:ModelAnalysis[]};

const number=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const string=(v:unknown):v is string=>typeof v==='string'&&v.length>0;
const nullableString=(v:unknown):v is string|null=>v===null||string(v);
const nullableNumber=(v:unknown):v is number|null=>v===null||number(v);

function explanationView(value:unknown, detectionId:string, modelVersion:string,detector:Detector):ModelExplanation|null{
 if(!object(value)||!string(value.id)||!Number.isInteger(value.projection_revision)||Number(value.projection_revision)<1||!object(value.record)||!object(value.coherence))return null;
 if(!number(value.coherence.absolute_error)||!number(value.coherence.reconstruction_tolerance)||
    value.coherence.absolute_error>value.coherence.reconstruction_tolerance||value.coherence.causality_or_detector_accuracy_proven!==false)return null;
 const r=value.record;const target=object(r.target)?r.target:{};
 const expectedDirection=detector==='random_forest'?'positive_increases_class_probability':'positive_increases_anomaly_score';
 if(r.record_type!=='explanation'||r.detection_id!==detectionId||r.model_version!==modelVersion||!string(r.method)||
    target.output!==(detector==='random_forest'?'CALIBRATED_CLASS_PROBABILITY':'ANOMALY_SCORE')||
    !(target.class_label===null||string(target.class_label))||!number(r.base_value)||!number(r.output_value)||
    (detector==='random_forest'?!string(target.class_label):target.class_label!==null)||
    !Array.isArray(r.contributions)||value.output_direction!==expectedDirection)return null;
 const contributions=[] as ModelExplanation['contributions'];
 for(const item of r.contributions){if(!object(item)||!string(item.feature)||!number(item.value)||!number(item.contribution))return null;contributions.push({feature:item.feature,value:item.value,contribution:item.contribution})}
 if(!contributions.length)return null;
 const limitations=Array.isArray(r.limitations)&&r.limitations.every(string)?r.limitations as string[]:[];
 if(typeof value.in_incident_explanation_refs!=='boolean')return null;
 return {id:value.id,projectionRevision:Number(value.projection_revision),detectionId,modelVersion,linkedToIncident:value.in_incident_explanation_refs,method:r.method,
  output:target.output as ModelExplanation['output'],classLabel:target.class_label as string|null,
  baseValue:r.base_value as number,outputValue:r.output_value as number,contributions,outputDirection:value.output_direction as string,
  createdAt:string(r.created_at)?r.created_at:null,limitations};
}

function analysisView(value:unknown,incidentId:string,incidentRevision:number):ModelAnalysis|null{
 if(!object(value)||!string(value.detection_id)||!(Number.isInteger(value.detection_revision)||value.detection_revision===undefined)||
    !['available','absent','invalid','unavailable'].includes(String(value.state))||
    !(value.reason_code===undefined||value.reason_code===null||string(value.reason_code))||!Array.isArray(value.explanations))return null;
 const hasMetadata=object(value.model)&&object(value.window)&&(value.incident_ref===null||object(value.incident_ref))&&object(value.asset)&&object(value.operational_outputs);
 if(!hasMetadata&&value.state!=='unavailable')return null;
 if(value.state!=='unavailable'&&(!Number.isInteger(value.detection_revision)||!string(value.reason_code)&&value.reason_code!==null))return null;
 const model=object(value.model)?value.model:null;const window=object(value.window)?value.window:null;
 const incidentRef=object(value.incident_ref)?value.incident_ref:null;const asset=object(value.asset)?value.asset:null;
 const outputs=object(value.operational_outputs)?value.operational_outputs:null;
 let detector:Detector|null=null;let modelVersion:string|null=null;let windowId:string|null=null;let windowStart:string|null=null;let windowEnd:string|null=null;
 let technicalAssetId:string|null=null;let assetName:string|null=null;let classification:Record<string,unknown>|null=null;let anomaly:Record<string,unknown>|null=null;
 if(hasMetadata){
  if(!model||!window||!asset||!outputs||!['random_forest','isolation_forest'].includes(String(model.detector))||!string(model.model_version)||!string(window.window_id)||
     (incidentRef&&(incidentRef.id!==incidentId||incidentRef.revision!==incidentRevision))||
     value.state!=='unavailable'&&incidentRef===null||
     !nullableString(asset.technical_id)||!nullableString(asset.display_name))return null;
  detector=model.detector as Detector;modelVersion=model.model_version;windowId=window.window_id;
  windowStart=string(window.start)?window.start:null;windowEnd=string(window.end)?window.end:null;
  technicalAssetId=typeof asset.technical_id==='string'?asset.technical_id:null;assetName=typeof asset.display_name==='string'?asset.display_name:null;
  const classificationValue=outputs.classification;const anomalyValue=outputs.anomaly;
  if(!(classificationValue===null||object(classificationValue))||!(anomalyValue===null||object(anomalyValue)))return null;
  classification=classificationValue as Record<string,unknown>|null;anomaly=anomalyValue as Record<string,unknown>|null;
  if(detector==='random_forest'&&(!classification||anomaly!==null)||detector==='isolation_forest'&&(!anomaly||classification!==null))return null;
 } else if(value.explanations.length||value.state!=='unavailable')return null;
 const parsedExplanations:ModelExplanation[]=[];
 for(const item of value.explanations){if(!detector||!modelVersion)return null;const parsed=explanationView(item,value.detection_id,modelVersion,detector);if(!parsed)return null;parsedExplanations.push(parsed)}
 if(value.state!=='available'&&parsedExplanations.length)return null;
 const explanations=parsedExplanations.filter(item=>item.linkedToIncident);
 // A persisted explanation that is not referenced by this exact incident is not
 // presented as an explanation of that incident.
 const state:AnalysisState=value.state==='available'&&!explanations.length?'absent':value.state as AnalysisState;
 if(value.state==='available'&&!parsedExplanations.length)return null;
 return {detectionId:value.detection_id,detectionRevision:Number.isInteger(value.detection_revision)?Number(value.detection_revision):null,state,
  reasonCode:state==='absent'&&value.state==='available'?'EXPLANATION_NOT_LINKED_TO_INCIDENT':typeof value.reason_code==='string'?value.reason_code:null,detector,modelVersion,windowId,windowStart,windowEnd,
  incidentId,incidentRevision,technicalAssetId,assetName,classification,anomaly,explanations};
}

/** Strictly binds every displayed explanation to the requested incident/revision and detection. */
export function parseIncidentModelResponse(value:unknown,incidentId:string,incidentRevision:number):IncidentModelResponse|null{
 if(!object(value)||!object(value.incident_ref)||value.incident_ref.id!==incidentId||value.incident_ref.revision!==incidentRevision||
    !['available','absent_or_unavailable'].includes(String(value.state))||!Array.isArray(value.analyses)||value.read_only!==true)return null;
 const analyses:ModelAnalysis[]=[];
 for(const row of value.analyses){const parsed=analysisView(row,incidentId,incidentRevision);if(!parsed)return null;analyses.push(parsed)}
 return {incidentId,incidentRevision,state:value.state as IncidentModelResponse['state'],analyses};
}

export function incidentIdentity(row:Row):{id:string;revision:number}|null{
 const id=string(row.data.incident_id)?row.data.incident_id:row.id;
 const revision=row.data.revision;
 return string(id)&&Number.isInteger(revision)&&Number(revision)>0?{id,revision:Number(revision)}:null;
}

export function methodLabel(method:string){return method==='SHAPLEY_PERMUTATION'?'Shapley por permutações':method==='SHAP_MODEL_AGNOSTIC'?'SHAP agnóstico de modelo':`Método informado: ${method}`}

export function formatModelValue(value:number,output:ModelExplanation['output'],digits=4){
 if(output==='CALIBRATED_CLASS_PROBABILITY')return `${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(value*100)}%`;
 return new Intl.NumberFormat('pt-BR',{maximumFractionDigits:digits}).format(value);
}

export function contributionDirection(value:number,outputDirection:string){
 const result=outputDirection==='positive_increases_class_probability'?'probabilidade da classe':
  outputDirection==='positive_increases_anomaly_score'?'score de anomalia':'resultado explicado';
 return value>0?`Aumentou ${result}`:value<0?`Reduziu ${result}`:`Sem alteração (${result})`;
}
