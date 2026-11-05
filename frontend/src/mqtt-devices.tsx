import React,{useEffect,useState,type ReactNode} from 'react';
import {ApiError,object} from './api';
import {Badge} from './components';

type Data=Record<string,unknown>;
const modeName=(mode:unknown)=>mode==='local_managed'?'Broker local gerenciado pelo HarpiSense':mode==='external'?'Broker externo':'Não informado pelo backend';
const parametersOf=(document:unknown):Data=>object(document)&&object(document.parameters)?document.parameters:{};
const validStatus=(value:unknown):value is Data=>object(value)&&value.schema_version==='1.0.0'&&
 ['component','broker','consumer'].every(key=>object(value[key])&&
  (value[key].state==='not_verified'||value[key].state===({component:'installed',broker:'available',consumer:'connected'} as Data)[key])&&
  (value[key].observed_at===null||typeof value[key].observed_at==='string'&&Number.isFinite(Date.parse(value[key].observed_at))))&&
 Array.isArray(value.devices)&&value.devices.every(item=>object(item)&&typeof item.device_id==='string'&&typeof item.observed_at==='string')&&
 ['not_verified','observed'].includes(String(value.device_observation));
export type MqttDevicesProps={
 capabilities:unknown;parameters:Data;savedParameters:Data|null;current:Data|null;
 request:(path:string,method?:string,body?:unknown)=>Promise<unknown>;logout:()=>void;
 change:(key:string,value:unknown)=>void;busy:boolean;children:ReactNode;
 errors:Record<string,string>;
};

