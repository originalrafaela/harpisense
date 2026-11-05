import {test,expect,type Page} from '@playwright/test';

const setup={version:0,document:null,state:'not_started',operational:false,pending:[]};
const current={desired_revision:0,effective_revision:null,state:'not_started',proposed_status:null,operational:false};
const saved={...setup,version:3,state:'draft_saved',document:{step:'mqtt',parameters:{display_name:'Laboratório salvo',mqtt_broker_host:'broker.lab'}}};
const catalog={firmware_profiles:[],deployment_profiles:['esp32-lighting'],applicators:[]};
async function routes(page:Page,progress:unknown=setup,revision:unknown=current){
 const writes:string[]=[];
 await page.route('**/api/v1/config/**',async route=>{
  if(route.request().method()!=='GET')writes.push(route.request().method());
  const path=new URL(route.request().url()).pathname;
  await route.fulfill({json:path.endsWith('/setup')?progress:path.endsWith('/current')?revision:path.endsWith('/catalog')?catalog:[]});
 });
 return writes;
}
test('new installation offers explicit action, never redirects or writes',async({page})=>{
 const writes=await routes(page);
 await page.goto('/tests/installation-harness.html');
 await expect(page.getByText(/Instalação nova:/)).toBeVisible();
 await page.getByRole('button',{name:'Iniciar assistente',exact:true}).click();
 await expect(page.getByText('Interações: 1')).toBeVisible();
 await expect(page).toHaveURL(/installation-harness.html$/);
 expect(writes).toEqual([]);
});
test('existing installation without wizard draft remains existing',async({page})=>{
 await routes(page,setup,{...current,desired_revision:1,state:'validated'});
 await page.goto('/tests/installation-harness.html');
 await expect(page.getByText(/Instalação existente com configuração pendente/)).toBeVisible();
 await expect(page.getByText(/a configuração existente será preservada/)).toBeVisible();
});
test('saved step is offered and optional navigation prop is safe',async({page})=>{
 await routes(page,saved);
 await page.goto('/tests/installation-harness.html?noCallback');
 await expect(page.getByText(/etapa mqtt/)).toBeVisible();
 await expect(page.getByText('O assistente permanece acessível em Configurações.')).toBeVisible();
 await expect(page.getByRole('button',{name:'Retomar assistente',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Função operacional disponível'}).click();
 await expect(page.getByText('Interações: 1')).toBeVisible();
});
test('completed configuration does not claim operational readiness',async({page})=>{
 await routes(page,saved,{...current,desired_revision:2,effective_revision:2,state:'applied_verified',proposed_status:'APPLIED',effective:{parameters:saved.document.parameters},presentation:{verified:true}});
 await page.goto('/tests/installation-harness.html');
 await expect(page.getByText(/Configuração concluída no escopo/)).toBeVisible();
 await expect(page.getByText(/Prontidão operacional: não comprovada/)).toBeVisible();
 await expect(page.getByRole('button',{name:'Abrir Configurações',exact:true})).toBeVisible();
});
test('failure remains nonblocking and retries explicitly without leaking server text',async({page})=>{
 await routes(page);
 await page.route('**/api/v1/config/setup',r=>r.fulfill({status:503,json:{detail:'private-server-value'}}));
 await page.goto('/tests/installation-harness.html');
 await expect(page.getByRole('alert')).toContainText('estado é desconhecido');
 await expect(page.locator('body')).not.toContainText('private-server-value');
 await page.getByRole('button',{name:'Função operacional disponível'}).click();
 await page.unroute('**/api/v1/config/setup');
 await page.getByRole('button',{name:'Tentar consultar novamente'}).click();
 await expect(page.getByText(/Instalação nova:/)).toBeVisible();
});
test('invalid progress and expired session do not become a fresh installation',async({page})=>{
 await routes(page,{...setup,document:{}});
 await page.goto('/tests/installation-harness.html');
 await expect(page.getByRole('alert')).toBeVisible();
 await page.route('**/api/v1/config/setup',r=>r.fulfill({status:401,json:{}}));
 await page.getByRole('button',{name:'Tentar consultar novamente'}).click();
 await expect(page.getByRole('alert')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Dashboard disponível'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Iniciar assistente',exact:true})).toHaveCount(0);
});
test('late response from replaced client cannot overwrite newer progress',async({page})=>{
 await routes(page,saved);
 let release!:()=>void;
 const gate=new Promise<void>(resolve=>{release=resolve});
 let started!:()=>void;
 const waiting=new Promise<void>(resolve=>{started=resolve});
 let first=true;
 await page.route('**/api/v1/config/setup',async r=>{
  if(first){first=false;started();await gate;await r.fulfill({json:setup})}
  else await r.fulfill({json:saved});
 });
 await page.goto('/tests/installation-harness.html');
 await waiting;
 await page.getByRole('button',{name:'Trocar cliente'}).click();
 await expect(page.getByText(/etapa mqtt/)).toBeVisible();
 release();
 await expect(page.getByText(/Instalação nova:/)).toHaveCount(0);
 await page.getByRole('button',{name:'Alternar montagem'}).click();
 await page.getByRole('button',{name:'Alternar montagem'}).click();
 await expect(page.getByText(/etapa mqtt/)).toBeVisible();
});
test('ConfigManager resumes persisted values explicitly without a write',async({page})=>{
 const writes=await routes(page,saved);
 await page.goto('/tests/installation-harness.html?manager');
 await expect(page.getByRole('button',{name:'4. MQTT'})).toHaveAttribute('aria-current','step');
 await page.getByLabel('Host do broker MQTT').fill('unsaved.lab');
 await page.route('**/api/v1/config/setup',r=>r.fulfill({json:{...saved,version:4,document:{step:'installation',parameters:{display_name:'Atualizado em outra sessão'}}}}));
 await page.getByRole('button',{name:'Retomar assistente',exact:true}).click();
 await expect(page.getByRole('button',{name:'1. Instalação'})).toHaveAttribute('aria-current','step');
 await expect(page.getByLabel('Nome da instalação')).toHaveValue('Atualizado em outra sessão');
 expect(writes).toEqual([]);
});
test('ConfigManager query failure does not expose an empty writable wizard',async({page})=>{
 await routes(page);
 await page.route('**/api/v1/config/setup',r=>r.fulfill({status:503,json:{}}));
 await page.goto('/tests/installation-harness.html?manager');
 await expect(page.getByRole('alert')).toContainText('Nenhum rascunho novo');
 await expect(page.getByLabel('Nome da instalação')).toHaveCount(0);
 await page.unroute('**/api/v1/config/setup');
 await page.getByRole('button',{name:'Tentar consultar novamente'}).click();
 await expect(page.getByLabel('Nome da instalação')).toBeVisible();
});
test('refresh preserves local edits; save retry keeps the same identity and idempotency key',async({page})=>{
 await routes(page,saved);
 const bodies:Record<string,unknown>[]=[];
 await page.route('**/api/v1/config/setup',async r=>{
  if(r.request().method()==='GET')return r.fulfill({json:saved});
  const body=r.request().postDataJSON();bodies.push(body);
  if(bodies.length===1)return r.fulfill({status:503,json:{}});
  return r.fulfill({json:{...saved,version:4,document:body.document}});
 });
 await page.goto('/tests/installation-harness.html?manager');
 await page.getByLabel('Host do broker MQTT').fill('edited.lab');
 await page.getByRole('button',{name:'Atualizar estado do servidor'}).click();
 await expect(page.getByLabel('Host do broker MQTT')).toHaveValue('edited.lab');
 await page.getByRole('button',{name:'Salvar e continuar',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Fixture query failed');
 await expect(page.getByLabel('Host do broker MQTT')).toHaveValue('edited.lab');
 await page.getByRole('button',{name:'Salvar e continuar',exact:true}).click();
 await expect(page.getByRole('button',{name:'5. Monitoramento'})).toHaveAttribute('aria-current','step');
 expect(bodies).toHaveLength(2);
 expect(bodies[0]).toEqual(bodies[1]);
 expect(bodies[1].expected_version).toBe(3);
 expect((bodies[1].document as any).parameters).toEqual({...saved.document.parameters,mqtt_broker_host:'edited.lab',mqtt_tls_mode:'required'});
});
