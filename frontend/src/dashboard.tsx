import {formatTime} from './presentation';
import {useEffect, useState} from 'react';
import {object, type Row, type ControlState, type Client} from './api';
import {Badge, Empty, Panel, show} from './components';
import {selectExplanation, originLabel as origin, incidentRevision, explanationRevision, explanationTime, explanationFreshness} from './harpia';

export type ControlValues = {
  autonomy: 1 | 2 | 3 | null;
  operation: 'IDS' | 'SIMULATION' | 'REAL' | null;
  execution: boolean | null;
};
export const unknownControls: ControlValues = {autonomy: null, operation: null, execution: null};
export type DashboardContext = {
  modelClient?:Pick<Client,'get'>;
  selectedModelIncidentId?:string|null;
  onModelIncidentChange?:(id:string)=>void;
  openModelAnalysis?:(id:string)=>void;
  demonstration: boolean;
  demoControls: ControlValues;
  onDemoControls: (values: ControlValues) => void;
  demoEmergencyStopped:boolean;
  onDemoEmergencyStopped:(value:boolean)=>void;
  loadHistory: (id: string) => Promise<Row[]>;
  loadRecordHistory?: (kind: string, id: string) => Promise<Row[]>;
  loadCaseDossier?: (path:string,ref:{id:string;revision:number})=>Promise<Record<string,unknown>>;
  loadExplanations?: (id: string) => Promise<Row[]>;
  loading?: boolean;
  loadControls?:()=>Promise<ControlState>;
  changeControls?:(value:ControlState['value'],revision:number,reason:string)=>Promise<ControlState>;
  stopControls?:(reason:string)=>Promise<ControlState>;
  onControls?:(state:ControlState|null)=>void;
};

// Optional values explicitly supplied by the backend. Never read historical decisions as controls.
export function backendControls(health: Record<string, unknown> | null): ControlValues {
  const values = object(health?.operational_controls) ? health.operational_controls : health;
  const autonomy = values?.autonomy_mode;
  const operation = values?.operation;
  return {
    autonomy: autonomy === 1 || autonomy === 2 || autonomy === 3 ? autonomy : null,
    operation: operation === 'IDS' || operation === 'SIMULATION' || operation === 'REAL' ? operation : null,
    execution: typeof values?.execution_enabled === 'boolean' ? values.execution_enabled : null,
  };
}

