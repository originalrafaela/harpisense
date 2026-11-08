import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';

const fixtureDir=join(process.cwd(),'tests','fixtures','cases-v2');
const controlled=(name:string)=>JSON.parse(readFileSync(join(fixtureDir,name+'.json'),'utf8'));
const dossier=(id:string,revision:number)=>({incident_ref:{id,revision},read_only:true,incident_card:{incident_id:id,occurred_at:'2026-11-07T23:30:18.379213-03:00',asset:{display_name:'Ativo de fixture',technical_id:'fixture-device'},attack_assessment:{state:'confirmed'},attack_situation:{state:'active',value:'ACTIVE'},operational_mode:{state:'known',value:'M1'}}});

test('casos V2 mostram classes sem soma e abrem ficha pela revisão do link publicado',async({page})=>{
 const cases=controlled('current-sufficient-active').response.cases;
 const calls:string[]=[];
 await page.route('**/p11-api/api/v1/p11/**',route=>{
  const url=new URL(route.request().url());calls.push(url.pathname+url.search);
  if(url.pathname.endsWith('/health'))return route.fulfill({json:{api:'available',control_api:{version:1},operational_controls:{autonomy_mode:1,operation:'IDS',execution_enabled:false,cases}}});
  if(url.pathname.endsWith('/dossier'))return route.fulfill({json:dossier(url.pathname.split('/').at(-2)!,Number(url.searchParams.get('incident_revision')))});
  return route.fulfill({json:[]});
 });
 await page.route('**/p11-api/api/v1/security/settings/mode/default',route=>route.fulfill({json:{value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:1,emergency_stopped:false,updated_at:'2026-11-07T23:00:00Z',observed_at:'2026-11-07T23:00:00Z',real_execution_blocked:true,pending:{reliable:true,blockers:[]},cases,change_allowed:false}}));
 await page.route('**/p11-api/api/v1/admin-auth/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/login'))return route.fulfill({json:{access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}});
  if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});
  return route.fulfill({status:204});
 });
 await page.route('**/p11-api/api/v1/config/presentation',route=>route.fulfill({status:404,json:{detail:'Not integrated in fixture'}}));
 await page.route('**/*',async route=>{const url=new URL(route.request().url());if(!url.pathname.includes('/api/v1/'))return route.continue();const path=url.pathname.replace(/^\/p11-api/,'');calls.push(path+url.search);if(path.endsWith('/admin-auth/login'))return route.fulfill({json:{access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}});if(path.endsWith('/admin-auth/session'))return route.fulfill({json:{authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});if(path.endsWith('/config/presentation'))return route.fulfill({status:404,json:{}});if(path==='/api/v1/security/settings/mode/default')return route.fulfill({json:{value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:1,emergency_stopped:false,updated_at:'2026-11-07T23:00:00Z',observed_at:'2026-11-07T23:00:00Z',real_execution_blocked:true,pending:{reliable:true,blockers:[]},cases,change_allowed:false}});if(path.endsWith('/p11/health'))return route.fulfill({json:{api:'available',control_api:{version:1},operational_controls:{autonomy_mode:1,operation:'IDS',execution_enabled:false,cases}}});if(path.endsWith('/dossier'))return route.fulfill({json:dossier(url.pathname.split('/').at(-2)!,Number(url.searchParams.get('incident_revision')))});if(path.startsWith('/api/v1/p11/'))return route.fulfill({json:[]});return route.fulfill({status:404,json:{detail:'Fixture isolada: rota sem resposta configurada'}})});
 await page.goto('http://127.0.0.1:5176/');await page.getByLabel('Usuário',{exact:true}).fill('fixture');await page.getByLabel('Senha',{exact:true}).fill('fixture');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('button',{name:/Anomalias e ataques/})).toContainText('1 caso(s) distinto(s) ativo(s)');
 await expect(page.getByRole('button',{name:/Anomalias e ataques/})).toContainText('Anomalias 1 · Ataques confirmados 1 · Incidentes 1 · classes sobrepostas');
 await page.evaluate(()=>{const badge=document.createElement('div');badge.textContent='FIXTURE CONTROLADA · sem conexão ao backend';badge.setAttribute('aria-label','Captura com fixture controlada, sem API real');badge.style.cssText='position:fixed;z-index:9999;top:8px;left:50%;transform:translateX(-50%);padding:8px 14px;border-radius:8px;background:#f7c948;color:#111;font:700 12px sans-serif;box-shadow:0 2px 12px #0008';document.body.append(badge)});
 await page.screenshot({path:'docs/evidence/dashboard-cases-v2-fixture-20261108.png',fullPage:true});
 await page.getByRole('link',{name:/Incidentes/}).click();
 const dossierButton=page.getByRole('button',{name:/Abrir ficha fixture-linked-case-7cac6972a8354698aa35f89f917b621b · rev. 1/});await expect(dossierButton).toBeVisible();await dossierButton.click();
 await expect(page.getByRole('heading',{name:/Ficha do caso/})).toBeVisible();await expect(page.getByText('Ativo de fixture')).toBeVisible();
 expect(calls).toContain('/api/v1/p11/incidents/fixture-linked-case-7cac6972a8354698aa35f89f917b621b/dossier?incident_revision=1');
});

