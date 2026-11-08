import {expect,type Page} from '@playwright/test';

/** Contract-valid existing administrator for isolated browser tests. No real identity or credentials. */
export const adminFixture={
 username:'fixture-admin',
 password:'isolated-fixture-password',
 totp:'123456',
 token:'F'.repeat(43),
 challenge:'C'.repeat(43),
};

const future=(seconds:number)=>new Date(Date.now()+seconds*1000).toISOString();

export type AuthFixtureEvent={path:string;method:string;authorizationPresent:boolean;bodyKeys:string[]};

/** Install only authentication/activation routes; operational routes remain owned by each test. */
export async function installReadyAdminFixture(page:Page,options:{username?:string;password?:string;token?:string;totp?:string}={}):Promise<AuthFixtureEvent[]>{
 const username=options.username??adminFixture.username;
 const password=options.password??adminFixture.password;
 const token=options.token??adminFixture.token;
 const totp=options.totp??adminFixture.totp;
 const events:AuthFixtureEvent[]=[];
 const expiresAt=()=>future(3600);
 const challengeExpires=()=>future(300);
 const firstAccess={contract_version:2,status:'completed',generation:1,codes_remaining:3,installation_id:'fixture-installation',account_id:'fixture-account'};
 const session={authenticated:true,username,expires_at:expiresAt(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false,first_access:firstAccess};

 await page.route('**/api/v1/activation/status',route=>route.fulfill({json:{contract_version:1,status:'activated',administrator:'ready',retry_allowed:false,first_use_authorized:false,loss_of_authenticator_policy:'not_approved'}}));
 await page.route('**/api/v1/admin-auth/**',async route=>{
  const request=route.request();const path=new URL(request.url()).pathname;
  let body:Record<string,unknown>={};try{const parsed=request.postDataJSON();if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed))body=parsed}catch{}
  events.push({path,method:request.method(),authorizationPresent:Boolean(request.headers().authorization),bodyKeys:Object.keys(body).sort()});
  if(path.endsWith('/admin-auth/login')){
   if(request.headers().authorization)return route.fulfill({status:400,json:{error:{code:'UNEXPECTED_AUTHORIZATION'}}});
   if(body.username!==username||body.password!==password)return route.fulfill({status:401,json:{error:{code:'INVALID_CREDENTIALS'}}});
   return route.fulfill({json:{challenge_token:adminFixture.challenge,next_step:'login',expires_at:challengeExpires()}});
  }
  if(path.endsWith('/admin-auth/mfa/verify')){
   if(body.challenge_token!==adminFixture.challenge||body.code!==totp)return route.fulfill({status:401,json:{error:{code:'FACTOR_INVALID'}}});
   return route.fulfill({json:{access_token:token,token_type:'Bearer',username,expires_at:expiresAt(),idle_timeout_seconds:1800}});
  }
  if(path.endsWith('/admin-auth/session')){
   if(request.headers().authorization!==`Bearer ${token}`)return route.fulfill({status:401,json:{error:{code:'AUTH_REQUIRED'}}});
   return route.fulfill({json:session});
  }
  if(path.endsWith('/admin-auth/first-access'))return route.fulfill({json:{first_access:firstAccess}});
  if(path.endsWith('/admin-auth/logout'))return route.fulfill({status:204});
  return route.fulfill({status:404,json:{error:{code:'FIXTURE_ROUTE_UNAVAILABLE'}}});
 });
 return events;
}

/** Complete the real UI's password + TOTP challenge using the fixture installed above. */
export async function loginReadyAdmin(page:Page,options:{username?:string;password?:string;totp?:string}={}):Promise<void>{
 const username=options.username??adminFixture.username;
 const password=options.password??adminFixture.password;
 const totp=options.totp??adminFixture.totp;
 await page.getByLabel('Usuário',{exact:true}).fill(username);
 await page.getByLabel('Senha',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Entrar na central',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Microsoft Authenticator',exact:true})).toBeVisible();
 await page.getByLabel('Código do aplicativo autenticador',{exact:true}).fill(totp);
 await page.getByRole('button',{name:'Verificar código',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sair',exact:true})).toBeVisible();
}
