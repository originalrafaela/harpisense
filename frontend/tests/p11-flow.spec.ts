import {test, expect} from './session-fixture';
import type {Page} from '@playwright/test';

// Isolated browser fixtures based on the documented P11/PostgreSQL shape, never a VM receipt.
const record = {
  id: 'poste2-fe153b85241ac04a091479a7a0ca647c87d94029a60aa769f0370298a1281840', revision: 1,
  source: 'trusted-service', created_at: '2026-10-18T01:14:12.498058-03:00',
  data: {device_id: 'poste2', temperatura: 28.4, tipo: 'teste_systemd'},
};
async function enter(page: Page, password = 'contract-fixture') {
  await page.goto('http://127.0.0.1:5174');
  await page.getByLabel('Usuário', {exact: true}).fill('contract-operator');
  await page.getByLabel('Senha', {exact: true}).fill(password);
  await page.getByRole('button', {name: 'Entrar na central'}).click();
}

test('sessão administrativa → telemetria → mesmo registro exibido, sem persistir credenciais (isolado)', async ({page}) => {
  const paths: string[] = []; const logs: string[] = [];
  page.on('console', message => logs.push(message.text()));
  await page.route('**/p11-api/api/v1/p11/**', route => {
    const url = new URL(route.request().url()); paths.push(url.pathname);
    expect(url.search).not.toContain('contract-fixture');
    if (route.request().headers().authorization !== 'Bearer ' + 'a'.repeat(43))
      return route.fulfill({status: 401, body: '{"detail":"Unauthorized"}'});
    if (url.pathname.endsWith('/health')) return route.fulfill({contentType: 'application/json', body: JSON.stringify({api: 'available', projection_store: 'available', broker: 'unknown'})});
    if (url.pathname.endsWith('/telemetry')) return route.fulfill({contentType: 'application/json', body: JSON.stringify([record])});
    return route.fulfill({status: 404, contentType: 'application/json', body: '{}'});
  });
  await enter(page);
  const card = page.getByRole('article', {name: 'Telemetria de poste2'});
  await expect(card).toBeVisible();
  for (const value of [record.id, record.created_at, 'trusted-service', '28.4', 'teste_systemd']) await expect(card).toContainText(value);
  await expect(card).toContainText('unidade não informada');
  await expect(card).toContainText('Não informada');
  expect(paths).toContain('/p11-api/api/v1/p11/health');expect(paths).toContain('/p11-api/api/v1/p11/telemetry');
  const stored = await page.evaluate(() => JSON.stringify({local: {...localStorage}, session: {...sessionStorage}, cookie: document.cookie}));
  expect(stored).not.toContain('contract-fixture');expect(stored).not.toContain('contract-operator');
  expect(logs.join(' ')).not.toContain('contract-fixture');expect(logs.join(' ')).not.toContain('Basic ');
  await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
  await page.evaluate(() => {
    const label = document.createElement('div'); label.textContent = 'TESTE ISOLADO — respostas de contrato, sem conexão à VM';
    label.style.cssText = 'background:#653300;color:white;padding:14px;text-align:center;font-weight:bold';
    document.body.prepend(label);
  });
  await page.screenshot({path: 'local-evidence/p11-contract-dashboard-isolated.png', fullPage: true});
  await page.getByRole('button', {name: 'Sair', exact: true}).click();
  await expect(page.getByLabel('Senha', {exact: true})).toHaveValue('');
});

test('consulta vazia não inventa dispositivo ou medição (isolado)', async ({page}) => {
  await page.route('**/p11-api/api/v1/p11/**', route => route.fulfill({contentType: 'application/json', body: route.request().url().endsWith('/health') ? '{"api":"available"}' : '[]'}));
  await enter(page);await expect(page.getByText('Consulta autenticada')).toBeVisible();
  await expect(page.getByText('Sem registros nesta consulta.').first()).toBeVisible();
  await expect(page.getByRole('article', {name: 'Telemetria de poste2'})).toHaveCount(0);
});

test('credencial inválida e rede indisponível não abrem operação nem demonstração (isolado)', async ({page}) => {
  await page.route('**/api/v1/admin-auth/login', route => route.fulfill({status:401,json:{error:{code:'INVALID_CREDENTIALS'}}}));
  await enter(page, 'invalid-fixture');await expect(page.getByRole('alert')).toContainText('Credenciais inválidas');
  await page.unroute('**/api/v1/admin-auth/login');
  await page.route('**/api/v1/admin-auth/login', route => route.abort('connectionrefused'));
  await page.getByLabel('Senha',{exact:true}).fill('invalid-fixture');
  await page.getByRole('button', {name: 'Entrar na central'}).click();
  await expect(page.getByRole('alert')).toContainText('Falha de rede/configuração');
  await expect(page.getByText('Consulta autenticada')).toHaveCount(0);
  await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});
