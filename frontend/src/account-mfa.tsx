import {useEffect,useRef,useState,type FormEvent,type KeyboardEvent} from 'react';
import {ApiError,Client,type AuthChallenge,type AuthFlowResult,type AdminSession} from './api';
import {Panel} from './components';
import './account-mfa.css';
import {PasswordRecovery} from './password-recovery';
import {InitialAccess} from './initial-access';
export {FirstAccessWelcomeModal} from './first-access-welcome';

type Enrollment={manualKey:string;qrSvg:string;expiresAt:string};
function SafeQr({svg}:{svg:string}){
 let viewBox='';let d='';let fill='#000';
 try{
  const doc=new DOMParser().parseFromString(svg,'image/svg+xml');const root=doc.documentElement;
  const candidate=root.getAttribute('viewBox')||'';const paths=[...root.getElementsByTagName('path')];
  if(root.localName==='svg'&&/^0 0 [1-9][0-9]{0,3} [1-9][0-9]{0,3}$/.test(candidate)&&paths.length===1&&root.getElementsByTagName('*').length===1){
   const path=paths[0];const value=path.getAttribute('d')||'';const color=path.getAttribute('fill')||'#000';
   if(/^[MmLlHhVvZz0-9.,\s-]+$/.test(value)&&value.length<95000&&/^#[0-9A-Fa-f]{3,8}$/.test(color)){viewBox=candidate;d=value;fill=color;}
  }
 }catch{}
 if(!d)return <p role="status">QR indisponível neste formato. Use a chave manual abaixo no aplicativo autenticador.</p>;
 return <svg className="mfa-qr" viewBox={viewBox} role="img" aria-label="QR code TOTP emitido pelo backend"><path d={d} fill={fill}/></svg>;
}
function message(error:unknown){
 if(error instanceof ApiError&&error.code==='CHALLENGE_INVALID')return 'Desafio expirado, inválido ou esgotado. Reinicie o fluxo para obter um novo.';
 return error instanceof Error?error.message:'Não foi possível concluir a solicitação.';
}
function Expiry({challenge}:{challenge:AuthChallenge}){
 return <p className="muted">Desafio temporário · expira {new Date(challenge.expires_at).toLocaleTimeString('pt-BR')} · não é uma sessão administrativa.</p>;
}

function EnrollmentFlow({client,challenge,onComplete,onCancel}:{client:Client;challenge:AuthChallenge;onComplete:(result:AuthFlowResult)=>void;onCancel:()=>void}){
 const [enrollment,setEnrollment]=useState<Enrollment|null>(null);const [code,setCode]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [expired,setExpired]=useState(Date.parse(challenge.expires_at)<=Date.now());
 useEffect(()=>{const timer=setTimeout(()=>{setExpired(true);setEnrollment(null);setCode('')},Math.max(0,Date.parse(challenge.expires_at)-Date.now()));return()=>clearTimeout(timer)},[challenge.expires_at]);
 async function begin(){if(busy||expired)return;setBusy(true);setError('');try{setEnrollment(await client.beginMfaEnrollment(challenge.challenge_token))}catch(e){setError(message(e))}finally{setBusy(false)}}
 async function confirm(event:FormEvent){event.preventDefault();if(busy||!/^\d{6}$/.test(code))return;if(Date.parse(challenge.expires_at)<=Date.now()){setError('O desafio expirou. Cancele e recomece para receber outro.');setEnrollment(null);return}setBusy(true);setError('');const submitted=code;setCode('');try{onComplete(await client.confirmMfaEnrollment(challenge.challenge_token,submitted))}catch(e){setError(message(e))}finally{setBusy(false)}}
 async function cancel(){if(busy)return;setBusy(true);try{await client.cancelMfaChallenge(challenge.challenge_token)}catch{}finally{setEnrollment(null);setCode('');setBusy(false);onCancel()}}
 return <section className="account-flow" aria-label="Configuração do aplicativo autenticador"><h3>Configurar Microsoft Authenticator</h3><Expiry challenge={challenge}/>{error&&<p role="alert" className="error">{error}</p>}{!enrollment?<><p>O MFA só será ativado quando o backend confirmar o código. A conta existente continua válida até essa confirmação.</p>{expired?<p role="alert">Desafio expirado. Cancele para voltar e iniciar um fluxo novo.</p>:<button type="button" className="primary" disabled={busy} onClick={begin}>{busy?'Solicitando…':'Mostrar QR e chave manual'}</button>}</>:<><p>No Microsoft Authenticator, toque em + → Outra conta e escaneie este QR dentro do aplicativo. Se a câmera abrir o gerenciador de senhas do celular, volte e use a chave manual no Authenticator. O QR e a chave ficam somente nesta tela e na memória.</p><div className="mfa-enrollment"><SafeQr svg={enrollment.qrSvg}/><div><label>Chave manual<input readOnly value={enrollment.manualKey} autoComplete="off"/></label><small>URI otpauth somente para o aplicativo; não abra nem compartilhe como link.</small></div></div><form onSubmit={confirm}><label>Código de 6 dígitos<input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))}/></label><button className="primary" disabled={busy||expired||code.length!==6}>{busy?'Confirmando…':'Confirmar MFA'}</button></form><small>Material emitido pelo servidor expira {new Date(enrollment.expiresAt).toLocaleTimeString('pt-BR')}.</small></>}<button type="button" disabled={busy} onClick={cancel}>Cancelar e voltar</button></section>;
}

