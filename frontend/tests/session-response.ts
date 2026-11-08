export const sessionResponse=(url:unknown):Response|null=>{
 const path=String(url);
 if(path.endsWith('/admin-auth/login'))return new Response(JSON.stringify({access_token:'a'.repeat(43),token_type:'Bearer',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,username:'fixture-owner'}));
 if(path.endsWith('/admin-auth/session'))return new Response(JSON.stringify({authenticated:true,username:'fixture-owner',expires_at:new Date(Date.now()+3600000).toISOString(),idle_timeout_seconds:1800,mfa_available:true,mfa_enabled:true,mfa_enrollment_available:true,email_recovery_available:false,first_access:{contract_version:2,status:"completed",generation:1,codes_remaining:3,installation_id:"fixture-installation",account_id:1}}));
 return null;
};
