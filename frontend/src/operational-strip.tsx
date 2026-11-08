import {useEffect,useRef,useState} from 'react';
import type {ControlState} from './api';
import type {DashboardContext} from './dashboard';
import {formatTime} from './presentation';

export function OperationalStrip({context}:{context:DashboardContext}){
 const [state,setState]=useState<ControlState|null>(null);
 const [candidate,setCandidate]=useState<1|2|3>(1);
 const [error,setError]=useState('');const [message,setMessage]=useState('');
 const [applying,setApplying]=useState(false);const [stopping,setStopping]=useState(false);
 const [fresh,setFresh]=useState(false);const [expanded,setExpanded]=useState(false);
 const [known,setKnown]=useState<{id:string;state:string}[]>([]);
 const selectionEdited=useRef(false);
 const loadRef=useRef(context.loadControls);loadRef.current=context.loadControls;
 const onControls=useRef(context.onControls);onControls.current=context.onControls;
 useEffect(()=>{let live=true;let initial=true;
  const load=async()=>{if(!loadRef.current||context.demonstration)return;try{const value=await loadRef.current();if(!live)return;setState(value);setFresh(true);if(initial){if(!selectionEdited.current)setCandidate(value.value.autonomy_mode);initial=false}setKnown(previous=>value.pending.reliable?value.pending.blockers:[...previous.filter(p=>!value.pending.blockers.some(n=>n.id===p.id)),...value.pending.blockers]);onControls.current?.(value)}catch{if(live)setFresh(false)}};
  void load();const timer=setInterval(()=>void load(),10000);return()=>{live=false;clearInterval(timer)};
 },[context.demonstration]);
 const effective=context.demonstration?context.demoControls.autonomy:state?.value.autonomy_mode;
 const cases=known.filter(item=>/^(incident|anomaly|attack):/.test(item.id));
 const reliable=fresh&&state?.pending.reliable===true;
 const activity=cases.length?`${cases.length} caso${cases.length===1?'':'s'} identificado${cases.length===1?'':'s'}${reliable?'':' · cobertura parcial'}`:reliable?'Sem casos ativos':'Estado desconhecido';
 async function apply(){if(context.demonstration){setMessage('Prévia visual: nenhum perfil foi aplicado.');return}if(!state||!context.changeControls)return;setApplying(true);setError('');setMessage('');try{const next=await context.changeControls({...state.value,autonomy_mode:candidate},state.revision,'Alteração de perfil solicitada pelo administrador');setState(next);setFresh(true);context.onControls?.(next);setMessage(`Perfil M${next.value.autonomy_mode} aplicado pelo servidor.`)}catch(e){setError((e as Error).message)}finally{setApplying(false)}}
 async function stop(){if(!context.stopControls||context.demonstration)return;setStopping(true);setError('');try{const next=await context.stopControls('Parada de emergência solicitada pelo administrador');setState(next);context.onControls?.(next);setMessage('Parada de emergência confirmada pelo servidor.')}catch(e){setError((e as Error).message)}finally{setStopping(false)}}
 return <section className="operational-strip" aria-label="Controles operacionais">
  <div className="strip-item"><label>Perfil de autonomia<select aria-label="Perfil de autonomia" value={candidate} onChange={e=>{selectionEdited.current=true;setCandidate(Number(e.target.value) as 1|2|3)}}>{[1,2,3].map(n=><option key={n} value={n}>M{n}</option>)}</select></label><button type="button" disabled={applying||(!context.demonstration&&(!state||!context.changeControls))} onClick={()=>void apply()}>{applying?'Aplicando…':'Aplicar'}</button><small>Selecionado M{candidate} · vigente {effective?`M${effective}`:'desconhecido'}</small></div>
  <button type="button" className="strip-item effective-button" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}><span>Estado Operacional Efetivo</span><strong>{effective?`M${effective}`:'Desconhecido'} · {state?.emergency_stopped?'parado':state?.value.operation||'não confirmado'}</strong><small>Executor: {state?.value.execution_enabled&&state.value.operation==='SIMULATION'?'simulado habilitado':state?.real_execution_blocked?'contenção real indisponível':state?'estado não confirmado':'desconhecido'}</small></button>
  <a className="strip-item activity-button" href="#incidents"><span>Anomalias e ataques</span><strong>{activity}</strong><small>{cases.length?'Abrir casos identificados':'Consultar incidentes'}</small></a>
  <div className="strip-item"><span>Parada de emergência</span><button className="danger-button" type="button" disabled={stopping||context.demonstration||!context.stopControls} onClick={()=>void stop()}>{stopping?'Solicitando…':'Parar'}</button><small>{state?.emergency_stopped?'Parada confirmada':'Independente da seleção de perfil'}</small></div>
  {expanded&&<div className="strip-details"><strong>Estado confirmado pelo backend</strong><dl className="dossier-fields"><div><dt>Última atualização</dt><dd>{state?formatTime(state.updated_at):'Não disponível'}</dd></div><div><dt>Disponibilidade</dt><dd>{fresh?'Consulta disponível':'Comunicação indisponível ou ainda não confirmada'}</dd></div><div><dt>Bloqueios</dt><dd>{state?.pending.dependency||(!fresh?'Estado operacional desconhecido':known.length?known.map(b=>`${b.id}: ${b.state}`).join(' · '):reliable?'Nenhuma pendência autoritativa registrada':'Cobertura desconhecida')}</dd></div></dl></div>}
  {error&&<p role="alert" className="error strip-feedback">{error}</p>}{message&&<p role="status" className="strip-feedback">{message}</p>}
 </section>;
}
