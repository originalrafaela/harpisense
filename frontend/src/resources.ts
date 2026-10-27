// Transport scope, not a new API contract or service discovery mechanism.
export function configuredResources(value: string | undefined): Set<string> | null {
  if (value === 'all') return null;
  return new Set((value ?? 'asset,telemetry,network_event,detection,xai,evidence,incident,risk,decision,approval,execution,verification,bitnet').split(',').map(part => part.trim()).filter(Boolean));
}
