"""Compatibilidade: encaminhamento não constitui autorização."""
from harpisense_catalog import AUTONOMY

def policy_route(mode,severity,*,confirmed=False):
    if type(mode) is not int or mode not in AUTONOMY: raise ValueError('Modo inválido')
    if severity is not None and severity not in AUTONOMY[mode]: raise ValueError('Grupo inválido')
    if not confirmed or severity is None:return 'INVESTIGATE'
    return 'REQUEST_APPROVAL' if AUTONOMY[mode][severity]=='MANUAL' else 'POLICY_ELIGIBLE'
