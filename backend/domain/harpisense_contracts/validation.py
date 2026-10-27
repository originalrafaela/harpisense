"""Validação estrutural, semântica e referencial. Não autoriza efeitos externos."""
import ipaddress
import math
import re
from datetime import datetime,timezone
from .schema_source import SCHEMAS,SCENARIOS,CLASSES,SCENARIO_ACTIONS
from .canonical import fingerprint as _official_fingerprint, input_fingerprint as _official_input_fingerprint

class ContractError(ValueError): pass

def require(condition,message):
    if not condition: raise ContractError(message)

def timestamp(value):
    require(isinstance(value,str),'Timestamp deve ser texto')
    try:
        require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)',value)),'Timestamp deve ser UTC explicito')
        return datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,TypeError) as exc: raise ContractError('Timestamp UTC invalido') from exc

def fingerprint(value):
    try: return _official_fingerprint(value)
    except (ValueError,TypeError) as exc: raise ContractError(str(exc)) from exc

def input_fingerprint(features):
    try: return _official_input_fingerprint(features)
    except (ValueError,TypeError) as exc: raise ContractError(str(exc)) from exc

def _shape(v,s,path='$'):
    # Implementa apenas o subconjunto usado pelos schemas deste pacote; não é validador JSON Schema genérico.
    if 'anyOf' in s:
        for choice in s['anyOf']:
            try: _shape(v,choice,path);return
            except ContractError: pass
        raise ContractError(path+': nenhuma alternativa valida')
    if 'const' in s: require(type(v) is type(s['const']) and v==s['const'],path+': constante incorreta')
    if 'enum' in s: require(any(type(v) is type(x) and v==x for x in s['enum']),path+': enum invalido')
    kind=s.get('type')
    checks={'object':lambda:type(v) is dict,'array':lambda:type(v) is list,
        'string':lambda:type(v) is str,'boolean':lambda:type(v) is bool,
        'integer':lambda:type(v) is int,'number':lambda:type(v) in [int,float] and math.isfinite(v),
        'null':lambda:v is None}
    if kind: require(checks[kind](),path+': tipo invalido '+kind)
    if kind=='object':
        require(len(v)>=s.get('minProperties',0),path+': objeto vazio')
        props=s.get('properties',{})
        require(set(s.get('required',[]))<=set(v),path+': campos obrigatorios ausentes')
        for k,value in v.items():
            require(type(k) is str,path+': chave nao textual')
            if k in props: _shape(value,props[k],path+'.'+k)
            else:
                extra=s.get('additionalProperties',True)
                require(extra is not False,path+': campo desconhecido '+k)
                if isinstance(extra,dict): _shape(value,extra,path+'.'+k)
    if kind=='array':
        require(len(v)>=s.get('minItems',0),path+': lista insuficiente')
        if s.get('uniqueItems'): require(len({fingerprint(x) for x in v})==len(v),path+': duplicatas')
        for i,x in enumerate(v): _shape(x,s['items'],path+f'[{i}]')
    if kind=='string':
        require(len(v.strip())>=s.get('minLength',0),path+': texto vazio')
        if 'pattern' in s: require(bool(re.search(s['pattern'],v)),path+': formato invalido')
        if s.get('format')=='date-time': timestamp(v)
        if s.get('format')=='ip':
            try: ipaddress.ip_address(v)
            except ValueError as exc: raise ContractError(path+': IP invalido') from exc
    if kind in ['number','integer']:
        if 'minimum' in s: require(v>=s['minimum'],path+': abaixo do minimo')
        if 'maximum' in s: require(v<=s['maximum'],path+': acima do maximo')

def scenario(record):
    case=record['scenario_id']; group=record['scenario_group']
    require((case is None and group is None) or (case is not None and SCENARIOS[case]==group),'Grupo do cenario inconsistente')

def risk_level(score): return 'CRITICAL' if score>=80 else 'HIGH' if score>=60 else 'MODERATE' if score>=30 else 'LOW'