test('zero V2 parcial nunca vira “Sem casos ativos”; observação suficiente pode',async({page})=>{
 const snapshots=['partial-observation','current-sufficient-zero'];let index=0;
 await page.route('**/p11-api/api/v1/p11/**',route=>route.fulfill({json:[]}));
 await page.route('**/p11-api/api/v1/p11/health',route=>{const cases=controlled(snapshots[index]).response.cases;return route.fulfill({json:{api:'available',control_api:{version:1},operational_controls:{autonomy_mode:1,operation:'IDS',execution_enabled:false,cases}}})});
 await page.route('**/p11-api/api/v1/security/settings/mode/default',route=>route.fulfill({status:503,json:{}}));
 await page.route('**/p11-api/api/v1/admin-auth/**',async route=>{const path=new URL(route.request().url()).pathname;if(path.endsWith('/login'))return route.fulfill({json:{access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}});if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});return route.fulfill({status:204})});
 await page.route('**/p11-api/api/v1/config/presentation',route=>route.fulfill({status:404,json:{}}));
 await page.route('**/*',async route=>{const url=new URL(route.request().url());if(!url.pathname.includes('/api/v1/'))return route.continue();const path=url.pathname.replace(/^\/p11-api/,'');if(path.endsWith('/admin-auth/login'))return route.fulfill({json:{access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-admin'}});if(path.endsWith('/admin-auth/session'))return route.fulfill({json:{authenticated:true,username:'fixture-admin',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});if(path.endsWith('/config/presentation'))return route.fulfill({status:404,json:{}});if(path==='/api/v1/security/settings/mode/default')return route.fulfill({status:503,json:{}});if(path.endsWith('/p11/health')){const cases=controlled(snapshots[index]).response.cases;return route.fulfill({json:{api:'available',control_api:{version:1},operational_controls:{autonomy_mode:1,operation:'IDS',execution_enabled:false,cases}}})}if(path.startsWith('/api/v1/p11/'))return route.fulfill({json:[]});return route.fulfill({status:404,json:{}})});
 await page.goto('http://127.0.0.1:5176/');await page.getByLabel('Usuário',{exact:true}).fill('fixture');await page.getByLabel('Senha',{exact:true}).fill('fixture');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('button',{name:/Anomalias e ataques/})).toContainText('Cobertura parcial');await expect(page.getByRole('button',{name:/Anomalias e ataques/})).not.toContainText('Sem casos ativos');
 index=1;await page.getByRole('button',{name:'↻ Atualizar consulta'}).click();await expect(page.getByRole('button',{name:/Anomalias e ataques/})).toContainText('Sem casos ativos');
});
