import {test,expect} from '@playwright/test';

async function enterPreview(page:import('@playwright/test').Page){
 await page.goto('http://127.0.0.1:5174');
 await page.getByRole('button',{name:'Explorar demonstração visual'}).click();
 await expect(page.getByText('Prévia visual — dados de demonstração, sem ações reais.')).toBeVisible();
}

test('prévia visual: estados de conta são ilustrativos e não enviam requisições operacionais',async({page})=>{
 const apiRequests:string[]=[];page.on('request',r=>{if(r.url().includes('/api/')||r.url().includes('/p11-api')||r.url().includes('localhost:8000'))apiRequests.push(r.url())});
 await page.goto('http://127.0.0.1:5174');
 await expect(page.getByLabel('Usuário',{exact:true})).toHaveValue('');await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
 await page.getByLabel('Senha',{exact:true}).fill('sensitive-preview-only');await page.getByRole('button',{name:'Mostrar senha'}).click();await expect(page.getByLabel('Senha',{exact:true})).toHaveAttribute('type','text');
 await page.getByRole('button',{name:'Explorar demonstração visual'}).click();await expect(page.getByLabel('Senha',{exact:true})).toHaveCount(0);expect(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).not.toContain('sensitive-preview-only');
 await page.getByRole('button',{name:'Sair'}).click();
 await page.getByRole('button',{name:'Esqueci minha senha'}).click();await expect(page.getByRole('heading',{name:'Recuperação de senha'})).toBeVisible();
 await page.getByRole('button',{name:'Simular etapa'}).click();await expect(page.getByRole('status').filter({hasText:'nenhuma conta ou serviço'})).toBeVisible();
 await page.getByRole('button',{name:'Verificar MFA'}).click();await expect(page.getByLabel('QR ilustrativo, não funcional')).toBeVisible();
 await expect(page.getByText('O código e o QR não são segredos reais')).toBeVisible();
 await page.getByRole('button',{name:'Ver estados de acesso (demonstração)'}).click();await page.getByRole('button',{name:'Credenciais inválidas'}).click();await expect(page.getByText('Credenciais inválidas · exemplo visual. Nenhuma autenticação foi tentada.')).toBeVisible();
 await page.getByRole('button',{name:'Serviço indisponível'}).click();await expect(page.getByText('Serviço indisponível · exemplo visual. Nenhuma chamada foi enviada.')).toBeVisible();expect(apiRequests).toEqual([]);
});

test('autonomia demonstrativa mantém operação e execução independentes e controla estado local',async({page})=>{
 const apiRequests:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))apiRequests.push(r.url())});await enterPreview(page);
 await expect(page.getByRole('heading',{name:'Perfil de autonomia'})).toBeVisible();
 await page.getByRole('button',{name:/Parada de emergência/}).click();await expect(page.locator('.effective-state .badge').filter({hasText:'Parada de emergência demonstrativa ativa'})).toBeVisible();
 await page.getByRole('button',{name:'M3 — Autônomo'}).click();await page.getByRole('button',{name:'Confirmar',exact:true}).click();
 await expect(page.getByText('Perfil atual: M3')).toBeVisible();
 await page.getByRole('link',{name:'Configurações',exact:true}).click();
 await expect(page.getByRole('button',{name:'Parada demonstrativa ativa · retomar visualmente'})).toBeVisible();
 await page.getByLabel('Modo operacional').selectOption('IDS');await page.getByLabel('Execução habilitada').selectOption('false');
 await page.getByRole('button',{name:'Selecionar M1'}).click();await page.getByRole('button',{name:'Confirmar apenas na demonstração'}).click();
 await expect(page.getByText('Trocar M1/M2/M3 não altera IDS/SIMULATION/REAL nem execution_enabled.')).toBeVisible();await expect(page.locator('.effective-state .badge').nth(1)).toContainText('IDS');expect(apiRequests).toEqual([]);
});

test('prévia de configurações, assistente, avaliação e aprovação não persiste alterações',async({page})=>{
 const apiRequests:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))apiRequests.push(r.url())});await enterPreview(page);
 await page.getByRole('link',{name:'Configurações',exact:true}).click();await page.getByRole('tab',{name:'Configurações avançadas'}).click();
 await expect(page.getByText('A URL da API é o endereço usado pelo navegador')).toBeVisible();
 await page.getByRole('button',{name:'Abrir assistente visual de primeira configuração'}).click();
 for(let step=1;step<8;step++)await page.getByRole('button',{name:'Continuar'}).click();
 await page.getByRole('button',{name:'Concluir prévia'}).click();await expect(page.getByRole('status').filter({hasText:'Prévia concluída — nenhuma configuração foi aplicada ao servidor.'}).first()).toBeVisible();
 await page.getByRole('link',{name:'Anomalias',exact:true}).click();await page.getByLabel('1. Avaliação do evento').selectOption({label:'Suspeita de ataque'});await page.getByLabel('2. Decisão sobre a defesa').selectOption({label:'Aprovar bloqueio'});await page.getByRole('button',{name:'Registrar apenas na demonstração'}).click();
 await expect(page.getByRole('status').filter({hasText:'Nenhum dado foi enviado'})).toBeVisible();
 await page.getByRole('link',{name:'Aprovações',exact:true}).click();await page.getByRole('button',{name:'Aprovar',exact:true}).click();await expect(page.getByText(/Aprovar: estado demonstrativo/)).toBeVisible();expect(apiRequests).toEqual([]);
 await page.screenshot({path:'docs/evidence/visual-approvals-notebook.png',fullPage:true});
});

test('capturas principais em notebook e mobile',async({page})=>{
 await page.goto('http://127.0.0.1:5174');await page.screenshot({path:'docs/evidence/visual-login-notebook.png'});
 await enterPreview(page);await page.screenshot({path:'docs/evidence/visual-dashboard-notebook.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'docs/evidence/visual-dashboard-mobile.png'});
 await page.setViewportSize({width:1366,height:768});await page.getByRole('link',{name:'Configurações',exact:true}).click();await page.getByRole('tab',{name:'Configurações avançadas'}).click();await page.getByRole('heading',{name:'Backend',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:'docs/evidence/visual-settings-notebook.png'});
 await page.getByRole('link',{name:'Aprovações',exact:true}).click();await page.getByRole('heading',{name:'Revisar decisão demonstrativa'}).scrollIntoViewIfNeeded();await page.screenshot({path:'docs/evidence/visual-approvals-notebook.png'});
});
