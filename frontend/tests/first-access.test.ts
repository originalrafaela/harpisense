import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,Client,firstAccessState} from '../src/api.ts';
import {sessionResponse} from './session-response.ts';
const state=(status='not_issued',generation=0)=>({contract_version:2,status,generation,codes_remaining:generation?3:0,installation_id:'installation-fixture',account_id:1});
const codes=['A'.repeat(32),'B'.repeat(32),'C'.repeat(32)];

test('v2 valida três slots e rejeita contrato antigo',()=>{
 assert.equal(firstAccessState(state()).status,'not_issued');assert.equal(firstAccessState(state('pending',1)).generation,1);
 for(const bad of [{status:'pending',password_reset_generation:1},{...state(),codes_remaining:4},{...state(),generation:1},state('completed',0)])assert.throws(()=>firstAccessState(bad),ApiError);
});
test('emissão corpo vazio, reemissão senha+MFA e confirmação apenas geração',async()=>{
 const calls:{path:string;body:unknown}[]=[];let current=state();
 const c=new Client('/p11-api','p11',async(url,init)=>{const path=String(url),body=init?.body?JSON.parse(String(init.body)):null;calls.push({path,body});
 if(path.endsWith('/first-access/codes')||path.endsWith('/first-access/reissue')){current=state('pending',current.generation+1);return new Response(JSON.stringify({first_access:current,recovery_codes:codes}));}
 if(path.endsWith('/first-access/confirm')){current=state('completed',current.generation);return new Response(JSON.stringify({first_access:current}));}
 return sessionResponse(url)||new Response(JSON.stringify({first_access:current}));});
 await c.login({username:'fixture-owner',password:'fixture-password'});assert.deepEqual((await c.issueFirstAccessCodes()).recoveryCodes,codes);await c.reissueFirstAccessCodes('fixture-password','123456');await c.confirmFirstAccess(2);
 assert.deepEqual(calls.find(x=>x.path.endsWith('/first-access/codes'))?.body,{});assert.deepEqual(calls.find(x=>x.path.endsWith('/first-access/reissue'))?.body,{current_password:'fixture-password',code:'123456'});assert.deepEqual(calls.find(x=>x.path.endsWith('/first-access/confirm'))?.body,{generation:2});
 assert.ok(calls.every(c=>!c.path.includes('123456')&&!c.path.includes('fixture-password')));
});
test('rejeita conjunto dez, duplicados e segunda finalidade',async()=>{
 for(const payload of [{recovery_codes:Array(10).fill('A'.repeat(32))},{recovery_codes:[codes[0],codes[0],codes[2]]},{recovery_codes:codes,password_reset_codes:codes}]){
 const c=new Client('/p11-api','p11',async url=>sessionResponse(url)||new Response(JSON.stringify({first_access:state('pending',1),...payload})));await c.login({username:'fixture-owner',password:'fixture-password'});await assert.rejects(()=>c.issueFirstAccessCodes(),/exatamente três/);
 }
});
test('conflito entre abas não repete emissão automaticamente',async()=>{
 let attempts=0;const c=new Client('/p11-api','p11',async url=>sessionResponse(url)||(()=>{attempts++;return new Response(JSON.stringify({error:{code:'CODES_ALREADY_ISSUED'}}),{status:409})})());await c.login({username:'fixture-owner',password:'fixture-password'});
 await assert.rejects(()=>c.issueFirstAccessCodes(),e=>e instanceof ApiError&&e.code==='CODES_ALREADY_ISSUED');assert.equal(attempts,1);
});
test('recuperação envia código e TOTP juntos sem obter sessão',async()=>{
 let sent:unknown;const c=new Client('/p11-api','p11',async(_url,init)=>{sent=JSON.parse(String(init?.body));return new Response(JSON.stringify({status:'password_reset',login_required:true,mfa_preserved:true}));});await c.resetPassword('owner',codes[0],'new-password','123456');assert.deepEqual(sent,{username:'owner',code:codes[0],new_password:'new-password',totp_code:'123456'});await assert.rejects(()=>c.health(),/Não autorizado/);
});
test('ativação usa cookie mesma origem e não envia licença pelo browser',async()=>{
 const calls:RequestInit[]=[];const c=new Client('/p11-api','p11',async(_url,init)=>{calls.push(init!);return new Response(JSON.stringify({contract_version:1,status:'connection_required',administrator:'absent',retry_allowed:true,first_use_authorized:true,loss_of_authenticator_policy:'not_approved'}));});await c.activationStatus();await c.retryActivation();assert.ok(calls.every(c=>c.credentials==='same-origin'));assert.deepEqual(JSON.parse(String(calls[1].body)),{});
});
test('sessão sem MFA não libera APIs administrativas',async()=>{
 const c=new Client('/p11-api','p11',async url=>String(url).endsWith('/session')?new Response(JSON.stringify({authenticated:true,username:'owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false})):sessionResponse(url)!);await assert.rejects(()=>c.login({username:'owner',password:'password'}),/MFA obrigatório/);await assert.rejects(()=>c.health(),/Não autorizado/);
});
