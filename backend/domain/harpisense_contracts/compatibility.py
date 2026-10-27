"""Adaptadores conservadores. Atestações requerem transporte/serviço autenticado.

Traduzir nomes ou resultados não fornece autoridade de ação. Não inventar
verified, approval_verified, origem confiável ou completude de captura.
"""
from .validation import ContractError, require, validate


def validate_record_compat(*args):
    """Suporta validate(record) ou validator(kind, data) sem relaxar schema."""
    if len(args)==1: record=args[0]
    elif len(args)==2:
        kind,record=args
        require(isinstance(record,dict) and record.get('record_type')==kind,'Tipo divergente')
    else: raise ContractError('Assinatura: validate(record) ou validator(kind,record)')
    return validate(record)


def canonical_operation(controls):
    """Traduz operation_mode LEGADO -> operation; rejeita conflito e extras."""
    require(isinstance(controls,dict),'Controles devem ser objeto')
    out=dict(controls)
    if 'operation_mode' in out:
        require('operation' not in out or out['operation']==out['operation_mode'],
                'operation/operation_mode conflitantes')
        out['operation']=out.pop('operation_mode')
    require({'operation','execution_enabled','autonomy_mode'} <= set(out) <= {'operation','execution_enabled','autonomy_mode','revision'},
            'Campos operacionais ausentes/desconhecidos')
    require(out['operation'] in ('IDS','SIMULATION','REAL'),'Operação inválida')
    require(type(out['execution_enabled']) is bool,'execution_enabled inválido')
    require(type(out['autonomy_mode']) is int and out['autonomy_mode'] in (1,2,3),'Autonomia inválida')
    if 'revision' in out:
        require(type(out['revision']) is int and out['revision']>=1,'Revisão inválida')
    require(out['operation']!='IDS' or out['execution_enabled'] is False,
            'IDS não admite execution_enabled')
    return out


def normalize_application_status(status, *, producer):
    """Traduz semântica de aplicação, não de eficácia.

    APPLIED do executor legado significa resultado declarado de despacho,
    não prova independente de efeito. Assim só retorna COMMAND_ACCEPTED.
    """
    mapping={
        'gerenciador':{'ACCEPTED':'COMMAND_ACCEPTED','UNAVAILABLE':'UNAVAILABLE','FAILED':'FAILED'},
        'executor_legado':{'APPLIED':'COMMAND_ACCEPTED','FAILED':'FAILED','UNKNOWN_OUTCOME':'UNKNOWN_OUTCOME', 'DENIED':'FAILED'},
        'controle_legado':{'APPLIED':'COMMAND_ACCEPTED','FAILED':'FAILED','SIMULATED':'SIMULATED',
                           'DENIED':'FAILED','REQUEST_APPROVAL':'REQUEST_APPROVAL','OBSERVE_ONLY':'OBSERVE_ONLY'},
    }
    require(producer in mapping and status in mapping[producer],'Resultado desconhecido; exige reconciliação')
    return mapping[producer][status]


def normalized_evidence_to_risk_stub(event, *, scenario_id, target_ref, scope_ref, window_id, collection_session_id):
    """Conversão incompleta e segura: impede uso como evidência verificada.

    NÃO gera registro Risk válido. A integração confiável deve associar um
    resultado de regra autenticado, cadastro de fontes e vínculo de janela.
    """
    require(isinstance(event,dict) and event.get('evidence_id') and event.get('source_ref'),
            'Evidência normalizada inválida')
    require(event.get('coverage') in ('COMPLETE','PARTIAL','UNKNOWN'),'Cobertura inválida')
    return {'evidence_id':event['evidence_id'],'source_ref':event['source'],
            'kind':None, 'scenario_id':scenario_id, 'target_ref':target_ref,
            'scope_ref':scope_ref, 'window_id':window_id,
            'collection_session_id':collection_session_id,
            'observed_at':event.get('observed_at'), 'verified':None, 'trigger_met':None,
            'artifact_ref':None, 'coverage':event['coverage'],
            'integration_required':True}
