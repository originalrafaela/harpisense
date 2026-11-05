import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Client,adaptRows,telemetry,stale} from '../src/api.ts';
import {sessionResponse} from './session-response.ts';
const credentials={username:'test-user',password:'test-password'};
test('P11 aceita lista válida e vazia, rejeita payload incompatível',()=>{
 assert.deepEqual(adaptRows([],'p11'),[]);
 assert.equal(adaptRows([{id:'a',revision:1,source:'synthetic',data:{}}],'p11').length,1);
 for(const bad of [{},[{}],[{id:'a',data:{}}]])assert.throws(()=>adaptRows(bad,'p11'));
});
test('telemetria preserva unidades e não inventa luz a partir de temperatura',()=>{
 assert.equal(telemetry({id:'a',data:{measurements:{temperature_c:23}}}).light,'Não informada');
 assert.equal(telemetry({id:'a',data:{measurements:{ldr_raw:640}}}).light,'640 (LDR bruto)');
 assert.equal(stale('2020-01-01'),true);
 assert.equal(stale(new Date().toISOString()),false);
});
test('payload ativo do Poste 2 mantém luminosity sem unidade e led_state sem alterar dados',()=>{
 const data={device_id:'poste2',source:'ubuntu',status:'online',luminosity:900,led_state:'OFF'};
 const row={id:'poste2-active',data};
 assert.equal(telemetry(row).light,'900 (luminosity · unidade não informada)');
 assert.equal(telemetry(row).led,'OFF (led_state do payload)');
 assert.equal(telemetry(row).observed,null);
 assert.equal(row.data,data);
 assert.equal(telemetry({id:'bad',data:{luminosity:NaN,led_state:'unknown'}}).light,'Não informada');
 assert.equal(telemetry({id:'bad',data:{led_state:'unknown'}}).led,'Não informado');
});