export const incidentId = (row: Row) => typeof row.data.incident_id === 'string' ? row.data.incident_id : row.id;
export function newest(rows: Row[]): Row[] {
  return [...rows].sort((a, b) => {
    const time = (r: Row) => Date.parse(typeof r.data.updated_at === 'string' ? r.data.updated_at : r.created_at || '');
    const x = time(a), y = time(b);
    return Number.isFinite(x) && Number.isFinite(y) ? y - x : 0;
  });
}
export function HarpiaCard({incidents, explanations, failure, health, context,records}: {
  incidents: Row[]; explanations: Row[]; failure?: string; health: Record<string, unknown> | null; context: DashboardContext; records?:Record<string,Row[]>;
}) {
  const ordered = newest(incidents);
  const [localSelection, setLocalSelection] = useState('');
  const selection = context.selectedModelIncidentId ?? localSelection;
  const setSelection = (id:string) => {setLocalSelection(id);context.onModelIncidentChange?.(id)};
  const selected = ordered.find(row => incidentId(row) === selection) || (!selection ? ordered[0] : undefined);
  const selectedId = selected ? incidentId(selected) : null;
  const [consultation, setConsultation] = useState<{key: string; rows: Row[]; error?: string} | null>(null);
  const [requested, setRequested] = useState<{key: string; id: string} | null>(null);
  const [consulting, setConsulting] = useState(false);
  const selectionKey = JSON.stringify([selectedId, selected && incidentRevision(selected)]);
  const currentConsultation = consultation?.key === selectionKey ? consultation : null;
  const explanation = selectExplanation(currentConsultation?.rows ?? explanations, selectedId);
  const recentExplanations=(currentConsultation?.rows??explanations).filter(row=>row.data.incident_id===selectedId&&typeof row.data.text==='string'&&row.data.text.trim()).sort((a,b)=>(Date.parse(explanationTime(b)??'')||0)-(Date.parse(explanationTime(a)??'')||0)).slice(0,3);
  const freshness = selected && explanation ? explanationFreshness(selected, explanation) : 'unknown';
  const deterministicAvailable = object(health?.harpia) && health.harpia.mode === 'deterministic_only' && health.harpia.contract_version === 1 && health.harpia.generation_enabled === false;
  useEffect(() => {
    if (!requested || requested.key !== selectionKey || !context.loadExplanations) return;
    let active = true;
    setConsulting(true);
    void context.loadExplanations(requested.id).then(rows => {
      if(active)setConsultation({key: requested.key, rows});
    }).catch(error => {if(active)setConsultation({key: requested.key, rows: [], error: (error as Error).message})})
      .finally(() => {if(active)setConsulting(false)});
    return () => {active = false};
  }, [requested, selectionKey]);
  useEffect(() => {setConsulting(false);setRequested(null);setConsultation(null)}, [selectionKey, explanations]);
  const [details, setDetails] = useState(false);
  const [history, setHistory] = useState<Row[] | null>(null);
  const [historyError, setHistoryError] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyRequested, setHistoryRequested] = useState<{key: string} | null>(null);
  const historyKey = JSON.stringify([selectedId, explanation?.id]);
  useEffect(() => {setDetails(false); setHistory(null); setHistoryError(''); setLoading(false); setHistoryRequested(null)}, [selectedId, explanation?.id]);
  useEffect(() => {
    if (!historyRequested || !explanation || historyRequested.key !== historyKey) return;
    let active = true;
    setLoading(true); setHistoryError('');
    void context.loadHistory(explanation.id).then(rows => {
      // A history response cannot introduce an explanation belonging to a different incident.
      if (active) setHistory(rows.filter(row => row.data.incident_id === selectedId));
    }).catch(error => {if (active) setHistoryError((error as Error).message)})
      .finally(() => {if (active) setLoading(false)});
    return () => {active = false};
  }, [historyRequested, explanation?.id, selectedId]);
  const notIntegrated = failure?.startsWith('Não integrado:') || failure?.startsWith('Não configurado:');
  const unavailable = Boolean(failure && !notIntegrated) || (!object(health?.harpia) || health.harpia.mode !== 'deterministic_only') && ['unavailable', 'not_configured'].includes(String(health?.bitnet));
  const recordData=records||{};const decisions=(recordData.decision||[]).filter(row=>row.data.incident_id===selectedId);const latestDecision=[...decisions].sort((a,b)=>(Date.parse(String(b.data.created_at||b.created_at||''))||0)-(Date.parse(String(a.data.created_at||a.created_at||''))||0))[0];
  const decisionId=String(latestDecision?.data.decision_id||latestDecision?.id||'');const approvals=(recordData.approval||[]).filter(row=>String(row.data.decision_id||'')===decisionId);const executions=(recordData.execution||[]).filter(row=>String(row.data.decision_id||'')===decisionId);
  const detections=(recordData.detection||[]).filter(row=>selected&&(Array.isArray(selected.data.detection_refs)?selected.data.detection_refs.includes(row.id):row.data.incident_id===selectedId));
  const detection=detections[0];const anomaly=object(detection?.data.anomaly)?detection.data.anomaly:null;const classification=object(detection?.data.classification)?detection.data.classification:null;
  const originalClass=classification?(typeof classification.predicted_class==='string'?classification.predicted_class:typeof classification.accepted_class==='string'?classification.accepted_class:null):null;const probabilities=object(classification?.probabilities)?classification.probabilities:null;const originalProbability=originalClass&&typeof probabilities?.[originalClass]==='number'?new Intl.NumberFormat('pt-BR',{style:'percent',maximumFractionDigits:2}).format(probabilities[originalClass] as number):null;
  const entity=object(detection?.data.entity)?detection.data.entity:null;const assetId=typeof selected?.data.target_ref==='string'?selected.data.target_ref:typeof entity?.device_id==='string'?entity.device_id:'';
  const asset=(recordData.asset||[]).find(row=>row.id===assetId||row.data.device_id===assetId);const assetName=typeof asset?.data.display_name==='string'?asset.data.display_name:typeof asset?.data.name==='string'?asset.data.name:'Não informado';
  const historical=object(latestDecision?.data.historical_profile)?latestDecision?.data.historical_profile:null;const historicalProfile=typeof historical?.applied_profile==='string'?historical.applied_profile:[1,2,3].includes(Number(historical?.autonomy_mode))?`M${Number(historical?.autonomy_mode)}`:null;
  const simulated=object(latestDecision?.data.trial)&&latestDecision.data.trial.simulated===true||object(selected?.data.trial)&&selected?.data.trial.simulated===true;
  const assessment=object(selected?.data.attack_assessment)?selected.data.attack_assessment:object(selected?.data.assessment)?selected.data.assessment:null;
  const decisionAction=object(latestDecision?.data.action)?latestDecision.data.action:null;
  const executionText=executions.length?executions.map(row=>`${String(row.data.action||'Ação não informada')} · ${String(row.data.status||'resultado não informado')}${row.data.trial&&object(row.data.trial)&&row.data.trial.simulated===true?' · simulação':''}`).join('; '):'Sem registro de execução';
  return <Panel title="HarpIA · explicação do incidente">
    <div className="harpia-card">
      <img className="harpia-avatar" src="/assets/harpy.png" alt="Harpia mecânica · HarpIA"/>
      <div className="harpia-body">
        <small>{context.demonstration?'Demonstração visual · nenhum comando enviado':`BitNet: ${show(health?.bitnet)} · geração operacional não confirmada`}</small>
        <label>Incidente selecionado<select value={selectedId ?? ''} disabled={!ordered.length}
          onChange={e => setSelection(e.target.value)}>
          {!ordered.length && <option value="">Sem incidente disponível</option>}
          {ordered.map(row => <option key={row.id} value={incidentId(row)}>{incidentId(row)} · {show(row.data.scenario_id)}</option>)}
        </select></label>
        {selected && <dl className="harpia-dossier"><dt>Incidente</dt><dd>{selectedId} · rev. {show(incidentRevision(selected))}</dd><dt>Data</dt><dd>{typeof selected.data.created_at==='string'?formatTime(selected.data.created_at):typeof selected.created_at==='string'?formatTime(selected.created_at):'Não informada'}</dd><dt>Ativo</dt><dd>{assetName}{assetId&&<small> · {assetId}</small>}</dd><dt>Origem</dt><dd>{context.demonstration?'Demonstração visual':simulated?'Simulação':typeof selected.data.origin==='string'?selected.data.origin:'Não informada'}</dd><dt>Anomalia observada</dt><dd>{anomaly?(anomaly.is_anomaly===true?'Detectada':anomaly.is_anomaly===false?'Não detectada':'Resultado do modelo não informado'):'Não informada'}</dd>{classification&&<><dt>Classificação original</dt><dd>{originalClass||'Classe não informada'}{originalProbability?` · probabilidade calibrada desta classe ${originalProbability}`:''}</dd></>}<dt>Avaliação do ataque</dt><dd>{assessment?String(assessment.status||'Não informada'):'Não informado pela API'}</dd><dt>Estado do incidente</dt><dd>{String(selected.data.status||'Não informado')}</dd><dt>Perfil efetivo na decisão</dt><dd>{historicalProfile||'Não registrado'}</dd><dt>Defesa recomendada</dt><dd>{decisionAction?`${String(decisionAction.name||decisionAction.action_id||decisionAction.type||'Ação não informada')}${typeof latestDecision?.data.reason==='string'?` · ${latestDecision.data.reason}`:''}`:'Não informada'}</dd><dt>Decisão de política</dt><dd>{String(latestDecision?.data.status||'Sem registro de decisão')}</dd><dt>Aprovação administrativa</dt><dd>{approvals.length?approvals.map(row=>String(row.data.status||'Estado não informado')).join(', '):'Sem registro de aprovação'}</dd><dt>Execução de defesa</dt><dd>{executionText}</dd></dl>}
        {selectedId && <button type="button" disabled={!context.openModelAnalysis} onClick={()=>context.openModelAnalysis?.(selectedId)}>Ver análise técnica</button>}
        {(context.loading || consulting) && <p role="status">Carregando explicações…</p>}
        {selectedId && <button disabled={Boolean(context.loading || consulting || notIntegrated || !context.loadExplanations)}
          onClick={() => {setConsultation(null);setRequested({key: selectionKey, id: selectedId})}}>{deterministicAvailable ? 'Consultar explicação determinística' : 'Consultar explicações registradas'}</button>}
        {currentConsultation?.error && <p role="alert" className="error">Erro ao consultar explicações: {currentConsultation.error}</p>}
        {notIntegrated && <p className="muted">Explicações não integradas nesta conexão. {failure}</p>}
        {unavailable && <p className="error" role="status">Serviço indisponível.{failure ? ` ${failure}` : ' BitNet não está disponível; uma alternativa recebida pode ser exibida abaixo.'}</p>}
        {explanation ? <>
          <div className="explanation-meta"><Badge>{origin(explanation)}</Badge><small>Incidente {selectedId} · revisão da explicação {show(explanation.revision)}</small></div>
          <small>Vínculo rev. {show(explanationRevision(explanation))} · {explanationTime(explanation) ? formatTime(explanationTime(explanation)!) : 'Horário não informado'}</small>
          {freshness === 'stale' && <p role="status" className="error">Explicação desatualizada: pertence a outra revisão do incidente. Não representa a revisão selecionada.</p>}
          {freshness === 'unknown' && <p role="status">Atualidade da explicação não verificada: revisão de vínculo não informada.</p>}
          {explanation.data.persisted === false && <small>Explicação calculada nesta consulta; não é uma revisão persistida de texto. Evidências originais permanecem no backend.</small>}
          <p className="explanation-text">{String(explanation.data.text)}</p>
          <div className="harpia-actions"><button onClick={() => setDetails(value => !value)} aria-expanded={details}>Detalhes da explicação</button>
            <button disabled={loading || explanation.data.persisted === false} onClick={() => setHistoryRequested({key: historyKey})}>Histórico da explicação</button></div>
          {details && <section className="detail" aria-label="Detalhes da explicação"><p>ID: {explanation.id} · origem: {show(explanation.source)}</p></section>}
        </> : !context.loading && !consulting && <Empty>Sem explicação disponível{selectedId ? ` para o incidente ${selectedId}` : ''}.</Empty>}
        {loading && <p role="status">Carregando histórico…</p>}
        {historyError && <p className="error" role="alert">Histórico indisponível: {historyError}</p>}
        {history !== null && <section className="explanation-history" aria-label="Histórico da explicação"><h3>Histórico da explicação</h3>
          {!history.length ? <Empty>Sem revisões disponíveis para este incidente.</Empty> : history.slice(0,3).map(row => <article key={row.id}>
            <Badge>{origin(row)}</Badge><p>Revisão {show(row.revision)} · {show(row.data.text)}</p>
          </article>)}
        </section>}
        <section className="harpia-mini-feed" aria-label="Três últimas explicações"><h3>Últimas explicações disponíveis</h3>{recentExplanations.length?recentExplanations.map(row=><article key={row.id}><Badge>{origin(row)}</Badge><small>Rev. {show(row.revision)} · {explanationTime(row)?formatTime(explanationTime(row)!):'Horário não informado'}</small><p>{String(row.data.text).slice(0,180)}{String(row.data.text).length>180?'…':''}</p></article>):<small>Sem explicações recentes para este incidente.</small>}</section>
        <a href="#harpia">Abrir HarpIA — Explicações</a>
      </div>
    </div>
  </Panel>;
}
