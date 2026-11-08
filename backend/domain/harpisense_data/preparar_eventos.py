"""Converte network_event bruto do Edge em janelas IF; nunca usa rótulo inferido."""
import argparse
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import pandas as pd
from .windows import SCHEMA_VERSION, LABELS, FEATURES, validate


def aggregate(events, *, session, profile, interface, destination, window_seconds=10,
              label=None, window_identity_version='legacy-preparar.v1'):
    if not all(isinstance(v,str) and v.strip() for v in [session,profile,interface]):
        raise ValueError('Sessao, perfil e interface obrigatorios')
    destination = str(ipaddress.ip_address(destination))
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError('Janela deve ser positiva')
    if label is not None and label not in LABELS:
        raise ValueError('Rotulo invalido')
    groups, seen = {}, {}
    for e in events:
        if e.get('event_type') != 'network_event' or e.get('aggregation') is not None:
            raise ValueError('Exigem-se network_event brutos, sem aggregation; nao converter resumos')
        if e.get('record_kind', 'raw_event') != 'raw_event':
            raise ValueError('record_kind nao bruto')
        if e.get('schema_version') != '1.0':
            raise ValueError('schema_version de evento nao suportado')
        eid = e.get('event_id')
        if not isinstance(eid,str) or not eid:
            raise ValueError('event_id ausente')
        canonical = json.dumps(e,sort_keys=True,allow_nan=False)
        if eid in seen:
            if seen[eid] != canonical:
                raise ValueError('identifier_conflict: '+eid)
            continue
        seen[eid] = canonical
        c = e['capture']
        # Uma interface evita dupla contagem de travessia no gateway.
        if c['interface'] != interface or c['protocol'].lower() != 'tcp':
            continue
        dst = str(ipaddress.ip_address(c['dst_ip']))
        if dst != destination:
            continue
        src = str(ipaddress.ip_address(c['src_ip']))
        stamp = pd.Timestamp(e['observed_at'])
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise ValueError('observed_at precisa de timezone')
        t = stamp.timestamp()
        size = c['packet_size_bytes']
        if isinstance(size,bool) or not isinstance(size,int) or size <= 0:
            raise ValueError('Tamanho de pacote invalido')
        for port in ['src_port','dst_port']:
            if isinstance(c[port],bool) or not isinstance(c[port],int) or not 0 <= c[port] <= 65535:
                raise ValueError('Porta invalida')
        flags = c['tcp_flags']
        if not isinstance(flags,str) or not set(flags) <= set('FSRPAUECN'):
            raise ValueError('tcp_flags deve ser a representacao textual Scapy')
        sensor = e.get('sensor_id')
        if not isinstance(sensor,str) or not sensor:
            raise ValueError('sensor_id obrigatorio')
        key = (sensor,src,dst,math.floor(t/window_seconds))
        groups.setdefault(key,[]).append((t,size,c['src_port'],c['dst_port'],flags))
    rows = []
    for key, packets in sorted(groups.items()):
        sensor,src,dst,bucket = key
        packets.sort()
        count, total = len(packets), sum(p[1] for p in packets)
        syns = [p for p in packets if 'S' in p[4] and 'A' not in p[4]]
        if window_identity_version=='legacy-preparar.v1':
            identity=json.dumps([session,profile,interface,window_seconds,*key])
            window_id=hashlib.sha256(identity.encode()).hexdigest()
        elif window_identity_version=='harpisense.window.v2':
            from harpisense_contracts.window_identity import window_identity
            window_id=window_identity(collection_session_id=session,sensor_id=sensor,
                traffic_profile=profile,capture_interface=interface,
                source_ip=src,destination_ip=dst,
                window_start=pd.Timestamp(bucket*window_seconds,unit='s',tz='UTC').isoformat(),
                window_end=pd.Timestamp((bucket+1)*window_seconds,unit='s',tz='UTC').isoformat(),
                window_seconds=window_seconds,feature_schema_version=SCHEMA_VERSION)
        else: raise ValueError('Versão de identidade de janela desconhecida')
        row = dict(window_id=window_id,
            collection_session_id=session,feature_schema_version=SCHEMA_VERSION,
            window_seconds=window_seconds,traffic_profile=profile,
            packet_count=count,bytes_total=total,packets_per_second=count/window_seconds,
            connections_per_second=len({(p[2],p[3]) for p in syns})/window_seconds,
            syn_count=len(syns),rst_count=sum('R' in p[4] for p in packets),
            unique_dst_ports=len({p[3] for p in packets}),avg_packet_size=total/count,
            mean_interarrival_ms=(packets[-1][0]-packets[0][0])*1000/(count-1) if count>1 else 0,
            src_ip=src,dst_ip=dst,sensor_id=sensor,
            window_start=pd.Timestamp(bucket*window_seconds,unit='s',tz='UTC').isoformat(),
            window_end=pd.Timestamp((bucket+1)*window_seconds,unit='s',tz='UTC').isoformat())
        if label is not None:
            row['label']=label
        rows.append(row)
    frame = pd.DataFrame(rows)
    validate(frame,FEATURES,profile,window_seconds,labelled=label is not None)
    return frame


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['input','out','session','profile','interface','destination']:
        p.add_argument('--'+name,required=True)
    p.add_argument('--window-seconds',type=float,default=10)
    p.add_argument('--label',choices=sorted(LABELS))
    p.add_argument('--confirm-ip-size',action='store_true',required=True,
        help='Confirma que packet_size_bytes mede pacote IP, sem Ethernet')
    a=p.parse_args()
    with open(a.input,encoding='utf-8') as f:
        events=[json.loads(line) for line in f if line.strip()]
    frame=aggregate(events,session=a.session,profile=a.profile,interface=a.interface,
        destination=a.destination,window_seconds=a.window_seconds,label=a.label)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,'x',encoding='utf-8',newline='') as f:
        frame.to_csv(f,index=False)
    print(f'{len(frame)} janelas gravadas')

if __name__=='__main__': main()
