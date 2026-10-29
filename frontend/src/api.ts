export type Profile = 'p11' | 'legacy';
export type Row = {id:string; revision?:number; source?:string; created_at?:string; data:Record<string,unknown>};
export type Credentials = {username:string;password:string};
export class ApiError extends Error { kind:string; constructor(kind:string,message:string){super(message);this.kind=kind} }
export const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object' && v!==null && !Array.isArray(v);
export function adaptRows(value:unknown,profile:Profile):Row[]{
 if(!Array.isArray(value))throw new ApiError('invalid','Resposta inválida: esperada uma lista.');
 return value.map(v=>{
  if(!object(v)||typeof v.id!=='string')throw new ApiError('invalid','Registro sem identificação válida.');
  if(profile==='p11'){
   if(!object(v.data)||!Number.isInteger(v.revision)||Number(v.revision)<1||typeof v.source!=='string')throw new ApiError('invalid','Projeção P11 incompatível.');
   return v as Row;
  }
  return {id:v.id,data:v};
 });
}
export function telemetry(row:Row){
 const d=row.data;const m=object(d.measurements)?d.measurements:{};
 // Somente campos conhecidos são apresentados com unidade. Payload original continua acessível.
 return {device:typeof d.device_id==='string'?d.device_id:'Não informado',observed:typeof d.observed_at==='string'?d.observed_at:null,
 light:typeof m.ldr_raw==='number'?`${m.ldr_raw} (LDR bruto)`:typeof m.luminosity_lux==='number'?`${m.luminosity_lux} lux`:typeof d.luminosity==='number'&&Number.isFinite(d.luminosity)?`${d.luminosity} (luminosity · unidade não informada)`:'Não informada',
 led:object(d.status)&&typeof d.status.led==='boolean'?(d.status.led?'Ligado':'Desligado'):['ON','OFF'].includes(String(d.led_state))?`${d.led_state} (led_state do payload)`:'Não informado',
 provisionalTemperature:typeof d.temperatura==='number'&&Number.isFinite(d.temperatura)?String(d.temperatura):null,
 recorded:typeof row.created_at==='string'?row.created_at:null,
 received:typeof d.received_at==='string'?d.received_at:null};
}
export function stale(date:string|null,now=Date.now()){return !date||!Number.isFinite(Date.parse(date))||now-Date.parse(date)>120_000}
export class Client {
 public base:string; public profile:Profile; private fetcher:typeof fetch; public timeout:number;
 private credentials:Credentials|null=null;
 private active=new Set<AbortController>();
 constructor(base:string,profile:Profile,fetcher:typeof fetch=fetch,timeout=10000){
  this.base=base;this.profile=profile;this.fetcher=fetcher.bind(globalThis);this.timeout=timeout;
  if(base&&base!=='/p11-api'){let u:URL;try{u=new URL(base)}catch{throw new ApiError('config','Use /p11-api para o túnel local ou uma URL HTTP(S) absoluta.')}if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.search||u.hash)throw new ApiError('config','URL inválida; use HTTP(S), sem credenciais, query ou fragmento.');}
 }
 cancel(){this.active.forEach(c=>c.abort());this.active.clear()}
 logout(){this.credentials=null;this.cancel()}
 async login(credentials:Credentials){
  if(!credentials.username||!credentials.password||credentials.username.includes(':'))throw new ApiError('config','Informe usuário e senha válidos.');
  this.logout();this.credentials={...credentials};
  try{if(this.profile==='p11')await this.health();else await this.rows('telemetry',0,1)}catch(e){this.logout();throw e}
 }
 path(kind:string){return this.profile==='p11'?`/api/v1/p11/${kind}`:`/api/v1/${kind==='network_event'?'network-events':kind}`}
 async get(path:string,method='GET',body?:unknown):Promise<unknown>{
  if(!this.base)throw new ApiError('config','API não configurada. Informe a URL acessível ao navegador.');
  if(!this.credentials)throw new ApiError('unauthorized','Não autorizado. Entre novamente.');
  const c=new AbortController();this.active.add(c);const timer=setTimeout(()=>c.abort(),this.timeout);
  try{
   const bytes=new TextEncoder().encode(`${this.credentials.username}:${this.credentials.password}`);
   const response=await this.fetcher(this.base.replace(/\/$/,'')+path,{method,body:body===undefined?undefined:JSON.stringify(body),headers:{Authorization:`Basic ${btoa(String.fromCharCode(...bytes))}`,...(body===undefined?{}:{'Content-Type':'application/json'})},signal:c.signal,cache:'no-store',credentials:'omit',redirect:'error'});
   if(response.status===409){let message='Alteração recusada pelo servidor. Consulte novamente.';try{const v=await response.json();if(object(v)&&object(v.detail)&&typeof v.detail.message==='string')message=v.detail.message}catch{}throw new ApiError('conflict',message)}
   if(!response.ok){const kind=response.status===401?'unauthorized':response.status===403?'forbidden':response.status===404?'unavailable':'error';throw new ApiError(kind, response.status===401?'Credenciais inválidas ou sessão não autorizada.':response.status===403?'Acesso negado.':response.status===404?'Endpoint indisponível nesta API.':`API indisponível (HTTP ${response.status}).`)}
   try{return await response.json()}catch{throw new ApiError('invalid','A API retornou JSON inválido.')}
  }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('network',c.signal.aborted?'Consulta cancelada ou tempo limite excedido.':'Falha de rede/configuração. Verifique URL, proxy, HTTPS e CORS. Não foi possível consultar a API.');}
  finally{clearTimeout(timer);this.active.delete(c)}
 }
 async rows(kind:string,offset=0,limit=50){return adaptRows(await this.get(`${this.path(kind)}?limit=${limit}${this.profile==='p11'?`&offset=${offset}`:''}`),this.profile)}
 async controls(){return controlState(await this.get('/api/v1/security/settings/mode/default'))}
 async changeControls(value:ControlState['value'],revision:number,reason:string){return controlState(await this.get('/api/v1/security/settings/mode/default','PUT',{value,expected_revision:revision,reason}))}
 async emergencyStop(reason:string){return controlState(await this.get('/api/v1/security/emergency-stop','POST',{reason}))}
 async audit(offset=0){return adaptRows(await this.get(`/api/v1/security/audit?limit=50&offset=${offset}`),'p11')}
 async explanationHistory(id:string):Promise<Row[]>{
  if(this.profile!=='p11')throw new ApiError('unavailable','Histórico não disponível na API da base Git.');
  const value=await this.get(`${this.path('bitnet')}/${encodeURIComponent(id)}/history`);
  if(!Array.isArray(value))throw new ApiError('invalid','Histórico em formato inválido.');
  return value.map(row=>{
   if(!object(row)||!Number.isInteger(row.revision)||typeof row.source!=='string'||!object(row.data))throw new ApiError('invalid','Revisão de explicação inválida.');
   return {id:`${id}@${row.revision}`,revision:row.revision as number,source:row.source,data:row.data};
  });
 }
 async incidentExplanations(incidentId:string):Promise<Row[]>{
  if(this.profile!=='p11')throw new ApiError('unavailable','Explicações não disponíveis nesta API.');
  const health = await this.health();
  if (object(health.harpia) && health.harpia.mode === 'deterministic_only' &&
      health.harpia.contract_version === 1 && health.harpia.generation_enabled === false) {
   const value = await this.get(`${this.path('explain')}/${encodeURIComponent(incidentId)}`);
   if (!object(value) || value.source !== 'deterministic_fallback' || value.incident_id !== incidentId ||
       !Number.isInteger(value.revision) || Number(value.revision) < 1 || typeof value.text !== 'string' ||
       !value.text.trim() || typeof value.generated_at !== 'string' || !Number.isFinite(Date.parse(value.generated_at)))
    throw new ApiError('invalid','Explicação determinística incompatível ou vinculada a outro incidente.');
   return [{id:`harpia:${incidentId}`,revision:Number(value.revision),source:'api-derived',data:value}];
  }
  // Old P11 /explain may invoke an LLM: never call without the explicit capability.
  const rows=await this.rows('bitnet',0,50);
  return rows.filter(row=>row.data.incident_id===incidentId);
 }
 async health(){const v=await this.get(this.path('health'));if(!object(v)||(this.profile==='p11'&&typeof v.api!=='string'))throw new ApiError('invalid','Saúde em formato inválido.');return v}
}

