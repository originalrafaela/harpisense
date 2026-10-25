import {test, expect, type Page} from '@playwright/test';

const projection = (id: string, data: Record<string, unknown>, created_at = '2026-10-18T12:00:00Z') => ({id, revision: 1, source: 'trusted-service', created_at, data});
async function login(page: Page, health: Record<string, unknown> = {}, records: Record<string, unknown[]> = {}, bitnetStatus = 200, explanationStatus = 200) {
  await page.route('**/api/v1/p11/**', async route => {
    const url = new URL(route.request().url());
    const kind = url.pathname.split('/')[4];
    if (url.pathname.endsWith('/history')) {
      return route.fulfill({contentType: 'application/json', body: JSON.stringify([
        {revision: 1, source: 'trusted-service', data: {incident_id: 'new', source: 'deterministic_fallback', text: 'Revisão anterior isolada'}},
        {revision: 2, source: 'trusted-service', data: {incident_id: 'foreign', text: 'Não pode aparecer neste histórico'}},
      ])});
    }
    if (url.pathname.includes('/explain/')) {
      return route.fulfill({status:explanationStatus,contentType:'application/json',body:JSON.stringify(records.explanation || {})});
    }
    await route.fulfill({status: kind === 'bitnet' ? bitnetStatus : 200, contentType: 'application/json', body: JSON.stringify(kind === 'health' ? {api:'available',...health} : records[kind] || [])});
  });
  await page.goto('http://127.0.0.1:5174');
  await page.getByText('Conexão da API').click();
  await page.getByLabel('URL da API').fill('http://127.0.0.1:5174');
  await page.getByRole('button', {name: 'Salvar conexão local'}).click();
  await page.getByLabel('Usuário', {exact: true}).fill('isolated');
  await page.getByLabel('Senha', {exact: true}).fill('isolated');
  await page.getByRole('button', {name: 'Entrar na central'}).click();
  await expect(page.getByText('Consulta autenticada')).toBeVisible();
  await expect(page.getByRole('button', {name: 'M1 — Supervisionado', exact: true})).toBeVisible();
}

