"""Funções puras: contexto normalizado pelo backend -> incidente e decisão auditáveis."""
import copy
from datetime import timedelta
from decimal import Decimal,ROUND_HALF_UP
from harpisense_catalog import CATALOG,CATALOG_VERSION,ACTION_SPECS,AUTONOMY,DEFAULT_CONFIG
from harpisense_contracts import validate,validate_links,fingerprint
from harpisense_contracts.validation import timestamp,risk_level


def need(ok,message):
    if not ok: raise ValueError(message)


def checked_config(config=None):
    c=copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    need(set(c)==set(DEFAULT_CONFIG),'Configuração incompleta ou desconhecida')
    need(set(c['weights'])==set(DEFAULT_CONFIG['weights']),'Fatores desconhecidos')
    need(all(type(v) is int and v>0 for v in c['weights'].values()) and sum(c['weights'].values())==100,'Pesos devem somar 100')
    for k in ['min_action_score','min_rf_confidence']:
        need(type(c[k]) in (int,float) and 0<=c[k]<=(100 if k=='min_action_score' else 1),'Limiar inválido')
    for k in ['min_independent_sources','max_evidence_age_seconds','decision_seconds','min_ttl_seconds','max_ttl_seconds','default_ttl_seconds']:
        need(type(c[k]) is int and c[k]>0,'Limite inválido')
    need(c['min_ttl_seconds']<=c['default_ttl_seconds']<=c['max_ttl_seconds']<=86400,'TTL inválido')
    need(isinstance(c['version'],str) and c['version'].strip(),'Versão ausente')
    return c


def policy_version(c):
    return c['version']+':'+fingerprint(dict(config=c,catalog=CATALOG,actions=ACTION_SPECS,autonomy=AUTONOMY,catalog_version=CATALOG_VERSION))[:20]


def context_check(ctx,now):
    t=timestamp(now)
    need(set(ctx)=={'scenario_id','detections','explanations','evidence','target','asset','trusted_sources'},'Campos do contexto inválidos')
    need(ctx['scenario_id'] is None or ctx['scenario_id'] in CATALOG,'Cenário desconhecido')
    ds=ctx['detections'];need(bool(ds),'Sem detecções')
    validate_links(detections=ds,explanations=ctx['explanations'],incidents=[],decisions=[])
    keys=['window_id','collection_session_id','sensor_id','start','end','traffic_profile','feature_schema_version']
    for d in ds:
        need(all(d['window'][k]==ds[0]['window'][k] for k in keys),'Mistura de janelas/sessões/perfis')
        need(timestamp(d['created_at'])<=t,'Detecção futura')
    need(len({d['model']['detector'] for d in ds})==len(ds),'Mais de uma detecção por detector/janela')
    if len(ds)==2:
        common=set(ds[0]['features'])&set(ds[1]['features'])
        need(all(ds[0]['features'][f]==ds[1]['features'][f] for f in common),'Features compartilhadas divergentes')
    target=ctx['target']
    if target is not None:
        need(set(target)=={'target_ref','target_kind','scope_ref','verified','scope_allowed','protected','executor_ready','detection_refs','allowed_parameters'},'Alvo inválido')
        need(target['target_kind'] in {v[0] for v in ACTION_SPECS.values()},'Tipo de alvo inválido')
        need(all(isinstance(target[k],str) and target[k].strip() for k in ['target_ref','scope_ref']),'Alvo vazio')
        need(all(target[k] is None or type(target[k]) is bool for k in ['verified','scope_allowed','protected','executor_ready']),'Gate inválido')
        need(set(target['detection_refs'])=={d['detection_id'] for d in ds},'Vínculo do alvo divergente')
        need(type(target['allowed_parameters']) is dict,'Parâmetros permitidos inválidos')
        need(set(target['allowed_parameters'])<={'rate_profile_ref','topic_ref','permission','message_id'},'Parâmetro desconhecido')
        need(all(type(v) is list and v and all(type(x) is str and x.strip() for x in v) for v in target['allowed_parameters'].values()),'Valores de parâmetros inválidos')
        need(set(target['allowed_parameters'].get('permission',[]))<={'PUBLISH','SUBSCRIBE'},'Permissão inválida')
    asset=ctx['asset']
    if asset is not None:
        need(set(asset)=={'asset_ref','criticality','scope_ref','inventory_version'},'Ativo inválido')
        need(all(isinstance(asset[k],str) and asset[k].strip() for k in ['asset_ref','scope_ref','inventory_version']),'Ativo sem proveniência')
        need(type(asset['criticality']) in (int,float) and 0<=asset['criticality']<=100,'Criticidade inválida')
        if target: need(asset['scope_ref']==target['scope_ref'],'Ativo de outro escopo')
    need(type(ctx['trusted_sources']) is dict,'Fontes inválidas')
    need(all(type(k) is str and k.strip() and type(v) is list and all(type(x) is str for x in v) for k,v in ctx['trusted_sources'].items()),'Cadastro de fontes inválido')
    ids=set()
    for e in ctx['evidence']:
        need(set(e)=={'evidence_id','source_ref','kind','scenario_id','target_ref','scope_ref','window_id','collection_session_id','observed_at','verified','trigger_met','artifact_ref'},'Evidência inválida')
        need(type(e['verified']) is bool and type(e['trigger_met']) is bool,'Indicador de evidência inválido')
        need(all(isinstance(e[k],str) and e[k].strip() for k in set(e)-{'verified','trigger_met'}),'Referência de evidência vazia')
        need(e['evidence_id'] not in ids,'Evidência duplicada');ids.add(e['evidence_id']);timestamp(e['observed_at'])
    return t


