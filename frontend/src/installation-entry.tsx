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
  {!result?<p role="status">Consultando progresso…</p>:
   result.failed?<p role="alert">Instalação indisponível</p>:
   snapshot?.status==='new'?<p role="status">Primeira configuração · não iniciada</p>:
   snapshot?.status==='pending'?<p role="status">Configuração pendente{snapshot.setup.document?` · etapa ${snapshot.setup.document.step}`:' · rascunho não iniciado'}</p>:
   <p role="status">Revisão aplicada: {String(snapshot?.current.effective_revision??'não informada')}</p>}
  {snapshot&&<dl className="installation-progress"><dt>Versão do progresso</dt><dd>{snapshot.setup.version}</dd><dt>Revisão desejada</dt><dd>{String(snapshot.current.desired_revision)}</dd><dt>Revisão efetiva</dt><dd>{String(snapshot.current.effective_revision??'não informada')}</dd><dt>Estado operacional</dt><dd>{snapshot.current.operational===true?'Confirmado pelo backend':'Não confirmado'}</dd></dl>}
  <div className="flow-actions">
   {snapshot&&onOpenSettings&&<button type="button" onClick={onOpenSettings}>{snapshot.status==='new'?'Iniciar assistente':snapshot.status==='pending'?'Retomar assistente':'Abrir Configurações'}</button>}
   <button type="button" disabled={!result} onClick={()=>setAttempt(n=>n+1)}>{result?.failed?'Tentar consultar novamente':'Atualizar progresso'}</button>
  </div>
  {!onOpenSettings&&snapshot&&<p>Assistente em Configurações</p>}
 </Panel>;
}
