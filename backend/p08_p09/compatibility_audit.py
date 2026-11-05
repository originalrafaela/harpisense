"""Read-only P08/model compatibility audit. Never infers, signs or authorizes.

Uses the deployed PCAP parser, approved P08 aggregator, and P09 model validator.
Compatible numeric values are distinct from certified coverage and model fitness.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
from harpisense_data.windows import FEATURES, OPTIONAL_FEATURES, SCHEMA_VERSION, validate, versions
from harpisense_contracts.window_identity import window_identity, legacy_edge_window_id
from .adaptador_logs_p08_p09.log_window_adapter import EVENT_FEATURES

ROOT = Path(__file__).resolve().parents[2]
SOURCES = Path(__file__).parent/'compatibility_sources'
UNITS = ['packets', 'IP_bytes', 'packets/s', 'estimated_distinct_SYN_attempts/s',
         'SYN_without_ACK_packets', 'RST_packets', 'destination_ports', 'IP_bytes', 'ms']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError('Duplicate JSON key: '+name)
            result[name] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def verified_sources():
    manifest = read_json(SOURCES/'ORIGINS.json')
    for name in ('pcap_to_events.py', 'edge_features.py'):
        if digest(SOURCES/name) != manifest[name]['sha256']:
            raise ValueError('Runtime source snapshot changed: '+name)
    from .compatibility_sources.pcap_to_events import convert
    from .compatibility_sources.edge_features import aggregate
    return convert, aggregate, manifest


def model_requirements(directory, pin, role, rows):
    result = dict(status='NOT_VERIFIED', model_loaded=False, numeric_status='NOT_CHECKED', reasons=[])
    if directory is None:
        result['reasons'].append('MODEL_DIRECTORY_NOT_PROVIDED')
        return result
    directory = Path(directory)
    if not (directory/'metadata.json').is_file():
        result['reasons'].append('MISSING_metadata.json')
        return result
    meta = read_json(directory/'metadata.json')
    result.update(metadata_sha256=digest(directory/'metadata.json'),
        model_version=meta.get('model_version'), features=meta.get('features'),
        profile=meta.get('profile'), window_seconds=meta.get('window_seconds'),
        feature_schema_version=meta.get('feature_schema_version'), versions=meta.get('versions'),
        counts=meta.get('counts'), dataset_sha256=meta.get('dataset_sha256'),
        calibration=meta.get('calibration') if role == 'rf' else meta.get('target_fpr'))
    features = meta.get('features')
    if not isinstance(features, list) or not features or any(type(f) is not str for f in features):
        result['reasons'].append('INVALID_FEATURE_ORDER')
        return result
    if len(features) != len(set(features)) or not set(features) <= set(FEATURES+OPTIONAL_FEATURES):
        result['reasons'].append('INVALID_FEATURE_ORDER')
        return result
    result['required_log_features'] = [f for f in features if f in OPTIONAL_FEATURES]
    result['missing_by_window'] = {row.get('window_id', str(i)):sorted(set(FEATURES+features)-set(row))
                                   for i, row in enumerate(rows) if set(FEATURES+features)-set(row)}
    if meta.get('artifact_version') != (1 if role == 'rf' else 2):
        result['reasons'].append('ARTIFACT_VERSION_MISMATCH')
    if meta.get('feature_schema_version') != SCHEMA_VERSION:
        result['reasons'].append('FEATURE_SCHEMA_MISMATCH')
    if meta.get('versions') != versions():
        result['reasons'].append('SERVING_ENVIRONMENT_MISMATCH')
    model_file = directory/'model.joblib'
    if not model_file.is_file():
        result['reasons'].append('MISSING_model.joblib')
    elif not pin:
        result['reasons'].append('EXTERNAL_SHA256_PIN_REQUIRED')
    elif digest(model_file) != pin or meta.get('artifact_sha256') != pin:
        result['reasons'].append('MODEL_SHA256_MISMATCH')
    else:
        result['artifact_sha256'] = pin
    if not rows:
        result['reasons'].append('NO_OBSERVED_WINDOWS')
    else:
        try:
            matrix = validate(pd.DataFrame(rows), features, meta['profile'], meta['window_seconds'])
            result.update(numeric_status='COMPATIBLE', ordered_columns=list(matrix.columns),
                          dtype='float32')
        except (KeyError, TypeError, ValueError) as exc:
            result.update(numeric_status='INCOMPATIBLE', numeric_error=str(exc))
            result['reasons'].append('WINDOW_VALIDATION_FAILED')
    if not result['reasons']:
        result['status'] = 'PINNED_ARTIFACT_AND_NUMERIC_INPUT_ONLY'
    return result


def inspect_pcap(pcap, session, profile):
    convert, aggregate, _ = verified_sources()
    events, stats = convert(Path(pcap), profile['sensor_id'], profile['interface'])
    result = aggregate(events, session=session['session_id'], profile=profile['traffic_profile'],
        interface=profile['interface'], destination=profile['destination_ip'],
        window_seconds=10, collection_complete=False, logs_complete=False)
    # Do not round, relabel, fill missing values or mutate legacy IDs.
    start = datetime.fromisoformat(session['capture_effective_started_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(session['capture_effective_ended_at'].replace('Z', '+00:00'))
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError('Invalid effective capture interval')
    windows = []
    for row in result['windows']:
        begin = datetime.fromisoformat(row['window_start'].replace('Z', '+00:00'))
        finish = datetime.fromisoformat(row['window_end'].replace('Z', '+00:00'))
        bucket = int(begin.timestamp()//row['window_seconds'])
        legacy = legacy_edge_window_id(session=row['collection_session_id'], profile=row['traffic_profile'],
            interface=row['capture_interface'], window_seconds=row['window_seconds'], sensor=row['sensor_id'],
            src=row['src_ip'], dst=row['dst_ip'], bucket=bucket)
        alias = window_identity(collection_session_id=row['collection_session_id'], sensor_id=row['sensor_id'],
            traffic_profile=row['traffic_profile'], capture_interface=row['capture_interface'],
            source_ip=row['src_ip'], destination_ip=row['dst_ip'], window_start=row['window_start'],
            window_end=row['window_end'], window_seconds=row['window_seconds'],
            feature_schema_version=row['feature_schema_version'])
        windows.append(dict(window_id=row['window_id'], canonical_v2_alias=alias,
                            legacy_edge_id_matches=legacy == row['window_id'],
                            partial_window=not (start <= begin and finish <= end),
                            source_matches_profile=row['src_ip'] == profile['source_ip']))
    return result, dict(converter=stats, windows=windows, pcap_sha256=digest(pcap),
                       packet_size_semantics='IPv4.total_length_without_Ethernet')


def audit(*, profile, models, pcap=None, session_path=None, evidence_dir=None, profile_path=None):
    _, _, origins = verified_sources()
    rows, packet_audit = [], None
    coverage = dict(status='NOT_VERIFIED', source_coverage={})
    blockers = ['P08_INFERENCE_GATE_REMAINS_CLOSED']
    if pcap is not None:
        if session_path is None or profile_path is None:
            raise ValueError('PCAP requires its session report and capture profile')
        # Reuse the signature/integrity checker, not caller-supplied booleans.
        sys.path.insert(0, str(ROOT/'p08_captura/integracao'))
        from validar_sessao import validar_sessao
        from coverage_evidence import build_coverage_report
        validated = validar_sessao(session_path, profile_path)
        session = read_json(session_path)
        if validated['pcap_sha256'] != digest(pcap) or Path(validated['pcap_path']).resolve() != Path(pcap).resolve():
            raise ValueError('PCAP differs from signed session')
        integration, packet_audit = inspect_pcap(pcap, session, profile)
        rows = integration['windows']
        if packet_audit['converter']['rejected']:
            blockers.append('PCAP_RECORDS_REJECTED')
        if any(w['partial_window'] for w in packet_audit['windows']):
            blockers.append('PARTIAL_WINDOWS_PRESENT')
        if any(not w['source_matches_profile'] or not w['legacy_edge_id_matches'] for w in packet_audit['windows']):
            blockers.append('WINDOW_CONTEXT_MISMATCH')
        if evidence_dir is not None:
            full_coverage = build_coverage_report(session, Path(session_path), Path(str(session_path)+'.sig'),
                {'aggregation':integration}, profile, Path(evidence_dir), Path(pcap))
            coverage = dict(status=full_coverage['source_coverage_status'],
                source_coverage=full_coverage['source_coverage'])
    else:
        blockers.append('NO_LAB_PCAP_SESSION_PROVIDED')
    if coverage['status'] != 'COMPLETE':
        blockers.append('REQUIRED_SOURCE_COVERAGE_NOT_VERIFIED')
    requirements = {role:model_requirements(*models.get(role, (None, None)), role, rows) for role in ('rf', 'if')}
    for role, model in requirements.items():
        if model['status'] != 'PINNED_ARTIFACT_AND_NUMERIC_INPUT_ONLY':
            blockers.append(role.upper()+'_COMPATIBILITY_NOT_VERIFIED')
    return dict(schema_version='harpisense.p08.compatibility.audit.v1',
        captured_at_utc=datetime.now(timezone.utc).isoformat(), status='BLOCKED', blockers=blockers,
        model_loaded=False, inference_performed=False, authorized_for_inference=False, authorized_for_ips=False,
        feature_contract=[dict(order=i, name=name, unit=unit) for i, (name, unit) in enumerate(zip(FEATURES, UNITS), 1)],
        feature_schema_version=SCHEMA_VERSION, window_seconds=10,
        grouping=['sensor_id','src_ip','dst_ip','UTC_epoch_bucket'],
        preprocessing='P09 validate -> ordered model columns -> float32; no imputation',
        profile=dict(profile_id=profile.get('profile_id'), traffic_profile=profile.get('traffic_profile'),
            sensor_id=profile.get('sensor_id'), interface=profile.get('interface'),
            required_sources=[dict(source=s['source'], kind=s['kind'], host_id=s['host_id']) for s in profile['required_sources']]),
        sources=origins, models=requirements, packet_audit=packet_audit, coverage=coverage,
        cross_host_clock_error_bound_verified=False,
        unmapped_optional_log_features=sorted(set(OPTIONAL_FEATURES)-set(EVENT_FEATURES.values())),
        limitations=['No artifact deserialization or inference; compatibility is not training provenance or efficacy',
                    'Source coverage checker does not establish a cross-host clock error bound',
                    'PCAP does not supply missing broker/API/consumer log features or target verification'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--pcap', type=Path)
    parser.add_argument('--session-report', type=Path)
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    for role in ('rf', 'if'):
        parser.add_argument('--'+role+'-directory', type=Path)
        parser.add_argument('--'+role+'-sha256')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; overwrite refused')
    profile = read_json(args.profile)
    result = audit(profile=profile, profile_path=args.profile, pcap=args.pcap,
        session_path=args.session_report, evidence_dir=args.evidence_dir,
        models={role:(getattr(args, role+'_directory'), getattr(args, role+'_sha256')) for role in ('rf','if')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write('\n')
    print(json.dumps(dict(status=result['status'], blockers=result['blockers'], output=str(args.output))))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
