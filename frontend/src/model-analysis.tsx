import {useEffect,useRef,useState} from 'react';
import type {Client,Row} from './api';
import {Empty,Panel} from './components';
import {contributionDirection,formatModelValue,incidentIdentity,methodLabel,parseIncidentModelResponse,type IncidentModelResponse,type ModelAnalysis,type ModelExplanation} from './model-analysis-data';
import {formatTime} from './presentation';
import './model-analysis.css';

export type ModelAnalysisProps={
 incidents:Row[];
 client:Pick<Client,'get'>;
 /** undefined means local selection; null means the caller explicitly has no selected incident. */
 selectedIncidentId?:string|null;
 onIncidentChange?:(incidentId:string)=>void;
};

const numberText=(value:number)=>new Intl.NumberFormat('pt-BR',{maximumFractionDigits:6}).format(value);
const detectorName=(analysis:ModelAnalysis)=>analysis.detector==='random_forest'?'Random Forest':analysis.detector==='isolation_forest'?'Isolation Forest':'Modelo não informado';
const assetLabel=(analysis:ModelAnalysis)=>analysis.assetName||analysis.technicalAssetId||'Ativo não identificado';
const when=(start:string|null,end:string|null)=>start&&end?`${formatTime(start)} — ${formatTime(end)}`:'Janela sem horário informado';
const contributionValue=(value:number,output:ModelExplanation['output'])=>output==='CALIBRATED_CLASS_PROBABILITY'?`${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2,signDisplay:'always'}).format(value*100)} pp`:new Intl.NumberFormat('pt-BR',{maximumFractionDigits:6,signDisplay:'always'}).format(value);