test('login próprio cria e valida sessão; consultas usam Bearer; logout revoga e impede chamadas',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[];
 const fetcher=(async(url,init)=>{calls.push({url:String(url),init});return sessionResponse(url)||(String(url).endsWith('/logout')?new Response(null,{status:204}):new Response('[]'))}) as typeof fetch;
 const c=new Client('https://example.test','p11',fetcher);
 await c.login(credentials);await c.rows('telemetry');
 assert.match(calls[0].url,/api\/v1\/admin-auth\/login$/);
 assert.deepEqual(JSON.parse(String(calls[0].init?.body)),credentials);
 assert.equal((calls[0].init?.headers as Record<string,string>).Authorization,undefined);
 assert.match(calls[1].url,/admin-auth\/session$/);
 assert.equal((calls[2].init?.headers as Record<string,string>).Authorization,'Bearer '+'a'.repeat(43));
 c.cancel();await c.rows('asset');await c.logout();await assert.rejects(()=>c.rows('telemetry'),/Não autorizado/);
 assert.match(calls[4].url,/admin-auth\/logout$/);assert.equal(calls[4].init?.method,'POST');
 assert.ok(calls.slice(1).every(call=>call.init?.body===undefined));
 assert.ok(calls.every(call=>call.init?.credentials==='omit'&&call.init?.cache==='no-store'));
});
for(const [status,message] of [[401,/Credenciais inválidas/],[403,/Acesso negado/],[404,/Endpoint indisponível/],[503,/API indisponível/]] as const){test(`falha HTTP ${status} não autentica`,async()=>{
 const c=new Client('https://example.test','p11',(async()=>new Response('{}',{status})) as typeof fetch);
 await assert.rejects(()=>c.login(credentials),message);await assert.rejects(()=>c.rows('asset'),/Não autorizado/);
})}
test('falha de rede e resposta inválida não viram lista vazia',async()=>{
 for(const fetcher of [(async()=>{throw Error('network')}) as typeof fetch,(async()=>new Response('not-json')) as typeof fetch]){
  const c=new Client('https://example.test','p11',fetcher);await assert.rejects(()=>c.login(credentials));
 }
});
test('configuração rejeita credenciais em URL e protocolos inválidos',()=>{
 for(const url of ['http://user:password@example.test','javascript:test','invalid','https://example.test?secret=x'])assert.throws(()=>new Client(url,'p11'));
});
test('timeout cancela a requisição',async()=>{
 const c=new Client('https://example.test','p11',((_u,i)=>new Promise((_resolve,reject)=>i?.signal?.addEventListener('abort',()=>reject(Error('aborted'))))) as typeof fetch,10);
 await assert.rejects(()=>c.login(credentials),/tempo limite/);
});
test('histórico P11 preserva revisão e origem e codifica o identificador',async()=>{
 const urls:string[]=[];
 const c=new Client('https://example.test','p11',(async(url)=>{
  const auth=sessionResponse(url);if(auth)return auth;urls.push(String(url));return new Response(JSON.stringify(String(url).endsWith('/history')?[{revision:2,source:'trusted-service',data:{incident_id:'inc-1',text:'Resposta de teste'}}]:[]));
 }) as typeof fetch);
 await c.login(credentials);const history=await c.explanationHistory('exp/1');
 assert.match(urls[0],/bitnet\/exp%2F1\/history$/);assert.equal(history[0].revision,2);assert.equal(history[0].data.incident_id,'inc-1');
});
test('histórico inválido é rejeitado sem inventar revisões',async()=>{
 const c=new Client('https://example.test','p11',(async(url)=>sessionResponse(url)||new Response(JSON.stringify(String(url).endsWith('/history')?[{revision:1,data:{}}]:[]))) as typeof fetch);
 await c.login(credentials);await assert.rejects(()=>c.explanationHistory('exp'),/Revisão de explicação inválida/);
});
test('histórico de incidente usa apenas GET autenticado e valida revisões da projeção',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[];
 const c=new Client('https://example.test','p11',(async(url,init)=>{const auth=sessionResponse(url);if(auth)return auth;calls.push({url:String(url),init});return new Response(JSON.stringify([{revision:2,source:'trusted-service',data:{incident_id:'inc/1',status:'OBSERVED'}}]))}) as typeof fetch);
 await c.login(credentials);const history=await c.recordHistory('incident','inc/1');
 assert.match(calls[0].url,/\/api\/v1\/p11\/incident\/inc%2F1\/history$/);assert.equal(calls[0].init?.method,'GET');assert.equal((calls[0].init?.headers as Record<string,string>).Authorization,'Bearer '+'a'.repeat(43));
 assert.equal(history[0].revision,2);assert.equal(history[0].data.incident_id,'inc/1');
 await assert.rejects(()=>c.recordHistory('apply','id'),/Histórico não disponível/);
});
test('histórico com esquema inválido não é apresentado como vazio',async()=>{
 const c=new Client('https://example.test','p11',(async url=>sessionResponse(url)||new Response('[{"revision":1,"source":"trusted-service"}]')) as typeof fetch);
 await c.login(credentials);await assert.rejects(()=>c.recordHistory('incident','inc-1'),/Revisão da projeção incompatível/);
});

