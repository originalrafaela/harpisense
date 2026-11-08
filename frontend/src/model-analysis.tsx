import {useEffect,useMemo,useRef,useState} from 'react';
import type {Client,Row} from './api';
import {Empty,Panel} from './components';
import {contributionDirection,formatModelValue,incidentIdentity,methodLabel,parseIncidentModelResponse,type IncidentModelResponse,type ModelAnalysis,type ModelExplanation} from './model-analysis-data';
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
const when=(start:string|null,end:string|null)=>start&&end?`${new Date(start).toLocaleString('pt-BR')} — ${new Date(end).toLocaleString('pt-BR')}`:'Janela sem horário informado';
const contributionValue=(value:number,output:ModelExplanation['output'])=>output==='CALIBRATED_CLASS_PROBABILITY'?`${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2,signDisplay:'always'}).format(value*100)} pp`:new Intl.NumberFormat('pt-BR',{maximumFractionDigits:6,signDisplay:'always'}).format(value);

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
 const [selectedDetection,setSelectedDetection]=useState('');
 const [selectedExplanation,setSelectedExplanation]=useState('');
 const queryKey=identity?`${identity.id}@${identity.revision}:${retry}`:'';

 useEffect(()=>{
  const request=++sequence.current;let active=true;
  setRequestedKey(queryKey);
  setResponse(null);setSelectedDetection('');setSelectedExplanation('');setError('');
  if(!identity){setRequestState('idle');return()=>{active=false}};
  setRequestState('loading');
  const path=`/api/v1/p11/incidents/${encodeURIComponent(identity.id)}/explanations?incident_revision=${identity.revision}`;
  void clientRef.current.get(path).then(raw=>{
   if(!active||request!==sequence.current)return;
   const parsed=parseIncidentModelResponse(raw,identity.id,identity.revision);
   if(!parsed){setRequestState('error');setError('A API retornou análise incompatível com o incidente ou revisão selecionados.');return}
   setResponse({key:queryKey,value:parsed});setRequestState('ready');
   const first=parsed.analyses.find(item=>item.state==='available')||parsed.analyses[0];
   setSelectedDetection(first?.detectionId||'');
   setSelectedExplanation(first?.explanations[0]?.id||'');
  }).catch(reason=>{
   if(!active||request!==sequence.current)return;
   setRequestState('error');setError((reason as Error)?.message||'Falha ao consultar a API de análise do modelo.');
  });
  return()=>{active=false};
 },[identity?.id,identity?.revision,retry]);

 const visibleResponse=response?.key===queryKey?response.value:null;
 const displayState=queryKey&&requestedKey!==queryKey?'loading':requestState;
 const analyses=visibleResponse?.analyses||[];
 const activeAnalysis=analyses.find(item=>item.detectionId===selectedDetection)||analyses.find(item=>item.state==='available')||analyses[0]||null;
 const explanation=activeAnalysis?.explanations.find(item=>item.id===selectedExplanation)||activeAnalysis?.explanations[0]||null;
 const sortedContributions=useMemo(()=>explanation?[...explanation.contributions].sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution)):[],[explanation]);
 const maxContribution=Math.max(0,...sortedContributions.map(item=>Math.abs(item.contribution)));
 const changeIncident=(id:string)=>{setLocalIncidentId(id);onIncidentChange?.(id)};
 const chooseDetection=(analysis:ModelAnalysis)=>{setSelectedDetection(analysis.detectionId);setSelectedExplanation(analysis.explanations[0]?.id||'')};
 const output=explanation?.output;

 return <Panel title="Análise do modelo (XAI/SHAP)">
  <div className="model-analysis-controls">
   <label>Incidente<select aria-label="Incidente da análise do modelo" value={resolvedIncidentId||''} onChange={event=>changeIncident(event.target.value)}>
    {!incidents.length&&<option value="">Nenhum incidente disponível</option>}
    {incidents.map(row=>{const id=incidentIdentity(row)?.id;return id?<option key={id} value={id}>{id} · {String(row.data.status||'estado não informado')}</option>:null})}
   </select></label>
   {activeAnalysis&&activeAnalysis.explanations.length>1&&<label>Explicação<select value={explanation?.id||''} onChange={event=>setSelectedExplanation(event.target.value)}>{activeAnalysis.explanations.map(item=><option key={item.id} value={item.id}>{item.id} · rev. {item.projectionRevision}</option>)}</select></label>}
  </div>
  {displayState==='ready'&&activeAnalysis&&analyses.length>1&&<div className="model-analysis-tabs" role="tablist" aria-label="Modelo e janela da análise">
   {analyses.map(item=><button type="button" role="tab" aria-selected={item.detectionId===activeAnalysis.detectionId} key={item.detectionId} onClick={()=>chooseDetection(item)}>
    {detectorName(item)} · {item.windowId}
   </button>)}
  </div>}
  {!incidents.length?<Empty>Explicação não disponível: nenhum incidente foi retornado.</Empty>:!identity?<p role="status" className="model-analysis-state">A revisão do incidente selecionado não está disponível.</p>:displayState==='loading'?<p role="status" className="model-analysis-state">Consultando explicação vinculada ao incidente…</p>:displayState==='error'?<div className="model-analysis-error" role="alert"><span>Falha ao consultar a API de análise do modelo.</span><small>{error}</small><button type="button" onClick={()=>setRetry(value=>value+1)}>Tentar novamente</button></div>:displayState==='ready'&&!activeAnalysis?<Empty>Explicação não disponível para o incidente selecionado.</Empty>:activeAnalysis?.state==='absent'?<Empty>Explicação não disponível para esta observação.</Empty>:activeAnalysis?.state==='invalid'?<p role="alert" className="model-analysis-error">A explicação retornada não passou na validação do contrato.</p>:activeAnalysis?.state==='unavailable'?<p role="status" className="model-analysis-state">Análise do modelo indisponível{activeAnalysis.reasonCode?` · ${activeAnalysis.reasonCode}`:''}.</p>:activeAnalysis&&explanation&&output?<>
   <section className="model-analysis-result" role="tabpanel" aria-label={`${detectorName(activeAnalysis)} explicação`}>
    <header className="model-analysis-heading"><div><strong>{assetLabel(activeAnalysis)}</strong><small>{activeAnalysis.technicalAssetId&&activeAnalysis.assetName?`ID técnico: ${activeAnalysis.technicalAssetId} · `:''}Incidente {activeAnalysis.incidentId} · rev. {activeAnalysis.incidentRevision}</small></div><div><strong>{detectorName(activeAnalysis)}</strong><small>Modelo {activeAnalysis.modelVersion}</small></div></header>
    <p className="model-analysis-window">Janela {activeAnalysis.windowId} · {when(activeAnalysis.windowStart,activeAnalysis.windowEnd)}</p>
    <div className="model-analysis-scores">
     {output==='CALIBRATED_CLASS_PROBABILITY'?<article><span>Classe analisada</span><strong>{explanation.classLabel||'Não informada'}</strong></article>:<article><span>Score de anomalia (IF)</span><strong>{formatModelValue(explanation.outputValue,output)}</strong></article>}
     <article><span>Valor de referência</span><strong>{formatModelValue(explanation.baseValue,output)}</strong></article>
     <article><span>{output==='CALIBRATED_CLASS_PROBABILITY'?'Probabilidade calibrada · pontuação final':'Pontuação final do modelo'}</span><strong>{formatModelValue(explanation.outputValue,output)}</strong></article>
    </div>
    <div className="model-analysis-meta"><span>Método: {methodLabel(explanation.method)}</span><span>Explicação {explanation.id} · rev. {explanation.projectionRevision}</span></div>
    <h3>Características que influenciaram o resultado</h3>
    <ol className="model-contributions">{sortedContributions.map((item,index)=>{const positive=item.contribution>=0;const width=item.contribution===0||!maxContribution?0:Math.max(1,Math.abs(item.contribution)/maxContribution*50);return <li key={`${item.feature}-${index}`}>
      <div className="model-feature"><strong>{item.feature}</strong><span>Valor observado: {numberText(item.value)}</span></div>
      <div className="model-contribution-plot" aria-hidden="true"><span className="model-contribution-axis"/><span className={positive?'model-contribution-bar positive':'model-contribution-bar negative'} style={positive?{left:'50%',width:`${width}%`}:{right:'50%',width:`${width}%`}}/></div>
      <div className="model-contribution-text"><span>{contributionDirection(item.contribution,explanation.outputDirection)}</span><strong>{contributionValue(item.contribution,output)}</strong></div>
     </li>})}</ol>
    {explanation.limitations.length>0&&<details className="model-limitations"><summary>Limitações informadas</summary><ul>{explanation.limitations.map((item,index)=><li key={`${item}-${index}`}>{item}</li>)}</ul></details>}
   </section>
  </>:displayState==='ready'?<Empty>Explicação não disponível para o incidente selecionado.</Empty>:null}
 </Panel>;
}