function ExplanationCard({analysis,explanation}:{analysis:ModelAnalysis;explanation:ModelExplanation}){
 const output=explanation.output;const sorted=[...explanation.contributions].sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution));const max=Math.max(0,...sorted.map(item=>Math.abs(item.contribution)));
 const outputLabel=output==='CALIBRATED_CLASS_PROBABILITY'?'Probabilidade calibrada da classe':'Score operacional de anomalia';
 const scale='escala operacional (-score_samples)';
 return <article className="model-analysis-result" aria-label={`${detectorName(analysis)} · ${explanation.method}`}>
  <header className="model-analysis-heading"><div><strong>{assetLabel(analysis)}</strong><small>Incidente {analysis.incidentId} · detecção {analysis.detectionId} · revisão {analysis.incidentRevision}</small></div><div><strong>{detectorName(analysis)}</strong><small>Modelo {analysis.modelVersion||'versão não informada'}</small></div></header>
  <dl className="model-facts"><dt>Incidente ou detecção</dt><dd>{analysis.incidentId} · {analysis.detectionId}</dd><dt>Ativo</dt><dd>{assetLabel(analysis)}{analysis.technicalAssetId&&<small> · ID {analysis.technicalAssetId}</small>}</dd><dt>Janela analisada</dt><dd>{analysis.windowId||'Não informada'} · {when(analysis.windowStart,analysis.windowEnd)}</dd><dt>Modelo</dt><dd>{detectorName(analysis)} · {analysis.modelVersion||'versão não informada'}</dd><dt>Método</dt><dd>{methodLabel(explanation.method)}{explanation.explainerVersion?` · ${explanation.explainerVersion}`:''}</dd><dt>Saída explicada</dt><dd>{output} · {outputLabel}{output==='ANOMALY_SCORE'?` · ${scale}`:explanation.classLabel?` · classe ${explanation.classLabel}`:''}</dd>{output==='CALIBRATED_CLASS_PROBABILITY'&&<><dt>Saída RF antes da calibração</dt><dd>Não fornecida por este contrato de explicação.</dd></>}<dt>Valor de referência</dt><dd>{formatModelValue(explanation.baseValue,output)}{explanation.referenceRef?` · ${explanation.referenceRef}`:''}</dd><dt>Resultado da janela</dt><dd>{formatModelValue(explanation.outputValue,output)}</dd><dt>Principal contribuição</dt><dd>{sorted[0]?`${sorted[0].feature} · valor ${numberText(sorted[0].value)} · contribuição ${contributionValue(sorted[0].contribution,output)}`:'Sem contribuição informada'}</dd><dt>Resumo</dt><dd>{explanation.summary||'Sem resumo registrado pela API.'}</dd></dl>
  <p className="model-analysis-note">{output==='CALIBRATED_CLASS_PROBABILITY'?'Valor calibrado da classe; não representa por si só o risco total.':'Score de anomalia na escala operacional; não é porcentagem nem probabilidade de ataque.'}</p>
  <h3>Contribuições desta explicação</h3>
  <ol className="model-contributions">{sorted.map((item,index)=>{const positive=item.contribution>=0;const width=item.contribution===0||!max?0:Math.max(1,Math.abs(item.contribution)/max*50);return <li key={`${item.feature}-${index}`}>
   <div className="model-feature"><strong>{item.feature}</strong><span>Valor observado: {numberText(item.value)}</span></div>
   <div className="model-contribution-plot" role="img" aria-label={`${contributionDirection(item.contribution,explanation.outputDirection)}: ${contributionValue(item.contribution,output)}`}><span className="model-contribution-axis"/><span className={positive?'model-contribution-bar positive':'model-contribution-bar negative'} style={positive?{left:'50%',width:`${width}%`}:{right:'50%',width:`${width}%`}}/></div>
   <div className="model-contribution-text"><span>{contributionDirection(item.contribution,explanation.outputDirection)}</span><strong>{contributionValue(item.contribution,output)}</strong></div>
  </li>})}</ol>
  <div className="table-wrap model-contribution-table" tabIndex={0}><table><caption>Características da mesma explicação {explanation.id} · revisão {explanation.projectionRevision}</caption><thead><tr><th>Característica</th><th>Valor observado</th><th>Contribuição com sinal</th><th>Direção</th></tr></thead><tbody>{sorted.map((item,index)=><tr key={`${item.feature}-table-${index}`}><th scope="row">{item.feature}</th><td>{numberText(item.value)}</td><td>{contributionValue(item.contribution,output)}</td><td>{contributionDirection(item.contribution,explanation.outputDirection)}</td></tr>)}</tbody></table></div>
  <div className="model-analysis-meta"><span>Registro {explanation.id} · revisão {explanation.projectionRevision}</span><span>{explanation.createdAt?new Date(explanation.createdAt).toLocaleString('pt-BR'):'Horário não informado'}</span></div>
  {explanation.limitations.length>0&&<details className="model-limitations"><summary>Limitações informadas</summary><ul>{explanation.limitations.map((item,index)=><li key={`${item}-${index}`}>{item}</li>)}</ul></details>}
 </article>;
}

