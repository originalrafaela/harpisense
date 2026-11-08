import {test,expect} from '@playwright/test';

test('navega RF/IF, ausência, falha de API e troca rápida de incidente sem cruzar resultados (fixture)',async({page})=>{
 await page.setViewportSize({width:1280,height:900});await page.goto('/tests/model-analysis-preview.html');
 await expect(page.getByText('Ativo RF')).toBeVisible();
 await expect(page.getByText('Probabilidade calibrada · pontuação final')).toBeVisible();
 await page.getByRole('tab',{name:/Isolation Forest/}).click();
 await expect(page.getByText('Ativo IF')).toBeVisible();
 await expect(page.getByText('Score de anomalia (IF)')).toBeVisible();
 await expect(page.locator('.model-analysis-scores')).not.toContainText('%');
 const select=page.getByLabel('Incidente da análise do modelo');
 await select.selectOption('incident-empty');await expect(page.getByText('Explicação não disponível para esta observação.')).toBeVisible();
 await select.selectOption('incident-error');await expect(page.getByText('Falha ao consultar a API de análise do modelo.')).toBeVisible();
 await select.selectOption('incident-slow');await select.selectOption('incident-fast');
 await expect(page.getByText('Ativo Rápido')).toBeVisible();
 await page.waitForTimeout(400);await expect(page.getByText('Ativo Rápido')).toBeVisible();await expect(page.getByText('Ativo Lento')).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('heading',{name:'Análise do modelo (XAI/SHAP)'})).toBeVisible();
 const tabs=page.getByRole('tablist');if(await tabs.count())await expect(tabs).toBeVisible();
 const width=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));expect(width.scroll).toBeLessThanOrEqual(width.client);
 await page.reload();await page.keyboard.press('Tab');await expect(page.getByLabel('Incidente da análise do modelo')).toBeFocused();
});