test('demonstração alterna controles independentes sem nenhuma chamada operacional', async ({page}) => {
  const calls: string[] = [];
  page.on('request', request => {if (request.url().includes('/api/')) calls.push(request.url())});
  await page.goto('http://127.0.0.1:5174');
  await page.getByRole('button', {name: 'Abrir prévia visual'}).click();
  for (const label of ['M1 — Supervisionado', 'M2 — Autonomia parcial', 'M3 — Autônomo']) {
    await page.getByRole('button', {name: label, exact: true}).click();
    await expect(page.getByRole('button', {name: label, exact: true})).toHaveAttribute('aria-pressed', 'true');
  }
  await page.getByRole('combobox', {name: 'Modo IDS / SIMULATION / REAL', exact: true}).selectOption('REAL');
  await page.getByRole('combobox', {name: 'execution_enabled', exact: true}).selectOption('false');
  await expect(page.getByRole('button', {name: 'M3 — Autônomo', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('combobox', {name: 'Modo IDS / SIMULATION / REAL', exact: true})).toHaveValue('REAL');
  await expect(page.getByRole('combobox', {name: 'execution_enabled', exact: true})).toHaveValue('false');
  await page.getByRole('button', {name: 'Detalhes da explicação', exact: true}).click();
  await expect(page.getByRole('region', {name: 'Detalhes da explicação'})).toContainText('inc-demo');
  await page.getByRole('button', {name: 'Histórico da explicação', exact: true}).click();
  await expect(page.getByRole('region', {name: 'Histórico da explicação'})).toContainText('Explicação determinística');
  await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toBeVisible();
  await page.getByRole('link', {name: 'Configurações', exact: true}).click();
  await expect(page.getByRole('button', {name: 'M3 — Autônomo', exact: true})).toHaveAttribute('aria-pressed', 'true');
  expect(calls).toEqual([]);
});

test('operação desconhecida mantém botões visíveis e sem ativo; não inventa explicações', async ({page}) => {
  await login(page);
  for (const label of ['M1 — Supervisionado', 'M2 — Autonomia parcial', 'M3 — Autônomo']) {
    const button = page.getByRole('button', {name: label, exact: true});
    await expect(button).toBeDisabled(); await expect(button).toHaveAttribute('aria-pressed', 'false');
  }
  await expect(page.getByRole('combobox', {name: 'Modo IDS / SIMULATION / REAL', exact: true})).toHaveValue('');
  await expect(page.getByRole('combobox', {name: 'execution_enabled', exact: true})).toHaveValue('');
  await expect(page.getByText('Alteração ainda não integrada.', {exact: false})).toBeVisible();
  await expect(page.getByText('Sem explicação disponível.', {exact: false})).toBeVisible();
});

test('valores explícitos do backend são apresentados sem habilitar mudanças', async ({page}) => {
  const writes: string[] = [];
  page.on('request', request => {if (request.url().includes('/api/') && request.method() !== 'GET') writes.push(request.method())});
  await login(page, {operational_controls: {operation: 'IDS', autonomy_mode: 2, execution_enabled: false}});
  await expect(page.getByRole('button', {name: 'M2 — Autonomia parcial', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', {name: 'M2 — Autonomia parcial', exact: true})).toBeDisabled();
  await expect(page.getByRole('combobox', {name: 'Modo IDS / SIMULATION / REAL', exact: true})).toHaveValue('IDS');
  await expect(page.getByRole('combobox', {name: 'execution_enabled', exact: true})).toHaveValue('false');
  expect(writes).toEqual([]);
});

test('HarpIA seleciona incidente mais recente, vincula texto e consulta histórico', async ({page}) => {
  await login(page, {}, {
    incident: [projection('old', {incident_id: 'old'}, '2026-10-17T12:00:00Z'), projection('new', {incident_id: 'new'})],
    bitnet: [projection('ex-new', {incident_id: 'new', source: 'deterministic_fallback', text: 'Explicação isolada do incidente recente'}), projection('ex-old', {incident_id: 'old', source: 'bitnet_unverified_text', text: 'Texto isolado do incidente anterior'})],
  });
  await expect(page.getByRole('combobox', {name: 'Incidente selecionado', exact: true})).toHaveValue('new');
  await expect(page.getByText('Explicação isolada do incidente recente', {exact: true})).toBeVisible();
  await expect(page.getByText('Explicação determinística', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Histórico da explicação', exact: true}).click();
  await expect(page.getByRole('region', {name: 'Histórico da explicação'})).toContainText('Revisão anterior isolada');
  await expect(page.getByText('Não pode aparecer neste histórico')).toHaveCount(0);
  await page.getByRole('combobox', {name: 'Incidente selecionado', exact: true}).selectOption('old');
  await expect(page.getByText('Texto isolado do incidente anterior', {exact: true})).toBeVisible();
  await expect(page.getByText('Explicação isolada do incidente recente', {exact: true})).toHaveCount(0);
});

test('falha da API de explicações identifica serviço indisponível', async ({page}) => {
  await login(page, {}, {incident: [projection('new', {incident_id: 'new'})]}, 503);
  await expect(page.getByText('Serviço indisponível.', {exact: false})).toBeVisible();
  await expect(page.getByText('Sem explicação disponível para o incidente new.', {exact: false})).toBeVisible();
  await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});

test('HarpIA mostra revisão desatualizada e horário; health disponível não libera geração',async({page})=>{
  const requests:string[]=[];
  page.on('request',request=>{if(request.url().includes('/api/'))requests.push(request.url())});
  await login(page,{bitnet:'available'},{
    incident:[{...projection('new',{incident_id:'new'}),revision:3}],
    bitnet:[projection('exp',{incident_id:'new',revision:2,source:'bitnet_unverified_text',text:'Explicação sintética antiga'})]
  });
  await expect(page.getByText('Explicação sintética antiga',{exact:true})).toBeVisible();
  await expect(page.getByText('Explicação desatualizada:',{exact:false})).toBeVisible();
  await expect(page.getByText('Horário da explicação:',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Gerar explicação',exact:true})).toBeDisabled();
  expect(requests.every(url=>!url.includes('/explain/')&&!url.includes(':8091')&&!url.includes(':8092'))).toBe(true);
  await page.screenshot({path:'local-evidence/harpia-stale.png',fullPage:true});
});

test('consulta registrada exibe carregando e erro sem usar fallback fictício',async({page})=>{
  await login(page,{}, {incident:[projection('new',{incident_id:'new'})]});
  const button=page.getByRole('button',{name:'Consultar explicações registradas',exact:true});
  await expect(button).toBeVisible();
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve});
  await page.route('**/api/v1/p11/bitnet?**',async route=>{await gate;await route.fulfill({status:503,body:'{}'})});
  await button.click();
  await expect(page.getByText('Carregando explicações…',{exact:true})).toBeVisible();
  release();
  await expect(page.getByText('Erro ao consultar explicações:',{exact:false})).toBeVisible();
  await expect(page.getByText('Sem explicação disponível para o incidente new.',{exact:false})).toBeVisible();
  await expect(page.getByText('Dados de demonstração — sem conexão operacional')).toHaveCount(0);
});

test('resposta atrasada não exibe texto de incidente anteriormente selecionado',async({page})=>{
  await login(page,{}, {incident:[projection('new',{incident_id:'new'}),projection('old',{incident_id:'old'})],
    bitnet:[projection('old-exp',{incident_id:'old',revision:1,source:'deterministic_fallback',text:'Texto sintético do antigo'})]});
  const button=page.getByRole('button',{name:'Consultar explicações registradas',exact:true});
  await expect(button).toBeVisible();
  let release!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve});
  await page.route('**/api/v1/p11/bitnet?**',async route=>{await gate;await route.fulfill({json:[projection('late',{incident_id:'new',text:'Resposta atrasada nova'})]})});
  await button.click();
  await expect(page.getByText('Carregando explicações…',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Incidente selecionado',exact:true}).selectOption('old');
  release();
  await expect(page.getByText('Texto sintético do antigo',{exact:true})).toBeVisible();
  await expect(page.getByText('Resposta atrasada nova',{exact:true})).toHaveCount(0);
});

test('API determinística vincula revisão, origem, horário e renderiza texto como conteúdo',async({page})=>{
  const xss='<img src=x onerror="window.pwned=true">';
  await login(page,{harpia:{mode:'deterministic_only',contract_version:1,generation_enabled:false,model:'bitnet'}},
    {incident:[projection('synthetic-ui',{incident_id:'synthetic-ui',revision:4})],explanation:{
      source:'deterministic_fallback',source_label:'Explicação determinística',incident_id:'synthetic-ui',revision:3,
      generated_at:'2026-10-25T13:00:00Z',persisted:false,text:`Explicação determinística sintética ${xss}`,
    }});
  await page.getByRole('button',{name:'Consultar explicação determinística',exact:true}).click();
  await expect(page.getByText('Explicação determinística',{exact:true})).toBeVisible();
  await expect(page.getByText('Explicação desatualizada:',{exact:false})).toBeVisible();
  await expect(page.getByText('Horário da explicação:',{exact:false})).toBeVisible();
  await expect(page.locator('.explanation-text')).toContainText(xss);
  await expect(page.locator('.explanation-text img')).toHaveCount(0);
  await expect(page.getByText('Explicação calculada nesta consulta',{exact:false})).toBeVisible();
});

test('API autenticada informa não autorizado sem substituir por fixture',async({page})=>{
  await login(page,{harpia:{mode:'deterministic_only',contract_version:1,generation_enabled:false}},
    {incident:[projection('synthetic-auth',{incident_id:'synthetic-auth',revision:1})]},200,401);
  await page.getByRole('button',{name:'Consultar explicação determinística',exact:true}).click();
  await expect(page.getByText('Erro ao consultar explicações:',{exact:false})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'Credenciais inválidas ou sessão não autorizada.'})).toBeVisible();
});

test('indisponibilidade da rota determinística aparece como erro sem fallback fictício',async({page})=>{
  await login(page,{harpia:{mode:'deterministic_only',contract_version:1,generation_enabled:false}},
    {incident:[projection('synthetic-offline',{incident_id:'synthetic-offline',revision:1})]},200,503);
  await page.getByRole('button',{name:'Consultar explicação determinística',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'API indisponível (HTTP 503)'})).toBeVisible();
  await expect(page.getByText('Sem explicação disponível para o incidente synthetic-offline.',{exact:false})).toBeVisible();
});
