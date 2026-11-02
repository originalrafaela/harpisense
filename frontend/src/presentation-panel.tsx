import React,{useState} from 'react';
import {Panel} from './components';
import {object} from './api';
import {setPresentation,formatTime} from './presentation';

export function PresentationPanel({current,request,refresh}:{current:Record<string,unknown>|null;request:(path:string,method?:string,body?:unknown)=>Promise<unknown>;refresh:()=>Promise<void>}){
 const [password,setPassword]=useState('');const [busy,setBusy]=useState(false);const [result,setResult]=useState('');
 const consumed=object(current?.presentation)?current.presentation:{};
 const parameters=object(consumed.parameters)?consumed.parameters:{};
 const apply=async()=>{
  const secret=password;setPassword('');setBusy(true);setResult('');
  try{
   const proposed=object(current?.proposed)?current.proposed:{};
   const p=object(proposed.parameters)?proposed.parameters:{};
   new Intl.DateTimeFormat('pt-BR',{timeZone:String(p.timezone)});
   const value=await request(`/proposals/${String(current?.proposed_operation_id)}/apply`,'POST',{expected_revision:current?.desired_revision,current_password:secret});
   if(!object(value))throw new Error('Resposta de aplicação incompatível.');
   setPresentation(value.presentation);
   setResult(`${String(value.status)}${value.idempotent?' · repetição idempotente':''}${value.recovery?` · ${String(value.recovery)}`:''}. Somente apresentação; prontidão geral permanece não operacional.`);
  }catch(error){setResult((error as Error).message)}
  finally{setBusy(false);await refresh()}
 };
 return <Panel title="Aplicação da apresentação">
  <p>Autoriza somente o nome da instalação e o fuso de exibição. Não altera o relógio do servidor, instantes armazenados ou outros serviços.</p>
  <p>Consumido pelo sistema: <strong>{String(parameters.display_name||'desconhecido')}</strong> · fuso {String(parameters.timezone||'desconhecido')} · revisão {String(consumed.revision??'nenhuma')} · verificado={String(consumed.verified===true)} · estado {String(consumed.status||'unknown')}.</p>
  <p>Instante original: <code>{String(consumed.original_instant||'não informado')}</code> · Exibição: <time dateTime={String(consumed.original_instant||'')}>{consumed.verified===true?formatTime(consumed.original_instant):'não confirmada'}</time>.</p>
  <p>Estado atual da operação: {String(current?.proposed_status||'sem proposta')}. Resultado persistido da recuperação: {String(consumed.last_result||'sem aplicação anterior')}. Revisão efetiva só avança após verificação do consumidor.</p>
  <label>Senha atual para autorizar apresentação<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} maxLength={128}/></label>
  <button disabled={busy||!password||!['VALIDATED','APPLIED'].includes(String(current?.proposed_status))||consumed.status==='unknown'} onClick={()=>void apply()}>{busy?'Aplicando apresentação…':current?.proposed_status==='APPLIED'?'Repetir aplicação da apresentação':'Autorizar e aplicar apresentação'}</button>
  {result&&<p role="status">Resposta da última solicitação nesta aba: {result}</p>}
  <p>MQTT, captura, detecção e defesa não se tornam operacionais com este resultado. Recuperação não confirmada aparece como desconhecida e bloqueia novas aplicações.</p>
 </Panel>;
}
