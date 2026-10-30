import {test,expect,type Page} from '@playwright/test';

const token='s'.repeat(43);
const password='isolated administrator password';
async function fixture(page:Page,{invalid=false,expired=false,logoutFailure=false}={}){
 const calls:{path:string;method:string;authorization?:string}[]=[];
 await page.route('**/p11-api/api/**',async route=>{
  const request=route.request();const path=new URL(request.url()).pathname;
  calls.push({path,method:request.method(),authorization:request.headers().authorization});
  if(path.endsWith('/admin-auth/login')){
   expect(request.headers().authorization).toBeUndefined();
   expect(request.postDataJSON()).toEqual({username:'owner',password});
   return route.fulfill({status:invalid?401:200,json:invalid?{error:{code:'INVALID_CREDENTIALS'}}:{access_token:token,token_type:'Bearer',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,username:'owner'}});
  }
  expect(request.headers().authorization).toBe('Bearer '+token);
  expect(request.postData()).toBeNull();
  if(path.endsWith('/admin-auth/session'))return route.fulfill({json:{authenticated:true,username:'owner',expires_at:new Date(Date.now()+60000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});
  if(path.endsWith('/admin-auth/logout'))return route.fulfill({status:logoutFailure?503:204,...(logoutFailure?{json:{error:{code:'AUTH_UNAVAILABLE'}}}:{})});
  if(path.endsWith('/health'))return route.fulfill({json:{api:'available'}});
  if(expired)return route.fulfill({status:401,json:{error:{code:'SESSION_EXPIRED'}}});
  return route.fulfill({json:[]});
 });
 await page.goto('http://127.0.0.1:5174');
 await page.getByLabel('Usuário',{exact:true}).fill('owner');
 await page.getByLabel('Senha',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Entrar na central',exact:true}).click();
 return calls;
}

test('conta própria: senha só no login, Bearer em memória, logout remoto e recarga sem sessão',async({page})=>{
 await page.clock.install();const calls=await fixture(page);
 await expect(page.getByText('Consulta autenticada',{exact:true})).toBeVisible();
 const stored=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage},cookies:document.cookie}));
 expect(stored).not.toContain(token);expect(stored).not.toContain(password);expect(stored).not.toContain('owner');
 await page.getByRole('button',{name:'Sair',exact:true}).click();
 await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
 await expect.poll(()=>calls.some(call=>call.path.endsWith('/logout')&&call.method==='POST')).toBe(true);
 const stopped=calls.length;await page.clock.runFor(20050);expect(calls.length).toBe(stopped);
 await page.reload();await expect(page.getByRole('heading',{name:'Acesso administrativo'})).toBeVisible();
 expect(calls.every(call=>!call.authorization?.startsWith('Basic '))).toBe(true);
});

test('login inválido mantém operação fechada e limpa a senha',async({page})=>{
 const calls=await fixture(page,{invalid:true});
 await expect(page.getByRole('alert')).toContainText('Credenciais inválidas');
 await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
 expect(calls.length).toBe(1);await expect(page.getByText('Consulta autenticada')).toHaveCount(0);
});

test('sessão expirada pela API encerra consulta e exige login, sem fallback técnico',async({page})=>{
 const calls=await fixture(page,{expired:true});
 await expect(page.getByRole('alert')).toContainText('Sessão expirada');
 await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
 expect(calls.filter(call=>call.path.endsWith('/login')).length).toBe(1);
});

test('limite absoluto encerra a sessão mesmo com consultas periódicas',async({page})=>{
 await page.clock.install();await fixture(page);
 await expect(page.getByText('Consulta autenticada',{exact:true})).toBeVisible();
 await page.clock.runFor(60050);
 await expect(page.getByRole('alert')).toContainText('Sessão expirada');
 await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
});

test('logout sem confirmação remota encerra localmente e informa a limitação',async({page})=>{
 await fixture(page,{logoutFailure:true});await expect(page.getByText('Consulta autenticada',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Sair',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Não foi possível confirmar a revogação');
 await expect(page.getByLabel('Senha',{exact:true})).toHaveValue('');
});
