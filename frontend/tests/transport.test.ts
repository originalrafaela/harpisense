import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer as httpServer} from 'node:http';
import {createServer, createLogger} from 'vite';
// @ts-ignore This is executable Node configuration, not browser code.
import {p11Transport, tunnelTarget} from '../scripts/p11-proxy.mjs';

test('transporte só aceita destino loopback sem credenciais',()=>{
  assert.equal(tunnelTarget(),'http://127.0.0.1:18000');
  for(const target of ['http://192.0.2.1:8000','https://127.0.0.1:18000','http://user:secret@127.0.0.1:18000','http://127.0.0.1:18000/path'])assert.throws(()=>tunnelTarget(target));
});

test('proxy real Vite: caminho, Bearer, status, leitura restrita e logs sem credenciais (fixture isolada)',async t=>{
  const calls:{url:string;method:string;authorization:string|undefined}[]=[];
  const fixture=httpServer((request,response)=>{
    calls.push({url:request.url||'',method:request.method||'GET',authorization:request.headers.authorization});
    response.setHeader('content-type','application/json');
    response.setHeader('set-cookie','session=should-not-be-forwarded');
    if(request.headers.authorization!=='Bearer '+'a'.repeat(43)){
      response.writeHead(401,{'www-authenticate':'Basic'});return response.end('{"detail":"Unauthorized"}');
    }
    if(request.url?.includes('/health'))return response.end('{"api":"available","projection_store":"available"}');
    if(request.url?.startsWith('/api/v1/config/current'))return response.end('{"desired_revision":0,"effective_revision":null,"operational":false}');
    if(request.url?.startsWith('/api/v1/config/setup')&&request.method==='GET')return response.end('{"version":0,"document":null,"state":"not_started","operational":false,"pending":[]}');
    if(request.url?.startsWith('/api/v1/config/setup')&&request.method==='PUT')return response.end('{"version":1,"state":"draft_saved","operational":false,"pending":[]}');
    if(request.url?.startsWith('/api/v1/config/catalog'))return response.end('{"firmware_profiles":[],"deployment_profiles":[],"applicators":[]}');
    if(request.url?.startsWith('/api/v1/config/history'))return response.end('[]');
    if(request.url?.startsWith('/api/v1/config/proposals/')&&request.url.endsWith('/validate'))return response.end('{"status":"VALIDATED"}');
    if(request.url?.startsWith('/api/v1/config/proposals/'))return response.end('{"status":"DRAFT"}');
    if(request.url==='/api/v1/config/proposals')return response.end('{"operation_id":"123e4567-e89b-12d3-a456-426614174000","revision":1,"status":"DRAFT"}');
    if(request.url==='/api/v1/p11/incident/incident-1/history')return response.end('[{"revision":1,"source":"trusted-service","data":{"incident_id":"incident-1","status":"OBSERVED"}}]');
    response.end('[{"id":"fixture-record","revision":1,"source":"trusted-service","created_at":"2026-10-18T01:14:12.498058-03:00","data":{"device_id":"poste2","temperatura":28.4,"tipo":"teste_systemd"}}]');
  });
  await new Promise<void>(resolve=>fixture.listen(0,'127.0.0.1',resolve));
  t.after(()=>{fixture.closeAllConnections();fixture.close()});
  const address=fixture.address();assert.ok(address&&typeof address!=='string');
  const transport=p11Transport(`http://127.0.0.1:${address.port}`);
  const logs:string[]=[];const logger=createLogger('silent');logger.error=message=>{logs.push(message)};
  const server=await createServer({configFile:false,customLogger:logger,plugins:[transport.plugin],
    server:{host:'127.0.0.1',port:0,hmr:false,cors:false,proxy:transport.proxy},optimizeDeps:{noDiscovery:true}});
  t.after(()=>server.close());await server.listen();
  const local=server.httpServer?.address();assert.ok(local&&typeof local!=='string');
  const base=`http://127.0.0.1:${local.port}/p11-api/api/v1/p11`;
  const headers={Authorization:'Bearer '+'a'.repeat(43)};
  const denied=await fetch(base+'/health');assert.equal(denied.status,401);
  const health=await fetch(base+'/health',{headers});assert.equal((await health.json()).api,'available');
  assert.equal(health.headers.get('set-cookie'),null);assert.equal(health.headers.get('cache-control'),'no-store');
  const telemetry=await fetch(base+'/telemetry?limit=50&offset=0',{headers});assert.equal(telemetry.status,200);
  assert.equal((await telemetry.json())[0].data.temperatura,28.4);
  assert.equal(calls[2].url,'/api/v1/p11/telemetry?limit=50&offset=0');assert.equal(calls[2].authorization,headers.Authorization);
  const explanation=await fetch(base+'/explain/synthetic-fixture',{headers});assert.equal(explanation.status,200);
  assert.equal(calls[3].url,'/api/v1/p11/explain/synthetic-fixture');assert.equal(calls[3].authorization,headers.Authorization);
  const incidentHistory=await fetch(base+'/incident/incident-1/history',{headers});assert.equal(incidentHistory.status,200);assert.equal((await incidentHistory.json())[0].revision,1);
  assert.equal(calls[4].url,'/api/v1/p11/incident/incident-1/history');assert.equal(calls[4].authorization,headers.Authorization);
  const count=calls.length;
  assert.equal((await fetch(base+'/health',{headers:{Authorization:'Basic '+btoa('technical:fixture')}})).status,401);
  assert.equal((await fetch(base+'/ingest/telemetry',{method:'POST',headers})).status,405);
  assert.equal((await fetch(base+'/telemetry',{method:'POST',headers})).status,405);
  assert.equal((await fetch(base+'/explain/synthetic-fixture',{method:'POST',headers})).status,405);
  assert.equal((await fetch(base+'/incident',{headers})).status,200);
  assert.equal((await fetch(base+'/unknown-kind/id/history',{headers})).status,404);
  assert.equal((await fetch(base+'/incident/incident-1/history?limit=10',{headers})).status,400);
  assert.equal((await fetch(base+'/health',{headers:{...headers,Origin:'https://foreign.example'}})).status,403);
  assert.equal((await fetch(base+'/telemetry?password=forbidden',{headers})).status,400);
  assert.equal(calls.length,count+1);
  assert.ok(!logs.join('').includes('transport-fixture'));assert.ok(!logs.join('').includes(headers.Authorization));
  const config=`http://127.0.0.1:${local.port}/p11-api/api/v1/config`;const operation='123e4567-e89b-12d3-a456-426614174000';const start=calls.length;
  for(const [path,method,body] of [['/presentation','GET',undefined],['/setup','GET',undefined],['/current','GET',undefined],['/catalog','GET',undefined],['/history?after=0&limit=100','GET',undefined],['/setup','PUT',{expected_version:0}],['/proposals','POST',{schema_version:'1.0.0'}],[`/proposals/${operation}`,'GET',undefined],[`/proposals/${operation}/validate`,'POST',{expected_revision:1}],[`/proposals/${operation}/apply`,'POST',{expected_revision:1,current_password:'isolated-reauth'}] ] as const){
    const response=await fetch(config+path,{method,headers:{...headers,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});assert.equal(response.status,200,`${method} ${path}`);
  }
  assert.deepEqual(calls.slice(start).map(call=>call.method),['GET','GET','GET','GET','GET','PUT','POST','GET','POST','POST']);
  assert.ok(calls.slice(start).every(call=>call.url.startsWith('/api/v1/config/')&&call.authorization===headers.Authorization));
  assert.ok(calls.slice(start).some(call=>call.url==='/api/v1/config/history?after=0&limit=100'));
  assert.equal((await fetch(config+'/apply',{method:'POST',headers})).status,405);
  assert.equal((await fetch(config+'/history?after=0&secret=no',{headers})).status,400);
});

test('proxy libera somente as rotas candidatas de primeiro acesso/MFA e não envia Basic',async t=>{
 const calls:{url:string;method:string;authorization:string|undefined;origin:string|undefined}[]=[];
 const fixture=httpServer((request,response)=>{
  calls.push({url:request.url||'',method:request.method||'GET',authorization:request.headers.authorization,origin:request.headers.origin});
  response.setHeader('content-type','application/json');response.setHeader('set-cookie','must-not-reach-browser');
  response.end('{"challenge_token":"fixture-only","next_step":"login","expires_at":"2099-01-01T00:00:00Z"}');
 });
 await new Promise<void>(resolve=>fixture.listen(0,'127.0.0.1',resolve));t.after(()=>{fixture.closeAllConnections();fixture.close()});
 const target=fixture.address();assert.ok(target&&typeof target!=='string');const transport=p11Transport(`http://127.0.0.1:${target.port}`);
 const logger=createLogger('silent');const server=await createServer({configFile:false,customLogger:logger,plugins:[transport.plugin],server:{host:'127.0.0.1',port:0,hmr:false,cors:false,proxy:transport.proxy},optimizeDeps:{noDiscovery:true}});
 t.after(()=>server.close());await server.listen();const local=server.httpServer?.address();assert.ok(local&&typeof local!=='string');const origin=`http://127.0.0.1:${local.port}`;const endpoint=`${origin}/p11-api/api/v1/admin-auth/mfa/verify`;
 const result=await fetch(endpoint,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({challenge_token:'temporary-challenge',code:'123456'})});
 assert.equal(result.status,200);assert.equal(result.headers.get('set-cookie'),null);assert.equal(calls[0].url,'/api/v1/admin-auth/mfa/verify');assert.equal(calls[0].method,'POST');assert.equal(calls[0].authorization,undefined);assert.equal(calls[0].origin,origin);
 assert.equal((await fetch(`${origin}/p11-api/api/v1/admin-auth/mfa/disable`,{method:'POST',headers:{Origin:origin}})).status,405);
 assert.equal((await fetch(`${origin}/p11-api/api/v1/admin-auth/mfa/verify?code=123456`,{method:'POST',headers:{Origin:origin}})).status,400);
 assert.equal((await fetch(endpoint,{method:'POST',headers:{Origin:origin,Authorization:'Basic dGVjaDpzZWNyZXQ='}})).status,401);
 assert.equal(calls.length,1);
});
