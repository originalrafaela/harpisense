"""Read-only metadata inspection. No app imports, SQL, collectors or file writes.

Optional root execution permits reading protected backups/capture reports. Only
whitelisted metadata is printed, never packets, payloads or credential files.
"""
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/opt/harpisense/staging/p09-deteccao-decisao')
ADAPTERS = BASE / 'adaptador_logs_p08_p09'
CAPTURES = Path('/opt/harpisense/capturas')
EXPECTED = {
    'auxiliary_audit_adapter.py': ('a6e2747e9cf857216297db1a9557fa12925e4e1c088b27152a0fcfbea8c827ff', '04b58d66d5d6d9cd513bff4b559c187bca4a2d13ea370e80fcbfc97bb9eb5416'),
    'p08_p09_pipeline.py': ('a43d0db34a5c6bca409248d8b464bdacafa3ed93e7eddd34da0fa2de1f4b85cf', '4ec9ed8c2fb5b068ebdae4b6cd7643d1aca5a5c0fcc5d9c354e28f5f7f12d8dc'),
}
def file_info(path, *, hash_content=True):
    info = {'path': str(path)}
    try:
        s = path.lstat()
        info.update(uid=s.st_uid, gid=s.st_gid, mode=oct(stat.S_IMODE(s.st_mode)),
                    size_bytes=s.st_size, mtime_ns=str(s.st_mtime_ns))
        if not stat.S_ISREG(s.st_mode):
            info['regular_file'] = False
        elif hash_content:
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
            info['sha256'] = h.hexdigest()
    except OSError as exc:
        info['error'] = type(exc).__name__
    return info

def read_json(path):
    try:
        if path.is_symlink(): return None, 'SymlinkSkipped'
        if path.stat().st_size > 32 * 1024 * 1024: return None, 'ReportTooLarge'
        return json.loads(path.read_bytes()), None
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__

def selected_fields(value, keys):
    return {k: value[k] for k in keys if k in value} if isinstance(value, dict) else {}

report = dict(captured_at_utc=datetime.now(timezone.utc).isoformat(), effective_uid=os.geteuid(),
              read_only=True, installed={}, backups=[], sessions=[], selected_session=None,
              batch_session_link_verified=False)
for name, (before, after) in EXPECTED.items():
    info = file_info(ADAPTERS / name)
    info['matches_validated_candidate'] = info.get('sha256') == after
    report['installed'][name] = info
report['adapter_directory'] = file_info(ADAPTERS, hash_content=False)
try:
    backups = sorted(ADAPTERS.glob('.validated-batch-backup-*'))
except OSError as exc:
    backups = []
    report['backup_listing_error'] = type(exc).__name__
for backup in backups:
    info = file_info(backup, hash_content=False)
    info['files'] = {}
    for name, (old, _) in EXPECTED.items():
        item = file_info(backup / name)
        item['matches_original'] = item['sha256'] == old if 'sha256' in item else None
        info['files'][name] = item
    receipt, error = read_json(backup / 'receipt.json')
    info['receipt'] = selected_fields(receipt, ('target', 'applied', 'files', 'backup_directory'))
    if error: info['receipt_error'] = error
    report['backups'].append(info)

audit = BASE / 'auditoria_cobertura_p08'
state_paths = sorted(audit.glob('mqtt_v4_*.json')) + sorted(audit.glob('*checkpoint*'))
before_state = {p.name: file_info(p) for p in state_paths}
report['batches'] = []
for p in state_paths:
    if not p.name.startswith('mqtt_v4_') or p.name.endswith('.manifest.json'): continue
    events, error = read_json(p)
    item = dict(batch=p.name, input_error=error)
    if isinstance(events, list):
        item['event_count'] = len(events)
        item['event_metadata'] = []
        for envelope in events:
            if not isinstance(envelope, dict): continue
            event = envelope.get('event')
            if not isinstance(event, dict): continue
            meta = selected_fields(event, ('event_type', 'observed_at', 'timestamp',
                'collection_session_id', 'window_id', 'sensor_id', 'target_ref'))
            meta['journal_cursor_present'] = bool(envelope.get('journal_cursor'))
            meta['journal_boot_id_present'] = bool(envelope.get('journal_boot_id'))
            item['event_metadata'].append(meta)
    manifest, error = read_json(p.with_suffix('.manifest.json'))
    item['manifest_metadata'] = selected_fields(manifest, ('schema_version', 'coverage',
        'continuity_verified', 'authorized_for_inference', 'authorized_for_ips', 'audit_events_found',
        'journal_records_read', 'collection_session_id', 'window_id', 'sensor_id', 'target_ref'))
    item['manifest_cursors_present'] = isinstance(manifest, dict) and all(manifest.get(k) for k in ('previous_cursor', 'next_cursor'))
    report['batches'].append(item)

