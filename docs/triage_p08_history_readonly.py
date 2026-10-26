"""Read-only P08 historical triage. No collection, SQL, app imports or writes.

Print metadata only. Deepen at most three ranked sessions plus auto02. Parse
classic PCAP record timestamps without exporting packet bytes or addresses.
"""
import hashlib
import json
import math
import os
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CAPTURES = Path('/opt/harpisense/capturas')
SELECTED = 'p08-v4-persistencia-auto02'
errors = []
def read(path):
    try:
        if path.is_symlink(): return None
        if path.stat().st_size > 32*1024*1024: return None
        return json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        errors.append({'path':str(path),'error':type(exc).__name__})
        return None
def utc(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat()
def epoch(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def fields(value,keys):
    return {k:value[k] for k in keys if k in value} if isinstance(value,dict) else {}
def packet_times(path):
    buckets=Counter(); first=last=None; count=0
    with path.open('rb') as f:
        header=f.read(24)
        formats={b'\xd4\xc3\xb2\xa1':('<',1000000),b'\xa1\xb2\xc3\xd4':('>',1000000),
                 b'\x4d\x3c\xb2\xa1':('<',1000000000),b'\xa1\xb2\x3c\x4d':('>',1000000000)}
        if len(header)!=24 or header[:4] not in formats: return {'error':'UnsupportedOrTruncatedPCAP'}
        endian,resolution=formats[header[:4]]
        while True:
            record=f.read(16)
            if not record: break
            if len(record)!=16: return {'error':'TruncatedRecordHeader','records_read':count}
            seconds,fraction,length,original=struct.unpack(endian+'IIII',record)
            if length>16*1024*1024: return {'error':'ExcessiveRecordLength'}
            if len(f.read(length))!=length: return {'error':'TruncatedPacket','records_read':count}
            stamp=seconds+fraction/resolution
            first=stamp if first is None else min(first,stamp)
            last=stamp if last is None else max(last,stamp)
            buckets[math.floor(stamp/10)*10]+=1; count+=1
    return dict(records=count,first_packet_utc=utc(first) if first else None,last_packet_utc=utc(last) if last else None,
                ten_second_record_counts=[dict(start=utc(k),records=v) for k,v in sorted(buckets.items())])

result={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'effective_uid':os.geteuid(),
        'read_only':True,'triage':[],'deep_candidates':[],'errors':errors,
        'scope':'metadata triage; no coverage promotion or association of audit batches'}
try:
    with os.scandir(CAPTURES) as stream: next(stream,None)
except OSError as exc:
    result['capture_access_error']=type(exc).__name__
    print(json.dumps(result,indent=2)); raise SystemExit(0)
documents={}
for p in sorted(CAPTURES.glob('*.session.json')):
    session=read(p)
    if not isinstance(session,dict): continue
    name=p.name.removesuffix('.session.json')
    integration=read(CAPTURES/(name+'.p08.json'))
    coverage=read(CAPTURES/(name+'.coverage.json'))
    aggregation=integration.get('aggregation',{}) if isinstance(integration,dict) else {}
    windows=aggregation.get('windows',[]) if isinstance(aggregation,dict) else []
    windows=windows if isinstance(windows,list) else []
    quality=aggregation.get('quality',{}) if isinstance(aggregation,dict) else {}
    monitoring=session.get('process_monitoring',{})
    artifacts={suffix:(CAPTURES/(name+suffix)).is_file() for suffix in ('.session.json','.pcap','.p08.json','.coverage.json')}
    row=dict(session=name,artifacts=artifacts,**fields(session,('started_at','finished_at','interface',
        'session_basic_checks_passed','collection_complete','ready_for_inference')),
        window_count=len(windows),quality=fields(quality,('status','logs_complete','collection_complete')),
        monitoring=fields(monitoring,('observations_total','tcpdump_observations_missing','continuous_capture_proven')),
        declared_required_sources=(integration.get('required_sources') if isinstance(integration,dict) else None),
        source_coverage_records_declared=bool(isinstance(coverage,dict) and coverage.get('coverage_records')),
        score=sum(artifacts.values())+2*(session.get('session_basic_checks_passed') is True)+2*bool(windows))
    result['triage'].append(row); documents[name]=(session,integration,coverage,windows)
ranked=sorted(result['triage'],key=lambda row:(row['score'],row.get('finished_at','')),reverse=True)
names=[r['session'] for r in ranked if r.get('session_basic_checks_passed') is True][:3]
if SELECTED in documents and SELECTED not in names: names.append(SELECTED)
for name in names:
    session,integration,coverage,windows=documents[name]
    detail=dict(session=name,selection='top score/latest timestamp or designated auto02',
                checks={},heartbeat_missing_observations=[],coverage_intervals=[])
    try:
        pcap=CAPTURES/(name+'.pcap')
        size=pcap.stat().st_size
        fingerprint=sha(pcap) if size<=256*1024*1024 else None
        detail['checks'].update(pcap_size_matches=size==session.get('pcap_size_bytes'),
            pcap_hash_matches=(fingerprint==session.get('pcap_sha256')) if fingerprint else None,
            pcap_path_matches=session.get('pcap_path')==str(pcap))
        if isinstance(integration,dict):
            source=integration.get('pcap',{})
            detail['checks'].update(integration_session_matches=integration.get('session')==name,
                integration_pcap_matches=source.get('sha256')==session.get('pcap_sha256') and source.get('path')==str(pcap),
                all_window_session_ids_match=all(w.get('collection_session_id')==name for w in windows),
                unique_window_ids=len({w.get('window_id') for w in windows})==len(windows))
        detail['artifact_gate_metadata_preflight']=bool(detail['checks'] and all(v is True for v in detail['checks'].values()))
        detail['pcap_record_times']=packet_times(pcap) if size<=256*1024*1024 else {'error':'SkippedLargePCAP'}
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        detail['pcap_error']=type(exc).__name__
    observations=session.get('process_monitoring',{}).get('observations',[])
    detail['session_process_metadata']=fields(session,('started_at','subprocess_started_at','finished_at','timeout_exit_status','tcpdump_stats'))
    if isinstance(observations,list):
        for i,observation in enumerate(observations):
            if not observation.get('tcpdump_active'):
                neighbors=[]
                for j in range(max(0,i-1),min(len(observations),i+2)):
                    neighbors.append(fields(observations[j],('timestamp','elapsed_seconds','process_active','tcpdump_detected','tcpdump_active','tcpdump_processes')))
                detail['heartbeat_missing_observations'].append({'index':i,'neighbors':neighbors})
    if isinstance(coverage,dict):
        detail['coverage_metadata']=fields(coverage,('schema_version','session','intervalos_total','intervalos_com_eventos',
            'intervalos_sem_eventos','intervalos_sem_dados_agregados','collection_complete','ready_for_inference'))
        detail['coverage_intervals']=[fields(v,('inicio','fim','pacotes_agregados','possui_eventos','intervalo_parcial','cobertura_comprovada'))
                                      for v in coverage.get('intervalos',[]) if isinstance(v,dict)]
    detail['window_metadata']=[fields(w,('window_id','collection_session_id','sensor_id','target_ref','scope_ref','window_start','window_end',
        'packet_count','window_seconds','feature_schema_version','traffic_profile','capture_interface')) for w in windows]
    result['deep_candidates'].append(detail)
result['additional_metadata_files']=[p.name for p in sorted(CAPTURES.iterdir()) if p.is_file() and
    any(term in p.name.lower() for term in ('log','binding','context','inventory','source','coverage'))]
print(json.dumps(result,indent=2))
