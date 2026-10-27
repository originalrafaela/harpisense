import {test,expect} from '@playwright/test';

test('composição local real: P11/PostgreSQL, pendência desconhecida e auditoria persistida',async({page})=>{
 test.skip(process.env.HARPISENSE_COMPOSITION_TEST!=='1','Requer composição local isolada; nunca apontar para VM.');
 const user=process.env.HARPISENSE_TEST_ADMIN_USER;const password=process.env.HARPISENSE_TEST_ADMIN_PASSWORD;
 if(!user||!password)throw Error('Defina as credenciais da composição de teste no ambiente do runner.');
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill(user);await page.getByLabel('Senha',{exact:true}).fill(password);await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByText('Consulta autenticada')).toBeVisible();await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Estado operacional efetivo'})).toBeVisible();await expect(page.getByText('M1',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'↻ Atualizar consulta'})).toBeEnabled();await page.screenshot({path:'local-evidence/delivery-dashboard-postgresql-isolated.png',fullPage:true});
 await page.getByRole('link',{name:'Configurações',exact:true}).click();await expect(page.getByText('Pendências não verificadas.',{exact:false})).toBeVisible();
 await page.getByLabel('Justificativa da alteração').fill('Validação isolada da recusa por fila não integrada');await page.getByRole('button',{name:'Solicitar M3',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Estado das pendências operacionais não verificado.');await expect(page.getByText('Servidor confirmou M3',{exact:false})).toHaveCount(0);
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'local-evidence/delivery-settings-postgresql-isolated.png',fullPage:true});
 await page.getByRole('link',{name:'Logs e auditoria',exact:true}).click();await expect(page.getByText('CONTROL_CHANGE_REJECTED',{exact:true}).first()).toBeVisible();
 await page.getByRole('link',{name:'Anomalias',exact:true}).click();await expect(page.getByRole('button',{name:'Registrar avaliação'})).toBeDisabled();await expect(page.getByText('Sem registros nesta consulta.').first()).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'local-evidence/delivery-anomalies-mobile-isolated.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
