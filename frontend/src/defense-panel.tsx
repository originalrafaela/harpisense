import {type Row} from './api';
import {Panel,Records} from './components';
import {backendControls,type DashboardContext} from './dashboard';

export function DefensePanel({data,failures,health,context}:{data:Record<string,Row[]>;failures:Record<string,string>;health:Record<string,unknown>|null;context:DashboardContext}) {
 const profile=context.demonstration?context.demoControls.autonomy:backendControls(health).autonomy;
 const decisions=data.decision||[];
 const hard=decisions.filter(row=>row.data.scenario_group==='Hard');
 return <Panel title="Defesa · acompanhamento junto ao HarpIA">
 <p>Perfil {profile?`M${profile}`:'não informado'}. M1 exige aprovação para toda defesa. M2 permite Low elegível automático; Medium e Hard exigem aprovação. M3 permite ações automáticas elegíveis.</p>
 <p>Execução automática e disponibilidade de ações não confirmadas: contrato de capacidades ainda não integrado. Não há autorização concedida por esta tela.</p>
 <p>Anomalia não comprova ataque. Decisão de defesa não é rótulo de treinamento. COMMAND_ACCEPTED confirma recebimento, sem comprovar mitigação.</p>
 {context.demonstration&&<p>Dados demonstrativos; nenhuma ação real.</p>}
 {context.loading?<p role="status">Consultando defesas…</p>:<>
 {hard.length>0&&<div className={profile===3?'detail':'error'} role={profile===3?'status':'alert'}><strong>Defesa Hard</strong><p>{profile===3?'Aviso informativo: consulte a execução e seu resultado.':'Confira a exigência de aprovação informada pelo servidor. Aprovação operacional ainda não integrada.'}</p><p>Este aviso não aprova nem rejeita uma defesa.</p></div>}
 {(['decision','approval','execution','verification'] as const).map(kind=><section key={kind}><h3>{{decision:'Recomendação e decisão',approval:'Aprovação registrada',execution:'Execução, falha, expiração e reversão',verification:'Verificação e resultado'}[kind]}</h3>{failures[kind]?<p role="status">{failures[kind]}</p>:<Records rows={data[kind]||[]} columns={kind==='decision'?[['id','Decisão'],['incident_id','Incidente'],['action','Ação proposta'],['status','Estado'],['reason_codes','Motivo'],['created_at','Horário'],['valid_until','Validade']]:kind==='approval'?[['id','Aprovação'],['decision_id','Decisão'],['status','Estado']]:kind==='execution'?[['id','Execução'],['decision_id','Decisão'],['status','Resultado'],['requested_at','Solicitada'],['verified_at','Verificada'],['expires_at','Expiração'],['reversed_at','Reversão']]:[['id','Verificação'],['execution_id','Execução'],['status','Resultado']]}/>}</section>)}
 </>}
 <p>Alternativas permitidas, aprovação e comandos operacionais: não integrados. Os registros acima são consultas HTTP das projeções; não autorizam execução.</p>
 </Panel>;
}