def validate(record):
    require(isinstance(record,dict),'Registro deve ser objeto')
    kind=record.get('record_type');require(kind in SCHEMAS,'record_type desconhecido')
    _shape(record,SCHEMAS[kind]);fingerprint(record)
    r=record
    if kind=='detection':
        w=r['window'];require(timestamp(w['start'])<timestamp(w['end'])<=timestamp(r['created_at']),'Janela invalida/futura')
        expiry=timestamp(r['quality']['valid_until']);require(expiry>=timestamp(w['end']),'Validade anterior a janela')
        fresh=timestamp(r['created_at'])<=expiry
        require((r['quality']['status']=='VALID')==fresh,'Status de frescor inconsistente')
        require(r['input_fingerprint']==input_fingerprint(r['features']),'Fingerprint de features divergente')
        c,a=r['classification'],r['anomaly']
        if r['model']['detector']=='random_forest':
            require(c is not None and a is None,'RF exige classification, sem anomaly')
            probabilities=c['probabilities'];require('normal' in probabilities and set(probabilities)<=set(CLASSES),'Classes invalidas')
            require(abs(sum(probabilities.values())-1)<1e-6,'Probabilidades nao somam 1')
            require(c['predicted_class'] in probabilities,'Classe ausente nas probabilidades')
            confidence=probabilities[c['predicted_class']]
            require(abs(confidence-max(probabilities.values()))<1e-8,'Classe nao corresponde ao argmax')
            require(abs(c['confidence']-confidence)<1e-8,'Confianca divergente')
            require(abs(c['attack_probability']-(1-probabilities['normal']))<1e-8,'Probabilidade de ataque divergente')
            require(c['confidence_threshold']>0,'Limiar de confianca deve ser positivo')
            review=confidence<c['confidence_threshold']
            require(c['needs_review']==review,'needs_review inconsistente')
            require(c['accepted_class']==(None if review else c['predicted_class']),'accepted_class inconsistente')
        else:
            require(a is not None and c is None,'IF exige anomaly, sem classification')
            require(abs(a['anomaly_margin']-(a['anomaly_score']-a['anomaly_threshold']))<1e-8,'Margem IF inconsistente')
            require(a['is_anomaly']==(a['anomaly_score']>a['anomaly_threshold']),'Decisao IF ignora limiar operacional')
    if kind=='explanation':
        names=[c['feature'] for c in r['contributions']]
        require(len(names)==len(set(names)),'Feature repetida na explicacao')
        require(r['method']!='BASELINE_COMPARISON','Baseline e diagnostico: usar evidence externa, nao explicacao aditiva v1')
        require(r['target']['output']!='BASELINE_DEVIATION','Alvo de explicacao nao aditivo')
        require(all(r[k] is not None for k in ['base_value','output_value','additivity_residual']),'Explicacao aditiva incompleta')
        require(bool(names),'Contribuicoes ausentes')
        residual=r['output_value']-r['base_value']-sum(c['contribution'] for c in r['contributions'])
        require(abs(residual-r['additivity_residual'])<1e-8 and abs(residual)<1e-5,'Falha de aditividade')
        if r['target']['output']=='ANOMALY_SCORE': require(r['target']['class_label'] is None,'IF nao explica classe')
        else: require(r['target']['class_label'] is not None,'Classe explicada ausente')
    if kind=='incident':
        scenario(r);require(timestamp(r['created_at'])<=timestamp(r['updated_at']),'updated_at invalido')
        risk=r['risk']
        if risk['status']=='COMPLETE':
            require(risk['score'] is not None and risk['formula_version'] is not None and all(v is not None for v in risk['factors'].values()),'Risco completo sem fatores/versao')
            require(risk['level']==risk_level(risk['score']),'Faixa de risco inconsistente')
        else: require(risk['score'] is None and risk['level'] is None,'Nao apresentar risco incompleto como score final')
        if r['status']=='CORROBORATED':
            require(r['scenario_id'] is not None and r['target_ref'] is not None and bool(r['evidence_refs']) and r['gates']['evidence']=='PASS','Incidente corroborado sem evidencia/contexto')
    if kind=='execution':
        from .execution import validate_execution_semantics
        validate_execution_semantics(r)
    if kind=='decision':
        scenario(r);require(timestamp(r['created_at'])<timestamp(r['valid_until']),'Decisao expirada ao criar')
        require(r['supersedes_decision_id']!=r['decision_id'],'Decisao nao pode substituir a si mesma')
        if r['risk_score'] is None: require(r['risk_level'] is None,'Risco nulo com nivel')
        else: require(r['risk_level']==risk_level(r['risk_score']),'Faixa de risco divergente')
        action=r['action'];approval=r['approval']
        if action is None: require(r['action_fingerprint'] is None,'Hash sem acao')
        else:
            require(r['action_fingerprint']==fingerprint(action),'Fingerprint da acao divergente')
            from harpisense_catalog import ACTION_SPECS
            expected=ACTION_SPECS[action['action_type']][0]
            require(action['target']['target_kind']==expected,'Tipo de alvo incompatível com acao')
            params=action['parameters']; needed=set(ACTION_SPECS[action['action_type']][1])
            require({k for k,v in params.items() if v is not None}==needed,'Parametros da acao invalidos')
        if r['status'] in ['AUTHORIZED','REQUEST_APPROVAL']:
            require(action is not None and r['scenario_id'] is not None and bool(r['evidence_refs']),'Acao sem contexto suficiente')
            require(action['action_type'] in SCENARIO_ACTIONS[r['scenario_id']],'Acao fora do catalogo do cenario')
            require(all(v=='PASS' for v in r['gates'].values()),'Gate obrigatorio nao passou')
            require(r['risk_score'] is not None,'Decisao de acao exige risco completo')
        if r['status']=='OBSERVE_ONLY': require(action is None,'Observar nao executa acao candidata')
        if r['status']!='AUTHORIZED': require(approval is None,'Aprovacao somente no snapshot autorizado')
        from harpisense_catalog import AUTONOMY
        manual=r['scenario_group'] is not None and AUTONOMY[r['autonomy_mode']][r['scenario_group']]=='MANUAL'
        if r['status']=='AUTHORIZED' and manual: require(approval is not None,'Modo exige aprovacao autenticada')
        if approval is not None:
            require(approval['decision_id']==r['decision_id'] and approval['action_fingerprint']==r['action_fingerprint'] and approval['policy_version']==r['policy_version'],'Aprovacao nao corresponde a decisao')
            require(timestamp(approval['approved_at'])<=timestamp(r['created_at'])<timestamp(approval['expires_at']),'Aprovacao fora da validade')
            require(timestamp(r['valid_until'])<=timestamp(approval['expires_at']),'Decisao excede validade da aprovacao')
    return record


