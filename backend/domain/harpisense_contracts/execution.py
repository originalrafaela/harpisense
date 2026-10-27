"""Contrato público de execução, preservando schema do gerenciador v1.

Estado COMMAND_ACCEPTED confirma somente recebimento de comando, NÃO mitigação.
Rastreamento de lease/decision_json/last_result segue interno ao gerenciador.
"""
from .validation import ContractError, require, timestamp

PUBLIC_FIELDS=('schema_version','record_type','execution_id','decision_id','action_fingerprint',
    'status','requested_at','started_at','accepted_at','verified_at','expires_at',
    'reversed_at','attempt_count')


def validate_execution_semantics(r):
    from .schema_source import EXECUTION_STATES
    require(r['record_type']=='execution' and r['status'] in EXECUTION_STATES,'Execution inválida')
    order=('requested_at','started_at','accepted_at','verified_at','reversed_at')
    stamps={key:(timestamp(r[key]) if r[key] is not None else None) for key in order}
    if r['expires_at'] is not None:
        stamps['expires_at']=timestamp(r['expires_at'])
        require(stamps['expires_at']>=stamps['requested_at'],'Expiração anterior à solicitação')
    for previous,later in [('requested_at','started_at'),('started_at','accepted_at'),
                           ('accepted_at','verified_at'),('verified_at','reversed_at')]:
        if stamps.get(previous) is not None and stamps.get(later) is not None:
            require(stamps[previous]<=stamps[later],'Ordem temporal incompatível: '+later)
    if r['status']=='QUEUED':
        require(r['attempt_count']==0 and all(r[k] is None for k in ('started_at','accepted_at','verified_at','expires_at','reversed_at')),
                'Fila não pode afirmar aplicação')
    if r['status'] in ('APPLYING','COMMAND_ACCEPTED','VERIFYING','MITIGATION_CONFIRMED',
                       'EXPIRING','EXPIRED','REVERSING','REVERSED','REVERSAL_FAILED'):
        require(r['started_at'] is not None and r['attempt_count']>=1,'Tentativa de execução sem início')
    if r['status'] in ('COMMAND_ACCEPTED','MITIGATION_CONFIRMED'):
        require(r['accepted_at'] is not None and r['expires_at'] is not None,'Aplicação aceita sem horário e TTL')
    if r['status']=='MITIGATION_CONFIRMED':
        require(r['verified_at'] is not None,'Mitigação não confirmada pelo verificador')
    if r['verified_at'] is not None:
        require(r['accepted_at'] is not None,'Verificação sem comando aceito')
    if r['status']=='REVERSED': require(r['reversed_at'] is not None,'Reversão sem confirmação temporal')
    if r['status']=='SIMULATED':
        require(r['verified_at'] is None and r['accepted_at'] is None,'Simulação não é efeito real')
    if r['status'] in ('EXPIRING','EXPIRED'):
        require(r['expires_at'] is not None,'Expiração sem prazo')
    return r


def project_execution_row(row):
    """Projeção whitelist do SQLite do gerenciador; NÃO expõe decision_json/lease.

    Valida estrutura e invariantes; não atesta vínculo com decisão sem referência externa.
    """
    from .validation import validate
    if not hasattr(row,'get'):
        row=dict(row)
    required_db={'execution_id','decision_id','action_fp','status','requested_at',
       'started_at','accepted_at','verified_at','expires_at','reversed_at','attempt_count'}
    require(required_db <= set(row),'Registro interno insuficiente')
    result={k:row[k] for k in PUBLIC_FIELDS if k not in ('schema_version','record_type','action_fingerprint')}
    result.update(schema_version='1.0.0',record_type='execution',action_fingerprint=row['action_fp'])
    validate(result)
    return result


def validate_execution_links(executions,decisions):
    from .validation import validate
    dec={d['decision_id']:d for d in decisions}
    ids=set()
    for e in executions:
        validate(e)
        require(e['record_type']=='execution','Tipo incorreto no grafo de execução')
        require(e['execution_id'] not in ids,'ID de execução duplicado')
        ids.add(e['execution_id'])
        require(e['decision_id'] in dec,'Execução sem decisão conhecida')
        d=dec[e['decision_id']]
        require(d['status']=='AUTHORIZED','Execução vinculada a decisão não autorizada')
        require(d['action'] is not None and d['action_fingerprint']==e['action_fingerprint'],
                'Fingerprint de ação divergente')
        require(timestamp(e['requested_at'])>=timestamp(d['created_at']),'Execução anterior à decisão')
    return True