export type ControlState={value:{autonomy_mode:1|2|3;operation:'IDS'|'SIMULATION'|'REAL';execution_enabled:boolean};revision:number;emergency_stopped:boolean;updated_at:string;observed_at:string;real_execution_blocked:true;pending:{reliable:boolean;blockers:{id:string;state:string}[];dependency?:string};change_allowed:boolean};
export function controlState(v:unknown):ControlState{
 if(!object(v)||!object(v.value)||![1,2,3].includes(Number(v.value.autonomy_mode))||typeof v.value.autonomy_mode!=='number'||!['IDS','SIMULATION','REAL'].includes(String(v.value.operation))||typeof v.value.execution_enabled!=='boolean'||!Number.isInteger(v.revision)||Number(v.revision)<1||typeof v.emergency_stopped!=='boolean'||typeof v.updated_at!=='string'||!Number.isFinite(Date.parse(v.updated_at))||typeof v.observed_at!=='string'||!Number.isFinite(Date.parse(v.observed_at))||v.real_execution_blocked!==true||typeof v.change_allowed!=='boolean'||!object(v.pending)||typeof v.pending.reliable!=='boolean'||!Array.isArray(v.pending.blockers)||v.pending.blockers.some(b=>!object(b)||typeof b.id!=='string'||typeof b.state!=='string'))throw new ApiError('invalid','Estado operacional incompatível; alteração não confirmada.');
 return v as ControlState;
}
