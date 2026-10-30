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
