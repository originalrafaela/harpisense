import {test,expect,type Page} from '@playwright/test';

const initial={value:{operation:'IDS',execution_enabled:false,autonomy_mode:1},revision:1,emergency_stopped:false,updated_at:'2026-10-27T12:00:00Z',observed_at:'2026-10-27T12:01:00Z',real_execution_blocked:true,pending:{reliable:true,blockers:[]},change_allowed:true};
async function enter(page:Page){
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill('fixture');await page.getByLabel('Senha',{exact:true}).fill('fixture');await page.getByRole('button',{name:'Entrar na central'}).click();await expect(page.getByText('Consulta autenticada')).toBeVisible();
}
test('confirma perfil só após servidor; recusa, parada e logs fora da home',async({page})=>{
 let state=structuredClone(initial);const bodies:unknown[]=[];let reject=false;
 let release:()=>void=()=>{};const delayed=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/v1/p11/**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(route.request().url().endsWith('/health')?{api:'available',operational_controls:{...state.value,updated_at:state.updated_at},control_api:{version:1}}:[])}));
 await page.route('**/api/v1/security/**',async route=>{
  const request=route.request();expect(request.headers().authorization).toBe('Basic '+btoa('fixture:fixture'));
  if(request.method()==='PUT'){
   bodies.push(request.postDataJSON());if(reject)return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{message:'Há pendências operacionais que impedem a transição.'}})});
   await delayed;state={...state,value:request.postDataJSON().value,revision:2};
  }
  if(request.method()==='POST')state={...state,emergency_stopped:true,revision:3};
  return route.fulfill({contentType:'application/json',body:JSON.stringify(request.url().includes('/audit')?[]:state)});
 });
 await enter(page);await expect(page.getByRole('heading',{name:'Logs e auditoria de controles'})).toHaveCount(0);
 await page.getByRole('link',{name:'Configurações',exact:true}).click();await expect(page.getByText('Último estado confirmado: M1',{exact:false})).toBeVisible();
 await page.getByLabel('Justificativa da alteração').fill('Teste isolado de mudança');await page.getByRole('button',{name:'Solicitar M3',exact:true}).click();
 await expect(page.getByText('Último estado confirmado: M1',{exact:false})).toBeVisible();await expect(page.getByText('Servidor confirmou M3',{exact:false})).toHaveCount(0);
 release();await expect(page.getByText('Servidor confirmou M3, revisão 2.')).toBeVisible();
 expect((bodies[0] as {value:unknown}).value).toEqual({operation:'IDS',execution_enabled:false,autonomy_mode:3});
 reject=true;await page.getByRole('button',{name:'Solicitar M2',exact:true}).click();await expect(page.getByRole('alert')).toContainText('pendências operacionais');await expect(page.getByText('Último estado confirmado: M3',{exact:false})).toBeVisible();
 await page.getByRole('link',{name:'Dashboard',exact:true}).click();await page.getByRole('button',{name:'Parada de emergência',exact:true}).click();await expect(page.getByText('Parada de emergência ativa',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Logs e auditoria',exact:true}).click();await expect(page.getByText('Sem registros nesta consulta.')).toBeVisible();
 await page.getByRole('link',{name:'Anomalias',exact:true}).click();await expect(page.getByText('Desvio do Isolation Forest não confirma ataque.',{exact:false})).toBeVisible();await expect(page.getByRole('button',{name:'Registrar avaliação'})).toBeDisabled();
});

test('API de anomalias e auditoria indisponível não cria eventos sintéticos',async({page})=>{
 await page.route('**/api/v1/p11/**',route=>route.fulfill({status:route.request().url().includes('/detection')?503:200,contentType:'application/json',body:route.request().url().endsWith('/health')?'{"api":"available"}':'[]'}));
 await page.route('**/api/v1/security/audit**',route=>route.fulfill({status:503,body:'{}'}));
 await enter(page);await page.getByRole('link',{name:'Anomalias',exact:true}).click();await expect(page.getByRole('alert').first()).toContainText('503');
 await page.getByRole('link',{name:'Logs e auditoria',exact:true}).click();await expect(page.getByRole('alert').first()).toContainText('503');await expect(page.getByText('Sem registros nesta consulta.')).toHaveCount(0);await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});

test('autorização negada nos controles encerra acesso e permite autenticar novamente',async({page})=>{
 await page.route('**/api/v1/p11/**',route=>route.fulfill({contentType:'application/json',body:route.request().url().endsWith('/health')?'{"api":"available","control_api":{"version":1}}':'[]'}));
 await page.route('**/api/v1/security/**',route=>route.fulfill({status:401,body:'{}'}));
 await enter(page);await page.getByRole('link',{name:'Configurações',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Acesso administrativo',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Entrar na central',exact:true})).toBeEnabled();
 await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});