def evaluate(ctx,*,now,config=None,previous=None):
    """ctx deve vir de coletores/inventário autenticados, nunca diretamente da LLM."""
    c=checked_config(config);t=context_check(ctx,now);ds=ctx['detections'];case=ctx['scenario_id'];target=ctx['target']
    accepted=[];rejected={}
    for e in ctx['evidence']:
        conditions=dict(verified=e['verified'],trigger=e['trigger_met'],source=e['kind'] in ctx['trusted_sources'].get(e['source_ref'],[]),
            scenario=case is not None and e['scenario_id']==case and e['kind']==CATALOG[case]['evidence_kind'],
            target=target is not None and e['target_ref']==target['target_ref'] and e['scope_ref']==target['scope_ref'],
            window=e['window_id']==ds[0]['window']['window_id'] and e['collection_session_id']==ds[0]['window']['collection_session_id'],
            freshness=0<=(t-timestamp(e['observed_at'])).total_seconds()<=c['max_evidence_age_seconds'])
        if all(conditions.values()):accepted.append(e)
        else:rejected[e['evidence_id']]=[k for k,v in conditions.items() if not v]
    sources=sorted({e['source_ref'] for e in accepted})
    rf=next((d['classification'] for d in ds if d['classification']),None)
    anomaly=next((d['anomaly'] for d in ds if d['anomaly']),None)
    factors=dict(detection=None if rf is None else 100*(rf['probabilities'].get(case,0) if case else rf['attack_probability']),
        corroboration=min(100,50*len(sources)),impact=None if case is None else CATALOG[case]['impact'],
        anomaly=None if anomaly is None else (100*anomaly['normal_reference_percentile'] if anomaly['is_anomaly'] else 0),
        criticality=None if ctx['asset'] is None else ctx['asset']['criticality'])
    factors={k:None if v is None else float(Decimal(str(v)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)) for k,v in factors.items()}
    terms={k:None if v is None else str(Decimal(str(v))*Decimal(c['weights'][k])/100) for k,v in factors.items()}
    complete=all(v is not None for v in factors.values())
    score=float(sum(Decimal(v) for v in terms.values()).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if complete else None
    gate=lambda v:'UNKNOWN' if v is None else ('PASS' if v else 'FAIL')
    rf_ok=rf is not None and case is not None and rf['accepted_class']==case and not rf['needs_review'] and rf['confidence']>=c['min_rf_confidence']
    gates=dict(evidence=gate(rf_ok and len(sources)>=c['min_independent_sources']),
        target=gate(None if target is None else target['verified']),scope=gate(None if target is None else target['scope_allowed']),
        freshness=gate(all(d['quality']['status']=='VALID' and t<timestamp(d['quality']['valid_until']) for d in ds)),
        protected_assets=gate(None if target is None or target['protected'] is None else not target['protected']),
        executor_ready=gate(None if target is None else target['executor_ready']))
    key=fingerprint([ds[0]['window'],case,None if target is None else target['target_ref']])
    incident_id='inc-'+key;revision=1;created=now
    if previous is not None:
        validate(previous);need(previous['record_type']=='incident' and previous['incident_id']==incident_id,'Incidente anterior incompatível')
        need(t>=timestamp(previous['updated_at']) and previous['status']!='CLOSED','Revisão inválida')
        revision=previous['revision']+1;created=previous['created_at']
    incident=dict(schema_version='1.0.0',record_type='incident',incident_id=incident_id,created_at=created,updated_at=now,
        revision=revision,correlation_key=key,status='CORROBORATED' if gates['evidence']=='PASS' and gates['target']=='PASS' else ('SUSPECTED' if case or (anomaly and anomaly['is_anomaly']) else 'OBSERVED'),
        scenario_id=case,scenario_group=None if case is None else CATALOG[case]['group'],
        detection_refs=sorted(d['detection_id'] for d in ds),explanation_refs=sorted(e['explanation_id'] for e in ctx['explanations']),
        evidence_refs=sorted(e['evidence_id'] for e in accepted),target_ref=None if target is None else target['target_ref'],
        risk=dict(status='COMPLETE' if complete else 'INCOMPLETE',score=score,level=None if score is None else risk_level(score),
            formula_version=policy_version(c),factors=factors),gates=gates)
    validate_links(detections=ds,explanations=ctx['explanations'],incidents=[incident],decisions=[])
    audit=dict(formula_version=policy_version(c),context_fingerprint=fingerprint(ctx),evaluated_at=now,weights=c['weights'],
        weighted_terms=terms,independent_sources=sources,rejected_evidence=rejected,missing_factors=[k for k,v in factors.items() if v is None],
        catalog_version=CATALOG_VERSION,config=c)
    return incident,audit


def decide(ctx,*,mode,now,config=None,proposal=None,previous=None):
    need(type(mode) is int and mode in AUTONOMY,'Modo inválido')
    c=checked_config(config);i,audit=evaluate(ctx,now=now,config=c,previous=previous);t=timestamp(now)
    reasons=[];action=None;case=i['scenario_id'];status='OBSERVE_ONLY'
    if i['risk']['status']!='COMPLETE':reasons.append('INCOMPLETE_RISK')
    if case is None:reasons.append('UNKNOWN_SCENARIO')
    if i['status']!='CORROBORATED':reasons.append('NOT_CORROBORATED')
    reasons.extend('GATE_'+k.upper()+'_'+v for k,v in i['gates'].items() if v!='PASS')
    if i['risk']['score'] is not None and i['risk']['score']<c['min_action_score']:reasons.append('BELOW_ACTION_THRESHOLD')
    expiry=t+timedelta(seconds=c['decision_seconds'])
    if not reasons:
        target=ctx['target']
        allowed=[x for x in CATALOG[case]['actions'] if ACTION_SPECS[x][0]==target['target_kind']]
        if not allowed: reasons.append('NO_ACTION_FOR_TARGET');status='DENIED'
        else:
            candidate=proposal if proposal is not None else dict(action_type=allowed[0],target={k:target[k] for k in ['target_ref','target_kind','scope_ref']},ttl_seconds=c['default_ttl_seconds'],
                parameters={k:(target['allowed_parameters'].get(k,[None])[0] if k in ACTION_SPECS[allowed[0]][1] else None) for k in ['rate_profile_ref','topic_ref','permission','message_id']})
            valid=type(candidate) is dict and set(candidate)=={'action_type','target','ttl_seconds','parameters'}
            if valid:
                typ=candidate['action_type'];params=candidate['parameters'];ttl=candidate['ttl_seconds']
                valid=type(typ) is str and typ in allowed and candidate['target']=={k:target[k] for k in ['target_ref','target_kind','scope_ref']} and type(ttl) is int and c['min_ttl_seconds']<=ttl<=c['max_ttl_seconds']
                valid=valid and type(params) is dict and set(params)=={'rate_profile_ref','topic_ref','permission','message_id'}
                if valid:
                    valid={k for k,v in params.items() if v is not None}==set(ACTION_SPECS[typ][1]) and all(v is None or v in target['allowed_parameters'].get(k,[]) for k,v in params.items())
                    if typ=='REVOKE_MQTT_PERMISSION':valid=valid and params['permission']==('SUBSCRIBE' if case=='C02' else 'PUBLISH')
            if not valid:status='DENIED';reasons.append('INVALID_PROPOSAL')
            else:
                action=copy.deepcopy(candidate);status='REQUEST_APPROVAL' if AUTONOMY[mode][i['scenario_group']]=='MANUAL' else 'AUTHORIZED'
                reasons.append('MANUAL_APPROVAL_REQUIRED' if status=='REQUEST_APPROVAL' else 'AUTONOMY_ALLOWED')
                deadlines=[timestamp(d['quality']['valid_until']) for d in ctx['detections']]
                deadlines.extend(timestamp(e['observed_at'])+timedelta(seconds=c['max_evidence_age_seconds']) for e in ctx['evidence'] if e['evidence_id'] in i['evidence_refs'])
                expiry=min([expiry,*deadlines])
                if expiry<=t:action=None;status='OBSERVE_ONLY';reasons=['EVIDENCE_EXPIRED']
                if expiry<=t:expiry=t+timedelta(seconds=1)
    decision=dict(schema_version='1.0.0',record_type='decision',decision_id='dec-'+fingerprint([i,mode,action,now,policy_version(c)]),
        created_at=now,supersedes_decision_id=None,incident_id=i['incident_id'],incident_revision=i['revision'],policy_version=policy_version(c),autonomy_mode=mode,
        scenario_id=case,scenario_group=i['scenario_group'],risk_score=i['risk']['score'],risk_level=i['risk']['level'],status=status,
        reason_codes=reasons,evidence_refs=i['evidence_refs'],detection_refs=i['detection_refs'],gates=i['gates'],action=action,
        action_fingerprint=None if action is None else fingerprint(action),approval=None,valid_until=expiry.isoformat(),execution_requested=False)
    validate_links(detections=ctx['detections'],explanations=ctx['explanations'],incidents=[i],decisions=[decision])
    return dict(incident=i,decision=decision,audit=audit)


def preflight(bundle,ctx,*,now,current_mode,current_incident_revision,config=None):
    """Revalidação imediatamente antes do despacho. Não executa nem reserva uma ação."""
    from harpisense_contracts import execution_precheck
    d=bundle['decision'];execution_precheck(d,now=now,incident_revision=current_incident_revision)
    need(current_mode==d['autonomy_mode'],'Modo mudou')
    need(fingerprint(ctx)==bundle['audit']['context_fingerprint'],'Contexto mudou')
    fresh=decide(ctx,now=now,mode=current_mode,config=config,proposal=d['action'])
    n=fresh['decision']
    need(n['policy_version']==d['policy_version'],'Política mudou')
    need(n['status'] in ['AUTHORIZED','REQUEST_APPROVAL'] and n['action_fingerprint']==d['action_fingerprint'],'Revalidação operacional falhou')
    need(fresh['incident']['incident_id']==d['incident_id'],'Incidente mudou')
    return True
