// Transport scope, not a new API contract or service discovery mechanism.
export function configuredResources(value: string | undefined): Set<string> | null {
  if (value === 'all') return null;
  return new Set((value ?? 'telemetry').split(',').map(part => part.trim()).filter(Boolean));
}