def validate_links(*,detections,explanations,incidents,decisions,executions=()):
    maps=[]
    for rows,kind,idkey in [(detections,'detection','detection_id'),(explanations,'explanation','explanation_id'),
                             (incidents,'incident','incident_id'),(decisions,'decision','decision_id')]:
        table={}
        for r in rows:
            validate(r);require(r['record_type']==kind,'Tipo incorreto no lote');require(r[idkey] not in table,'ID duplicado no lote')
            table[r[idkey]]=r
        maps.append(table)
    ds,xs,ins,decs=maps
    for e in xs.values():
        require(e['detection_id'] in ds,'Explicacao sem deteccao');d=ds[e['detection_id']]
        require(e['model_version']==d['model']['model_version'] and e['window_id']==d['window']['window_id'] and e['collection_session_id']==d['window']['collection_session_id'] and e['input_fingerprint']==d['input_fingerprint'],'Explicacao de modelo/janela/vetor diferente')
        require(timestamp(e['created_at'])>=timestamp(d['created_at']),'Explicacao anterior a deteccao')
        require({v['feature'] for v in e['contributions']}==set(d['features']),'Explicacao deve conter todas as features, inclusive zeros')
        for v in e['contributions']: require(abs(v['value']-d['features'][v['feature']])<1e-8,'Valor explicado diferente da entrada')
        target=e['target']; c=d['classification'];a=d['anomaly']
        if target['output']=='CALIBRATED_CLASS_PROBABILITY':
            require(c is not None and target['class_label'] in c['probabilities'],'Alvo de explicacao invalido')
            require(abs(e['output_value']-c['probabilities'][target['class_label']])<1e-6,'Explicacao nao reconstrói probabilidade operacional')
        elif target['output']=='ANOMALY_SCORE':
            require(a is not None and abs(e['output_value']-a['anomaly_score'])<1e-6,'Explicacao nao reconstrói score IF')
        else: raise ContractError('RAW_CLASS_PROBABILITY exige deteccao bruta separada; nao ligar a deteccao calibrada')
    for i in ins.values():
        require(set(i['detection_refs'])<=set(ds),'Incidente referencia deteccao inexistente')
        require(set(i['explanation_refs'])<=set(xs),'Incidente referencia explicacao inexistente')
        for ref in i['explanation_refs']: require(xs[ref]['detection_id'] in i['detection_refs'],'Explicacao fora do incidente')
        for ref in i['detection_refs']: require(timestamp(ds[ref]['created_at'])<=timestamp(i['updated_at']),'Incidente anterior as deteccoes')
    for d in decs.values():
        require(d['incident_id'] in ins,'Decisao sem incidente');i=ins[d['incident_id']]
        require(d['incident_revision']==i['revision'],'Decisao usa revisao antiga')
        for key in ['scenario_id','scenario_group','gates']: require(d[key]==i[key],'Decisao diverge do incidente: '+key)
        require(d['risk_score']==i['risk']['score'] and d['risk_level']==i['risk']['level'],'Snapshot de risco divergente')
        require(set(d['detection_refs'])<=set(i['detection_refs']),'Deteccao fora do incidente')
        require(set(d['evidence_refs'])<=set(i['evidence_refs']),'Evidencia fora do incidente')
        require(timestamp(d['created_at'])>=timestamp(i['updated_at']),'Decisao anterior a revisao')
        if d['status'] in ['AUTHORIZED','REQUEST_APPROVAL']:
            require(i['status']=='CORROBORATED','Incidente nao corroborado')
            require(d['action']['target']['target_ref']==i['target_ref'],'Alvo diferente do incidente')
            for ref in d['detection_refs']:
                source=ds[ref]
                require(source['quality']['status']=='VALID' and timestamp(d['created_at'])<=timestamp(source['quality']['valid_until']),'Decisao usa deteccao expirada')
                require(timestamp(d['valid_until'])<=timestamp(source['quality']['valid_until']),'Validade da decisao excede evidencias')
    if executions:
        from .execution import validate_execution_links
        validate_execution_links(executions, decisions)
    return True


def execution_precheck(decision,*,now,incident_revision):
    """Só verifica o contrato e seu prazo; não autentica aprovador nem confirma estado real."""
    validate(decision);require(decision['status']=='AUTHORIZED','Decisao nao autorizada')
    require(decision['incident_revision']==incident_revision,'Revisao alterada')
    require(timestamp(decision['created_at'])<=timestamp(now)<timestamp(decision['valid_until']),'Decisao fora da validade')
    return True
