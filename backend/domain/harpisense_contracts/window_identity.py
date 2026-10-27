"""Identidade de janela v2, explícita, sem migrar hashes antigos automaticamente.

Não altere agregação, features nem treinamento. O produtor seleciona v2 explicitamente;
origens legadas são indexadas em uma tabela de aliases (não sobrescritas).
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import hashlib
from .canonical import fingerprint

WINDOW_ID_VERSION='harpisense.window.v2'

def _seconds(value):
    if type(value) is bool or type(value) not in (int,float,str,Decimal):
        raise ValueError('Duração deve ser numérica')
    try: result=Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('Duração inválida') from exc
    if not result.is_finite() or result<=0: raise ValueError('Duração não finita ou não positiva')
    return result.normalize()

def _instant(value):
    if isinstance(value,datetime): t=value
    elif isinstance(value,str):
        try: t=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError as exc: raise ValueError('UTC inválido') from exc
    else: raise ValueError('Timestamp inválido')
    if t.tzinfo is None: raise ValueError('Timestamp sem timezone')
    return t.astimezone(timezone.utc)

def window_identity(*, collection_session_id, sensor_id, traffic_profile,
                    capture_interface, source_ip, destination_ip,
                    window_start, window_end, window_seconds,
                    feature_schema_version):
    fields=(collection_session_id,sensor_id,traffic_profile,capture_interface,feature_schema_version)
    if not all(type(v) is str and v.strip() for v in fields): raise ValueError('Contexto de captura incompleto')
    src=str(ipaddress.ip_address(source_ip));dst=str(ipaddress.ip_address(destination_ip))
    start=_instant(window_start);end=_instant(window_end)
    duration=_seconds(window_seconds)
    epoch=datetime(1970,1,1,tzinfo=timezone.utc)
    def micros(t):
        delta=t-epoch
        return Decimal(delta.days*86400000000+delta.seconds*1000000+delta.microseconds)
    start_us=micros(start)
    end_us=micros(end)
    if end<=start or end_us-start_us!=duration*1000000: raise ValueError('Duração do intervalo divergente')
    if (start_us/(duration*1000000))%1!=0: raise ValueError('Janela não alinhada ao relógio UTC')
    payload={'identity_version':WINDOW_ID_VERSION,'collection_session_id':collection_session_id,
      'sensor_id':sensor_id,'traffic_profile':traffic_profile,'capture_interface':capture_interface,
      'feature_schema_version':feature_schema_version,'source_ip':src,'destination_ip':dst,
      'window_start_us':str(int(start_us)),'window_end_us':str(int(end_us)),
      'window_seconds':str(duration)}
    return fingerprint(payload)

def legacy_aggregate_window_id(*,session,profile,interface,window_seconds,sensor,src,dst,bucket):
    # Recupera exatamente o json.dumps() padrão da base, inclusive espaços/escape ASCII.
    payload=[session,profile,interface,window_seconds,sensor,src,dst,bucket]
    return hashlib.sha256(json.dumps(payload).encode('utf-8')).hexdigest()

def legacy_edge_window_id(*,session,profile,interface,window_seconds,sensor,src,dst,bucket):
    from .canonical import fingerprint
    return fingerprint([session,profile,interface,window_seconds,sensor,src,dst,bucket])