test('login com segundo fator retorna desafio temporário sem criar sessão administrativa',async()=>{
 const calls:{path:string;method:string;authorization:string|undefined;body:unknown}[]=[];
 const candidateSession={authenticated:true,username:'fixture-owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false};
 const fetcher=(async(url,init)=>{const path=new URL(String(url),'http://local').pathname;const headers=init?.headers as Record<string,string>|undefined;let body:unknown;try{body=JSON.parse(String(init?.body))}catch{}calls.push({path,method:init?.method||'GET',authorization:headers?.Authorization,body});
  if(path.endsWith('/admin-auth/login'))return new Response(JSON.stringify({challenge_token:'c'.repeat(43),next_step:'login',expires_at:new Date(Date.now()+300000).toISOString()}));
  if(path.endsWith('/mfa/verify'))return new Response(JSON.stringify({access_token:'b'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-owner'}));
  if(path.endsWith('/admin-auth/session'))return new Response(JSON.stringify(candidateSession));
  return new Response('[]');
 }) as typeof fetch;
 const client=new Client('/p11-api','p11',fetcher);const first=await client.login(credentials);
 assert.equal(first.kind,'challenge');if(first.kind!=='challenge')return;
 assert.equal(first.challenge.next_step,'login');await assert.rejects(()=>client.rows('incident'),/Não autorizado/);
 const completed=await client.verifyMfa(first.challenge.challenge_token,'123456');assert.equal(completed.kind,'session');
 assert.deepEqual(calls.map(call=>call.path),['/p11-api/api/v1/admin-auth/login','/p11-api/api/v1/admin-auth/mfa/verify','/p11-api/api/v1/admin-auth/session']);
 assert.equal(calls[1].authorization,undefined);assert.deepEqual(calls[1].body,{challenge_token:'c'.repeat(43),code:'123456'});
 assert.equal(calls[2].authorization,'Bearer '+'b'.repeat(43));
});

test('bootstrap, QR, confirmação e códigos de recuperação ficam em memória e validam sessão',async()=>{
 const calls:{path:string;authorization:string|undefined;body:unknown}[]=[];const recovery=Array.from({length:10},(_,i)=>String(i).padStart(32,'a'));
 const session={authenticated:true,username:'new-owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false};
 const fetcher=(async(url,init)=>{const path=new URL(String(url),'http://local').pathname;const headers=init?.headers as Record<string,string>|undefined;let body:unknown;try{body=JSON.parse(String(init?.body))}catch{}calls.push({path,authorization:headers?.Authorization,body});
  if(path.endsWith('/bootstrap'))return new Response(JSON.stringify({challenge_token:'e'.repeat(43),next_step:'enroll',expires_at:new Date(Date.now()+300000).toISOString()}));
  if(path.endsWith('/enrollment/begin'))return new Response(JSON.stringify({manual_key:'JBSWY3DPEHPK3PXP',provisioning_uri:'otpauth://totp/HarpiSense:owner?secret=JBSWY3DPEHPK3PXP',qr_svg:'<svg viewBox="0 0 21 21"><path fill="#000000" d="M0 0h1v1z"/></svg>',expires_at:new Date(Date.now()+300000).toISOString()}));
  if(path.endsWith('/enrollment/confirm'))return new Response(JSON.stringify({access_token:'f'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'new-owner',recovery_codes:recovery}));
  if(path.endsWith('/admin-auth/session'))return new Response(JSON.stringify(session));
  return new Response('{}',{status:404});
 }) as typeof fetch;
 const client=new Client('/p11-api','p11',fetcher);const begun=await client.bootstrap('g'.repeat(43),'new-owner','new-password-is-temporary');assert.equal(begun.kind,'challenge');if(begun.kind!=='challenge')return;
 const material=await client.beginMfaEnrollment(begun.challenge.challenge_token);assert.equal(material.manualKey,'JBSWY3DPEHPK3PXP');assert.deepEqual(Object.keys(material).sort(),['expiresAt','manualKey','qrSvg']);assert.equal(JSON.stringify(material).includes('otpauth://'),false);
 const confirmed=await client.confirmMfaEnrollment(begun.challenge.challenge_token,'123456');assert.equal(confirmed.kind,'session');if(confirmed.kind!=='session')return;
 assert.deepEqual(confirmed.recoveryCodes,recovery);assert.equal(confirmed.session.mfa_enabled,true);
 assert.ok(calls.slice(0,3).every(call=>call.authorization===undefined));assert.deepEqual(calls[0].body,{bootstrap_secret:'g'.repeat(43),username:'new-owner',password:'new-password-is-temporary'});
 assert.deepEqual(calls[1].body,{challenge_token:'e'.repeat(43)});assert.deepEqual(calls[2].body,{challenge_token:'e'.repeat(43),code:'123456'});
 assert.equal(calls[3].authorization,'Bearer '+'f'.repeat(43));
});

test('código de recuperação emite somente enrollment; adesão existente exige sessão Bearer',async()=>{
 const calls:{path:string;authorization:string|undefined;body:unknown}[]=[];
 const fetcher=(async(url,init)=>{const path=new URL(String(url),'http://local').pathname;const headers=init?.headers as Record<string,string>|undefined;let body:unknown;try{body=JSON.parse(String(init?.body))}catch{}calls.push({path,authorization:headers?.Authorization,body});
  if(path.endsWith('/admin-auth/login'))return new Response(JSON.stringify({challenge_token:'l'.repeat(43),next_step:'login',expires_at:new Date(Date.now()+300000).toISOString()}));
  if(path.endsWith('/mfa/recover'))return new Response(JSON.stringify({challenge_token:'n'.repeat(43),next_step:'enroll',expires_at:new Date(Date.now()+300000).toISOString()}));
  if(path.endsWith('/enrollment/authorize'))return new Response(JSON.stringify({challenge_token:'o'.repeat(43),next_step:'enroll',expires_at:new Date(Date.now()+300000).toISOString()}));
  return new Response('{}',{status:404});
 }) as typeof fetch;const client=new Client('/p11-api','p11',fetcher);
 const login=await client.login(credentials);assert.equal(login.kind,'challenge');if(login.kind!=='challenge')return;
 const enroll=await client.recoverMfa(login.challenge.challenge_token,'R'.repeat(32));assert.equal(enroll.kind,'challenge');if(enroll.kind==='challenge')assert.equal(enroll.challenge.next_step,'enroll');
 assert.equal(calls[1].authorization,undefined);assert.deepEqual(calls[1].body,{challenge_token:'l'.repeat(43),code:'R'.repeat(32)});
 await assert.rejects(()=>client.authorizeMfaEnrollment('current-password'),/Não autorizado/);
 assert.equal(calls.length,2);
});

test('desafio MFA malformado ou expirado não é tratado como sessão',async()=>{
 for(const expires of [new Date(Date.now()-1000).toISOString(),'not-a-date']){
  const client=new Client('/p11-api','p11',(async()=>new Response(JSON.stringify({challenge_token:'c'.repeat(43),next_step:'login',expires_at:expires}))) as typeof fetch);
  await assert.rejects(()=>client.login(credentials),/Desafio de autenticação inválido/);
  await assert.rejects(()=>client.health(),/Não autorizado/);
 }
});

test('sessão recusada é descartada sem Basic ou repetição do login',async()=>{
 const paths:string[]=[];
 const c=new Client('/p11-api','p11',(async(url)=>{paths.push(String(url));return sessionResponse(url)||new Response('{"error":{"code":"SESSION_REVOKED"}}',{status:401})}) as typeof fetch);
 await c.login(credentials);await assert.rejects(()=>c.rows('telemetry'),/Sessão inválida/);
 await assert.rejects(()=>c.health(),/Não autorizado/);
 assert.equal(paths.length,3);
});

test('expiração absoluta bloqueia consulta antes do envio',async()=>{
 const c=new Client('/p11-api','p11',(async url=>sessionResponse(url)!) as typeof fetch);
 await c.login(credentials);const original=Date.now;
 try{Date.now=()=>original()+9*3600000;await assert.rejects(()=>c.rows('telemetry'),/Sessão expirada/)}finally{Date.now=original}
});

test('logout indisponível encerra memória e informa falha de revogação',async()=>{
 const c=new Client('/p11-api','p11',(async url=>sessionResponse(url)||new Response('{}',{status:503})) as typeof fetch);
 await c.login(credentials);await assert.rejects(()=>c.logout(),/API indisponível/);
 await assert.rejects(()=>c.rows('telemetry'),/Não autorizado/);
});

test('resposta tardia de login não reabre uma sessão encerrada',async()=>{
 let finish:(value:Response)=>void=()=>{};
 const c=new Client('/p11-api','p11',(()=>new Promise<Response>(resolve=>{finish=resolve})) as typeof fetch);
 const login=c.login(credentials);c.forgetSession();finish(sessionResponse('/admin-auth/login')!);
 await assert.rejects(()=>login,/Login cancelado/);await assert.rejects(()=>c.health(),/Não autorizado/);
});

test('HTTP fora do loopback e contrato legado não enviam credenciais administrativas',async()=>{
 assert.throws(()=>new Client('http://192.0.2.1:8000','p11'),/HTTPS/);
 let calls=0;const c=new Client('/p11-api','legacy',(async()=>{calls++;return new Response('{}')}) as typeof fetch);
 await assert.rejects(()=>c.login(credentials),/conta e sessão/);assert.equal(calls,0);
});

test('cancelar consultas na troca de tela não cancela a revogação de logout',async()=>{
 const c=new Client('/p11-api','p11',(async(url,init)=>sessionResponse(url)||await new Promise<Response>((resolve,reject)=>{
  init?.signal?.addEventListener('abort',()=>reject(Error('aborted')));
  setTimeout(()=>resolve(new Response(null,{status:204})),10);
 })) as typeof fetch);
 await c.login(credentials);const logout=c.logout();c.forgetSession();await logout;
});
