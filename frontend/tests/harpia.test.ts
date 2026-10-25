import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Client, type Row} from '../src/api.ts';
import {explanationFreshness, explanationRevision, selectExplanation, explanationTime, originLabel} from '../src/harpia.ts';

const incident: Row = {id:'synthetic-1',revision:3,data:{}};
const explanation: Row = {id:'synthetic-exp',revision:99,source:'trusted-service',created_at:'2026-10-25T13:00:00Z',
  data:{incident_id:'synthetic-1',revision:2,source:'deterministic_fallback',text:'Fixture sintética'}};
test('revisão de projeção não substitui vínculo com revisão do incidente',()=>{
  assert.equal(explanationFreshness(incident,explanation),'stale');
  assert.equal(explanationRevision(explanation),2);
  assert.equal(explanationFreshness(incident,{...explanation,data:{...explanation.data,revision:3}}),'current');
  assert.equal(explanationFreshness(incident,{...explanation,data:{incident_id:'synthetic-1'}}),'unknown');
});
test('origem e horário ausentes não são inventados',()=>{
  assert.equal(originLabel(explanation),'Alternativa determinística');
  assert.equal(explanationTime(explanation),explanation.created_at);
  assert.equal(explanationTime({id:'none',data:{}}),null);
  assert.match(originLabel({id:'none',source:'trusted-service',data:{}}),/não informada/);
});
test('seleção não cruza incidentes e escolhe registro mais recente',()=>{
  const newer={...explanation,id:'newer',created_at:'2026-10-26T13:00:00Z'};
  const foreign={...newer,id:'foreign',data:{...newer.data,incident_id:'other'}};
  assert.equal(selectExplanation([foreign,explanation,newer],'synthetic-1')?.id,'newer');
  assert.equal(selectExplanation([foreign],'synthetic-1'),undefined);
});
test('consulta somente projeções P11; nunca chama endpoint que gera explicação',async()=>{
  const paths:string[]=[];
  const client=new Client('https://synthetic.test','p11',(async url=>{
    paths.push(String(url));return new Response(JSON.stringify(String(url).endsWith('/health')?{api:'available'}:
      [explanation,{...explanation,id:'foreign',data:{...explanation.data,incident_id:'other'}}]));
  }) as typeof fetch);
  await client.login({username:'synthetic',password:'fixture'});
  assert.deepEqual(await client.incidentExplanations('synthetic-1'),[explanation]);
  assert.match(paths[1],/\/api\/v1\/p11\/bitnet\?limit=50&offset=0$/);
  assert.ok(paths.every(p=>!p.includes('/explain/')&&!p.includes(':8091')&&!p.includes(':8092')));
});
test('falha de API ou contrato indisponível não vira dado sintético',async()=>{
  const client=new Client('https://synthetic.test','p11',(async url=>
    new Response(String(url).endsWith('/health')?' {"api":"available"}':'{}',{status:String(url).endsWith('/health')?200:404})) as typeof fetch);
  await client.login({username:'synthetic',password:'fixture'});
  await assert.rejects(()=>client.incidentExplanations('synthetic-1'),/Endpoint indisponível/);
  await assert.rejects(()=>new Client('https://synthetic.test','legacy').incidentExplanations('id'),/não disponíveis/);
});
