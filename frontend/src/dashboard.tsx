import {formatTime} from './presentation';
import {IncidentDossier} from './incident-dossier';
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
export function HarpiaCard({incidents,context,failure}: {incidents:Row[];explanations:Row[];failure?:string;health:Record<string,unknown>|null;context:DashboardContext;compact?:boolean}) {
 const ordered=newest(incidents);const [localSelection,setLocalSelection]=useState('');
 const selection=context.selectedModelIncidentId??localSelection;
 const selected=ordered.find(row=>incidentId(row)===selection)||(!selection?ordered[0]:undefined);
 return <Panel title="HarpIA"><label>Incidente selecionado<select aria-label="Incidente selecionado" value={selected?incidentId(selected):''} disabled={!ordered.length} onChange={e=>{setLocalSelection(e.target.value);context.onModelIncidentChange?.(e.target.value)}}>{!ordered.length&&<option value="">Sem incidente disponível</option>}{ordered.map(row=><option key={row.id} value={incidentId(row)}>{incidentId(row)}</option>)}</select></label>{failure&&<p role="alert" className="error">{failure}</p>}{selected?<IncidentDossier client={context.modelClient} incident={selected} compact={location.hash!=='#harpia'} onTechnical={context.openModelAnalysis}/>:<p>Explicação não disponível</p>}</Panel>;
}
