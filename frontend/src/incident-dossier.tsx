import {useEffect,useRef,useState} from 'react';
import type {Client,Row} from './api';
import {formatTime} from './presentation';
import {incidentIdentity} from './model-analysis-data';
import {data,methodName,outputName,parseDossier,text,type Dossier} from './incident-dossier-data';

type Props={client?:Pick<Client,'get'>;incident:Row;compact?:boolean;showLogs?:boolean;onTechnical?:(id:string)=>void};
const signed=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('pt-BR',{maximumFractionDigits:6,signDisplay:'always'}).format(v):'Não informado';
const numeric=(v:unknown)=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('pt-BR',{maximumFractionDigits:6}).format(v):'Não informado';
function Fields({fields}:{fields:[string,string][]}){return <dl className="dossier-fields">{fields.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
function recordDescription(value:unknown,missing:string){const entry=data(value);if(entry.state==='missing')return missing;const rows=Array.isArray(entry.records)?entry.records:[];if(!rows.length)return missing;return rows.map(row=>{const r=data(row);const d=data(r.data||r);const action=data(d.action);return [text(d.action_type??action.action_type,''),text(d.status,''),text(d.result,'')].filter(Boolean).join(' · ')||text(r.id??d.decision_id??d.execution_id,'Registro vinculado')}).join('; ')}
function LogRecord({row}:{row:Record<string,unknown>}){const d=data(row.data);const observed=d.observed_at??d.timestamp??d.created_at??row.created_at;const endpoints=[text(d.source_ip,''),text(d.destination_ip,'')].filter(Boolean).join(' → ');return <li><strong>{text(d.event_type??d.type??row.kind,'Evento de rede')}</strong><time>{observed?formatTime(text(observed)):'Horário não registrado'}</time>{d.message||d.text||d.summary?<p>{text(d.message??d.text??d.summary)}</p>:null}{endpoints&&<p>{endpoints}{d.protocol?` · ${text(d.protocol)}`:''}</p>}<small>ID {text(row.id)} · revisão {text(row.revision)} · origem {text(row.source)}</small></li>}
export function TechnicalDossier({card}:{card:Record<string,unknown>}){
 const asset=data(card.asset),window=data(card.window),model=data(card.model),output=data(card.output),reference=data(card.reference),result=data(card.result),principal=data(card.principal_contribution);
 return <article className="technical-dossier"><h3>{methodName(card.method)}</h3><Fields fields={[
  ['Incidente ou detecção',text(data(card.incident_ref).id??card.detection_id)],['Ativo',text(asset.display_name??asset.technical_id,'Ativo não identificado')],
  ['Janela analisada',window.start&&window.end?`${formatTime(text(window.start))} — ${formatTime(text(window.end))}`:'Não informada'],
  ['Modelo',`${model.detector==='random_forest'?'RF':model.detector==='isolation_forest'?'IF':text(model.detector)} · ${text(model.model_version)}`],
  ['Método',methodName(card.method)],['Saída explicada',outputName(output.kind,output.class_label)],['Valor de referência',numeric(reference.value)],['Resultado da janela',numeric(result.value)],
  ['Principal contribuição',principal.feature?`${text(principal.feature)} · valor ${numeric(principal.value)} · contribuição ${signed(principal.contribution)}`:'Não informada'],['Resumo',text(card.summary,'Explicação não disponível')]
 ]}/></article>;
}
export function IncidentDossier({client,incident,compact=false,showLogs=false,onTechnical}:Props){
 const identity=incidentIdentity(incident);const key=identity?`${identity.id}@${identity.revision}`:'';
 const clientRef=useRef(client);clientRef.current=client;const keyRef=useRef(key);keyRef.current=key;
 const [response,setResponse]=useState<{key:string;dossier:Dossier}|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(false);const [refresh,setRefresh]=useState(0);
 const [assessment,setAssessment]=useState('confirmed');const [reason,setReason]=useState('');const [saving,setSaving]=useState(false);const [notice,setNotice]=useState('');
 useEffect(()=>{let active=true;setResponse(null);setError('');setNotice('');setReason('');if(!identity||!clientRef.current){setLoading(false);return}setLoading(true);void clientRef.current.get(`/api/v1/p11/incidents/${encodeURIComponent(identity.id)}/dossier?incident_revision=${identity.revision}`).then(raw=>{if(!active)return;const dossier=parseDossier(raw,identity.id,identity.revision);if(!dossier)throw new Error('Ficha incompatível com o incidente selecionado.');setResponse({key,dossier})}).catch(e=>{if(active)setError((e as Error).message)}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[key,refresh,!!client]);
 const dossier=response?.key===key?response.dossier:null;const card=data(dossier?.incident_card);const asset=data(card.asset),anomaly=data(card.anomaly),attack=data(card.attack_assessment),situation=data(card.attack_situation),mode=data(card.operational_mode);
 const latest=Array.isArray(dossier?.latest_explanations)?dossier.latest_explanations.filter(value=>typeof value==='object'&&value!==null).slice(0,3) as Record<string,unknown>[]:[];
 const observations=Array.isArray(anomaly.observations)?anomaly.observations:[];
 const observationText=observations.map(v=>{if(typeof v==='string')return v;const row=data(v),classification=data(row.classification),anomalyValue=data(row.anomaly);return classification.predicted_class?`RF: ${text(classification.predicted_class)} · confiança ${numeric(classification.confidence)}`:typeof anomalyValue.is_anomaly==='boolean'?`IF: ${anomalyValue.is_anomaly?'anomalia detectada':'sem anomalia detectada'} · score ${numeric(anomalyValue.anomaly_score)}`:text(row.text??row.observation??row.label,'Observação registrada')}).join('; ')||'Sem observação registrada';
 const attackText=attack.state==='confirmed'?'Sim':attack.state==='discarded'?'Não':attack.state==='inconclusive'?'Inconclusivo':'Não avaliado';
 async function saveAssessment(){if(!identity||!clientRef.current||saving)return;const requestedKey=key;setSaving(true);setNotice('');try{const raw=await clientRef.current.get(`/api/v1/p11/incidents/${encodeURIComponent(identity.id)}/assessments`,'POST',{incident_revision:identity.revision,assessment,reason});const result=data(raw);const effects=data(result.side_effects);if(effects.profile_changed!==false||effects.defense_approved!==false||effects.defense_dispatched!==false)throw new Error('Resposta de avaliação incompatível.');if(requestedKey===keyRef.current){setNotice('Avaliação registrada; perfil e defesa preservados.');setRefresh(v=>v+1)}}catch(e){if(requestedKey===keyRef.current)setError((e as Error).message)}finally{setSaving(false)}}
 return <div className={showLogs?'incident-dossier-layout':'incident-dossier'}>
  <section aria-label="Ficha do incidente"><h3>Ficha do incidente</h3>{loading?<p role="status">Consultando ficha…</p>:error?<p role="alert" className="error">{error}</p>:!dossier?<p>Explicação não disponível</p>:<>
   <Fields fields={[
    ['Incidente',text(card.incident_id)],['Data',card.occurred_at?formatTime(text(card.occurred_at)):'Horário não registrado'],['Ativo',text(asset.display_name??asset.technical_id,'Ativo não identificado')],
    ['Anomalia',`${observationText} — ataque confirmado: ${attackText}`],['Situação do ataque',text(situation.value,'Estado não registrado')],
    ['Decisão de defesa',recordDescription(card.defense_decision,'Sem registro de decisão')],['Execução de defesa',recordDescription(card.defense_execution,'Sem registro de execução')],['Modo operacional',text(mode.value,'Não registrado na decisão')]
   ]}/>
   {compact?<section className="latest-explanations" aria-label="Últimas três explicações"><h4>Últimas explicações</h4>{latest.length?latest.map((technical,index)=><p key={String(data(technical.explanation).id??index)}><strong>{methodName(technical.method)}</strong> · {text(technical.summary,'Explicação não disponível')}</p>):<p>Explicação não disponível</p>}</section>:<section aria-label="Fichas técnicas">{dossier.technical_cards.length?dossier.technical_cards.map((technical,index)=><TechnicalDossier key={String(data(technical.explanation).id??index)} card={technical}/>):<p>Explicação não disponível</p>}</section>}
   {!compact&&<form className="incident-assessment" onSubmit={e=>{e.preventDefault();void saveAssessment()}}><h3>Avaliação do incidente</h3><label>Avaliação<select value={assessment} onChange={e=>setAssessment(e.target.value)}><option value="confirmed">Ataque confirmado</option><option value="discarded">Ataque descartado</option><option value="inconclusive">Inconclusivo</option></select></label><label>Motivo<textarea required minLength={3} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={saving||reason.trim().length<3}>{saving?'Registrando…':'Registrar avaliação'}</button><small>A avaliação não aprova nem executa uma defesa.</small>{notice&&<p role="status">{notice}</p>}</form>}
   {dossier.missing_links.length>0&&!compact&&<details><summary>Vínculos ainda indisponíveis</summary><ul>{dossier.missing_links.map((value,index)=><li key={index}>{text(value,text(data(value).reason??data(value).code))}</li>)}</ul></details>}
  </>}
  <div className="harpia-actions">{identity&&<button type="button" disabled={!onTechnical} onClick={()=>onTechnical?.(identity.id)}>Ver análise técnica</button>}{compact&&<a className="button-link" href="#harpia">Abrir HarpIA</a>}</div></section>
  {showLogs&&<section aria-label="Logs vinculados"><h3>Logs do incidente</h3>{dossier?.logs.length?<ol className="linked-logs">{dossier.logs.map((row,index)=><LogRecord key={text(row.id,String(index))} row={row}/>)}</ol>:<p>{loading?'Consultando logs…':'Sem logs vinculados disponíveis'}</p>}</section>}
 </div>;
}