export function AdminAccess({client,onAuthenticated}:{client:Client;onAuthenticated:(result?:Extract<AuthFlowResult,{kind:'session'}>)=>void}){
 const [view,setView]=useState<'login'|'bootstrap'|'password-reset'>('login'),[challenge,setChallenge]=useState<AuthChallenge|null>(null),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[code,setCode]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[showPassword,setShowPassword]=useState(false);
 const initialNavigation=useRef(true);
 useEffect(()=>{let active=true;void client.activationStatus().then(state=>{if(active&&initialNavigation.current&&state.administrator==='absent'&&(state.first_use_authorized||state.status!=='activated'&&state.retry_allowed))setView('bootstrap')}).catch(()=>{});return()=>{active=false}},[client]);
 function reset(){initialNavigation.current=false;setChallenge(null);setPassword('');setCode('');setError('');setView('login')}
 function accept(result:AuthFlowResult){if(result.kind==='challenge'){setChallenge(result.challenge);setCode('');return}onAuthenticated(result)}
 async function submit(e:FormEvent){e.preventDefault();initialNavigation.current=false;if(busy)return;const secret=password;setPassword('');setBusy(true);setError('');try{accept(await client.login({username,password:secret}))}catch(e){setError(message(e))}finally{setBusy(false)}}
 async function verify(e:FormEvent){e.preventDefault();if(!challenge||busy)return;const submitted=code;setCode('');setBusy(true);setError('');try{accept(await client.verifyMfa(challenge.challenge_token,submitted))}catch(e){setError(message(e))}finally{setBusy(false)}}
 if(challenge?.next_step==='enroll')return <EnrollmentFlow client={client} challenge={challenge} onComplete={accept} onCancel={reset}/>;
 if(challenge?.next_step==='login')return <section className="account-flow" aria-label="Verificação em duas etapas"><h2>Microsoft Authenticator</h2><Expiry challenge={challenge}/><form onSubmit={verify}><label>Código do aplicativo autenticador<input required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))}/></label>{error&&<p role="alert">{error}</p>}<button className="primary" disabled={busy||code.length!==6}>{busy?'Verificando…':'Verificar código'}</button></form><p>A recuperação por perda do autenticador ainda não possui política aprovada. Um código de recuperação não substitui o MFA.</p><button onClick={reset}>Cancelar e voltar ao login</button></section>;
 if(view==='bootstrap')return <InitialAccess client={client} onComplete={accept} onBack={reset}/>;
 if(view==='password-reset')return <PasswordRecovery client={client} onBack={reset}/>;
 return <section className="account-flow" aria-label="Acesso administrativo"><h2>Acesso administrativo</h2><p>Entre com sua senha e confirme o código do Microsoft Authenticator.</p><form onSubmit={submit}><label>Usuário<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label><label>Senha<span className="password-field"><input aria-label="Senha" type={showPassword?'text':'password'} required autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={showPassword?'Ocultar senha':'Mostrar senha'} onClick={()=>setShowPassword(v=>!v)}>{showPassword?'Ocultar':'Mostrar'}</button></span></label>{error&&<p role="alert" className="error">{error}</p>}<button className="primary" aria-label="Entrar na central" disabled={busy}>{busy?'Aguarde…':'Entrar'}</button></form><div className="flow-actions"><button onClick={()=>{initialNavigation.current=false;setView('bootstrap')}}>Autenticação inicial</button><button onClick={()=>{initialNavigation.current=false;setView('password-reset')}}>Esqueci minha senha</button></div></section>;
}
export function AccountSecurityPanel({client}:{client:Client}){
 const [session,setSession]=useState<AdminSession|null>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;void client.session().then(value=>{if(active)setSession(value)}).catch(e=>{if(active)setError(message(e))});return()=>{active=false}},[client]);
 return <Panel title="Conta e autenticação"><p>Conta administrativa: {session?.username||'consultando sessão'} · MFA: {session?.mfa_enabled?'habilitado':'estado não informado'}.</p><p>A perda do autenticador é um caso separado, cuja política de recuperação ainda não foi aprovada. Licença e códigos de recuperação não permitem remover ou recadastrar o MFA.</p>{error&&<p role="alert">{error}</p>}</Panel>;
}
