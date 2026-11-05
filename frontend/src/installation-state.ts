import type {Client} from './api';

/** Uses the authenticated shared client; no bootstrap, account or MFA methods. */
export type InstallationClient = Pick<Client, 'get'>;
export type SetupDraft = {
 step:string; deployment_profile?:string;
 devices?:{device_id:string;firmware_id:string;firmware_version:string}[];
 parameters:Record<string,unknown>; backup?:string;
};
export type SetupProgress = {
 version:number; document:SetupDraft|null; state:string; operational:boolean;
 pending:{section:string;code:string}[]; updated_at?:string;
};
export type InstallationStatus = 'new'|'pending'|'completed';
export type InstallationSnapshot = {
 status:InstallationStatus; setup:SetupProgress; current:Record<string,unknown>;
};
const record=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const revision=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const steps=['installation','deployment','devices','mqtt','capture','backup','review'];

export function parseSetupProgress(value:unknown):SetupProgress {
 if(!record(value)||!revision(value.version)||typeof value.state!=='string'||
    typeof value.operational!=='boolean'||!Array.isArray(value.pending)||
    !value.pending.every(p=>record(p)&&typeof p.section==='string'&&typeof p.code==='string'))
  throw new Error('Resposta do progresso de configuração incompatível.');
 const d=value.document;
 if(d!==null&&(!record(d)||typeof d.step!=='string'||!steps.includes(d.step)||!record(d.parameters)||
    (d.devices!==undefined&&(!Array.isArray(d.devices)||!d.devices.every(v=>record(v)&&
     typeof v.device_id==='string'&&typeof v.firmware_id==='string'&&typeof v.firmware_version==='string')))))
  throw new Error('Documento do progresso de configuração incompatível.');
 if((value.version===0)!==(d===null))throw new Error('Versão e documento do progresso incompatíveis.');
 return value as SetupProgress;
}

const canonical=(value:unknown):string=>JSON.stringify(value,(_key,v:unknown)=>
 record(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);

export function installationSnapshot(setupValue:unknown,currentValue:unknown):InstallationSnapshot {
 const setup=parseSetupProgress(setupValue);
 if(!record(currentValue)||!revision(currentValue.desired_revision)||
    !(currentValue.effective_revision===null||revision(currentValue.effective_revision))||
    typeof currentValue.operational!=='boolean'||typeof currentValue.state!=='string')
  throw new Error('Resposta da configuração vigente incompatível.');
 const current=currentValue;
 const applied=Number(current.effective_revision)>0&&current.desired_revision===current.effective_revision&&
  current.state==='applied_verified'&&current.proposed_status==='APPLIED'&&record(current.effective)&&
  record(current.effective.parameters)&&
  (current.presentation===undefined||(record(current.presentation)&&current.presentation.verified===true));
 // A saved draft may contain changes made after the last application. Never mark those complete.
 const draftMatches=!setup.document||(record(current.effective)&&
  canonical(setup.document.parameters)===canonical(current.effective.parameters));
 const status:InstallationStatus=applied&&draftMatches?'completed':
  setup.version===0&&current.desired_revision===0&&current.effective_revision===null?'new':'pending';
 return {status,setup,current};
}

export async function readInstallation(client:InstallationClient):Promise<InstallationSnapshot> {
 const [setup,current]=await Promise.all([
  client.get('/api/v1/config/setup'),client.get('/api/v1/config/current'),
 ]);
 return installationSnapshot(setup,current);
}