/** One controlled editor: persistence, proposal and audit belong to ConfigManager. */
export function MqttDevices({capabilities,parameters,savedParameters,current,request,logout,change,busy,children,errors}:MqttDevicesProps){
 const supported=object(capabilities)&&capabilities.schema_version==='1.0.0';
 const constraints=supported&&object(capabilities.constraints)?capabilities.constraints:{};
 const modes=supported&&Array.isArray(capabilities.modes)?capabilities.modes:[];
 const [attempt,setAttempt]=useState(0);
 const [query,setQuery]=useState<{request:MqttDevicesProps['request'];attempt:number;value:Data|null;failed:boolean}|null>(null);
 useEffect(()=>{let active=true;void request('/mqtt/status').then(value=>{
  if(active)setQuery({request,attempt,value:validStatus(value)?value:null,failed:!validStatus(value)});
 },error=>{if(!active)return;if(error instanceof ApiError&&error.kind==='unauthorized')logout();setQuery({request,attempt,value:null,failed:true})});return()=>{active=false}},[request,logout,attempt]);
 const result=query?.request===request&&query.attempt===attempt?query:null;
 const observed=result?.value;
 const stateOf=(key:string)=>observed&&object(observed[key])?observed[key] as Data:null;
 const broker=stateOf('broker'), consumer=stateOf('consumer');
 const fresh=(entry:Data|null)=>entry&&typeof entry.observed_at==='string'&&Date.now()-Date.parse(entry.observed_at)<=45000;
 const brokerAvailable=broker?.state==='available'&&fresh(broker);
 const consumerConnected=consumer?.state==='connected'&&fresh(consumer);
 const devices=observed&&Array.isArray(observed.devices)?observed.devices.filter(object):[];
 const awaiting=brokerAvailable&&consumerConnected&&observed?.device_observation==='observed'&&devices.length===0&&Array.isArray(observed?.inventory)&&observed.inventory.length>0;
 const effective=parametersOf(current?.effective);
 const proposed=parametersOf(current?.proposed);
 const hasEffective=typeof current?.effective_revision==='number'&&current.effective_revision>0&&Object.keys(effective).some(k=>k.startsWith('mqtt_'));
 const hasSaved=Boolean(savedParameters&&Object.keys(savedParameters).some(k=>k.startsWith('mqtt_')));
 const existingWithoutMode=Boolean(savedParameters?.mqtt_broker_host||effective.mqtt_broker_host)&&savedParameters?.mqtt_broker_mode===undefined;
 const selected=parameters.mqtt_broker_mode??(!existingWithoutMode&&supported&&modes.includes(capabilities.default_mode)?capabilities.default_mode:'');
 const topics=Array.isArray(parameters.mqtt_topics)?parameters.mqtt_topics.join('\n'):'';
 return <section aria-label="MQTT e dispositivos">
  <h3>MQTT e dispositivos</h3>
  <p>Use esta mesma área no primeiro uso e depois em Configurações. Salvar prepara um rascunho; validar parâmetros não testa a conexão nem aplica alterações.</p>
  <div className="config-status-grid">
   <article aria-label="Rascunho MQTT"><strong>Rascunho MQTT</strong><Badge>{hasSaved?'Rascunho salvo':'Sem rascunho MQTT salvo'}</Badge><p>Modo salvo: {modeName(savedParameters?.mqtt_broker_mode)}</p><p>Destino salvo: {String(savedParameters?.mqtt_broker_host??'Não informado')}</p></article>
   <article aria-label="Configuração efetiva MQTT"><strong>Configuração efetiva MQTT</strong><p>{hasEffective?`Revisão ${String(current?.effective_revision)}`:'Nenhuma configuração MQTT efetiva comprovada'}</p>{hasEffective&&<><p>Modo efetivo: {modeName(effective.mqtt_broker_mode)}</p><p>Destino efetivo: {String(effective.mqtt_broker_host??'Não informado')}</p></>}<small>Uma edição ou proposta não substitui o destino efetivo.</small></article>
   <article aria-label="Proposta MQTT"><strong>Proposta MQTT</strong><p>{Object.keys(proposed).some(k=>k.startsWith('mqtt_'))?(current?.proposed_status==='VALIDATED'?'Proposta validada em parâmetros; conexão não verificada':`Estado informado: ${String(current?.proposed_status??'Não verificado')}`):'Nenhuma proposta MQTT informada'}</p></article>
  </div>
  <div className="config-status-grid" aria-label="Observações MQTT">
   <article><strong>Componente instalado</strong><p>{stateOf('component')?.state==='installed'?'Instalado pelo instalador nativo':'Não verificado'}</p></article>
   <article><strong>Broker disponível</strong><p>{brokerAvailable?'Disponível · MQTT autenticado':'Não verificado'}</p></article>
   <article><strong>Consumidor conectado</strong><p>{consumerConnected?'Conectado · assinatura confirmada':'Não verificado'}</p></article>
   <article><strong>Última mensagem por dispositivo</strong>{devices.length?devices.map(item=><p key={String(item.device_id)}>{String(item.device_id)} · {String(item.message_id??'Identificador não informado')} · {String(item.observed_at)}</p>):<p>{awaiting?'Broker ativo, aguardando primeira mensagem':'Não verificado'}</p>}<small>Recebimento observado não comprova sensor físico ou defesa disponível.</small></article>
  </div>
  {!result?<p role="status">Consultando estados MQTT…</p>:result.failed?<p role="alert">Não foi possível consultar os estados MQTT. Não verificado; o rascunho foi preservado.</p>:<p>{observed?.device_observation==='observed'?'Observação do consumidor nativo; estados de conexão perdem validade após 45 segundos sem atualização.':'O backend ainda não confirmou observação MQTT. Lista vazia não comprova ausência de dispositivos.'}</p>}
  <button type="button" disabled={!result} onClick={()=>setAttempt(n=>n+1)}>Atualizar estados MQTT</button>
  {!supported&&<p role="alert">Capacidades MQTT indisponíveis ou incompatíveis. Nenhuma operação MQTT será presumida.</p>}
  <fieldset disabled={busy||!supported}>
   <legend>Destino MQTT · rascunho em edição</legend>
   <label>Modo do broker<select value={String(selected)} onChange={e=>change('mqtt_broker_mode',e.target.value)}><option value="">Selecione um modo autorizado</option>{modes.includes('local_managed')&&<option value="local_managed">Broker local gerenciado pelo HarpiSense</option>}{modes.includes('external')&&<option value="external">Broker externo</option>}</select></label>
   <p>Modo escolhido: {modeName(selected)}. {parameters.mqtt_broker_mode===undefined?'Sugestão ainda não salva; não determina o modo da configuração existente.':'Seleção do formulário; ainda depende de salvar, validar e aplicar.'}</p>
   <p>{selected==='external'?'O HarpiSense não altera o servidor externo. Use um destino e referências autorizados.':'O instalador nativo instala o componente e registra o serviço no Windows ou Ubuntu com as permissões do sistema.'}</p>
   <label>Host do broker MQTT<input value={String(parameters.mqtt_broker_host??'')} onChange={e=>change('mqtt_broker_host',e.target.value)} autoComplete="off" maxLength={253}/></label>
   <label>Porta<input type="number" min="1" max="65535" value={String(parameters.mqtt_broker_port??'')} onChange={e=>change('mqtt_broker_port',e.target.value?Number(e.target.value):undefined)}/></label>
   <label>Modo TLS<input value="required" readOnly/></label>
   <label>Referência do certificado CA<input value={String(parameters.mqtt_ca_ref??'')} onChange={e=>change('mqtt_ca_ref',e.target.value)} autoComplete="off"/></label>
   <label>Referência opaca da identidade MQTT<input value={String(parameters.mqtt_identity_secret_ref??'')} onChange={e=>change('mqtt_identity_secret_ref',e.target.value)} autoComplete="off" placeholder="secret://…"/></label>
   <label>Tópicos autorizados<textarea value={topics} onChange={e=>change('mqtt_topics',e.target.value.split('\n'))}/></label>
   <label>ID do cliente MQTT<input value={String(parameters.mqtt_client_id??'')} onChange={e=>change('mqtt_client_id',e.target.value)} autoComplete="off"/></label>
   <p>Destinos autorizados: {Array.isArray(constraints.hosts)?constraints.hosts.join(', ')||'nenhum':'Não informado'}. Tópicos: {Array.isArray(constraints.topics)?constraints.topics.join(', ')||'nenhum':'Não informado'}. Uma lista vazia não autoriza qualquer destino.</p>
   {Object.entries(errors).filter(([key])=>key.includes('mqtt_')).map(([key,message])=><p role="alert" key={key}>{message}</p>)}
  </fieldset>
  <p>Informe somente referências do cofre; nunca senhas técnicas. Selecionar um perfil não grava firmware, não ativa MQTT e não habilita IDS/IPS. O instalador funciona sem Wokwi.</p>
  <fieldset disabled={busy}><legend>Dispositivos preparatórios</legend>{children}</fieldset>
  <div className="flow-actions"><button disabled>Verificar conexão — indisponível</button><button disabled>Aplicar MQTT — indisponível</button><button disabled>Cadastrar dispositivo — indisponível</button></div>
  <p>O contrato atual permite salvar e validar parâmetros. Ainda não oferece teste real de conexão, aplicação com recuperação ou cadastro operacional. O destino efetivo permanece preservado.</p>
 </section>;
}
