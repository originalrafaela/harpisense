import {object} from './api.ts';
export type Dossier=Record<string,unknown>&{incident_ref:{id:string;revision:number};incident_card:Record<string,unknown>;technical_cards:Record<string,unknown>[];logs:Record<string,unknown>[];missing_links:unknown[]};
export function parseDossier(value:unknown,id:string,revision:number):Dossier|null{
 if(!object(value)||!object(value.incident_ref)||value.incident_ref.id!==id||value.incident_ref.revision!==revision||value.read_only!==true||!object(value.incident_card)||value.incident_card.incident_id!==id||!Array.isArray(value.technical_cards)||!Array.isArray(value.logs)||!Array.isArray(value.missing_links))return null;
 if(!value.technical_cards.every(card=>{if(!object(card)||!object(card.incident_ref)||card.incident_ref.id!==id||card.incident_ref.revision!==revision||!object(card.explanation)||!object(card.explanation.record))return false;const r=card.explanation.record;return r.detection_id===card.detection_id&&r.method===card.method&&r.explanation_id===card.explanation.id&&object(card.output)&&object(r.target)&&card.output.kind===r.target.output&&card.output.class_label===r.target.class_label&&object(card.reference)&&card.reference.value===r.base_value&&object(card.result)&&card.result.value===r.output_value}))return null;
 if(!value.logs.every(object))return null;
 return value as Dossier;
}
export const text=(v:unknown,fallback='Não informado'):string=>typeof v==='string'&&v.trim()?v:typeof v==='number'&&Number.isFinite(v)?String(v):fallback;
export const data=(v:unknown):Record<string,unknown>=>object(v)?v:{};
export function methodName(v:unknown){return v==='SHAP_TREE_EXPLAINER'?'TreeExplainer':v==='SHAP_PERMUTATION_EXPLAINER'?'PermutationExplainer':v==='SHAPLEY_PERMUTATION'?'SHAPLEY_PERMUTATION (histórico)':text(v)}
export function outputName(v:unknown,label:unknown){return v==='RAW_CLASS_PROBABILITY'?`Classe ${text(label)} · probabilidade original antes da calibração`:v==='CALIBRATED_CLASS_PROBABILITY'?`Classe ${text(label)} · probabilidade calibrada`:v==='ANOMALY_SCORE'?'Score operacional de anomalia':text(v)}
