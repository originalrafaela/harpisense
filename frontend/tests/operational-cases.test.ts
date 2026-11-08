import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {ApiError,caseSnapshot,casesConfirmNoActive,controlState,Client} from '../src/api.ts';

const fixtureDir=fileURLToPath(new URL('./fixtures/cases-v2/',import.meta.url));
function fixtureResponse(name:string){const value=JSON.parse(readFileSync(join(fixtureDir,name+'.json'),'utf8'));assert.match(value.fixture_notice,/controlled|fixture/i);return value.response}
function fixture(name:string){const response=fixtureResponse(name);return response.cases||response.detail?.current?.cases||response.detail?.pending?.cases}

test('cases v2 mantém caso/ataque conhecido durante perda de comunicação sem inferir total',()=>{
 const parsed=caseSnapshot(fixture('communication-loss-known-attack'));
 assert.equal(parsed?.contract_version,2);assert.equal(parsed?.coverage,'partial');assert.equal(parsed?.observation_sufficient,false);assert.equal(parsed?.known_active_count,1);assert.equal(parsed?.total_active_count,null);
 const item=parsed?.items[0] as {case_id:string;links:{incident_ref:{id:string}}[];classifications:string[]};assert.equal(item.case_id,item.links[0].incident_ref.id);
 assert.equal(item.classifications.includes('confirmed_attack'),true);assert.equal(casesConfirmNoActive(parsed),false);
});

test('contagens por classe sobreposta não são somadas e link usa path/revisão fornecidos',()=>{
 const parsed=caseSnapshot(fixture('current-sufficient-active'));assert.equal(parsed?.contract_version,2);
 assert.equal(parsed?.total_active_count,1);assert.deepEqual(parsed?.classification_counts,{anomaly:1,confirmed_attack:1,incident:1});
 const item=parsed?.items[0] as {case_id:string;links:{path:string;incident_ref:{revision:number}}[]};
 assert.equal(item.links[0].incident_ref.revision,1);assert.match(item.links[0].path,/dossier\?incident_revision=1$/);
});

test('somente observação suficiente v2 confirma zero casos',()=>{
 const parsed=caseSnapshot(fixture('current-sufficient-zero'));
 assert.equal(casesConfirmNoActive(parsed),true);assert.equal(parsed?.total_active_count,0);
 assert.equal(casesConfirmNoActive(caseSnapshot(fixture('partial-observation'))),false);
 assert.equal(casesConfirmNoActive(caseSnapshot(fixture('never-observed'))),false);
});

test('caso conhecido stale continua visível e zero parcial não é segurança',()=>{
 const stale=caseSnapshot(fixture('stale-known-attack'));assert.equal(stale?.known_active_count,1);assert.equal(stale?.total_active_count,null);assert.equal(casesConfirmNoActive(stale),false);
 const partial=caseSnapshot(fixture('partial-unlinked'));assert.equal(partial?.known_active_count,null);assert.equal(partial?.unlinked_active_item_count,1);assert.equal(casesConfirmNoActive(partial),false);
});

test('snapshot legado v1 não pode ser exibido como total distinto nem zero confirmado',()=>{
 const v1={status:'none_active',coverage:'complete',known_active_count:0,count_basis:'source_item',sources:[{source:'incidents',source_revision:1,observed_at:'2026-11-07T12:00:00Z',fresh:true,valid:true,complete:true}],items:[]};
 const parsed=caseSnapshot(v1);assert.equal(parsed?.contract_version,1);assert.equal(casesConfirmNoActive(parsed),false);
});

test('parser rejeita casos v2 que contradizem contagem distinta ou navegação canônica',()=>{
 const value=fixture('current-sufficient-active');assert.equal(caseSnapshot({...value,count_basis:'source_item'}),null);
 const broken=structuredClone(value);broken.items[0].links[0].path='/api/v1/p11/incidents/source-record/dossier?incident_revision=1';assert.equal(caseSnapshot(broken),null);
 const coverageMarker=structuredClone(value);coverageMarker.items[0].items.push({source:'__coverage__',record_id:'coverage',source_revision:1,source_observed_at:null,fresh:false,state:'UNKNOWN',origin:null,incident_ref:coverageMarker.items[0].incident_ref});assert.equal(caseSnapshot(coverageMarker),null);
});

test('estado operacional conserva snapshot v2 do endpoint sem recalcular classes',()=>{
 const cases=fixture('current-sufficient-active');const state={value:{autonomy_mode:2,operation:'IDS',execution_enabled:false},revision:7,emergency_stopped:false,updated_at:'2026-11-07T17:00:00Z',observed_at:'2026-11-07T17:00:00Z',real_execution_blocked:true,pending:{reliable:true,blockers:[]},cases,change_allowed:false,effective_state:{applied_profile:'M2',control_revision:7,executor_state:{status:'not_integrated',available:false,observed_at:null,source:null,blockers:['REAL_EXECUTOR_NOT_INTEGRATED']},execution_enabled:false,updated_at:'2026-11-07T17:00:00Z',operational_visibility:'current',blockers:[],change_allowed:false,containment_confirmed:false}};
 const parsed=controlState(state);assert.equal(parsed.cases?.contract_version,2);assert.equal(parsed.cases?.total_active_count,1);assert.equal(parsed.effective_state?.containment_confirmed,false);
});

test('consulta de ficha usa somente o link ID/revisão recebido e exige vínculo da resposta',async()=>{
 const calls:{url:string;authorization:string|undefined}[]=[];const ref={id:'inc-v2-1',revision:4};
 const client=new Client('/p11-api','p11',async(input,init)=>{const url=String(input);calls.push({url,authorization:new Headers(init?.headers).get('authorization')||undefined});if(url.endsWith('/admin-auth/login'))return new Response(JSON.stringify({access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}),{status:200});if(url.endsWith('/admin-auth/session'))return new Response(JSON.stringify({authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}),{status:200});return new Response(JSON.stringify({incident_ref:ref,incident_card:{incident_id:ref.id},read_only:true}),{status:200})});
 await client.login({username:'fixture-admin',password:'fixture-password'});const path='/api/v1/p11/incidents/inc-v2-1/dossier?incident_revision=4';const result=await client.caseDossier(path,ref);assert.equal((result.incident_card as {incident_id:string}).incident_id,ref.id);assert.equal(calls.at(-1)?.url,'/p11-api'+path);assert.match(calls.at(-1)?.authorization||'',/^Bearer /);
 const before=calls.length;await assert.rejects(()=>client.caseDossier(path,{id:ref.id,revision:3}));assert.equal(calls.length,before);
});

test('409 de perfil preserva o caso V2 e o perfil vigente retornados pelo backend',async()=>{
 const refused=fixtureResponse('profile-change-refused');let sent=false;
 const client=new Client('/p11-api','p11',async(input,init)=>{const url=String(input);if(url.endsWith('/admin-auth/login'))return new Response(JSON.stringify({access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}),{status:200});if(url.endsWith('/admin-auth/session'))return new Response(JSON.stringify({authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}),{status:200});sent=true;return new Response(JSON.stringify(refused),{status:409})});
 await client.login({username:'fixture-admin',password:'fixture-password'});await assert.rejects(()=>client.changeControls({autonomy_mode:3,operation:'IDS',execution_enabled:false},2,'Fixture refusal'),error=>error instanceof ApiError&&error.currentState?.value.autonomy_mode===2&&error.currentState.cases?.contract_version===2&&error.currentState.cases.total_active_count===1);assert.equal(sent,true);
});
