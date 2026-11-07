import {useState,type FormEvent} from 'react';
import {Client,object,ApiError} from './api';

export function PasswordRecovery({client,onBack}:{client:Client;onBack:()=>void}){
 const [username,setUsername]=useState(''),[code,setCode]=useState(''),[password,setPassword]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[done,setDone]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{
  await client.resetPassword(username,code,password);setCode('');setPassword('');setDone(true);
 }catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="account-flow"><h2>Esqueci minha senha</h2>
 <p>Use um código de redefinição de senha gerado pelo HarpiSense e guardado no cadastro. Os códigos para recuperar o autenticador têm outra finalidade.</p>
 {done?<p role="status">Senha redefinida. Entre novamente com a nova senha e o Microsoft Authenticator. O MFA foi preservado.</p>:<form onSubmit={submit}>
 <label>Usuário<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label>
 <label>Código de redefinição de senha<input required type="password" autoComplete="off" value={code} onChange={e=>setCode(e.target.value.trim())}/></label>
 <label>Nova senha<input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
 {error&&<p role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'Redefinindo…':'Redefinir senha'}</button></form>}
 <button type="button" onClick={onBack}>Voltar ao login</button></section>;
}

export function PasswordResetTools({client}:{client:Client}){
 const [password,setPassword]=useState(''),[code,setCode]=useState('');
 const [codes,setCodes]=useState<string[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{
  const value=await client.get('/api/v1/admin-auth/password-reset/codes','POST',{current_password:password,code});
  if(!object(value)||!Array.isArray(value.password_reset_codes)||value.password_reset_codes.length!==10||value.password_reset_codes.some(c=>typeof c!=='string'))throw new ApiError('invalid','Resposta de recuperação incompatível.');
  setCodes(value.password_reset_codes as string[]);
 }catch(e){setError((e as Error).message)}finally{setPassword('');setCode('');setBusy(false)}}
 return <section className="account-flow"><h3>Códigos para redefinir a senha</h3><p>Gerar novos códigos invalida os anteriores para essa finalidade. Os códigos do autenticador são preservados. Use um código TOTP ainda não utilizado.</p>
 {codes.length?<><ol className="password-reset-codes">{codes.map(c=><li key={c}>{c}</li>)}</ol><button onClick={()=>setCodes([])}>Guardei os códigos; ocultar</button></>:<form onSubmit={submit}>
 <label>Senha atual para gerar códigos<input type="password" required autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
 <label>Código atual do Microsoft Authenticator<input required inputMode="numeric" pattern="[0-9]{6}" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))}/></label>
 <button disabled={busy}>Gerar códigos de redefinição</button></form>}{error&&<p role="alert">{error}</p>}</section>;
}
