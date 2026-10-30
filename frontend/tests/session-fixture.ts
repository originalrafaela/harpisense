import {test as base, expect} from '@playwright/test';

// Isolated browser contract only. No VM identity, credentials or real session.
export const test=base.extend<{sessionFixture:void}>({
 sessionFixture:[async({page},use)=>{
  await page.route('**/api/v1/admin-auth/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path.endsWith('/login'))return route.fulfill({json:{access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'isolated-owner'}});
   if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,username:'isolated-owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:false,email_recovery_available:false}});
   if(path.endsWith('/logout'))return route.fulfill({status:204});
   return route.fulfill({status:404,json:{}});
  });
  await use();
 },{auto:true}],
});
export {expect};
