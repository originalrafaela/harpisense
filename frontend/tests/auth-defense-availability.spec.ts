import {test,expect} from '@playwright/test';

test('primeiro acesso, recuperação e MFA ausentes não coletam fatores nem simulam sucesso',async({page})=>{
 const requests:string[]=[];
 page.on('request',request=>{if(request.url().includes('/api/'))requests.push(request.url())});
 await page.goto('http://127.0.0.1:5174');
 for(const name of ['Primeiro acesso e segurança da conta','Esqueci minha senha','Verificar MFA']){
  await page.getByRole('button',{name,exact:true}).click();
  const panel=page.getByRole('region',{name:'Disponibilidade da instalação e MFA'});
  // section has an accessible name and exposes the missing HTTP contract.
  await expect(panel).toContainText('Não integrado');
  await expect(panel.locator('input')).toHaveCount(0);
  await expect(panel).toContainText('Nenhuma conta foi criada');
  await panel.getByRole('button',{name:'Fechar',exact:true}).click();
 }
 expect(requests).toEqual([]);
});
