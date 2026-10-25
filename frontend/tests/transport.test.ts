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

test('proxy real Vite: caminho, Basic, status, leitura restrita e logs sem credenciais (fixture isolada)',async t=>{
  const calls:{url:string;authorization:string|undefined}[]=[];
  const fixture=httpServer((request,response)=>{
    calls.push({url:request.url||'',authorization:request.headers.authorization});
    response.setHeader('content-type','application/json');
    response.setHeader('set-cookie','session=should-not-be-forwarded');
    if(request.headers.authorization!=='Basic '+btoa('isolated:transport-fixture')){
      response.writeHead(401,{'www-authenticate':'Basic'});return response.end('{"detail":"Unauthorized"}');
    }
    if(request.url?.includes('/health'))return response.end('{"api":"available","projection_store":"available"}');
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
  const headers={Authorization:'Basic '+btoa('isolated:transport-fixture')};
  const denied=await fetch(base+'/health');assert.equal(denied.status,401);
  const health=await fetch(base+'/health',{headers});assert.equal((await health.json()).api,'available');
  assert.equal(health.headers.get('set-cookie'),null);assert.equal(health.headers.get('cache-control'),'no-store');
  const telemetry=await fetch(base+'/telemetry?limit=50&offset=0',{headers});assert.equal(telemetry.status,200);
  assert.equal((await telemetry.json())[0].data.temperatura,28.4);
  assert.equal(calls[2].url,'/api/v1/p11/telemetry?limit=50&offset=0');assert.equal(calls[2].authorization,headers.Authorization);
  const explanation=await fetch(base+'/explain/synthetic-fixture',{headers});assert.equal(explanation.status,200);
  assert.equal(calls[3].url,'/api/v1/p11/explain/synthetic-fixture');assert.equal(calls[3].authorization,headers.Authorization);
  const count=calls.length;
  assert.equal((await fetch(base+'/telemetry',{method:'POST',headers})).status,405);
  assert.equal((await fetch(base+'/explain/synthetic-fixture',{method:'POST',headers})).status,405);
  assert.equal((await fetch(base+'/incident',{headers})).status,200);
  assert.equal((await fetch(base+'/health',{headers:{...headers,Origin:'https://foreign.example'}})).status,403);
  assert.equal((await fetch(base+'/telemetry?password=forbidden',{headers})).status,400);
  assert.equal(calls.length,count+1);
  assert.ok(!logs.join('').includes('transport-fixture'));assert.ok(!logs.join('').includes(headers.Authorization));
});
