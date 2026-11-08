import {test,expect} from './session-fixture';

const appUrl=process.env.HARPISENSE_TEST_URL||'http://127.0.0.1:5174';

const emptySetup={version:0,document:null,state:'not_started',operational:false,pending:[]};
const emptyCurrent={desired_revision:0,effective_revision:null,operational:false,state:'not_configured',proposed_status:'NONE'};
const catalog={firmware_profiles:[],deployment_profiles:[],applicators:[]};
async function openDashboard(page:any,setup:unknown,current:unknown){
 await page.route('**/api/v1/p11/**',route=>route.fulfill({json:new URL(route.request().url()).pathname.endsWith('/health')?{api:'available'}:[]}));
 await page.route('**/api/v1/security/**',route=>route.fulfill({json:{value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:1,emergency_stopped:false,updated_at:new Date().toISOString()}}));
 await page.route('**/api/v1/config/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/setup'))return route.fulfill({json:setup});
  if(path.endsWith('/current'))return route.fulfill({json:current});
  if(path.endsWith('/catalog'))return route.fulfill({json:catalog});
  if(path.endsWith('/history'))return route.fulfill({json:[]});
  if(path.endsWith('/presentation'))return route.fulfill({status:404,json:{detail:'Optional'}});
  return route.fulfill({status:404,json:{}});
 });
 await page.goto(appUrl);
 await page.getByLabel('Usuário',{exact:true}).fill('isolated-owner');
 await page.getByLabel('Senha',{exact:true}).fill('isolated-password');
 await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
}

test('após sessão autorizada a instalação nova não bloqueia dashboard e abre o assistente existente',async({page})=>{
 const calls:string[]=[];
 await page.route('**/api/v1/config/**',async route=>{
  const path=new URL(route.request().url()).pathname;calls.push(path);
  if(path.endsWith('/setup'))return route.fulfill({json:emptySetup});
  if(path.endsWith('/current'))return route.fulfill({json:emptyCurrent});
  if(path.endsWith('/catalog'))return route.fulfill({json:catalog});
  if(path.endsWith('/history'))return route.fulfill({json:[]});
  return route.fulfill({status:404,json:{detail:'Optional'}});
 });
 await page.route('**/api/v1/p11/**',route=>route.fulfill({json:new URL(route.request().url()).pathname.endsWith('/health')?{api:'available'}:[]}));
 await page.route('**/api/v1/security/**',route=>route.fulfill({json:{value:{autonomy_mode:1,operation:'IDS',execution_enabled:false},revision:1,emergency_stopped:false,updated_at:new Date().toISOString()}}));
 await page.goto(appUrl);await page.getByLabel('Usuário',{exact:true}).fill('isolated-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByText(/Instalação nova: nenhum progresso/)).toBeVisible();
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
 expect(calls.some(path=>path.endsWith('/config/setup'))).toBe(true);expect(calls.some(path=>path.endsWith('/config/current'))).toBe(true);
 await page.getByRole('button',{name:'Iniciar assistente'}).click();
 await expect(page.getByRole('heading',{name:'Configuração do gerenciador'})).toBeVisible();
 await page.getByRole('button',{name:'Retomar assistente'}).click();
 await expect(page.getByLabel('Nome da instalação')).toBeVisible();
});

test('progresso pendente salvo pelo servidor é retomado na etapa persistida',async({page})=>{
 const saved={version:2,document:{step:'devices',devices:[{device_id:'poste-1',firmware_id:'esp32-wroom32-lighting',firmware_version:'1.0.0'}],parameters:{display_name:'Laboratório de ensaio'}},state:'draft_saved',operational:false,pending:[]};
 const current={desired_revision:1,effective_revision:null,operational:false,state:'draft_saved',proposed_status:'DRAFT'};
 await openDashboard(page,saved,current);
 await expect(page.getByText(/configuração pendente/)).toBeVisible();
 await page.getByRole('button',{name:'Retomar assistente'}).click();
 await expect(page.getByRole('heading',{name:'Configuração do gerenciador'})).toBeVisible();
 await page.getByRole('button',{name:'Retomar assistente'}).click();
 await expect(page.getByRole('button',{name:'3. Dispositivos'})).toHaveAttribute('aria-current','step');
 await expect(page.getByLabel('Perfil de firmware do catálogo')).toBeVisible();
});

test('rascunho do gerenciador continua separado e retomável após recarregar a sessão',async({page})=>{
 const saved={version:5,document:{step:'mqtt',devices:[],parameters:{display_name:'Unidade Oeste',mqtt_broker_host:'broker.interno'}},state:'draft_saved',operational:false,pending:[]};
 const current={desired_revision:1,effective_revision:null,operational:false,state:'draft_saved',proposed_status:'DRAFT'};
 await openDashboard(page,saved,current);
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
 await expect(page.getByText(/configuração pendente/)).toBeVisible();
 await page.reload();
 await page.getByLabel('Usuário',{exact:true}).fill('isolated-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('heading',{name:'Dashboard',exact:true})).toBeVisible();
 await expect(page.getByText('Primeiro acesso')).toHaveCount(0);
 await page.getByRole('button',{name:'Retomar assistente'}).click();
 await page.getByRole('button',{name:'Retomar assistente'}).click();
 await expect(page.getByRole('button',{name:'4. MQTT'})).toHaveAttribute('aria-current','step');
 await expect(page.getByLabel('Broker MQTT')).toHaveValue('broker.interno');
});
