import {test,expect} from '@playwright/test';

const accessToken='T'.repeat(43);
const challenge={challenge_token:'C'.repeat(43),next_step:'enroll',expires_at:new Date(Date.now()+300_000).toISOString()};
const recoveryCodes=Array.from({length:10},(_,i)=>String(i).padStart(32,'a'));
const resetCodes=Array.from({length:10},(_,i)=>String(i+10).padStart(32,'b'));
const expires=()=>new Date(Date.now()+3_600_000).toISOString();
const fullSession=(withCodes=false)=>({access_token:accessToken,token_type:'Bearer',expires_at:expires(),idle_timeout_seconds:1800,username:'admin-operador',...(withCodes?{recovery_codes:recoveryCodes,password_reset_codes:resetCodes}:{})});
const sessionState=()=>({authenticated:true,username:'admin-operador',expires_at:expires(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false});

test('boas-vindas protege códigos em memória até confirmação explícita e segue ao dashboard',async({page})=>{
 const requestUrls:string[]=[];let firstAccess={status:'pending',password_reset_generation:1,password_reset_purpose:'password_reset',codes_issued:true,issued_at:expires(),completed_at:null};
 await page.route('**/api/v1/**',async route=>{
  const request=route.request();const url=new URL(request.url());requestUrls.push(url.href);const path=url.pathname;
  if(path.endsWith('/admin-auth/bootstrap'))return route.fulfill({json:challenge});
  if(path.endsWith('/admin-auth/mfa/enrollment/begin'))return route.fulfill({json:{manual_key:'JBSWY3DPEHPK3PXP',provisioning_uri:'otpauth://totp/fixture',qr_svg:'<svg viewBox="0 0 21 21"><path fill="#000" d="M0 0h1v1z"/></svg>',expires_at:expires()}});
  if(path.endsWith('/admin-auth/mfa/enrollment/confirm'))return route.fulfill({json:fullSession(true)});
  if(path.endsWith('/admin-auth/login'))return route.fulfill({json:fullSession(false)});
  if(path.endsWith('/admin-auth/session'))return route.fulfill({json:{...sessionState(),first_access:firstAccess}});
  if(path.endsWith('/admin-auth/first-access'))return route.fulfill({json:{username:'admin-operador',first_access:firstAccess}});
  if(path.endsWith('/admin-auth/first-access/confirm')){firstAccess={...firstAccess,status:'completed',completed_at:expires()};return route.fulfill({json:{username:'admin-operador',first_access:firstAccess}})}
  if(path.endsWith('/admin-auth/logout'))return route.fulfill({status:204});
  if(path.endsWith('/config/setup'))return route.fulfill({json:{version:0,document:null,state:'empty',operational:false,pending:[]}});
  if(path.endsWith('/config/current'))return route.fulfill({json:{desired_revision:0,effective_revision:null,operational:false,state:'not_configured'}});
  if(path.endsWith('/health'))return route.fulfill({json:{api:'available',database:'available',operational_controls:{cases:{status:'unknown',coverage:'unknown',known_active_count:null,sources:[],items:[]}}}});
  if(path.includes('/p11/'))return route.fulfill({json:[]});
  return route.fulfill({status:404,json:{error:{code:'NOT_FOUND'}}});
 });

 await page.goto('http://127.0.0.1:5175/');
 await page.getByRole('button',{name:'Primeira configuração'}).click();
 await page.getByLabel('Grant local de uso único').fill('G'.repeat(43));
 await page.getByLabel('Usuário',{exact:true}).fill('admin-operador');
 await page.getByLabel('Senha da conta administrativa').fill('isolated-bootstrap-password');
 await page.getByRole('button',{name:'Criar conta e configurar MFA'}).click();
 await page.getByRole('button',{name:'Mostrar QR e chave manual'}).click();
 await page.getByLabel('Código de 6 dígitos').fill('123456');
 await page.getByRole('button',{name:'Confirmar MFA'}).click();

 const modal=page.getByRole('dialog');
 await expect(page.locator('#content h1')).toHaveText('Dashboard');
 await expect(page.locator('#content')).toContainText('Instalação e configuração');
 await expect(page.locator('#content').getByText('Iniciar assistente')).toBeVisible();
 await expect(modal.getByRole('heading',{name:'Boas-vindas ao HarpiSense, admin-operador!'})).toBeVisible();
 await expect(modal.locator('#recovery-welcome-copy')).toHaveText('O HarpiSense monitora seus dispositivos IoT e ajuda você a investigar incidentes de segurança.');
 await expect(modal.getByRole('heading',{name:'Códigos para redefinir sua senha'})).toBeVisible();
 await expect(modal.locator('.password-reset-codes li')).toHaveCount(10);
 await expect(modal.getByRole('heading',{name:'Códigos de recuperação do autenticador'})).toBeVisible();
 await expect(modal.locator('.recovery-codes li')).toHaveCount(10);
 const continueButton=modal.getByRole('button',{name:'Continuar para o dashboard'});
 await expect(continueButton).toBeDisabled();
 await page.keyboard.press('Escape');
 await expect(modal).toBeVisible();
 await page.locator('.recovery-modal-backdrop').click({position:{x:4,y:4}});
 await expect(modal).toBeVisible();
 expect(await page.evaluate(async()=>({local:localStorage.length,session:sessionStorage.length,indexed:typeof indexedDB.databases==='function'?await indexedDB.databases():[]}))).toEqual({local:0,session:0,indexed:[]});
 for(const url of requestUrls){expect(recoveryCodes.some(code=>url.includes(code))).toBe(false);expect(resetCodes.some(code=>url.includes(code))).toBe(false)}
 await modal.getByRole('checkbox',{name:'Guardei meus códigos em um local seguro.'}).check();
 await expect(continueButton).toBeEnabled();
 await continueButton.click();
 await expect(page.getByRole('heading',{name:'Dashboard'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Instalação e configuração'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Iniciar assistente'})).toBeVisible();
 expect(requestUrls.some(url=>new URL(url).pathname.endsWith('/admin-auth/session'))).toBe(true);

 await page.getByRole('button',{name:'Sair',exact:true}).click();
 await page.getByLabel('Usuário',{exact:true}).fill('admin-operador');
 await page.getByLabel('Senha',{exact:true}).fill('isolated-login-password');
 await page.getByRole('button',{name:'Entrar na central'}).click();
 await expect(page.getByRole('heading',{name:'Dashboard'})).toBeVisible();
 await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('reload com primeiro acesso pendente permite reemitir os dois conjuntos e confirma a geração exibida',async({page})=>{
 const token='T'.repeat(43);let generation=1;let firstAccess={status:'pending',password_reset_generation:generation,password_reset_purpose:'password_reset',codes_issued:true,issued_at:expires(),completed_at:null};const bodies:{path:string;body:unknown;auth:string|undefined}[]=[];
 await page.route('**/api/v1/**',async route=>{
  const request=route.request();const url=new URL(request.url());const path=url.pathname;let body:unknown=null;try{body=request.postDataJSON()}catch{}bodies.push({path,body,auth:request.headers()['authorization']});
  if(path.endsWith('/admin-auth/login'))return route.fulfill({json:{access_token:token,token_type:'Bearer',expires_at:expires(),idle_timeout_seconds:1800,username:'admin-operador'}});
  if(path.endsWith('/admin-auth/session'))return route.fulfill({json:{...sessionState(),first_access:firstAccess}});
  if(path.endsWith('/admin-auth/first-access/codes')){generation++;firstAccess={status:'pending',password_reset_generation:generation,password_reset_purpose:'password_reset',codes_issued:true,issued_at:expires(),completed_at:null};return route.fulfill({json:{username:'admin-operador',recovery_codes:recoveryCodes,password_reset_codes:resetCodes,first_access:firstAccess}})}
  if(path.endsWith('/admin-auth/first-access/confirm')){expect(body).toEqual({password_reset_generation:generation});firstAccess={...firstAccess,status:'completed',completed_at:expires()};return route.fulfill({json:{username:'admin-operador',first_access:firstAccess}})}
  if(path.endsWith('/admin-auth/first-access'))return route.fulfill({json:{username:'admin-operador',first_access:firstAccess}});
  if(path.endsWith('/health'))return route.fulfill({json:{api:'available',database:'available',operational_controls:{cases:{status:'unknown',coverage:'unknown',known_active_count:null,sources:[],items:[]}}}});
  if(path.includes('/p11/'))return route.fulfill({json:[]});
  if(path.endsWith('/config/setup'))return route.fulfill({json:{version:0,document:null,state:'empty',operational:false,pending:[]}});
  if(path.endsWith('/config/current'))return route.fulfill({json:{desired_revision:0,effective_revision:null,operational:false,state:'not_configured'}});
  return route.fulfill({status:204});
 });
 await page.goto('http://127.0.0.1:5175/');await page.getByLabel('Usuário',{exact:true}).fill('admin-operador');await page.getByLabel('Senha',{exact:true}).fill('isolated-login-password');await page.getByRole('button',{name:'Entrar na central'}).click();
 const modal=page.getByRole('dialog');await expect(modal.getByRole('heading',{name:'Boas-vindas ao HarpiSense, admin-operador!'})).toBeVisible();
 await expect(modal.getByText(/códigos originais não podem ser recuperados/i)).toBeVisible();
 await modal.getByLabel('Senha atual').fill('isolated-current-password');await modal.getByLabel('Código TOTP atual').fill('654321');await modal.getByRole('button',{name:'Reemitir códigos'}).click();
 await expect(modal.locator('.recovery-codes li')).toHaveCount(10);await expect(modal.locator('.password-reset-codes li')).toHaveCount(10);
 await modal.getByRole('checkbox',{name:'Guardei meus códigos em um local seguro.'}).check();await modal.getByRole('button',{name:'Continuar para o dashboard'}).click();await expect(page.getByRole('heading',{name:'Dashboard'})).toBeVisible();
 const reissue=bodies.find(item=>item.path.endsWith('/admin-auth/first-access/codes'))!;expect(reissue.auth).toBe(`Bearer ${token}`);expect(Object.keys(reissue.body as object).sort()).toEqual(['code','current_password']);
 const ack=bodies.find(item=>item.path.endsWith('/admin-auth/first-access/confirm'))!;expect(ack.auth).toBe(`Bearer ${token}`);expect(ack.body).toEqual({password_reset_generation:2});
 expect(await page.evaluate(async()=>({local:localStorage.length,session:sessionStorage.length,indexed:await indexedDB.databases()}))).toEqual({local:0,session:0,indexed:[]});
});
