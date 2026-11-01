import {test} from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,Client,object} from '../src/api.ts';
import {sessionResponse} from './session-response.ts';

test('cliente autenticado usa as oito rotas confirmadas do gerenciador sem persistir credenciais',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[];
 const fetcher=(async(url,init)=>{
  const path=new URL(String(url)).pathname;calls.push({url:String(url),init});const auth=sessionResponse(url);if(auth)return auth;
  if(path.endsWith('/setup')&&init?.method==='PUT')return Response.json({version:1,document:JSON.parse(String(init.body)).document,state:'draft_saved',operational:false,pending:[]});
  if(path.endsWith('/setup'))return Response.json({version:0,document:null,state:'not_started',operational:false,pending:[]});
  if(path.endsWith('/current'))return Response.json({desired_revision:0,effective_revision:null,proposed:null,effective:null,state:'not_started',operational:false});
  if(path.endsWith('/catalog'))return Response.json({firmware_profiles:[{id:'esp32-wroom32-lighting',version:'1.0.0',available:false}],deployment_profiles:['esp32-lighting'],applicators:[]});
  if(path.endsWith('/history'))return Response.json([]);
  if(path.endsWith('/proposals')&&init?.method==='POST')return Response.json({operation_id:'123e4567-e89b-12d3-a456-426614174000',revision:1,status:'DRAFT'});
  if(path.endsWith('/validate'))return Response.json({status:'VALIDATED'});
  if(path.includes('/proposals/'))return Response.json({status:'DRAFT'});
  return Response.json({api:'available'});
 }) as typeof fetch;
 const client=new Client('https://example.test','p11',fetcher);await client.login({username:'fixture-admin',password:'fixture-password'});
 const setup=await client.get('/api/v1/config/setup');await client.get('/api/v1/config/current');await client.get('/api/v1/config/catalog');await client.get('/api/v1/config/history?after=0&limit=100');
 const draft={step:'installation',parameters:{display_name:'Instalação'}},saved=await client.get('/api/v1/config/setup','PUT',{expected_version:0,idempotency_key:'setup-key-0001',document:draft});
 const proposal=await client.get('/api/v1/config/proposals','POST',{schema_version:'1.0.0',record_type:'config.proposal',request_id:'123e4567-e89b-12d3-a456-426614174000',idempotency_key:'proposal-key-0001',expected_revision:0,reason_code:'INITIAL_IMPORT',document:{schema_version:'1.0.0',record_type:'config.document',parameters:{display_name:'Instalação'}}});
 await client.get('/api/v1/config/proposals/123e4567-e89b-12d3-a456-426614174000');await client.get('/api/v1/config/proposals/123e4567-e89b-12d3-a456-426614174000/validate','POST',{expected_revision:1});
 assert.equal((setup as {version:number}).version,0);assert.equal((saved as {version:number}).version,1);assert.equal((proposal as {status:string}).status,'DRAFT');
 const paths=calls.map(c=>new URL(c.url).pathname);for(const route of ['/current','/proposals','/proposals/123e4567-e89b-12d3-a456-426614174000','/proposals/123e4567-e89b-12d3-a456-426614174000/validate','/history','/setup','/catalog'])assert.ok(paths.some(p=>p.endsWith(route)),route);
 assert.ok(calls.filter(c=>c.url.includes('/api/v1/config/')).every(c=>(c.init?.headers as Record<string,string>).Authorization==='Bearer '+'a'.repeat(43)));
 assert.ok(calls.every(c=>c.init?.credentials==='omit'&&c.init?.cache==='no-store'));
 assert.equal('localStorage' in globalThis,false);
 assert.equal(object(await client.get('/api/v1/config/current')),true);
});

test('409 preserva current_revision e 422 preserva campos sanitizados na camada HTTP',async()=>{
 const client=new Client('/p11-api','p11',(async(url)=>sessionResponse(url)||new Response(JSON.stringify({error:{code:'SETUP_VERSION_CONFLICT',current_revision:4,fields:[{field:'document.parameters.display_name',code:'INVALID_FIELD'}]}}),{status:String(url).endsWith('/setup')?409:422})) as typeof fetch);
 await client.login({username:'fixture-admin',password:'fixture-password'});
 await assert.rejects(()=>client.get('/api/v1/config/setup','PUT',{}),(error:unknown)=>error instanceof ApiError&&error.kind==='conflict'&&error.currentRevision===4);
 await assert.rejects(()=>client.get('/api/v1/config/proposals','POST',{}),(error:unknown)=>error instanceof ApiError&&error.fields[0]?.field==='document.parameters.display_name');
});

test('sessão expirada é descartada e a chamada seguinte não sai do navegador',async()=>{
 let configCalls=0;const client=new Client('/p11-api','p11',(async(url)=>sessionResponse(url)||(++configCalls,new Response(JSON.stringify({error:{code:'SESSION_EXPIRED'}}),{status:401}))) as typeof fetch);
 await client.login({username:'fixture-admin',password:'fixture-password'});await assert.rejects(()=>client.get('/api/v1/config/setup'),/Sessão expirada/);await assert.rejects(()=>client.get('/api/v1/config/current'),/Não autorizado/);assert.equal(configCalls,1);
});
