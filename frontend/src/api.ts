export type Profile = 'p11' | 'legacy';
export type Row = {id:string; revision?:number; source?:string; created_at?:string; data:Record<string,unknown>};
export type Credentials = {username:string;password:string};
export type AuthChallenge={challenge_token:string;next_step:'login'|'enroll';expires_at:string};
export type FirstAccessState={contract_version:2;status:'not_issued'|'pending'|'completed';generation:number;codes_remaining:number;installation_id:string;account_id:string|number};
export type FirstAccessEmission={firstAccess:FirstAccessState;recoveryCodes:string[]};
export type ActivationState={contract_version:1;status:'not_activated'|'activation_pending'|'activated'|'invalid_local_identity'|'connection_required';administrator:'absent'|'mfa_pending'|'ready'|'migration_required';retry_allowed:boolean;first_use_authorized:boolean;loss_of_authenticator_policy:'not_approved'};
export type AdminSession={authenticated:true;username:string;expires_at:string;idle_timeout_seconds:1800;mfa_available:boolean;mfa_enabled?:boolean;mfa_enrollment_available?:boolean;email_recovery_available:boolean;first_access?:FirstAccessState};
export type AuthFlowResult={kind:'challenge';challenge:AuthChallenge}|{kind:'session';session:AdminSession;firstAccess?:FirstAccessState;recoveryCodes?:string[];passwordResetCodes?:string[];sessionVerified?:boolean};
export class ApiError extends Error { kind:string; fields:{field:string;code:string}[]; currentRevision:number|null; code:string|null; currentState:ControlState|null; constructor(kind:string,message:string,fields:{field:string;code:string}[]=[],currentRevision:number|null=null,code:string|null=null,currentState:ControlState|null=null){super(message);this.kind=kind;this.fields=fields;this.currentRevision=currentRevision;this.code=code;this.currentState=currentState} }
export const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object' && v!==null && !Array.isArray(v);
export function firstAccessState(value:unknown):FirstAccessState{
 if(!object(value)||value.contract_version!==2||!['not_issued','pending','completed'].includes(String(value.status))||!Number.isSafeInteger(value.generation)||Number(value.generation)<0||!Number.isInteger(value.codes_remaining)||Number(value.codes_remaining)<0||Number(value.codes_remaining)>3||typeof value.installation_id!=='string'||!value.installation_id||!['string','number'].includes(typeof value.account_id))throw new ApiError('invalid','Estado de primeiro acesso incompatível com três códigos.');
 if(value.status==='not_issued'&&(value.generation!==0||value.codes_remaining!==0)||value.status!=='not_issued'&&Number(value.generation)<1)throw new ApiError('invalid','Geração de primeiro acesso inconsistente.');
 return value as FirstAccessState;
}
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
 private authenticatedUsername:string|null=null;
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
 forgetSession(){this.epoch++;this.token=null;this.authenticatedUsername=null;this.expiresAt=0;this.cancelSessionRequests()}
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
  this.token=value.access_token;this.authenticatedUsername=value.username;this.expiresAt=Date.parse(value.expires_at);
  try{const session=await this.session();return {kind:'session',session,sessionVerified:true,...(session.first_access?{firstAccess:session.first_access}:{})}}
  catch(error){this.forgetSession();throw error}
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
 async resetPassword(username:string,code:string,newPassword:string,totpCode:string){
  this.requireP11Auth();this.forgetSession();
  const value=await this.request('/api/v1/admin-auth/password-reset/confirm','POST',{username,code,totp_code:totpCode,new_password:newPassword});
  if(!object(value)||value.status!=='password_reset'||value.mfa_preserved!==true||value.login_required!==true||'access_token' in value)throw new ApiError('invalid','Redefinição não confirmada pelo servidor.');
  return value;
 }
 private async publicChallenge(path:string,body:unknown,next:'login'|'enroll'):Promise<AuthFlowResult>{
  if(this.profile!=='p11')throw new ApiError('config','Primeiro acesso e MFA exigem o contrato P11 candidato.');
  const epoch=this.epoch;const value=await this.request(path,'POST',body);
  if(epoch!==this.epoch)throw new ApiError('cancelled','Fluxo cancelado; recomece a autenticação.');
  return {kind:'challenge',challenge:this.challenge(value,next)};
 }
 bootstrap(username:string,password:string){return this.publicChallenge('/api/v1/admin-auth/bootstrap',{username,password},'enroll')}
 async localRecovery(..._args:string[]):Promise<AuthFlowResult>{throw new ApiError('forbidden','Política de perda do autenticador ainda não aprovada.')} 
 async verifyMfa(challengeToken:string,code:string){this.requireP11Auth();const epoch=this.epoch;const value=await this.request('/api/v1/admin-auth/mfa/verify','POST',{challenge_token:challengeToken,code});return this.completeSession(value,epoch)}
 async recoverMfa(..._args:string[]):Promise<AuthFlowResult>{throw new ApiError('forbidden','Código de recuperação não permite substituir o autenticador.')} 
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
  return this.completeSession(value,epoch);
 }
 async activationStatus():Promise<ActivationState>{return this.parseActivation(await this.request('/api/v1/activation/status'))}
 async retryActivation():Promise<ActivationState>{return this.parseActivation(await this.request('/api/v1/activation/retry','POST',{}))}
 private parseActivation(value:unknown):ActivationState{
  if(!object(value)||value.contract_version!==1||!['not_activated','activation_pending','activated','invalid_local_identity','connection_required'].includes(String(value.status))||!['absent','mfa_pending','ready','migration_required'].includes(String(value.administrator))||typeof value.retry_allowed!=='boolean'||typeof value.first_use_authorized!=='boolean'||value.loss_of_authenticator_policy!=='not_approved')throw new ApiError('invalid','Estado de ativação incompatível.');return value as ActivationState;
 }
 async firstAccess():Promise<{firstAccess:FirstAccessState}>{
  const value=await this.get('/api/v1/admin-auth/first-access');
  return {firstAccess:firstAccessState(object(value)&&value.first_access!==undefined?value.first_access:value)};
 }
 private async emission(path:string,body:unknown):Promise<FirstAccessEmission>{
  const value=await this.get(path,'POST',body);
  if(!object(value)||!Array.isArray(value.recovery_codes)||value.recovery_codes.length!==3||new Set(value.recovery_codes).size!==3||value.recovery_codes.some(c=>typeof c!=='string'||!/^[-_A-Za-z0-9]{32}$/.test(c))||value.password_reset_codes!==undefined)throw new ApiError('invalid','O servidor deve emitir exatamente três códigos independentes.');
  const firstAccess=firstAccessState(value.first_access);
  if(firstAccess.status!=='pending'||firstAccess.codes_remaining!==3)throw new ApiError('invalid','Emissão sem conjunto pendente de três códigos.');
  return {firstAccess,recoveryCodes:value.recovery_codes as string[]};
 }
 issueFirstAccessCodes(){return this.emission('/api/v1/admin-auth/first-access/codes',{})}
 reissueFirstAccessCodes(currentPassword:string,code:string){return this.emission('/api/v1/admin-auth/first-access/reissue',{current_password:currentPassword,code})}
 async confirmFirstAccess(generation:number):Promise<FirstAccessState>{
  if(!Number.isSafeInteger(generation)||generation<1)throw new ApiError('config','Geração de códigos inválida.');
  const value=await this.get('/api/v1/admin-auth/first-access/confirm','POST',{generation});
  const state=firstAccessState(object(value)?value.first_access:undefined);
  if(state.status!=='completed'||state.generation!==generation)throw new ApiError('invalid','O servidor não confirmou a geração exibida.');return state;
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
   const response=await this.fetcher(this.base.replace(/\/$/,'')+path,{method,body:body===undefined?undefined:JSON.stringify(body),headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{'Content-Type':'application/json'})},signal:c.signal,cache:'no-store',credentials:(path.startsWith('/api/v1/activation/')||path==='/api/v1/admin-auth/bootstrap')?'same-origin':'omit',redirect:'error'});
   if(response.status===409){let message='Conflito de revisão. O estado salvo mudou; consulte a versão atual antes de tentar novamente.';let currentRevision:number|null=null;let currentState:ControlState|null=null;let code:string|null=null;try{const v=await response.json();const detail=object(v)&&object(v.detail)?v.detail:object(v)&&object(v.error)?v.error:null;if(detail){if(typeof detail.message==='string')message=detail.message;if(typeof detail.current_revision==='number')currentRevision=detail.current_revision;if(typeof detail.code==='string')code=detail.code;if(object(detail.current)){try{currentState=controlState(detail.current)}catch{/* keep only the safe conflict message */}}}}catch{}throw new ApiError('conflict',message,[],currentRevision,code,currentState)}
   if(!response.ok){let code='';let fields:{field:string;code:string}[]=[];const retryHeader=response.headers.get('retry-after');const retryAfter=retryHeader&&/^\d+$/.test(retryHeader)?Number(retryHeader):0;try{const value=await response.json();if(object(value)&&object(value.error)){if(typeof value.error.code==='string')code=value.error.code;if(Array.isArray(value.error.fields))fields=value.error.fields.filter((f):f is {field:string;code:string}=>object(f)&&typeof f.field==='string'&&typeof f.code==='string')}}catch{}
    if(response.status===401&&token===this.token)this.forgetSession();
    const kind=response.status===401?'unauthorized':response.status===403?(code==='REAUTHENTICATION_REQUIRED'?'reauthentication':'forbidden'):response.status===404?'unavailable':response.status===429?'throttled':'error';
    throw new ApiError(kind,response.status===401?(code==='SESSION_EXPIRED'?'Sessão expirada. Entre novamente.':code==='SESSION_REVOKED'||code==='SESSION_INVALID'||code==='AUTH_REQUIRED'?'Sessão inválida ou encerrada. Entre novamente.':code==='CHALLENGE_INVALID'?'Desafio inválido ou expirado. Recomece o fluxo.':code==='FACTOR_INVALID'?'Código de verificação inválido ou já utilizado.':code==='INVALID_CREDENTIALS'?'Usuário ou senha inválidos.':code==='GRANT_INVALID'?'Autenticação inicial expirada. Reabra pelo instalador.':'Credenciais inválidas ou sessão não autorizada.'):response.status===403?(code==='REAUTHENTICATION_REQUIRED'?'Senha atual inválida; a conta existente permanece ativa.':'Acesso negado pela política de origem da API.'):response.status===404?'Endpoint indisponível nesta API, ou recurso ausente.':response.status===413?'Documento acima do limite permitido.':response.status===422?(code==='INVALID_USERNAME'?'Nome de usuário inválido; use 3 a 64 letras, números, ponto, sublinhado, hífen ou @.':code==='INVALID_PASSWORD'?'Senha inválida; use de 8 a 128 caracteres e não reutilize credencial técnica.':code==='TECHNICAL_CREDENTIAL_REUSE'?'A conta não pode reutilizar credenciais técnicas da API, banco ou MQTT.':'A API recusou os campos enviados; revise as instruções do formulário.'):response.status===429?(retryAfter?`Muitas tentativas. Aguarde ${retryAfter} segundos antes de tentar novamente.`:'Muitas tentativas. Aguarde antes de tentar novamente.'):response.status===409?(code==='ALREADY_PROVISIONED'?'Esta instalação já tem uma conta administrativa; entre pela tela de login.':`Estado de autenticação incompatível (${code||'CONFLICT'}). Consulte a instalação antes de repetir.`):`API indisponível (HTTP ${response.status}).`,fields,null,code||null)}
   if(response.status===204)return null;
   try{return await response.json()}catch{throw new ApiError('invalid','A API retornou JSON inválido.')}
  }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('network',c.signal.aborted?'Consulta cancelada ou tempo limite excedido.':'Falha de rede/configuração. Verifique URL, proxy, HTTPS e CORS. Não foi possível consultar a API.');}
  finally{clearTimeout(timer);this.active.delete(c);this.configActive.delete(c)}
 }
 async session():Promise<AdminSession>{const value=await this.get('/api/v1/admin-auth/session');const common=object(value)&&value.authenticated===true&&typeof value.username==='string'&&typeof value.expires_at==='string'&&typeof value.idle_timeout_seconds==='number'&&Number.isFinite(Date.parse(value.expires_at));const legacy=object(value)&&value.mfa_available===false&&value.email_recovery_available===false;const candidate=object(value)&&value.mfa_available===true&&typeof value.mfa_enabled==='boolean'&&value.mfa_enrollment_available===true&&value.email_recovery_available===false;if(!common||!candidate||value.mfa_enabled!==true)throw new ApiError('invalid','Estado de sessão incompatível: MFA obrigatório.');if(candidate&&value.first_access===undefined)throw new ApiError('unavailable','O backend ainda não fornece o estado persistido de primeiro acesso.');if(object(value)&&value.first_access!==undefined)firstAccessState(value.first_access);if(this.authenticatedUsername&&value.username!==this.authenticatedUsername)throw new ApiError('invalid','A sessão retornou uma conta diferente da autenticada.');this.authenticatedUsername=String(value.username);return value as AdminSession}
 async rows(kind:string,offset=0,limit=50){return adaptRows(await this.get(`${this.path(kind)}?limit=${limit}${this.profile==='p11'?`&offset=${offset}`:''}`),this.profile)}
 async controls(){return controlState(await this.get('/api/v1/security/settings/mode/default'))}
 async changeControls(value:ControlState['value'],revision:number,reason:string){return controlState(await this.get('/api/v1/security/settings/mode/default','PUT',{value,expected_revision:revision,reason}))}
 async caseDossier(path:string,expected:CaseReference):Promise<Record<string,unknown>>{
  if(this.profile!=='p11'||!validDossierPath(path))throw new ApiError('unavailable','Link de ficha de incidente inválido ou não fornecido pelo backend.');
  const match=path.match(/^\/api\/v1\/p11\/incidents\/((?:[A-Za-z0-9_.:@-]|%[0-9A-Fa-f]{2}){1,256})\/dossier\?incident_revision=([1-9]\d{0,8})$/);
  if(!match||decodeCasePathId(match[1])!==expected.id||Number(match[2])!==expected.revision)throw new ApiError('invalid','O link da ficha não corresponde ao caso e à revisão selecionados.');
  const value=await this.get(path);if(!object(value)||!object(value.incident_ref)||value.incident_ref.id!==expected.id||value.incident_ref.revision!==expected.revision||!object(value.incident_card))throw new ApiError('invalid','Ficha retornada não corresponde ao caso selecionado.');return value;
 }
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
  if (object(health.harpia) && health.harpia.contract_version === 1 &&
      (health.harpia.mode === 'deterministic_only' && health.harpia.generation_enabled === false ||
       health.harpia.mode === 'bitnet_optional' && health.harpia.generation_enabled === true)) {
   const value = await this.get(`${this.path('explain')}/${encodeURIComponent(incidentId)}`);
   if (!object(value) || !(value.source === 'deterministic_fallback' ||
       health.harpia.mode === 'bitnet_optional' && value.source === 'bitnet_unverified_text' && value.bitnet_status === 'responded_unverified') || value.incident_id !== incidentId ||
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

export type EffectiveControlState={applied_profile:string;control_revision:number;executor?:string;availability?:string;executor_state?:{status:string;available:boolean;observed_at:string|null;source:string|null;blockers?:string[]};execution_enabled:boolean;updated_at:string;operational_visibility:string;blockers:{id:string;state:string}[];change_allowed:boolean;containment_confirmed:boolean};
export type CaseReference={id:string;revision:number};
export type CaseFact={source:string;record_id:string;source_revision:number|string|null;source_observed_at:string|null;fresh:boolean;state:string;origin:string|null;incident_ref:CaseReference|null;record_revision?:number;activity_type?:string};
export type LinkedCase={case_id:string;incident_refs:CaseReference[];incident_ref:CaseReference|null;classifications:('anomaly'|'confirmed_attack'|'incident')[];confirmed_attack_refs:CaseReference[];items:CaseFact[];assessment_records:Record<string,unknown>[];links:{rel:'incident_dossier';incident_ref:CaseReference;path:string}[]};
export type CaseSnapshot={contract_version:1|2;status:'active'|'none_active'|'partial'|'unknown';coverage:'complete'|'partial'|'unknown';known_active_count:number|null;count_basis:string;total_active_count?:number|null;classification_counts?:{anomaly:number;confirmed_attack:number;incident:number};classification_overlap?:true;observation_sufficient?:boolean;observed_at?:string|null;unlinked_active_item_count?:number;reason_codes?:{code:string;source:string;record_id?:string}[];sources:{source:string;source_revision:number|string|null;observed_at:string|null;fresh:boolean;valid:boolean;complete:boolean;reason_codes?:string[];freshness_policy?:{version:string;max_age_seconds:number;clock:string}}[];items:({source:string;record_id:string;source_revision:number|string|null;state:string;fresh:boolean;record_revision?:number}|LinkedCase)[]};
const validCaseReference=(v:unknown):v is CaseReference=>object(v)&&typeof v.id==='string'&&!!v.id&&Number.isSafeInteger(v.revision)&&Number(v.revision)>0;
const validDossierPath=(path:unknown)=>typeof path==='string'&&/^\/api\/v1\/p11\/incidents\/(?:[A-Za-z0-9_.:@-]|%[0-9A-Fa-f]{2}){1,256}\/dossier\?incident_revision=[1-9]\d{0,8}$/.test(path);
const decodeCasePathId=(value:string)=>{try{return decodeURIComponent(value)}catch{return null}};
export function caseSnapshot(v:unknown):CaseSnapshot|null{
 if(!object(v)||(v.contract_version!==undefined&&v.contract_version!==1&&v.contract_version!==2)||!['active','none_active','partial','unknown'].includes(String(v.status))||!['complete','partial','unknown'].includes(String(v.coverage))||!(v.known_active_count===null||Number.isInteger(v.known_active_count)&&Number(v.known_active_count)>=0)||typeof v.count_basis!=='string'||!Array.isArray(v.sources)||!Array.isArray(v.items))return null;
 const sources:CaseSnapshot['sources']=[];for(const row of v.sources){if(!object(row)||typeof row.source!=='string'||!(row.source_revision===null||typeof row.source_revision==='string'||Number.isInteger(row.source_revision))||!(row.observed_at===null||typeof row.observed_at==='string'&&Number.isFinite(Date.parse(row.observed_at)))||typeof row.fresh!=='boolean'||typeof row.valid!=='boolean'||typeof row.complete!=='boolean')return null;const policy=row.freshness_policy;if(policy!==undefined&&(!object(policy)||typeof policy.version!=='string'||!Number.isInteger(policy.max_age_seconds)||typeof policy.clock!=='string'))return null;if(row.reason_codes!==undefined&&(!Array.isArray(row.reason_codes)||row.reason_codes.some(x=>typeof x!=='string')))return null;sources.push({source:row.source,source_revision:row.source_revision as number|string|null,observed_at:row.observed_at as string|null,fresh:row.fresh,valid:row.valid,complete:row.complete,...(Array.isArray(row.reason_codes)?{reason_codes:row.reason_codes as string[]}:{}),...(object(policy)?{freshness_policy:policy as NonNullable<CaseSnapshot['sources'][number]['freshness_policy']>}: {})})}
 const isV2=v.contract_version===2;
 const items:CaseSnapshot['items']=[];for(const row of v.items){if(!object(row))return null;if(!isV2){if(typeof row.source!=='string'||typeof row.record_id!=='string'||!(row.source_revision===null||typeof row.source_revision==='string'||Number.isInteger(row.source_revision))||typeof row.state!=='string'||typeof row.fresh!=='boolean'||(row.record_revision!==undefined&&(!Number.isInteger(row.record_revision)||Number(row.record_revision)<1)))return null;items.push({source:row.source,record_id:row.record_id,source_revision:row.source_revision as number|string|null,state:row.state,fresh:row.fresh,...(row.record_revision===undefined?{}:{record_revision:Number(row.record_revision)})});continue}
  if(typeof row.case_id!=='string'||!row.case_id||row.case_id==='__coverage__'||!Array.isArray(row.incident_refs)||row.incident_refs.some(ref=>!validCaseReference(ref))||!(row.incident_ref===null||validCaseReference(row.incident_ref))||!Array.isArray(row.classifications)||row.classifications.some(x=>!['anomaly','confirmed_attack','incident'].includes(String(x)))||!Array.isArray(row.confirmed_attack_refs)||row.confirmed_attack_refs.some(ref=>!validCaseReference(ref))||!Array.isArray(row.items)||!Array.isArray(row.assessment_records)||!Array.isArray(row.links))return null;
  const facts:CaseFact[]=[];for(const fact of row.items){if(!object(fact)||typeof fact.source!=='string'||fact.source==='__coverage__'||typeof fact.record_id!=='string'||!(fact.source_revision===null||typeof fact.source_revision==='string'||Number.isInteger(fact.source_revision))||!(fact.source_observed_at===null||typeof fact.source_observed_at==='string'&&Number.isFinite(Date.parse(fact.source_observed_at)))||typeof fact.fresh!=='boolean'||typeof fact.state!=='string'||!(fact.origin===null||typeof fact.origin==='string')||!(fact.incident_ref===null||validCaseReference(fact.incident_ref))||(fact.record_revision!==undefined&&(!Number.isInteger(fact.record_revision)||Number(fact.record_revision)<1))||(fact.activity_type!==undefined&&typeof fact.activity_type!=='string'))return null;facts.push(fact as unknown as CaseFact)}
  const links:{rel:'incident_dossier';incident_ref:CaseReference;path:string}[]=[];for(const link of row.links){if(!object(link)||link.rel!=='incident_dossier'||!validCaseReference(link.incident_ref)||!validDossierPath(link.path))return null;const pathMatch=String(link.path).match(/^\/api\/v1\/p11\/incidents\/((?:[A-Za-z0-9_.:@-]|%[0-9A-Fa-f]{2}){1,256})\/dossier\?incident_revision=([1-9]\d{0,8})$/);if(!pathMatch||decodeCasePathId(pathMatch[1])!==link.incident_ref.id||Number(pathMatch[2])!==link.incident_ref.revision)return null;links.push(link as unknown as (typeof links)[number])}
  items.push({case_id:row.case_id,incident_refs:row.incident_refs as CaseReference[],incident_ref:row.incident_ref as CaseReference|null,classifications:row.classifications as LinkedCase['classifications'],confirmed_attack_refs:row.confirmed_attack_refs as CaseReference[],items:facts,assessment_records:row.assessment_records as Record<string,unknown>[],links});
 }
 if(isV2){const counts=v.classification_counts;const validCount=(n:unknown)=>Number.isSafeInteger(n)&&Number(n)>=0;if((v.total_active_count!==null&&!validCount(v.total_active_count))||!object(counts)||!validCount(counts.anomaly)||!validCount(counts.confirmed_attack)||!validCount(counts.incident)||v.count_basis!=='distinct_incident_id'||v.classification_count_basis!=='distinct_incident_id_per_class'||v.classification_overlap!==true||!Number.isSafeInteger(v.unlinked_active_item_count)||Number(v.unlinked_active_item_count)<0||typeof v.observation_sufficient!=='boolean'||!(v.observed_at===null||typeof v.observed_at==='string'&&Number.isFinite(Date.parse(v.observed_at)))||v.observation_basis!=='oldest_required_source_report'||!Array.isArray(v.unlinked_items)||!Array.isArray(v.reason_codes))return null;const sufficient=v.observation_sufficient===true;const unlinked=Number(v.unlinked_active_item_count);const classCounts=[counts.anomaly,counts.confirmed_attack,counts.incident].map(Number);if((!sufficient||v.coverage!=='complete'||v.status==='partial'||v.status==='unknown')&&v.total_active_count!==null)return null;if(sufficient&&(!['anomaly','incident'].every(name=>sources.some(source=>source.source===name&&source.observed_at!==null&&source.fresh&&source.valid&&source.complete))||unlinked>0))return null;if(sufficient&&v.known_active_count!==v.total_active_count)return null;if(v.status==='none_active'&&!(sufficient&&v.coverage==='complete'&&v.known_active_count===0&&v.total_active_count===0&&unlinked===0&&items.length===0&&classCounts.every(count=>count===0)))return null;if(sufficient&&v.status==='active'&&(Number(v.total_active_count)===0||classCounts.some(count=>count>Number(v.total_active_count))))return null;if(v.reason_codes.some(reason=>!object(reason)||typeof reason.code!=='string'||typeof reason.source!=='string'))return null;return {contract_version:2,status:v.status as CaseSnapshot['status'],coverage:v.coverage as CaseSnapshot['coverage'],known_active_count:v.known_active_count as number|null,count_basis:'distinct_incident_id',total_active_count:v.total_active_count as number|null,classification_counts:counts as CaseSnapshot['classification_counts'],classification_overlap:true,observation_sufficient:sufficient,observed_at:v.observed_at as string|null,unlinked_active_item_count:unlinked,reason_codes:v.reason_codes as CaseSnapshot['reason_codes'],sources,items};}
 return {contract_version:1,status:v.status as CaseSnapshot['status'],coverage:v.coverage as CaseSnapshot['coverage'],known_active_count:v.known_active_count as number|null,count_basis:v.count_basis,sources,items};
}
export function casesConfirmNoActive(snapshot:CaseSnapshot|null|undefined){return snapshot?.contract_version===2&&snapshot.status==='none_active'&&snapshot.coverage==='complete'&&snapshot.observation_sufficient===true&&snapshot.total_active_count===0}
export type ControlState={value:{autonomy_mode:1|2|3;operation:'IDS'|'SIMULATION'|'REAL';execution_enabled:boolean};revision:number;emergency_stopped:boolean;updated_at:string;observed_at:string;real_execution_blocked:true;pending:{reliable:boolean;blockers:{id:string;state:string}[];dependency?:string};change_allowed:boolean;executor?:string;effective_state?:EffectiveControlState;cases?:CaseSnapshot};
export function controlState(v:unknown):ControlState{
 if(!object(v)||!object(v.value)||![1,2,3].includes(Number(v.value.autonomy_mode))||typeof v.value.autonomy_mode!=='number'||!['IDS','SIMULATION','REAL'].includes(String(v.value.operation))||typeof v.value.execution_enabled!=='boolean'||!Number.isInteger(v.revision)||Number(v.revision)<1||typeof v.emergency_stopped!=='boolean'||typeof v.updated_at!=='string'||!Number.isFinite(Date.parse(v.updated_at))||typeof v.observed_at!=='string'||!Number.isFinite(Date.parse(v.observed_at))||v.real_execution_blocked!==true||typeof v.change_allowed!=='boolean'||!object(v.pending)||typeof v.pending.reliable!=='boolean'||!Array.isArray(v.pending.blockers)||v.pending.blockers.some(b=>!object(b)||typeof b.id!=='string'||typeof b.state!=='string'))throw new ApiError('invalid','Estado operacional incompatível; alteração não confirmada.');
 let effectiveState:EffectiveControlState|undefined;
 if(v.effective_state!==undefined){const s=v.effective_state;const executorState=object(s)&&s.executor_state;if(!object(s)||typeof s.applied_profile!=='string'||!Number.isInteger(s.control_revision)||!(s.executor===undefined||typeof s.executor==='string')||!(s.availability===undefined||typeof s.availability==='string')||(executorState!==undefined&&(!object(executorState)||typeof executorState.status!=='string'||typeof executorState.available!=='boolean'||!(executorState.observed_at===null||typeof executorState.observed_at==='string')||!(executorState.source===null||typeof executorState.source==='string')||(executorState.blockers!==undefined&&(!Array.isArray(executorState.blockers)||executorState.blockers.some((b:unknown)=>typeof b!=='string')))))||typeof s.execution_enabled!=='boolean'||typeof s.updated_at!=='string'||!Number.isFinite(Date.parse(s.updated_at))||typeof s.operational_visibility!=='string'||!Array.isArray(s.blockers)||s.blockers.some(b=>!object(b)||typeof b.id!=='string'||typeof b.state!=='string')||typeof s.change_allowed!=='boolean'||typeof s.containment_confirmed!=='boolean')throw new ApiError('invalid','Estado efetivo incompatível; resposta não confirmada.');effectiveState=s as unknown as EffectiveControlState;}
 const cases=v.cases===undefined?undefined:caseSnapshot(v.cases);if(v.cases!==undefined&&!cases)throw new ApiError('invalid','Snapshot de casos incompatível; cobertura não confirmada.');
 return {...v as unknown as ControlState,...(effectiveState?{effective_state:effectiveState}:{}),...(cases?{cases}:{})};
}
