import {test,expect} from './session-fixture';

const challenge=(next_step:'login'|'enroll',milliseconds=300_000)=>({challenge_token:'c'.repeat(43),next_step,expires_at:new Date(Date.now()+milliseconds).toISOString()});
const token='t'.repeat(43);const key='JBSWY3DPEHPK3PXP';const svg='<svg viewBox="0 0 21 21"><path fill="#000000" d="M0 0h1v1z"/></svg>';
const codes=Array.from({length:10},(_,i)=>String(i).padStart(32,'a'));
const session=(enabled:boolean)=>({authenticated:true,username:'fixture-owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:enabled,mfa_enrollment_available:true,email_recovery_available:false});
const sessionResponse=(enabled:boolean)=>({access_token:token,token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-owner',recovery_codes:codes});

async function isolateOperationalReads(page:any){
 await page.route('**/api/v1/p11/**',route=>route.fulfill({json:[]}));
 await page.route('**/api/v1/security/**',route=>route.fulfill({status:503,json:{error:{code:'AUTH_UNAVAILABLE'}}}));
 await page.route('**/api/v1/config/**',route=>route.fulfill({status:404,json:{detail:'Fixture without config API'}}));
}

test('primeiro cadastro → TOTP → códigos de recuperação → sessão autorizada → logout',async({page})=>{
 const calls:{path:string;method:string;auth:string|undefined;url:string;body:any}[]=[];
 await isolateOperationalReads(page);
 await page.route('**/api/v1/admin-auth/**',async route=>{
  const req=route.request();const url=new URL(req.url());let body:any={};try{body=req.postDataJSON()}catch{}calls.push({path:url.pathname,method:req.method(),auth:req.headers()['authorization'],url:req.url(),body});
  if(url.pathname.endsWith('/bootstrap'))return route.fulfill({json:challenge('enroll')});
  if(url.pathname.endsWith('/enrollment/begin'))return route.fulfill({json:{manual_key:key,provisioning_uri:`otpauth://totp/HarpiSense:fixture?secret=${key}`,qr_svg:svg,expires_at:new Date(Date.now()+300000).toISOString()}});
  if(url.pathname.endsWith('/enrollment/confirm'))return route.fulfill({json:sessionResponse(true)});
  if(url.pathname.endsWith('/session'))return route.fulfill({json:session(true)});
  if(url.pathname.endsWith('/logout'))return route.fulfill({status:204});
  return route.fulfill({status:404,json:{error:{code:'NOT_FOUND'}}});
 });
 await page.goto('http://127.0.0.1:5174');await page.getByRole('button',{name:'Primeira configuração'}).click();
 await page.getByLabel('Grant local de uso único').fill('g'.repeat(43));await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');await page.getByLabel('Senha da conta administrativa').fill('isolated-new-password');
 await page.getByRole('button',{name:'Criar conta e configurar MFA'}).click();
 await expect(page.getByRole('heading',{name:'Configurar Microsoft Authenticator'})).toBeVisible();await page.getByRole('button',{name:'Mostrar QR e chave manual'}).click();
 await expect(page.getByRole('img',{name:'QR code TOTP emitido pelo backend'})).toBeVisible();await expect(page.getByLabel('Chave manual')).toHaveValue(key);
 await page.getByLabel('Código de 6 dígitos').fill('123456');await page.getByRole('button',{name:'Confirmar MFA'}).click();
 await expect(page.getByRole('heading',{name:'Boas-vindas ao HarpiSense, fixture-owner!'})).toBeVisible();await expect(page.locator('.recovery-codes li')).toHaveCount(10);
 expect(await page.evaluate(()=>localStorage.length)).toBe(0);
 expect(calls.filter(x=>x.path.endsWith('/bootstrap')||x.path.endsWith('/enrollment/begin')||x.path.endsWith('/enrollment/confirm')).every(x=>!x.auth)).toBe(true);
 expect(calls.every(x=>!x.url.includes(key)&&!x.url.includes(codes[0])&&!x.url.includes('g'.repeat(43)))).toBe(true);
 await page.getByLabel('Guardei meus códigos em um local seguro.').check();await page.getByRole('button',{name:'Continuar para o dashboard'}).click();
 await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Sair',exact:true}).click();await expect(page.getByRole('heading',{name:'Acesso administrativo'})).toBeVisible();
 expect(calls.some(x=>x.path.endsWith('/admin-auth/logout')&&x.method==='POST'&&x.auth===`Bearer ${token}`)).toBe(true);
});

test('login pede TOTP, código inválido não abre sessão, e o desafio pode expirar',async({page})=>{
 const calls:string[]=[];await isolateOperationalReads(page);
 await page.route('**/api/v1/admin-auth/**',async route=>{
  const path=new URL(route.request().url()).pathname;calls.push(path);
  if(path.endsWith('/login'))return route.fulfill({json:challenge('login')});
  if(path.endsWith('/mfa/verify')&&calls.filter(x=>x.endsWith('/mfa/verify')).length===1)return route.fulfill({status:401,json:{error:{code:'FACTOR_INVALID'}}});
  if(path.endsWith('/mfa/verify'))return route.fulfill({json:sessionResponse(true)});
  if(path.endsWith('/session'))return route.fulfill({json:session(true)});
  return route.fulfill({status:204});
 });
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('heading',{name:'Verificação em duas etapas'})).toBeVisible();await expect(page.getByRole('button',{name:'Sair',exact:true})).toHaveCount(0);
 await page.getByLabel('Código do aplicativo autenticador').fill('000000');await page.getByRole('button',{name:'Verificar código'}).click();await expect(page.getByRole('alert')).toContainText('Código de verificação inválido');await expect(page.getByRole('button',{name:'Sair',exact:true})).toHaveCount(0);
 await page.getByLabel('Código do aplicativo autenticador').fill('123456');await page.getByRole('button',{name:'Verificar código'}).click();await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();
 expect(calls.filter(path=>path.endsWith('/mfa/verify'))).toHaveLength(2);
});

test('desafio que expira na tela é descartado sem validar código nem abrir sessão',async({page})=>{
 const calls:string[]=[];await isolateOperationalReads(page);
 await page.route('**/api/v1/admin-auth/**',async route=>{const path=new URL(route.request().url()).pathname;calls.push(path);if(path.endsWith('/login'))return route.fulfill({json:challenge('login',100)});return route.fulfill({status:401,json:{error:{code:'CHALLENGE_INVALID'}}})});
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('heading',{name:'Verificação em duas etapas'})).toBeVisible();await page.waitForTimeout(150);await page.getByLabel('Código do aplicativo autenticador').fill('123456');await page.getByRole('button',{name:'Verificar código'}).click();
 await expect(page.getByRole('alert')).toContainText('desafio expirou');await expect(page.getByRole('button',{name:'Sair',exact:true})).toHaveCount(0);expect(calls.some(path=>path.endsWith('/mfa/verify'))).toBe(false);
});

test('código de recuperação retorna apenas enrollment e requer novo cadastro MFA',async({page})=>{
 const calls:string[]=[];await isolateOperationalReads(page);
 await page.route('**/api/v1/admin-auth/**',async route=>{
  const path=new URL(route.request().url()).pathname;calls.push(path);
  if(path.endsWith('/login'))return route.fulfill({json:challenge('login')});
  if(path.endsWith('/mfa/recover'))return route.fulfill({json:challenge('enroll')});
  if(path.endsWith('/enrollment/begin'))return route.fulfill({json:{manual_key:key,provisioning_uri:`otpauth://totp/HarpiSense:fixture?secret=${key}`,qr_svg:svg,expires_at:new Date(Date.now()+300000).toISOString()}});
  if(path.endsWith('/enrollment/confirm'))return route.fulfill({json:sessionResponse(true)});
  if(path.endsWith('/session'))return route.fulfill({json:session(true)});
  return route.fulfill({status:204});
 });
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await page.getByRole('button',{name:'Usar código de recuperação'}).click();await page.getByLabel('Código de recuperação').fill('R'.repeat(32));await page.getByRole('button',{name:'Usar código de recuperação'}).click();
 await expect(page.getByRole('heading',{name:'Configurar Microsoft Authenticator'})).toBeVisible();await expect(page.getByRole('button',{name:'Sair',exact:true})).toHaveCount(0);
 expect(calls.some(path=>path.endsWith('/mfa/recover'))).toBe(true);expect(calls.some(path=>path.endsWith('/admin-auth/session'))).toBe(false);
});

test('adesão de conta existente só troca sessão após confirmação e não bloqueia na senha incorreta',async({page})=>{
 const calls:{path:string;auth:string|undefined;body:any}[]=[];let authorizationAttempts=0;let enabled=false;await isolateOperationalReads(page);
 await page.route('**/api/v1/admin-auth/**',async route=>{
  const request=route.request();const path=new URL(request.url()).pathname;let body:any={};try{body=request.postDataJSON()}catch{}calls.push({path,auth:request.headers()['authorization'],body});
  if(path.endsWith('/login'))return route.fulfill({json:{access_token:token,token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-owner'}});
  if(path.endsWith('/session'))return route.fulfill({json:session(enabled)});
  if(path.endsWith('/enrollment/authorize')){authorizationAttempts++;if(authorizationAttempts===1)return route.fulfill({status:403,json:{error:{code:'REAUTHENTICATION_REQUIRED'}}});return route.fulfill({json:challenge('enroll')});}
  if(path.endsWith('/enrollment/begin'))return route.fulfill({json:{manual_key:key,provisioning_uri:`otpauth://totp/HarpiSense:fixture?secret=${key}`,qr_svg:svg,expires_at:new Date(Date.now()+300000).toISOString()}});
  if(path.endsWith('/enrollment/confirm')){enabled=true;return route.fulfill({json:sessionResponse(true)});}
  return route.fulfill({status:204});
 });
 await page.goto('http://127.0.0.1:5174');await page.getByLabel('Usuário',{exact:true}).fill('fixture-owner');await page.getByLabel('Senha',{exact:true}).fill('isolated-current-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();await page.getByRole('link',{name:/Configurações/}).click();
 await expect(page.getByRole('button',{name:'Ativar aplicativo autenticador'})).toBeVisible();
 await page.getByLabel('Senha atual').fill('wrong-password');await page.getByRole('button',{name:'Ativar aplicativo autenticador'}).click();await expect(page.getByRole('alert').filter({hasText:'conta existente permanece ativa'})).toBeVisible();await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();
 await page.getByLabel('Senha atual').fill('isolated-current-password');await page.getByRole('button',{name:'Ativar aplicativo autenticador'}).click();await page.getByRole('button',{name:'Mostrar QR e chave manual'}).click();await page.getByLabel('Código de 6 dígitos').fill('123456');await page.getByRole('button',{name:'Confirmar MFA'}).click();
 await expect(page.getByRole('heading',{name:'Guarde seus códigos de segurança'})).toBeVisible();expect(calls.find(x=>x.path.endsWith('/enrollment/authorize'))?.auth).toBe(`Bearer ${token}`);
 await page.getByLabel('Guardei meus códigos em um local seguro.').check();await page.getByRole('button',{name:'Continuar para o dashboard'}).click();await expect(page.getByText(/MFA: habilitado/)).toBeVisible();
});