export function ModelAnalysis({incidents,client,selectedIncidentId,onIncidentChange}:ModelAnalysisProps){
 const [localIncidentId,setLocalIncidentId]=useState<string|null>(null);
 const resolvedIncidentId=selectedIncidentId===undefined?(localIncidentId??(incidents[0]?incidentIdentity(incidents[0])?.id??null:null)):selectedIncidentId;
 const selectedIncident=incidents.find(row=>incidentIdentity(row)?.id===resolvedIncidentId)||null;
 const identity=selectedIncident?incidentIdentity(selectedIncident):null;
 const clientRef=useRef(client);clientRef.current=client;
 const sequence=useRef(0);
 const [retry,setRetry]=useState(0);
 const [response,setResponse]=useState<{key:string;value:IncidentModelResponse}|null>(null);
 const [requestedKey,setRequestedKey]=useState('');
 const [requestState,setRequestState]=useState<'idle'|'loading'|'ready'|'error'>('idle');
 const [error,setError]=useState('');
 const queryKey=identity?`${identity.id}@${identity.revision}:${retry}`:'';

 useEffect(()=>{
  const request=++sequence.current;let active=true;
  setRequestedKey(queryKey);
  setResponse(null);setError('');
  if(!identity){setRequestState('idle');return()=>{active=false}};
  setRequestState('loading');
  const path=`/api/v1/p11/incidents/${encodeURIComponent(identity.id)}/explanations?incident_revision=${identity.revision}`;
  void clientRef.current.get(path).then(raw=>{
   if(!active||request!==sequence.current)return;
   const parsed=parseIncidentModelResponse(raw,identity.id,identity.revision);
   if(!parsed){setRequestState('error');setError('A API retornou análise incompatível com o incidente ou revisão selecionados.');return}
   setResponse({key:queryKey,value:parsed});setRequestState('ready');
  }).catch(reason=>{
   if(!active||request!==sequence.current)return;
   setRequestState('error');setError((reason as Error)?.message||'Falha ao consultar a API de análise do modelo.');
  });
  return()=>{active=false};
 },[identity?.id,identity?.revision,retry]);

 const visibleResponse=response?.key===queryKey?response.value:null;
 const displayState=queryKey&&requestedKey!==queryKey?'loading':requestState;
 const analyses=visibleResponse?.analyses||[];
 const changeIncident=(id:string)=>{setLocalIncidentId(id);onIncidentChange?.(id)};
 const available=analyses.flatMap(analysis=>analysis.state==='available'?analysis.explanations.map(explanation=>({analysis,explanation})):[]);

 return <Panel title="Análise do modelo (XAI/SHAP)">
  <div className="model-analysis-controls">
   <label>Incidente<select aria-label="Incidente da análise do modelo" value={resolvedIncidentId||''} onChange={event=>changeIncident(event.target.value)}>
    {!incidents.length&&<option value="">Nenhum incidente disponível</option>}
    {incidents.map(row=>{const id=incidentIdentity(row)?.id;return id?<option key={id} value={id}>{id} · {String(row.data.status||'estado não informado')}</option>:null})}
   </select></label>
   {identity&&<small>Revisão selecionada {identity.revision}. Cada ficha abaixo usa somente explicações vinculadas a este incidente e revisão.</small>}
  </div>
  {!incidents.length?<Empty>Explicação não disponível: nenhum incidente foi retornado.</Empty>:!identity?<p role="status" className="model-analysis-state">A revisão do incidente selecionado não está disponível.</p>:displayState==='loading'?<p role="status" className="model-analysis-state">Consultando explicação vinculada ao incidente…</p>:displayState==='error'?<div className="model-analysis-error" role="alert"><span>Falha ao consultar a API de análise do modelo.</span><small>{error}</small><button type="button" onClick={()=>setRetry(value=>value+1)}>Tentar novamente</button></div>:displayState==='ready'&&available.length? <div className="model-analysis-cards">{analyses.map(analysis=>analysis.state==='available'&&analysis.explanations.length?analysis.explanations.map(explanation=><ExplanationCard key={`${analysis.detectionId}:${explanation.id}:${explanation.projectionRevision}`} analysis={analysis} explanation={explanation}/>):analysis.state==='invalid'?<p key={analysis.detectionId} role="alert" className="model-analysis-error">Explicação inválida para a detecção {analysis.detectionId}.</p>:analysis.state==='unavailable'?<p key={analysis.detectionId} role="status" className="model-analysis-state">Análise indisponível para {analysis.detectionId}{analysis.reasonCode?` · ${analysis.reasonCode}`:''}.</p>:<Empty key={analysis.detectionId}>Explicação não disponível para a detecção {analysis.detectionId}.</Empty>)}</div>:displayState==='ready'?<Empty>Explicação não disponível para o incidente selecionado.</Empty>:null}
 </Panel>;
}
