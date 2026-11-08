import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,Client,firstAccessState} from '../src/api.ts';

const expiry=()=>new Date(Date.now()+3_600_000).toISOString();
const issuedAt=()=>new Date().toISOString();
const pending=(generation:number)=>({status:'pending',password_reset_generation:generation,password_reset_purpose:'password_reset',codes_issued:generation>0,issued_at:generation>0?issuedAt():null,completed_at:null});
const completed=(generation:number)=>({...pending(generation),status:'completed',completed_at:issuedAt()});
const currentSession=(state:unknown)=>({authenticated:true,username:'admin-operador',expires_at:expiry(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false,first_access:state});
const codes=(prefix:string)=>Array.from({length:10},(_,i)=>`${prefix}${String(i).padStart(31,'0')}`);

test('first_access valida propósito, geração e timestamps sem tratar códigos como status',()=>{
 assert.equal(firstAccessState(pending(0)).status,'pending');
 assert.equal(firstAccessState(completed(2)).password_reset_generation,2);
 assert.throws(()=>firstAccessState({...pending(0),codes_issued:true}),ApiError);
 assert.throws(()=>firstAccessState({...pending(1),password_reset_purpose:'authenticator_recovery'}),ApiError);
});

test('emissão autenticada substitui ambos os conjuntos e confirmação só envia a geração',async()=>{
 const token='A'.repeat(43);let state:unknown=pending(1);const calls:{path:string;method:string;auth:string|null;body:unknown}[]=[];
 const client=new Client('https://harpi.example','p11',async(input,init)=>{
  const url=new URL(String(input));let body:unknown=null;try{body=JSON.parse(String(init?.body))}catch{}
  calls.push({path:url.pathname,method:init?.method||'GET',auth:new Headers(init?.headers).get('authorization'),body});
  if(url.pathname.endsWith('/admin-auth/login'))return new Response(JSON.stringify({access_token:token,token_type:'Bearer',expires_at:expiry(),idle_timeout_seconds:1800,username:'admin-operador'}),{headers:{'content-type':'application/json'}});
  if(url.pathname.endsWith('/admin-auth/session'))return new Response(JSON.stringify(currentSession(state)),{headers:{'content-type':'application/json'}});
  if(url.pathname.endsWith('/admin-auth/first-access'))return new Response(JSON.stringify({username:'admin-operador',first_access:state}),{headers:{'content-type':'application/json'}});
  if(url.pathname.endsWith('/admin-auth/first-access/codes')){state=pending(2);return new Response(JSON.stringify({username:'admin-operador',recovery_codes:codes('R'),password_reset_codes:codes('P'),first_access:state}),{headers:{'content-type':'application/json'}})}
  if(url.pathname.endsWith('/admin-auth/first-access/confirm')){assert.deepEqual(body,{password_reset_generation:2});state=completed(2);return new Response(JSON.stringify({username:'admin-operador',first_access:state}),{headers:{'content-type':'application/json'}})}
  return new Response(JSON.stringify({error:{code:'NOT_FOUND'}}),{status:404,headers:{'content-type':'application/json'}});
 });
 const login=await client.login({username:'admin-operador',password:'fixture-password'});assert.equal(login.kind,'session');
 if(login.kind!=='session')throw new Error('fixture login did not return a session');
 assert.equal(login.firstAccess?.status,'pending');
 const initial=await client.firstAccess();assert.equal(initial.firstAccess.password_reset_generation,1);
 const emission=await client.issueFirstAccessCodes('fixture-password','123456');
 assert.equal(emission.firstAccess.password_reset_generation,2);assert.equal(emission.recoveryCodes.length,10);assert.equal(emission.passwordResetCodes.length,10);
 assert.equal((await client.confirmFirstAccess(2)).status,'completed');
 assert.ok(calls.some(call=>call.path.endsWith('/admin-auth/first-access/codes')&&call.method==='POST'&&call.auth===`Bearer ${token}`&&JSON.stringify(call.body).includes('current_password')));
 const confirmation=calls.find(call=>call.path.endsWith('/admin-auth/first-access/confirm'))!;
 assert.equal(confirmation.auth,`Bearer ${token}`);assert.deepEqual(confirmation.body,{password_reset_generation:2});
 assert.ok(calls.every(call=>!call.path.includes('123456')&&!call.path.includes(codes('R')[0])&&!call.path.includes(codes('P')[0])));
 client.forgetSession();
});

test('conflito de geração é preservado para o modal solicitar nova emissão',async()=>{
 const token='B'.repeat(43);let state:unknown=pending(3);
 const client=new Client('https://harpi.example','p11',async(input,init)=>{
  const path=new URL(String(input)).pathname;
  if(path.endsWith('/admin-auth/login'))return new Response(JSON.stringify({access_token:token,token_type:'Bearer',expires_at:expiry(),idle_timeout_seconds:1800,username:'admin-operador'}),{headers:{'content-type':'application/json'}});
  if(path.endsWith('/admin-auth/session'))return new Response(JSON.stringify(currentSession(state)),{headers:{'content-type':'application/json'}});
  if(path.endsWith('/admin-auth/first-access/confirm'))return new Response(JSON.stringify({error:{code:'FIRST_ACCESS_GENERATION_CONFLICT'}}),{status:409,headers:{'content-type':'application/json'}});
  if(path.endsWith('/admin-auth/first-access'))return new Response(JSON.stringify({username:'admin-operador',first_access:state}),{headers:{'content-type':'application/json'}});
  return new Response(JSON.stringify({error:{code:'NOT_FOUND'}}),{status:404,headers:{'content-type':'application/json'}});
 });
 await client.login({username:'admin-operador',password:'fixture-password'});
 await assert.rejects(()=>client.confirmFirstAccess(2),error=>error instanceof ApiError&&error.kind==='conflict'&&error.code==='FIRST_ACCESS_GENERATION_CONFLICT');
 assert.equal((await client.firstAccess()).firstAccess.password_reset_generation,3);client.forgetSession();
});
