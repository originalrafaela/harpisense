import {test,expect} from './session-fixture';

const rows={
 incident:[{id:'inc-1',revision:2,source:'trusted-service',created_at:'2026-11-04T12:00:00Z',data:{incident_id:'inc-1',status:'SUSPECTED',scenario_id:'C01',scenario_group:'Low',evidence_refs:['ev-1'],risk:{score:34,level:'LOW'}}}],
 evidence:[{id:'ev-1',revision:1,source:'trusted-service',created_at:'2026-11-04T12:00:00Z',data:{evidence_id:'ev-1',observed_at:'2026-11-04T11:59:00Z'}}],
 decision:[{id:'dec-1',revision:1,source:'trusted-service',data:{decision_id:'dec-1',incident_id:'inc-1',status:'REQUEST_APPROVAL',scenario_group:'Low',valid_until:'2026-11-04T12:05:00Z',action:{action_type:'BLOCK_SOURCE_IP',target:{target_ref:'192.0.2.4',target_kind:'SOURCE_IP'},ttl_seconds:120}}}],
 approval:[{id:'ap-1',revision:1,source:'trusted-service',data:{approval_id:'ap-1',decision_id:'dec-1',approved_by:'admin-fixture',approved_at:'2026-11-04T12:01:00Z',expires_at:'2026-11-04T12:05:00Z'}}],
 execution:[{id:'ex-1',revision:1,source:'trusted-service',data:{execution_id:'ex-1',decision_id:'dec-1',status:'SIMULATED',requested_at:'2026-11-04T12:02:00Z',expires_at:'2026-11-04T12:04:00Z'}}],
 verification:[{id:'ver-1',revision:1,source:'trusted-service',data:{execution_id:'ex-1',status:'UNKNOWN_OUTCOME'}}],
};

async function enter(page:any){
 await page.goto('http://127.0.0.1:5174');
 await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');
 await page.getByLabel('Senha',{exact:true}).fill('fixture-password');
 await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();
}

test('incident, approval and defense views read projections and incident history without writes',async({page})=>{
 const calls:{method:string;url:string}[]=[];
 await page.route('**/api/v1/p11/**',async route=>{
  const request=route.request();const url=new URL(request.url());calls.push({method:request.method(),url:url.pathname});
  if(url.pathname.endsWith('/health'))return route.fulfill({json:{api:'available',projection_store:'available'}});
  const history=url.pathname.match(/\/api\/v1\/p11\/incident\/([^/]+)\/history$/);
  if(history)return route.fulfill({json:[{revision:1,source:'trusted-service',data:{incident_id:'inc-1',status:'OBSERVED'}},{revision:2,source:'trusted-service',data:{incident_id:'inc-1',status:'SUSPECTED'}}]});
  const kind=url.pathname.split('/').at(-1)||'';
  return route.fulfill({json:(rows as Record<string,unknown[]>)[kind]||[]});
 });
 await enter(page);
 await page.getByRole('link',{name:'Incidentes',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Detalhes do incidente · inc-1'})).toBeVisible();
 await expect(page.getByText('Revisão 1',{exact:true})).toBeVisible();
 await expect(page.getByText('Revisão 2',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Aprovações',exact:true}).click();
 await expect(page.getByText('dec-1',{exact:false}).first()).toBeVisible();
 await expect(page.getByRole('button',{name:'Aprovar decisão'})).toBeDisabled();
 await expect(page.getByText(/Nenhuma alteração operacional foi enviada/)).toBeVisible();
 await page.getByRole('link',{name:'Defesas',exact:true}).click();
 await expect(page.getByText('SIMULATED',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Executar defesa'})).toBeDisabled();
 expect(calls.some(call=>call.url.endsWith('/incident/inc-1/history'))).toBe(true);
 expect(calls.every(call=>call.method==='GET')).toBe(true);
});

test('consultation failures stay distinct from empty incident and approval results',async({page})=>{
 await page.route('**/api/v1/p11/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/health'))return route.fulfill({json:{api:'available'}});
  if(path.endsWith('/approval'))return route.fulfill({status:503,json:{detail:'projection unavailable'}});
  if(path.endsWith('/incident/inc-1/history'))return route.fulfill({status:503,json:{detail:'history unavailable'}});
  if(path.endsWith('/incident'))return route.fulfill({json:[{id:'inc-1',revision:1,source:'trusted-service',data:{incident_id:'inc-1',status:'OBSERVED'}}]});
  return route.fulfill({json:[]});
 });
 await enter(page);await page.getByRole('link',{name:'Incidentes',exact:true}).click();
 await expect(page.getByRole('alert').filter({hasText:'503'}).first()).toBeVisible();
 await expect(page.getByText('Nenhuma revisão histórica retornada')).toHaveCount(0);
 await page.getByRole('link',{name:'Aprovações',exact:true}).click();
 await expect(page.getByRole('alert').filter({hasText:'503'}).first()).toBeVisible();
 await expect(page.getByText('A API não retornou aprovações nesta consulta.')).toHaveCount(0);
});

test('first access and MFA state says unavailable instead of sending guessed routes',async({page})=>{
 const requests:string[]=[];page.on('request',request=>{if(request.url().includes('/api/'))requests.push(new URL(request.url()).pathname)});
 await page.goto('http://127.0.0.1:5174');
 await page.getByRole('button',{name:'Primeiro acesso e segurança da conta'}).click();
 await expect(page.getByText(/backend entregue oferece login por senha e sessão/)).toBeVisible();
 await expect(page.getByText(/Cadastro e confirmação TOTP/)).toBeVisible();
 expect(requests).toEqual([]);
});
