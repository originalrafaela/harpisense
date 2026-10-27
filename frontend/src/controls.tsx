import {useEffect,useRef,useState} from 'react';
import {object,type ControlState} from './api';
import {Panel,Badge} from './components';
import {backendControls,type DashboardContext} from './dashboard';

export function EffectiveState({health,context}:{health:Record<string,unknown>|null;context:DashboardContext}){
 const c=context.demonstration?context.demoControls:backendControls(health);
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const enabled=!context.demonstration&&object(health?.control_api)&&health.control_api.version===1;
 return <Panel title="Estado operacional efetivo"><div className="effective-state"><Badge>{c.autonomy?`M${c.autonomy}`:'Autonomia não informada'}</Badge><Badge>{c.operation||'Modo não informado'}</Badge><Badge>{c.execution===null?'Execução não informada':c.execution?'Execução habilitada':'Execução desabilitada'}</Badge>{object(health?.operational_controls)&&health.operational_controls.emergency_stopped===true&&<Badge>Parada de emergência ativa</Badge>}<a href="#settings">Configurar perfis e operação</a></div>
 <small>{context.demonstration?'Prévia visual sem estado operacional.':object(health?.operational_controls)&&typeof health.operational_controls.updated_at==='string'?`Confirmado pelo servidor em ${new Date(health.operational_controls.updated_at).toLocaleString('pt-BR')}`:'Estado efetivo não confirmado pelo servidor.'}</small>
 <p>Execução real bloqueada nesta entrega. Autonomia não habilita execução nem muda o modo operacional.</p>
 <button disabled={!enabled||busy} onClick={async()=>{setBusy(true);setError('');try{const state=await context.stopControls!('Parada solicitada no dashboard');context.onControls?.(state)}catch(e){setError((e as Error).message);context.onControls?.(null)}finally{setBusy(false)}}}>{busy?'Solicitando parada…':'Parada de emergência'}</button>{error&&<p role="alert" className="error">{error}</p>}</Panel>;
}

export function ServerControls({context,health}:{context:DashboardContext;health:Record<string,unknown>|null}){
 const live=useRef(true);useEffect(()=>{live.current=true;return()=>{live.current=false}},[]);
 const [state,setState]=useState<ControlState|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [message,setMessage]=useState('');const [uncertain,setUncertain]=useState(false);
 const [reason,setReason]=useState('');const [operation,setOperation]=useState<'IDS'|'SIMULATION'>('IDS');const [execution,setExecution]=useState(false);
 const enabled=!context.demonstration&&object(health?.control_api)&&health.control_api.version===1&&!!context.loadControls;
 async function load(){setBusy(true);setError('');try{const s=await context.loadControls!();if(!live.current)return;setState(s);setUncertain(false);setOperation(s.value.operation==='SIMULATION'?'SIMULATION':'IDS');setExecution(s.value.execution_enabled);context.onControls?.(s)}catch(e){if(!live.current)return;setState(null);context.onControls?.(null);setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{if(enabled)void load()},[enabled]);
 async function submit(value:ControlState['value']){if(!state)return;setBusy(true);setError('');setMessage('');try{const s=await context.changeControls!(value,state.revision,reason);setState(s);context.onControls?.(s);setMessage(`Servidor confirmou M${s.value.autonomy_mode}, revisão ${s.revision}.`)}catch(e){setError((e as Error).message);setUncertain(true);context.onControls?.(null)}finally{setBusy(false)}}
 return <Panel title="Perfis de autonomia e operação"><p>M1: escolha/aprovação administrativa. M2: Low elegível automático; Medium e Hard exigem aprovação. M3: todos os níveis elegíveis automáticos. A Policy mantém os critérios de evidência, alvo, impacto e permissões.</p>
 {!enabled?<p>Alteração indisponível: {context.demonstration?'prévia visual sem comandos ao servidor.':'API de controles não declarada nesta conexão.'}</p>:<>
 <button disabled={busy} onClick={()=>void load()}>Consultar estado do servidor</button>{busy&&<p role="status">Aguardando servidor…</p>}
 {state&&<><p>Último estado confirmado: M{state.value.autonomy_mode} · {state.value.operation} · execução {state.value.execution_enabled?'habilitada':'desabilitada'} · revisão {state.revision}.</p><small>Alterado em {new Date(state.updated_at).toLocaleString('pt-BR')} · consultado em {new Date(state.observed_at).toLocaleString('pt-BR')}</small>
 <p>{state.pending.reliable?(state.pending.blockers.length?'Há pendências operacionais.':'Fila consultada sem pendências operacionais.'):'Pendências não verificadas. A troca será recusada pelo servidor.'}</p>{state.pending.dependency&&<p>{state.pending.dependency}</p>}{state.pending.blockers.length>0&&<ul>{state.pending.blockers.map(b=><li key={b.id}>{b.id} · {b.state}</li>)}</ul>}
 <label>Justificativa da alteração<input value={reason} onChange={e=>setReason(e.target.value)} minLength={3} maxLength={1000}/></label>
 <div className="autonomy-buttons">{([1,2,3] as const).map(mode=><button key={mode} disabled={busy||uncertain||reason.trim().length<3||state.value.autonomy_mode===mode} aria-pressed={state.value.autonomy_mode===mode} onClick={()=>void submit({...state.value,autonomy_mode:mode})}>Solicitar M{mode}</button>)}</div>
 <details><summary>Configurações avançadas · IDS / SIMULATION / REAL</summary><p>SIMULATION usa executor isolado, sem contenção real. REAL permanece bloqueado. Alterar autonomia preserva estes controles.</p><label>Modo operacional<select value={operation} onChange={e=>{const op=e.target.value as 'IDS'|'SIMULATION';setOperation(op);if(op==='IDS')setExecution(false)}}><option>IDS</option><option>SIMULATION</option><option disabled>REAL</option></select></label><label><input type="checkbox" checked={execution} disabled={operation==='IDS'} onChange={e=>setExecution(e.target.checked)}/> Habilitar somente execução simulada</label><button disabled={busy||uncertain||reason.trim().length<3} onClick={()=>void submit({...state.value,operation,execution_enabled:execution})}>Solicitar configuração avançada</button></details>
 {state.emergency_stopped&&<p>Parada de emergência ativa. Retomada não disponível nesta entrega.</p>}</>}
 </>}{error&&<p role="alert" className="error">{error}</p>}{uncertain&&<p>Alteração não confirmada. Consulte o servidor antes de outra solicitação.</p>}{message&&<p role="status">{message}</p>}</Panel>;
}
