import React,{useEffect,useState} from 'react';
import {Panel} from './components';
import {readInstallation,type InstallationClient,type InstallationSnapshot} from './installation-state';

export type InstallationEntryProps={client:InstallationClient;onOpenSettings?:()=>void};
type Query={client:InstallationClient;attempt:number;value?:InstallationSnapshot;failed?:boolean};

/** Mount after authenticated access to an approved composition. Never redirects or writes. */
export function InstallationEntry({client,onOpenSettings}:InstallationEntryProps){
 const [attempt,setAttempt]=useState(0);
 const [query,setQuery]=useState<Query|null>(null);
 useEffect(()=>{
  let active=true;
  void readInstallation(client).then(value=>{
   if(active)setQuery({client,attempt,value});
  },()=>{if(active)setQuery({client,attempt,failed:true})});
  return()=>{active=false};
 },[client,attempt]);
 const result=query?.client===client&&query.attempt===attempt?query:null;
 const snapshot=result?.value;
 return <Panel title="Instalação e configuração">
  {!result?<p role="status">Consultando progresso persistido… As funções disponíveis continuam acessíveis.</p>:
   result.failed?<p role="alert">Não foi possível consultar a instalação. O estado é desconhecido; as funções disponíveis continuam acessíveis.</p>:
   snapshot?.status==='new'?<p role="status">Instalação nova: nenhum progresso ou revisão de configuração foi registrado. Abra Configurações para iniciar o assistente.</p>:
   snapshot?.status==='pending'?<p role="status">Instalação existente com configuração pendente. {snapshot.setup.document?`O assistente pode ser retomado na etapa ${snapshot.setup.document.step}.`:'Ainda não há rascunho do assistente; a configuração existente será preservada.'}</p>:
   <p role="status">Configuração concluída no escopo da revisão aplicada e confirmada. Isso não comprova prontidão operacional de todos os serviços.</p>}
  {snapshot&&<p>Progresso salvo: versão {snapshot.setup.version}. Revisão desejada: {String(snapshot.current.desired_revision)}. Revisão efetiva: {String(snapshot.current.effective_revision??'nenhuma')}. Prontidão operacional: {snapshot.current.operational===true?'confirmada pelo backend':'não comprovada pelo backend'}.</p>}
  <div className="flow-actions">
   {snapshot&&onOpenSettings&&<button type="button" onClick={onOpenSettings}>{snapshot.status==='new'?'Iniciar assistente':snapshot.status==='pending'?'Retomar assistente':'Abrir Configurações'}</button>}
   <button type="button" disabled={!result} onClick={()=>setAttempt(n=>n+1)}>{result?.failed?'Tentar consultar novamente':'Atualizar progresso'}</button>
  </div>
  {!onOpenSettings&&snapshot&&<p>O assistente permanece acessível em Configurações.</p>}
 </Panel>;
}
