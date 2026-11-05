export type Profile = 'p11' | 'legacy';
export type Row = {id:string; revision?:number; source?:string; created_at?:string; data:Record<string,unknown>};
export type Credentials = {username:string;password:string};
export type AuthChallenge={challenge_token:string;next_step:'login'|'enroll';expires_at:string};
export type AdminSession={authenticated:true;username:string;expires_at:string;idle_timeout_seconds:1800;mfa_available:boolean;mfa_enabled?:boolean;mfa_enrollment_available?:boolean;email_recovery_available:boolean};
export type AuthFlowResult={kind:'challenge';challenge:AuthChallenge}|{kind:'session';session:AdminSession;recoveryCodes?:string[];sessionVerified?:boolean};
export class ApiError extends Error { kind:string; fields:{field:string;code:string}[]; currentRevision:number|null; code:string|null; constructor(kind:string,message:string,fields:{field:string;code:string}[]=[],currentRevision:number|null=null,code:string|null=null){super(message);this.kind=kind;this.fields=fields;this.currentRevision=currentRevision;this.code=code} }
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
 private token:string|null=null;
 private expiresAt=0;
 private epoch=0;
 private active=new Set<AbortController>();
 private configActive=new Set<AbortController>();
 constructor(base:string,profile:Profile,fetcher:typeof fetch=fetch,timeout=10000){
  this.base=base;this.profile=profile;this.fetcher=fetcher.bind(globalThis);this.timeout=timeout;
  if(base&&base!=='/p11-api'){let u:URL;try{u=new URL(base)}catch{throw new ApiError('config','Use /p11-api para o túnel local ou uma URL HTTPS absoluta.')}if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.search||u.hash||(u.protocol==='http:'&&!['localhost','127.0.0.1','[::1]'].includes(u.hostname)))throw new ApiError('config','Use HTTPS ou HTTP no loopback, sem credenciais, query ou fragmento.');}
 }
 cancel(){this.active.forEach(c=>c.abort());this.active.clear()}
 private cancelSessionRequests(){this.cancel();this.configActive.forEach(c=>c.abort());this.configActive.clear()}
 forgetSession(){this.epoch++;this.token=null;this.expiresAt=0;this.cancelSessionRequests()}
 remainingSessionMs(){return Math.max(0,this.expiresAt-Date.now())}
 async logout(){const token=this.token;this.forgetSession();if(token)await this.request('/api/v1/admin-auth/logout','POST',undefined,token,true)}
 private requireP11Auth(){if(this.profile!=='p11')throw new ApiError('config','Primeiro acesso e MFA exigem o contrato P11 candidato.')}
 private challenge(value:unknown,next:'login'|'enroll'):AuthChallenge{
  if(!object(value)||typeof value.challenge_token!=='string'||!/^[-_A-Za-z0-9]{43}$/.test(value.challenge_token)||value.next_step!==next||typeof value.expires_at!=='string'||!Number.isFinite(Date.parse(value.expires_at))||Date.parse(value.expires_at)<=Date.now())throw new ApiError('invalid','Desafio de autenticação inválido ou expirado.');
  return {challenge_token:value.challenge_token,next_step:next,expires_at:value.expires_at};
 }
 private async completeSession(value:unknown,epoch:number,recoveryCodes?:unknown):Promise<AuthFlowResult>{
  if(!object(value)||typeof value.access_token!=='string'||!/^[-_A-Za-z0-9]{43}$/.test(value.access_token)||value.token_type!=='Bearer'||typeof value.expires_at!=='string'||!Number.isFinite(Date.parse(value.expires_at))||Date.parse(value.expires_at)<=Date.now()||value.idle_timeout_seconds!==1800||typeof value.username!=='string')throw new ApiError('invalid','Resposta de sessão inválida.');
  if(epoch!==this.epoch)throw new ApiError('cancelled','Autenticação cancelada; recomece o fluxo.');
  this.token=value.access_token;this.expiresAt=Date.parse(value.expires_at);
  if(recoveryCodes!==undefined&&(!Array.isArray(recoveryCodes)||recoveryCodes.length!==10||recoveryCodes.some(code=>typeof code!=='string'||!/^[-_A-Za-z0-9]{32}$/.test(code)))){this.forgetSession();throw new ApiError('invalid','A API retornou códigos de recuperação incompatíveis.');}
  try{const session=await this.session();return {kind:'session',session,sessionVerified:true,...(recoveryCodes?{recoveryCodes:recoveryCodes as string[]}:{})}}
  catch(error){
   if(recoveryCodes){return {kind:'session',session:{authenticated:true,username:value.username,expires_at:value.expires_at,idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false},sessionVerified:false,recoveryCodes:recoveryCodes as string[]}}
   this.forgetSession();throw error
  }
 }
 async login(credentials:Credentials):Promise<AuthFlowResult>{
  this.forgetSession();const epoch=this.epoch;
  if(this.profile!=='p11')throw new ApiError('config','O acesso administrativo exige P11 com conta e sessão. O contrato legado não oferece esse login.');
  if(!credentials.username||!credentials.password)throw new ApiError('config','Informe usuário e senha válidos.');
  const value=await this.request('/api/v1/admin-auth/login','POST',credentials);
  if(epoch!==this.epoch)throw new ApiError('cancelled','Login cancelado; entre novamente.');
  if(object(value)&&value.challenge_token!==undefined)return {kind:'challenge',challenge:this.challenge(value,value.next_step==='login'?'login':'enroll')};
  return this.completeSession(value,epoch);
 }
 private async publicChallenge(path:string,body:unknown,next:'login'|'enroll'):Promise<AuthFlowResult>{
  if(this.profile!=='p11')throw new ApiError('config','Primeiro acesso e MFA exigem o contrato P11 candidato.');
  const epoch=this.epoch;const value=await this.request(path,'POST',body);
  if(epoch!==this.epoch)throw new ApiError('cancelled','Fluxo cancelado; recomece a autenticação.');
  return {kind:'challenge',challenge:this.challenge(value,next)};
 }
 bootstrap(bootstrapSecret:string,username:string,password:string){return this.publicChallenge('/api/v1/admin-auth/bootstrap',{bootstrap_secret:bootstrapSecret,username,password},'enroll')}
 localRecovery(bootstrapSecret:string,username:string,password:string){return this.publicChallenge('/api/v1/admin-auth/local-recovery',{bootstrap_secret:bootstrapSecret,username,password},'enroll')}
 async verifyMfa(challengeToken:string,code:string){this.requireP11Auth();const epoch=this.epoch;const value=await this.request('/api/v1/admin-auth/mfa/verify','POST',{challenge_token:challengeToken,code});return this.completeSession(value,epoch)}
 recoverMfa(challengeToken:string,code:string){return this.publicChallenge('/api/v1/admin-auth/mfa/recover',{challenge_token:challengeToken,code},'enroll')}
 async authorizeMfaEnrollment(currentPassword:string,code?:string){
  this.requireP11Auth();
  const body={current_password:currentPassword,...(code?{code}:{})};const value=await this.get('/api/v1/admin-auth/mfa/enrollment/authorize','POST',body);
  return this.challenge(value,'enroll');
 }
 async beginMfaEnrollment(challengeToken:string){
  this.requireP11Auth();
  const value=await this.request('/api/v1/admin-auth/mfa/enrollment/begin','POST',{challenge_token:challengeToken});
  if(!object(value)||typeof value.manual_key!=='string'||!/^[A-Z2-7]{16,64}$/.test(value.manual_key)||typeof value.provisioning_uri!=='string'||!/^otpauth:\/\/totp\//.test(value.provisioning_uri)||typeof value.qr_svg!=='string'||value.qr_svg.length>100_000||typeof value.expires_at!=='string'||!Number.isFinite(Date.parse(value.expires_at))||Date.parse(value.expires_at)<=Date.now())throw new ApiError('invalid','Material de cadastro MFA incompatível.');
  // The provisioning URI embeds the TOTP secret. Validate the contract, then
  // discard it; the UI only needs the QR and manual key already delivered.
  return {manualKey:value.manual_key,qrSvg:value.qr_svg,expiresAt:value.expires_at};
 }
 async confirmMfaEnrollment(challengeToken:string,code:string):Promise<AuthFlowResult>{
  this.requireP11Auth();
  const epoch=this.epoch;const value=await this.request('/api/v1/admin-auth/mfa/enrollment/confirm','POST',{challenge_token:challengeToken,code});
  if(!object(value)||!Array.isArray(value.recovery_codes))throw new ApiError('invalid','A confirmação MFA não retornou os códigos de recuperação esperados.');
  return this.completeSession(value,epoch,value.recovery_codes);
 }
 async cancelMfaChallenge(challengeToken:string){this.requireP11Auth();await this.request('/api/v1/admin-auth/mfa/cancel','POST',{challenge_token:challengeToken})}
 path(kind:string){return this.profile==='p11'?`/api/v1/p11/${kind}`:`/api/v1/${kind==='network_event'?'network-events':kind}`}
 async get(path:string,method='GET',body?:unknown):Promise<unknown>{
  if(!this.token)throw new ApiError('unauthorized','Não autorizado. Entre novamente.');
  if(this.expiresAt<=Date.now()){this.forgetSession();throw new ApiError('unauthorized','Sessão expirada. Entre novamente.');}
  return this.request(path,method,body,this.token);
 }
 private async request(path:string,method='GET',body?:unknown,token?:string,detached=false):Promise<unknown>{
  if(!this.base)throw new ApiError('config','API não configurada. Informe a URL acessível ao navegador.');
  const c=new AbortController();if(!detached){if(path.startsWith('/api/v1/config/'))this.configActive.add(c);else this.active.add(c)}const timer=setTimeout(()=>c.abort(),this.timeout);
  try{
   const response=await this.fetcher(this.base.replace(/\/$/,'')+path,{method,body:body===undefined?undefined:JSON.stringify(body),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},signal:c.signal,cache:'no-store',credentials:'omit',redirect:'error'});
   if(response.status===409){let message='Conflito de revisão. O estado salvo mudou; consulte a versão atual antes de tentar novamente.';let currentRevision:number|null=null;try{const v=await response.json();if(object(v)&&object(v.detail)&&typeof v.detail.message==='string')message=v.detail.message;if(object(v)&&object(v.error)){if(typeof v.error.current_revision==='number')currentRevision=v.error.current_revision;if(typeof v.error.code==='string')message=`Conflito informado pela API (${v.error.code}). Consulte a versão atual antes de reapresentar a alteração.`}}catch{}throw new ApiError('conflict',message,[],currentRevision)}
   if(!response.ok){let code='';let fields:{field:string;code:string}[]=[];const retryHeader=response.headers.get('retry-after');const retryAfter=retryHeader&&/^\d+$/.test(retryHeader)?Number(retryHeader):0;try{const value=await response.json();if(object(value)&&object(value.error)){if(typeof value.error.code==='string')code=value.error.code;if(Array.isArray(value.error.fields))fields=value.error.fields.filter((f):f is {field:string;code:string}=>object(f)&&typeof f.field==='string'&&typeof f.code==='string')}}catch{}
    if(response.status===401&&token===this.token)this.forgetSession();
    const kind=response.status===401?'unauthorized':response.status===403?(code==='REAUTHENTICATION_REQUIRED'?'reauthentication':'forbidden'):response.status===404?'unavailable':response.status===429?'throttled':'error';
    throw new ApiError(kind,response.status===401?(code==='SESSION_EXPIRED'?'Sessão expirada. Entre novamente.':code==='SESSION_REVOKED'||code==='SESSION_INVALID'||code==='AUTH_REQUIRED'?'Sessão inválida ou encerrada. Entre novamente.':code==='CHALLENGE_INVALID'?'Desafio inválido ou expirado. Recomece o fluxo.':code==='FACTOR_INVALID'?'Código de verificação inválido ou já utilizado.':code==='INVALID_CREDENTIALS'?'Usuário ou senha inválidos.':code==='GRANT_INVALID'?'Grant local inválido, expirado ou consumido. Solicite um novo ao operador autorizado.':'Credenciais inválidas ou sessão não autorizada.'):response.status===403?(code==='REAUTHENTICATION_REQUIRED'?'Senha atual inválida; a conta existente permanece ativa.':'Acesso negado pela política de origem da API.'):response.status===404?'Endpoint indisponível nesta API, ou recurso ausente.':response.status===413?'Documento acima do limite permitido.':response.status===422?(code==='INVALID_USERNAME'?'Nome de usuário inválido; use 3 a 64 letras, números, ponto, sublinhado, hífen ou @.':code==='INVALID_PASSWORD'?'Senha inválida; use de 8 a 128 caracteres e não reutilize credencial técnica.':code==='TECHNICAL_CREDENTIAL_REUSE'?'A conta não pode reutilizar credenciais técnicas da API, banco ou MQTT.':'A API recusou os campos enviados; revise as instruções do formulário.'):response.status===429?(retryAfter?`Muitas tentativas. Aguarde ${retryAfter} segundos antes de tentar novamente.`:'Muitas tentativas. Aguarde antes de tentar novamente.'):response.status===409?(code==='ALREADY_PROVISIONED'?'Esta instalação já tem uma conta administrativa; entre pela tela de login.':`Estado de autenticação incompatível (${code||'CONFLICT'}). Consulte a instalação antes de repetir.`):`API indisponível (HTTP ${response.status}).`,fields,null,code||null)}
   if(response.status===204)return null;
   try{return await response.json()}catch{throw new ApiError('invalid','A API retornou JSON inválido.')}
  }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('network',c.signal.aborted?'Consulta cancelada ou tempo limite excedido.':'Falha de rede/configuração. Verifique URL, proxy, HTTPS e CORS. Não foi possível consultar a API.');}
  finally{clearTimeout(timer);this.active.delete(c);this.configActive.delete(c)}
 }
 async session():Promise<AdminSession>{const value=await this.get('/api/v1/admin-auth/session');const common=object(value)&&value.authenticated===true&&typeof value.username==='string'&&typeof value.expires_at==='string'&&typeof value.idle_timeout_seconds==='number'&&Number.isFinite(Date.parse(value.expires_at));const legacy=object(value)&&value.mfa_available===false&&value.email_recovery_available===false;const candidate=object(value)&&value.mfa_available===true&&typeof value.mfa_enabled==='boolean'&&value.mfa_enrollment_available===true&&value.email_recovery_available===false;if(!common||(!legacy&&!candidate))throw new ApiError('invalid','Estado de sessão incompatível.');return value as AdminSession}
 async rows(kind:string,offset=0,limit=50){return adaptRows(await this.get(`${this.path(kind)}?limit=${limit}${this.profile==='p11'?`&offset=${offset}`:''}`),this.profile)}
 async controls(){return controlState(await this.get('/api/v1/security/settings/mode/default'))}
 async changeControls(value:ControlState['value'],revision:number,reason:string){return controlState(await this.get('/api/v1/security/settings/mode/default','PUT',{value,expected_revision:revision,reason}))}
 async emergencyStop(reason:string){return controlState(await this.get('/api/v1/security/emergency-stop','POST',{reason}))}
 async audit(offset=0){return adaptRows(await this.get(`/api/v1/security/audit?limit=50&offset=${offset}`),'p11')}
 async recordHistory(kind:string,id:string):Promise<Row[]>{
  const kinds=new Set(['asset','telemetry','network_event','window','detection','xai','evidence','incident','risk','decision','approval','execution','verification','bitnet']);
  if(this.profile!=='p11'||!kinds.has(kind)||!id)throw new ApiError('unavailable','Histórico não disponível para este recurso nesta API.');
  const value=await this.get(`/api/v1/p11/${kind}/${encodeURIComponent(id)}/history`);
  if(!Array.isArray(value))throw new ApiError('invalid','Histórico de projeção em formato inválido.');
  return value.map((row,index)=>{
   if(!object(row)||!Number.isInteger(row.revision)||Number(row.revision)<1||typeof row.source!=='string'||!object(row.data))throw new ApiError('invalid','Revisão da projeção incompatível.');
   return {id:`${kind}:${id}@${row.revision}:${index}`,revision:Number(row.revision),source:row.source,data:row.data};
  });
 }
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
