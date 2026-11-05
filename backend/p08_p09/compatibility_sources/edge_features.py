"""Adaptador de eventos brutos Edge -> janelas RF/IF. Biblioteca padrão, sem inferir zeros de ausências."""
from __future__ import annotations
import hashlib, ipaddress, json, math
from collections import defaultdict
from datetime import datetime, timezone

VERSION='harpisense.if.window.v1'
BASE=['packet_count','bytes_total','packets_per_second','connections_per_second','syn_count','rst_count','unique_dst_ports','avg_packet_size','mean_interarrival_ms']
OPTIONAL=['connection_failures','auth_failures','auth_successes','mqtt_publish_count','mqtt_acl_denials','api_auth_failures','admin_auth_failures','telemetry_identifier_conflicts','telemetry_stale_count']

def timestamp(value):
    if not isinstance(value,str): raise ValueError('timestamp ausente')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('timestamp sem timezone')
    return dt.astimezone(timezone.utc).timestamp()

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def fingerprint(value): return hashlib.sha256(canonical(value).encode()).hexdigest()

def aggregate(events, *, session, profile, interface, destination, window_seconds=10, log_counts=None, required_log_features=(), logs_complete=False, collection_complete=True):
    """Agrupa por sensor/origem/destino/janela; seleciona UMA interface para não duplicar travessias.

    log_counts: mapeamento window_id -> contagens deduplicadas, ou None.
    required_log_features: lista exata de features exigidas pelo artefato treinado.
    """
    if not session or not profile or not interface: raise ValueError('sessão/perfil/interface obrigatórios')
    if isinstance(window_seconds,bool) or not isinstance(window_seconds,(int,float)) or not math.isfinite(window_seconds) or window_seconds<=0: raise ValueError('janela inválida')
    dst_target=str(ipaddress.ip_address(destination)); seen={}; groups=defaultdict(list)
    quality={'received':0,'selected':0,'duplicate_event_ids':0,'ignored_interface':0,'ignored_destination_or_protocol':0,'invalid':[], 'collection_complete':bool(collection_complete),'logs_complete':bool(logs_complete),'feature_schema_version':VERSION}
    if not collection_complete: quality['invalid'].append('COLLECTION_INCOMPLETE')
    for pos,e in enumerate(events):
        quality['received']+=1
        try:
            if e.get('event_type')!='network_event' or e.get('aggregation') is not None or e.get('record_kind','raw_event')!='raw_event' or e.get('schema_version')!='1.0': raise ValueError('evento não bruto ou versão inválida')
            eid=e['event_id']; sensor=e['sensor_id']
            if not isinstance(eid,str) or not eid or not isinstance(sensor,str) or not sensor: raise ValueError('identificação ausente')
            digest=fingerprint(e)
            if eid in seen:
                if seen[eid]!=digest: raise ValueError('EVENT_ID_CONFLICT')
                quality['duplicate_event_ids']+=1;continue
            seen[eid]=digest
            c=e['capture']
            if c['interface']!=interface:
                quality['ignored_interface']+=1;continue
            if str(c['protocol']).lower()!='tcp' or str(ipaddress.ip_address(c['dst_ip']))!=dst_target:
                quality['ignored_destination_or_protocol']+=1;continue
            src=str(ipaddress.ip_address(c['src_ip'])); t=timestamp(e['observed_at'])
            size=c['packet_size_bytes'];sport=c['src_port'];dport=c['dst_port'];flags=c['tcp_flags']
            if type(size)!=int or size<=0 or any(type(p)!=int or not 0<=p<=65535 for p in (sport,dport)): raise ValueError('tamanho/porta inválido')
            if not isinstance(flags,str) or not set(flags)<=set('FSRPAUECN'): raise ValueError('flags inválidas')
            bucket=math.floor(t/window_seconds);groups[(sensor,src,dst_target,bucket)].append((t,size,sport,dport,flags,eid));quality['selected']+=1
        except (KeyError,TypeError,ValueError,OverflowError) as exc:
            quality['invalid'].append({'index':pos,'reason':str(exc)})
    rows=[]
    for (sensor,src,dst,bucket),packets in sorted(groups.items()):
        packets.sort();n=len(packets);bytes_total=sum(p[1] for p in packets)
        syn=[p for p in packets if 'S' in p[4] and 'A' not in p[4]]
        # Repetições de SYN no mesmo fluxo contam uma tentativa, mas syn_count conta pacotes.
        attempts=len({(p[2],p[3]) for p in syn})
        wid=fingerprint([session,profile,interface,window_seconds,sensor,src,dst,bucket])
        start=datetime.fromtimestamp(bucket*window_seconds,timezone.utc).isoformat().replace('+00:00','Z')
        end=datetime.fromtimestamp((bucket+1)*window_seconds,timezone.utc).isoformat().replace('+00:00','Z')
        row=dict(window_id=wid,collection_session_id=session,feature_schema_version=VERSION,window_seconds=window_seconds,traffic_profile=profile,
                 packet_count=n,bytes_total=bytes_total,packets_per_second=n/window_seconds,connections_per_second=attempts/window_seconds,
                 syn_count=len(syn),rst_count=sum('R' in p[4] for p in packets),unique_dst_ports=len({p[3] for p in packets}),
                 avg_packet_size=bytes_total/n,mean_interarrival_ms=(packets[-1][0]-packets[0][0])*1000/(n-1) if n>1 else 0,
                 sensor_id=sensor,src_ip=src,dst_ip=dst,window_start=start,window_end=end,capture_interface=interface)
        for name in required_log_features:
            if name not in OPTIONAL: raise ValueError('feature de log desconhecida: '+name)
            if not logs_complete or log_counts is None or wid not in log_counts or name not in log_counts[wid]:
                quality['invalid'].append({'window_id':wid,'reason':'LOG_FEATURE_UNAVAILABLE:'+name});continue
            value=log_counts[wid][name]
            if type(value)!=int or value<0: quality['invalid'].append({'window_id':wid,'reason':'LOG_FEATURE_INVALID:'+name});continue
            row[name]=value
        rows.append(row)
    quality['windows']=len(rows)
    quality['status']='COMPLETE' if not quality['invalid'] else 'INCOMPLETE'
    return {'windows':rows,'quality':quality,'ready_for_inference':quality['status']=='COMPLETE' and bool(rows)}

def validate_for_model(result, *, features, profile, window_seconds):
    """Recusa inferência se qualquer feature treinada está ausente ou qualidade incompleta."""
    if not result['ready_for_inference']: raise ValueError('coleta incompleta ou sem janelas')
    if not features or len(set(features))!=len(features) or not set(features)<=set(BASE+OPTIONAL): raise ValueError('features incompatíveis')
    for row in result['windows']:
        if row['feature_schema_version']!=VERSION or row['traffic_profile']!=profile or row['window_seconds']!=window_seconds: raise ValueError('perfil/versão/janela incompatíveis')
        for f in features:
            if f not in row: raise ValueError('feature ausente: '+f)
            v=row[f]
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0: raise ValueError('feature inválida: '+f)
    return [{f:r[f] for f in features} for r in result['windows']]
