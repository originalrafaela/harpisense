import {useEffect, useState} from 'react';
import {object, type Row, type ControlState} from './api';
import {Badge, Empty, Panel, show} from './components';
import {selectExplanation, originLabel as origin, incidentRevision, explanationRevision, explanationTime, explanationFreshness} from './harpia';

export type ControlValues = {
  autonomy: 1 | 2 | 3 | null;
  operation: 'IDS' | 'SIMULATION' | 'REAL' | null;
  execution: boolean | null;
};
export const unknownControls: ControlValues = {autonomy: null, operation: null, execution: null};
export type DashboardContext = {
  demonstration: boolean;
  demoControls: ControlValues;
  onDemoControls: (values: ControlValues) => void;
  demoEmergencyStopped:boolean;
  onDemoEmergencyStopped:(value:boolean)=>void;
  loadHistory: (id: string) => Promise<Row[]>;
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
export function HarpiaCard({incidents, explanations, failure, health, context}: {
  incidents: Row[]; explanations: Row[]; failure?: string; health: Record<string, unknown> | null; context: DashboardContext;
}) {
  const ordered = newest(incidents);
  const [selection, setSelection] = useState('');
  const selected = ordered.find(row => incidentId(row) === selection) || ordered[0];
  const selectedId = selected ? incidentId(selected) : null;
  const [consultation, setConsultation] = useState<{key: string; rows: Row[]; error?: string} | null>(null);
  const [requested, setRequested] = useState<{key: string; id: string} | null>(null);
  const [consulting, setConsulting] = useState(false);
  const selectionKey = JSON.stringify([selectedId, selected && incidentRevision(selected)]);
  const currentConsultation = consultation?.key === selectionKey ? consultation : null;
  const explanation = selectExplanation(currentConsultation?.rows ?? explanations, selectedId);
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
  return <Panel title="HarpIA · explicação do incidente">
    <div className="harpia-card">
      <img className="harpia-avatar" src="/assets/harpy.png" alt="Harpia mecânica · HarpIA"/>
      <div className="harpia-body">
        <p className="muted">Explicações com contexto. HarpIA não decide nem executa comandos.</p>
        <p className="muted">Disponibilidade técnica: {show(health?.bitnet)}. Geração operacional não habilitada nesta integração.</p>
        <button disabled title="Habilitação operacional e contrato de geração pelo backend ainda pendentes">Gerar explicação</button>
        <small>{context.demonstration?'A explicação abaixo é um exemplo fictício identificado como demonstração; nenhuma consulta foi enviada. BitNet não é indicado como habilitado.':'Geração indisponível: health não autoriza uso operacional. Esta tela consulta a API do HarpiServer; o modo determinístico não chama o BitNet.'}</small>
        <label>Incidente selecionado<select value={selectedId ?? ''} disabled={!ordered.length}
          onChange={e => setSelection(e.target.value)}>
          {!ordered.length && <option value="">Sem incidente disponível</option>}
          {ordered.map(row => <option key={row.id} value={incidentId(row)}>{incidentId(row)} · {show(row.data.scenario_id)}</option>)}
        </select></label>
        {!selection && selected && <small>Incidente mais recente da página consultada. Sem horário, preservada a ordem da API.</small>}
        {selected && <small>Incidente {selectedId} · revisão do incidente {show(incidentRevision(selected))}</small>}
        {(context.loading || consulting) && <p role="status">Carregando explicações…</p>}
        {selectedId && <button disabled={Boolean(context.loading || consulting || notIntegrated || !context.loadExplanations)}
          onClick={() => {setConsultation(null);setRequested({key: selectionKey, id: selectedId})}}>{deterministicAvailable ? 'Consultar explicação determinística' : 'Consultar explicações registradas'}</button>}
        <small>{deterministicAvailable ? 'A API declarou modo determinístico; a consulta resume os campos estruturados da revisão atual e não chama o BitNet.' : 'Sem capacidade determinística declarada, somente projeções de explicação já registradas são consultadas; o endpoint histórico de geração não é chamado.'}</small>
        {currentConsultation?.error && <p role="alert" className="error">Erro ao consultar explicações: {currentConsultation.error}</p>}
        {notIntegrated && <p className="muted">Explicações não integradas nesta conexão. {failure}</p>}
        {unavailable && <p className="error" role="status">Serviço indisponível.{failure ? ` ${failure}` : ' BitNet não está disponível; uma alternativa recebida pode ser exibida abaixo.'}</p>}
        {explanation ? <>
          <div className="explanation-meta"><Badge>{origin(explanation)}</Badge><small>Incidente {selectedId} · revisão da explicação {show(explanation.revision)}</small></div>
          <small>Revisão do incidente explicada: {show(explanationRevision(explanation))} · Horário da explicação: {explanationTime(explanation) ? new Date(explanationTime(explanation)!).toLocaleString('pt-BR') : 'Não informado'}{explanationTime(explanation) && !explanation.data.generated_at ? ' (registro na API; horário de geração não informado)' : ''}</small>
          {freshness === 'stale' && <p role="status" className="error">Explicação desatualizada: pertence a outra revisão do incidente. Não representa a revisão selecionada.</p>}
          {freshness === 'unknown' && <p role="status">Atualidade da explicação não verificada: revisão de vínculo não informada.</p>}
          {explanation.data.persisted === false && <small>Explicação calculada nesta consulta; não é uma revisão persistida de texto. Evidências originais permanecem no backend.</small>}
          <p className="explanation-text">{String(explanation.data.text)}</p>
          <div className="harpia-actions"><button onClick={() => setDetails(value => !value)} aria-expanded={details}>Detalhes da explicação</button>
            <button disabled={loading || explanation.data.persisted === false} onClick={() => setHistoryRequested({key: historyKey})}>Histórico da explicação</button></div>
          {details && <section className="detail" aria-label="Detalhes da explicação"><p>ID: {explanation.id} · origem da projeção: {show(explanation.source)}</p><pre>{JSON.stringify(explanation.data, null, 2)}</pre></section>}
        </> : !context.loading && !consulting && <Empty>Sem explicação disponível{selectedId ? ` para o incidente ${selectedId}` : ''}.</Empty>}
        {loading && <p role="status">Carregando histórico…</p>}
        {historyError && <p className="error" role="alert">Histórico indisponível: {historyError}</p>}
        {history !== null && <section className="explanation-history" aria-label="Histórico da explicação"><h3>Histórico da explicação</h3>
          {!history.length ? <Empty>Sem revisões disponíveis para este incidente.</Empty> : history.map(row => <article key={row.id}>
            <Badge>{origin(row)}</Badge><p>Revisão {show(row.revision)} · {show(row.data.text)}</p>
          </article>)}
        </section>}
        <a href="#harpia">Abrir HarpIA — Explicações</a>
      </div>
    </div>
  </Panel>;
}
