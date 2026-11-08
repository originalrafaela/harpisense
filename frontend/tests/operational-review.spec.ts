import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {installReadyAdminFixture,loginReadyAdmin} from './fixtures/admin-session-v2';

const appUrl=process.env.HARPISENSE_TEST_URL||'http://127.0.0.1:5175/';

const now=new Date().toISOString();
const cases=JSON.parse(readFileSync(join(process.cwd(),'tests/fixtures/cases-v2/current-sufficient-active.json'),'utf8')).response.cases;
const current={value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:7,emergency_stopped:false,updated_at:now,observed_at:now,real_execution_blocked:true,pending:{reliable:true,blockers:[{id:'inc-fixture-1',state:'ACTIVE'}],cases},cases,change_allowed:false,effective_state:{applied_profile:'M1',control_revision:7,executor:'isolated_simulation_only',availability:'real_executor_unavailable',executor_state:{status:'not_integrated',available:false,observed_at:null,source:null,blockers:['REAL_EXECUTOR_NOT_INTEGRATED']},execution_enabled:false,updated_at:now,operational_visibility:'current',blockers:[{id:'inc-fixture-1',state:'ACTIVE'}],change_allowed:false,containment_confirmed:false}};

test('seletor local alterna livremente; recusa HTTP mantém perfil efetivo e emergência independente (fixture isolada)',async({page})=>{
 const writes:string[]=[];
 await page.route('**/api/v1/p11/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/health'))return route.fulfill({json:{api:'available',control_api:{version:1},operational_controls:{...current.value,revision:current.revision,updated_at:now,effective_state:current.effective_state,cases,real_execution_blocked:true}}});
  return route.fulfill({json:[]});
 });
 await page.route('**/api/v1/security/**',route=>{
  const request=route.request();writes.push(request.method());
  if(request.method()==='GET')return route.fulfill({json:current});
  if(request.method()==='PUT')return route.fulfill({status:409,json:{detail:{code:'OPERATIONAL_PENDING',message:'Há pendências operacionais que impedem a transição.',current_revision:current.revision,current}}});
  return route.fulfill({json:{...current,emergency_stopped:true,value:{...current.value,execution_enabled:false}}});
 });
 const auth=await installReadyAdminFixture(page);await page.goto(appUrl);await loginReadyAdmin(page);
 const profile=page.getByRole('group',{name:'Selecionar perfil de autonomia'});
 const effective=page.getByRole('button',{name:/Estado Operacional Efetivo/});
 await profile.getByRole('button',{name:'M2'}).click();await profile.getByRole('button',{name:'M3'}).click();await profile.getByRole('button',{name:'M1'}).click();
 await expect(effective).toContainText('M1');
 await profile.getByRole('button',{name:'M2'}).click();await page.getByRole('button',{name:'Aplicar',exact:true}).first().click();
 await expect(page.locator('.strip-message')).toContainText('Há pendências operacionais');
 await expect(effective).toContainText('M1');
 await expect(profile.getByRole('button',{name:'M3'})).toBeEnabled();await profile.getByRole('button',{name:'M3'}).click();
 await expect(effective).toContainText('M1');
 await page.getByRole('button',{name:'Parada de emergência',exact:true}).click();
 await expect(page.locator('.strip-emergency')).toContainText('Emergência ativa');
 expect(writes).toContain('PUT');expect(writes).toContain('POST');
 expect(auth.filter(event=>event.path.endsWith('/admin-auth/login')).map(event=>event.bodyKeys)).toEqual([['password','username']]);
 expect(auth.some(event=>event.path.endsWith('/admin-auth/mfa/verify')&&event.method==='POST')).toBe(true);
 expect(auth.some(event=>event.path.endsWith('/admin-auth/session')&&event.authorizationPresent)).toBe(true);
});
