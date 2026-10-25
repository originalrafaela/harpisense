import type {Row} from './api.ts';

const revision = (v: unknown): number | null => Number.isInteger(v) && Number(v) > 0 ? Number(v) : null;
export const incidentRevision = (row: Row) => revision(row.data.revision) ?? revision(row.revision);
// A projection revision is not necessarily the incident revision it explains.
export const explanationRevision = (row: Row) => revision(row.data.incident_revision) ?? revision(row.data.revision);
export const explanationTime = (row: Row) => {
  const value = row.data.generated_at ?? row.data.created_at ?? row.created_at;
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? value : null;
};
export function explanationFreshness(incident: Row, explanation: Row): 'current' | 'stale' | 'unknown' {
  const expected = incidentRevision(incident), actual = explanationRevision(explanation);
  if (expected === null || actual === null) return 'unknown';
  return actual === expected ? 'current' : 'stale';
}
export function selectExplanation(rows: Row[], id: string | null): Row | undefined {
  return rows.filter(r => r.data.incident_id === id && typeof r.data.text === 'string' && r.data.text.trim())
    .sort((a,b) => (Date.parse(explanationTime(b) ?? '') || 0) - (Date.parse(explanationTime(a) ?? '') || 0) ||
      (b.revision ?? 0) - (a.revision ?? 0))[0];
}
export function originLabel(row: Row): string {
  if (row.data.source === 'deterministic_fallback') return 'Alternativa determinística';
  if (row.data.source === 'bitnet_unverified_text') return 'BitNet · texto não verificado';
  return 'Origem da explicação não informada';
}
