import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Client,adaptRows,telemetry,stale} from '../src/api.ts';
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
test('Basic usa consulta protegida, sem endpoint de login; logout impede novas chamadas',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[];
 const fetcher=(async(url,init)=>{calls.push({url:String(url),init});return new Response('[]')}) as typeof fetch;
 const c=new Client('https://example.test','p11',fetcher);
 await c.login(credentials);await c.rows('telemetry');
 assert.match(calls[0].url,/api\/v1\/p11\/telemetry/);
 assert.match(String((calls[0].init?.headers as Record<string,string>).Authorization),/^Basic /);
 c.cancel();await c.rows('asset');c.logout();await assert.rejects(()=>c.rows('telemetry'),/Não autorizado/);
 assert.equal(calls.length,3);
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
  urls.push(String(url));return new Response(JSON.stringify(String(url).endsWith('/history')?[{revision:2,source:'trusted-service',data:{incident_id:'inc-1',text:'Resposta de teste'}}]:[]));
 }) as typeof fetch);
 await c.login(credentials);const history=await c.explanationHistory('exp/1');
 assert.match(urls[1],/bitnet\/exp%2F1\/history$/);assert.equal(history[0].revision,2);assert.equal(history[0].data.incident_id,'inc-1');
});
test('histórico inválido é rejeitado sem inventar revisões',async()=>{
 const c=new Client('https://example.test','p11',(async(url)=>new Response(JSON.stringify(String(url).endsWith('/history')?[{revision:1,data:{}}]:[]))) as typeof fetch);
 await c.login(credentials);await assert.rejects(()=>c.explanationHistory('exp'),/Revisão de explicação inválida/);
});
