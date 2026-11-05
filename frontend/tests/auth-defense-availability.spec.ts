import {test,expect} from '@playwright/test';

test('login não chama a API até o administrador iniciar um fluxo explicitamente',async({page})=>{
 const requests:string[]=[];page.on('request',request=>{if(request.url().includes('/api/'))requests.push(request.url())});
 await page.goto('http://127.0.0.1:5174');
 await expect(page.getByRole('heading',{name:'Acesso administrativo'})).toBeVisible();
 await page.getByRole('button',{name:'Primeira configuração'}).click();
 await expect(page.getByText(/grant temporário entregue localmente pelo operador/)).toBeVisible();
 await expect(page.getByLabel('Grant local de uso único')).toBeVisible();
 expect(requests).toEqual([]);
});

test('recuperação por e-mail não é oferecida nem tenta enviar mensagens',async({page})=>{
 const requests:string[]=[];page.on('request',request=>{if(request.url().includes('/api/'))requests.push(request.url())});
 await page.goto('http://127.0.0.1:5174');
 await expect(page.getByText(/Recuperação por e-mail não está integrada/).first()).toBeVisible();
 await expect(page.getByRole('button',{name:/recuperar por e-mail/i})).toHaveCount(0);
 expect(requests).toEqual([]);
});
