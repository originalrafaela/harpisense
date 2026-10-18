import {test} from 'node:test';
import assert from 'node:assert/strict';
import {adaptRows, Client, telemetry} from '../src/api.ts';
import {configuredResources} from '../src/resources.ts';

test('projeção PostgreSQL descrita no relatório mantém identidade, timestamp e payload',()=>{
  // Fixture de contrato baseada no PDF; não é uma coleta real desta sessão.
  const record={id:'poste2-fe153b85241ac04a091479a7a0ca647c87d94029a60aa769f0370298a1281840',revision:1,source:'trusted-service',created_at:'2026-10-18T01:14:12.498058-03:00',data:{device_id:'poste2',temperatura:28.4,tipo:'teste_systemd'}};
  const row=adaptRows([record],'p11')[0];assert.deepEqual(row,record);
  const view=telemetry(row);assert.equal(view.device,'poste2');assert.equal(view.provisionalTemperature,'28.4');
  assert.equal(view.observed,null);assert.equal(view.recorded,record.created_at);assert.equal(view.received,null);
  assert.equal(view.light,'Não informada');assert.equal(view.led,'Não informado');
  assert.deepEqual(adaptRows([],'p11'),[]);assert.throws(()=>adaptRows([{...record,revision:0}],'p11'));
});
test('escopo padrão de integração limita consultas aos recursos confirmados',()=>{
  assert.deepEqual([...configuredResources(undefined)!],['telemetry']);
  assert.equal(configuredResources('all'),null);
});
test('P11 autentica no health protegido; legacy continua autenticando em telemetria',async()=>{
  for(const profile of ['p11','legacy'] as const){
    const paths:string[]=[];
    const client=new Client('/p11-api',profile,(async url=>{
      paths.push(String(url));return new Response(String(url).endsWith('/health')?' {"api":"available"}':'[]');
    }) as typeof fetch);
    await client.login({username:'isolated',password:'fixture'});
    assert.match(paths[0],profile==='p11'?/p11\/health$/:/v1\/telemetry\?/);
    client.logout();await assert.rejects(()=>client.rows('telemetry'),/Não autorizado/);
  }
});