try:
    session_paths = sorted(p for p in CAPTURES.rglob('*.session.json') if not p.is_symlink())
    # rglob may suppress PermissionError: explicit open distinguishes empty from inaccessible.
    with os.scandir(CAPTURES) as entries: next(entries, None)
    report['sessions'] = [file_info(p) for p in session_paths]
    preferred = next((p for p in session_paths if p.name == 'p08-v4-persistencia-auto02.session.json'), None)
    chosen = preferred or (session_paths[-1] if session_paths else None)
    if chosen:
        name = chosen.name.removesuffix('.session.json')
        session, error = read_json(chosen)
        detail = dict(candidate_name=name, selection='identification only; no association to audit batches',
            session_file=file_info(chosen), session_read_error=error,
            session_metadata=selected_fields(session, ('schema_version', 'started_at', 'finished_at',
                'interface', 'duration_requested_seconds', 'pcap_path', 'pcap_size_bytes', 'pcap_sha256',
                'session_basic_checks_passed', 'collection_complete', 'ready_for_inference')))
        if isinstance(session, dict):
            detail['monitoring_summary'] = selected_fields(session.get('process_monitoring'),
                ('observations_total', 'tcpdump_observations_active', 'tcpdump_observations_missing',
                 'tcpdump_observed_in_all_heartbeats', 'continuous_capture_proven'))
        pcap = chosen.with_name(name + '.pcap')
        detail['pcap'] = file_info(pcap, hash_content=pcap.is_file() and pcap.stat().st_size <= 256 * 1024 * 1024)
        detail['pcap_hash_matches_session'] = bool(isinstance(session, dict) and
            detail['pcap'].get('sha256') and detail['pcap']['sha256'] == session.get('pcap_sha256'))
        integration_path = chosen.with_name(name + '.p08.json')
        integration, error = read_json(integration_path)
        detail['integration_file'] = file_info(integration_path)
        detail['integration_read_error'] = error
        detail['integration_metadata'] = selected_fields(integration, ('schema_version', 'session', 'sensor_id',
            'interface', 'traffic_profile', 'events_converted', 'ready_for_inference'))
        if isinstance(integration, dict):
            detail['integration_pcap'] = selected_fields(integration.get('pcap'), ('path', 'size_bytes', 'sha256'))
            aggregation = integration.get('aggregation', {})
            if isinstance(aggregation, dict):
                detail['quality'] = selected_fields(aggregation.get('quality'), ('status', 'collection_complete', 'logs_complete'))
                windows = aggregation.get('windows', [])
                if isinstance(windows, list):
                    detail['window_count'] = len(windows)
                    detail['window_links'] = [selected_fields(w, ('window_id', 'collection_session_id', 'sensor_id',
                        'target_ref', 'window_start', 'window_end', 'window_seconds', 'feature_schema_version',
                        'traffic_profile', 'capture_interface')) for w in windows if isinstance(w, dict)]
        coverage_path = chosen.with_name(name + '.coverage.json')
        coverage, error = read_json(coverage_path)
        detail['coverage_file'] = file_info(coverage_path)
        detail['coverage_read_error'] = error
        detail['coverage_metadata'] = selected_fields(coverage, ('schema_version', 'session', 'intervalos_total',
            'intervalos_com_eventos', 'intervalos_sem_eventos', 'intervalos_sem_dados_agregados',
            'collection_complete', 'ready_for_inference'))
        report['selected_session'] = detail
except OSError as exc:
    report['session_discovery_error'] = type(exc).__name__
report['state_before'] = before_state
report['state_after'] = {p.name: file_info(p) for p in state_paths}
report['original_batches_manifests_checkpoint_unchanged'] = report['state_before'] == report['state_after']
report['p11_files'] = {name: file_info(Path('/opt/harpisense/staging/p11-postgresql') / name)
                       for name in ('postgres_store.py', 'app.py')}
print(json.dumps(report, indent=2))
