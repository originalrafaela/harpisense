import {test,expect} from '@playwright/test';
test('prévia isolada: telas, controles e logout em notebook',async({page})=>{
 const operational:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))operational.push(r.url())});
 await page.goto('http://127.0.0.1:5174');await page.getByRole('button',{name:'Abrir prévia visual'}).click();
 await page.screenshot({path:'local-evidence/dashboard-notebook.png',fullPage:true});
 await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toBeVisible();
 const links=await page.getByRole('navigation').getByRole('link').all();
 for(const link of links){await link.click();await expect(page.locator('main h1')).toBeVisible();await expect(page.locator('.panel').first()).toBeVisible()}
 await page.getByRole('link',{name:'Aprovações',exact:true}).click();await expect(page.getByRole('button',{name:'Aprovar',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Sair',exact:true}).click();await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');expect(operational).toEqual([]);
});
test('login, navegação autenticada e logout com API simulada isolada',async({page})=>{
 await page.route('**/api/v1/p11/**',route=>route.fulfill({contentType:'application/json',body:route.request().url().includes('/health')?JSON.stringify({api:'available'}):'[]'}));
 await page.goto('http://127.0.0.1:5174');await page.getByText('Conexão da API').click();await page.getByLabel('URL da API').fill('http://127.0.0.1:5174');await page.getByRole('button',{name:'Salvar conexão local'}).click();
 await page.getByLabel('Usuário',{exact:true}).fill('isolated');await page.getByLabel('Senha',{exact:true}).fill('isolated');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByText('Consulta autenticada')).toBeVisible();await page.getByRole('link',{name:'Postes e telemetria',exact:true}).click();await expect(page.getByText('Sem registros nesta consulta.').first()).toBeVisible();
 await page.getByRole('button',{name:'Sair',exact:true}).click();await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
 expect(await page.evaluate(()=>JSON.stringify({...localStorage}))).not.toContain('isolated');
});
test('mobile: navegação não causa overflow global',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:5174');await page.getByRole('button',{name:'Abrir prévia visual'}).click();await page.getByRole('button',{name:'☰ Menu'}).click();await page.getByRole('link',{name:'Laboratório C01–C09'}).click();await expect(page.getByRole('heading',{name:'Laboratório C01–C09',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
for(const status of [401,403,503])test(`login com HTTP ${status} permanece fora da operação`,async({page})=>{
 await page.route('**/api/v1/p11/**',route=>route.fulfill({status,contentType:'application/json',body:'{}'}));
 await page.goto('http://127.0.0.1:5174');await page.getByText('Conexão da API').click();await page.getByLabel('URL da API').fill('http://127.0.0.1:5174');await page.getByRole('button',{name:'Salvar conexão local'}).click();await page.getByLabel('Usuário',{exact:true}).fill('test');await page.getByLabel('Senha',{exact:true}).fill('test');await page.getByRole('button',{name:'Entrar na central'}).click();await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByRole('heading',{name:'Acesso administrativo'})).toBeVisible();await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});
test('capturas login e mobile',async({page})=>{
 await page.goto('http://127.0.0.1:5174');await page.screenshot({path:'local-evidence/login-notebook.png',fullPage:true});await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Abrir prévia visual'}).click();await page.screenshot({path:'local-evidence/dashboard-mobile.png',fullPage:true});
});
test('resposta inválida após login é erro, não zero registros ou demonstração',async({page})=>{
 let invalid=false;
 await page.route('**/api/v1/p11/**',route=>route.fulfill({contentType:'application/json',body:route.request().url().includes('/health')?JSON.stringify({api:'available'}):invalid?'{}':'[]'}));
 await page.goto('http://127.0.0.1:5174');await page.getByText('Conexão da API').click();await page.getByLabel('URL da API').fill('http://127.0.0.1:5174');await page.getByRole('button',{name:'Salvar conexão local'}).click();await page.getByLabel('Usuário',{exact:true}).fill('test');await page.getByLabel('Senha',{exact:true}).fill('test');await page.getByRole('button',{name:'Entrar na central'}).click();await expect(page.getByText('Consulta autenticada')).toBeVisible();invalid=true;
 await page.getByRole('link',{name:'Postes e telemetria',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Resposta inválida'}).first()).toBeVisible();await expect(page.getByText('Sem registros nesta consulta.')).toHaveCount(0);await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});
test('login pode ser alcançado por teclado em notebook',async({page})=>{
 await page.goto('http://127.0.0.1:5174');await page.keyboard.press('Tab');await expect(page.getByLabel('Usuário',{exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByLabel('Senha',{exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Entrar na central'})).toBeFocused();
 const bounds=await page.getByRole('button',{name:'Entrar na central'}).boundingBox();expect(bounds!.y+bounds!.height).toBeLessThan(768);
});
