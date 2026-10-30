import {sessionResponse} from './session-response.ts';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Client,controlState} from '../src/api.ts';

const state={value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:1,emergency_stopped:false,updated_at:'2026-10-27T12:00:00Z',observed_at:'2026-10-27T12:01:00Z',real_execution_blocked:true,pending:{reliable:false,blockers:[],dependency:'Queue not connected'},change_allowed:false};
test('estado desconhecido/incompatível não confirma alteração',()=>{
 assert.equal(controlState(state).revision,1);
 for(const bad of [{},{...state,revision:0},{...state,real_execution_blocked:false},{...state,pending:{}},{...state,value:{...state.value,autonomy_mode:true}}])assert.throws(()=>controlState(bad));
});
test('mudança envia Bearer, revisão e justificativa; M3 preserva IDS e execução false',async()=>{
 const calls:{url:string;init:RequestInit|undefined}[]=[];
 const api=new Client('/p11-api','p11',(async(url,init)=>{const auth=sessionResponse(url);if(auth)return auth;calls.push({url:String(url),init});return new Response(JSON.stringify(String(url).endsWith('/health')?{api:'available'}:{...state,value:{...state.value,autonomy_mode:3},revision:2}))}) as typeof fetch);
 await api.login({username:'fixture',password:'fixture'});
 const response=await api.changeControls({...state.value,autonomy_mode:3} as never,1,'isolated');
 assert.equal(response.revision,2);assert.equal(calls[0].init?.method,'PUT');
 assert.deepEqual(JSON.parse(String(calls[0].init?.body)),{value:{autonomy_mode:3,operation:'IDS',execution_enabled:false},expected_revision:1,reason:'isolated'});
 assert.ok((calls[0].init?.headers as Record<string,string>).Authorization.startsWith('Bearer '));
});
test('recusa e falha de autenticação não viram confirmação',async()=>{
 for(const status of [401,403,409,503]){
  let logged=false;
  const api=new Client('/p11-api','p11',(async url=>sessionResponse(url)||new Response(JSON.stringify(logged?{detail:{message:'Pending operational work'}}:{api:'available'}),{status:logged?status:200})) as typeof fetch);
  await api.login({username:'fixture',password:'fixture'});logged=true;
  await assert.rejects(()=>api.changeControls(state.value as never,1,'isolated'));
 }
});
