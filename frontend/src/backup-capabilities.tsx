import {object} from './api';
import type {CloudBackupDraft} from './installation-state';
import './backup-capabilities.css';

export function BackupCapabilities({catalog,value,saved,onChange,disabled=false}:{catalog:unknown;value?:CloudBackupDraft;saved?:CloudBackupDraft;onChange:(value:CloudBackupDraft)=>void;disabled?:boolean}){
 const data=object(catalog)?catalog:{};
 const providers=Array.isArray(data.providers)?data.providers.filter(p=>object(p)&&['s3','azure_blob','gcs','s3_compatible'].includes(String(p.id))).filter(object):[];
 const draft=value??{mode:'deferred' as const};
 const change=(patch:Partial<CloudBackupDraft>)=>onChange({...draft,...patch});
 const selections:[string,string][]=[['configuration','Configurações'],['inventory','Inventário e vínculos'],['telemetry','Telemetria'],['audit','Auditoria']];
 return <section aria-label="Backup em nuvem" className="cloud-backup">
  <h3>Backup em nuvem</h3>
  <p role="status">{saved&&(saved.mode==='draft'||saved.provider)?'Rascunho salvo':'Backup em nuvem: não configurado'}</p>
  <p>Opcional. Configure agora ou volte a esta seção em Configurações.</p>
  <div className="flow-actions"><button type="button" disabled={disabled} aria-pressed={draft.mode==='deferred'} onClick={()=>change({mode:'deferred'})}>Configurar depois</button><button type="button" disabled={disabled} aria-pressed={draft.mode==='draft'} onClick={()=>change({mode:'draft'})}>Preparar rascunho</button></div>
  {draft.mode==='draft'&&<fieldset disabled={disabled}><legend>Backup para restauração · planejamento</legend>
   <label>Provedor<select aria-label="Provedor" value={draft.provider||''} onChange={e=>change({provider:e.target.value||undefined})}><option value="">Selecione um provedor</option>{providers.map(p=><option key={String(p.id)} value={String(p.id)}>{String(p.label)} · {p.implemented===true&&p.tested===true?'conector implementado e testado':'planejado; conector indisponível'}</option>)}</select></label>
   {!providers.length&&<p>Catálogo de provedores indisponível.</p>}
   <label>Destino do backup<input value={draft.destination||''} maxLength={200} placeholder="Nome lógico do destino ou prefixo" onChange={e=>change({destination:e.target.value||undefined})}/></label>
   <small>Use apenas nome e caminho lógico. Não informe URL, chave, senha ou token.</small>
   <fieldset className="backup-includes"><legend>O que incluir</legend>{selections.map(([key,label])=><label key={key}><input type="checkbox" checked={draft.include?.includes(key)??false} onChange={e=>change({include:e.target.checked?[...(draft.include||[]),key]:(draft.include||[]).filter(v=>v!==key)})}/>{label}</label>)}</fieldset>
   <label>Periodicidade<select aria-label="Periodicidade" value={draft.periodicity||'manual'} onChange={e=>change({periodicity:e.target.value as CloudBackupDraft['periodicity']})}><option value="manual">Manual</option><option value="daily">Diária</option><option value="weekly">Semanal</option></select></label>
   <label>Retenção em dias<input type="number" min={1} max={3650} value={draft.retention_days??''} onChange={e=>change({retention_days:e.target.value===''?undefined:Number(e.target.value)})}/></label>
   <p>Salvar guarda somente o planejamento. Não agenda nem envia dados.</p>
  </fieldset>}
  <dl><dt>Configuração efetiva</dt><dd>Não configurada</dd><dt>Última execução</dt><dd>Sem evidência disponível</dd><dt>Última restauração verificada</dt><dd>Sem evidência disponível</dd></dl>
  <div className="flow-actions">{['Conectar provedor','Executar backup','Restaurar backup'].map(label=><button type="button" key={label} disabled title="Conector operacional indisponível nesta versão">{label}</button>)}</div>
  <p>Conectores indisponíveis nesta versão. Nenhuma conta será conectada.</p>
  <p><strong>Exportar logs selecionados</strong> salva registros para análise. <strong>Backup para restauração</strong> exige dados e procedimento de recuperação verificado. Exportar logs não restaura o HarpiSense.</p>
 </section>;
}
