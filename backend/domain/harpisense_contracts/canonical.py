"""Serialização/fingerprints oficiais, sem alterar hashes históricos v1.

HISTÓRICO: ``action.v1`` reproduz harpisense_contracts.validation.fingerprint
(UTF-8 sem escape ASCII). ``legacy-manager-ascii.v1`` só verifica legado:
NÃO o utilize para emitir novas decisões.
"""
import hashlib
import json
import math

ACTION_HASH_VERSION = 'harpisense.action.v1'
FEATURE_HASH_VERSION = 'harpisense.features.float.v1'
CONTEXT_HASH_VERSION = 'harpisense.context.v1'

def _check(value):
    if isinstance(value, dict):
        if not all(type(k) in (str,int) for k in value):
            raise ValueError('Chaves JSON inválidas')
        for child in value.values(): _check(child)
    elif isinstance(value, (list, tuple)):
        for child in value: _check(child)
    elif type(value) is float and not math.isfinite(value):
        raise ValueError('Valor numérico não finito')
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError('Tipo não serializável')

def canonical_json(value):
    _check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()

def action_fingerprint(action):
    return fingerprint(action)

def input_fingerprint(features):
    if type(features) is not dict or not features or any(type(k) is not str or type(v) not in (int,float) or not math.isfinite(v) for k,v in features.items()):
        raise ValueError('Features numéricas finitas são obrigatórias')
    return fingerprint({key:float(value) for key,value in features.items()})

def context_fingerprint(context):
    return fingerprint(context)

def legacy_manager_ascii_fingerprint(value):
    _check(value)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')).hexdigest()
