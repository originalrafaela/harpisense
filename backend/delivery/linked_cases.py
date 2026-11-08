"""Distinct cases from explicit incident links, under the existing control lock.

No alternative controller, inferred correlation, synthetic promotion or model
execution. Unlinked operational items still block Apply and make totals partial.
"""
from collections import defaultdict
from copy import deepcopy
from urllib.parse import quote

from psycopg.types.json import Jsonb
from harpisense_contracts import validate
from .operational_queue import OperationalQueue, summarize, valid_item, ACTIVE, CLOSED, UNKNOWN, CASE_SOURCES


def reason_for_source(source):
    if source['observed_at'] is None:return 'SOURCE_NOT_OBSERVED'
    if not source['valid']:return 'INVALID_SOURCE_REPORT'
    if not source['fresh']:return 'SOURCE_REPORT_STALE'
    if not source['complete']:return 'SOURCE_STATE_UNKNOWN'
    return None


class LinkedOperationalQueue(OperationalQueue):
    def snapshot(self,tx):
        # Reuse the published queue semantics and one authoritative report read.
        rows=tx.conn.execute("SELECT source,items,observed_at>clock_timestamp()-interval '30 seconds',"
                             'revision,observed_at FROM hs_operational_authority').fetchall()
        result=summarize(rows)
        legacy=deepcopy(result['cases'])
        facts=[];unknowns=[];reasons=[]
        for source,items,fresh,revision,observed_at in rows:
            if source not in CASE_SOURCES or not isinstance(items,list):continue
            for item in items:
                if not valid_item(item) or item['state'] not in ACTIVE:continue
                fact={'source':source,'record_id':item['id'],'source_revision':revision,
                      'source_observed_at':observed_at.isoformat(),'fresh':fresh is True,
                      'state':item['state'],'origin':item.get('origin'),'item':item}
                if item['state'] in UNKNOWN:unknowns.append(fact)
                else:facts.append(fact)
        # An UNKNOWN report is not an explicit closure. Retain a previously
        # recorded active fact when the producer persisted its exact lineage.
        if unknowns:
            exists=tx.conn.execute("SELECT to_regclass('hs_activity_event')").fetchone()[0]
            prior={}
            if exists:
                keys=[{'source':f['source'],'record_id':f['record_id']} for f in unknowns]
                old=tx.conn.execute("SELECT DISTINCT ON(source,record_id) source,record_id,source_revision,data,at "
                    "FROM hs_activity_event WHERE origin='trusted-service' AND data->>'state' NOT IN ('UNKNOWN','UNKNOWN_OUTCOME') "
                    'AND (source,record_id) IN (SELECT source,record_id FROM jsonb_to_recordset(%s::jsonb) '
                    'AS r(source text,record_id text)) ORDER BY source,record_id,source_revision DESC',
                    (Jsonb(keys),)).fetchall()
                prior={(r[0],r[1]):r for r in old}
            for fact in unknowns:
                old=prior.get((fact['source'],fact['record_id']))
                if old and old[3]['state'] in ACTIVE-UNKNOWN:
                    fact.update(item=old[3],origin='trusted-service',fresh=False,
                        last_known_state=old[3]['state'],last_known_source_revision=old[2],
                        last_known_observed_at=old[4].isoformat())
                    facts.append(fact)
                    reasons.append({'code':'KNOWN_ACTIVE_RETAINED_AFTER_UNKNOWN','source':fact['source'],
                                    'record_id':fact['record_id']})
                else:
                    facts.append(fact)

        references=[]
        for fact in facts:
            ref=fact['item'].get('incident_ref')
            if (isinstance(ref,dict) and set(ref)=={'id','revision'} and isinstance(ref['id'],str)
                    and type(ref['revision']) is int and ref['revision']>0):references.append(ref)
        records={};assessments={}
        if references:
            linked=tx.conn.execute("SELECT id,revision,source,data FROM projections WHERE kind='incident' "
                'AND (id,revision) IN (SELECT id,revision FROM jsonb_to_recordset(%s::jsonb) AS r(id text,revision integer))',
                (Jsonb(references),)).fetchall()
            for identifier,revision,origin,data in linked:
                try:
                    validate(data)
                    if (data['incident_id']!=identifier or data['revision']!=revision
                            or origin!='trusted-service'):raise ValueError('Incident origin/identity mismatch')
                    records[(identifier,revision)]=data
                except (ValueError,TypeError,KeyError):pass
            if tx.conn.execute("SELECT to_regclass('hs_incident_assessment')").fetchone()[0]:
                assessed=tx.conn.execute('SELECT DISTINCT ON(incident_id,incident_revision) incident_id,incident_revision, '
                    'id,assessment,reason,actor,at FROM hs_incident_assessment WHERE '
                    '(incident_id,incident_revision) IN (SELECT id,revision FROM jsonb_to_recordset(%s::jsonb) '
                    'AS r(id text,revision integer)) ORDER BY incident_id,incident_revision,id DESC',
                    (Jsonb(references),)).fetchall()
                assessments={(r[0],r[1]):{'assessment_id':str(r[2]),'state':r[3],
                    'reason':r[4],'actor':r[5],'at':r[6].isoformat()} for r in assessed}

        grouped=defaultdict(list);unlinked=[]
        for fact in facts:
            item=fact['item'];ref=item.get('incident_ref')
            key=(ref.get('id'),ref.get('revision')) if isinstance(ref,dict) else None
            if fact['origin']!='trusted-service' or key not in records:
                unlinked.append({'source':fact['source'],'record_id':fact['record_id'],
                    'source_revision':fact['source_revision'],'state':fact['state'],
                    'fresh':fact['fresh'],'reason':'MISSING_OR_UNVERIFIED_INCIDENT_LINK'})
                continue
            if fact['state'] in UNKNOWN and 'last_known_state' not in fact:
                unlinked.append({'source':fact['source'],'record_id':fact['record_id'],
                    'source_revision':fact['source_revision'],'state':fact['state'],
                    'fresh':fact['fresh'],'reason':'ACTIVITY_STATE_UNKNOWN'})
                continue
            fact['incident_ref']=ref
            if 'record_revision' in item:fact['record_revision']=item['record_revision']
            fact['activity_type']=item.get('activity_type',fact['source'])
            grouped[ref['id']].append(fact)

        cases=[];counts={'anomaly':0,'confirmed_attack':0,'incident':0}
        for case_id,items in sorted(grouped.items()):
            refs=sorted({(i['incident_ref']['id'],i['incident_ref']['revision']) for i in items})
            refs=[{'id':identifier,'revision':revision} for identifier,revision in refs]
            classifications=set()
            if any(i['source']=='anomaly' for i in items):classifications.add('anomaly')
            if any(i['source']=='incident' for i in items):classifications.add('incident')
            confirmed_refs=[]
            for item in items:
                ref=item['incident_ref'];assessment=assessments.get((ref['id'],ref['revision']))
                if item['activity_type']=='attack' and assessment and assessment['state']=='confirmed':
                    classifications.add('confirmed_attack');confirmed_refs.append(ref)
            for kind in classifications:counts[kind]+=1
            clean=[{k:v for k,v in item.items() if k!='item'} for item in items]
            cases.append({'case_id':case_id,'incident_refs':refs,
                'incident_ref':refs[0] if len(refs)==1 else None,
                'classifications':sorted(classifications),'confirmed_attack_refs':confirmed_refs,
                'items':clean,'assessment_records':[
                    {'incident_ref':ref,**assessments[(ref['id'],ref['revision'])]}
                    for ref in refs if (ref['id'],ref['revision']) in assessments],
                'links':[{'rel':'incident_dossier','incident_ref':ref,
                    'path':'/api/v1/p11/incidents/'+quote(ref['id'],safe='')+'/dossier?incident_revision='+str(ref['revision'])}
                    for ref in refs]})
        sources=deepcopy(legacy['sources'])
        for source in sources:
            code=reason_for_source(source)
            source['reason_codes']=[] if code is None else [code]
            source['freshness_policy']={'version':'operational-authority.v1','max_age_seconds':30,'clock':'postgresql'}
            if code:reasons.append({'code':code,'source':source['source']})
        reasons.extend({'code':item['reason'],'source':item['source'],'record_id':item['record_id']} for item in unlinked)
        coverage=legacy['coverage']
        if unlinked and coverage=='complete':coverage='partial'
        sufficient=coverage=='complete' and not unlinked
        active=bool(cases or unlinked)
        status='active' if active else ('none_active' if sufficient else coverage)
        observed=[s['observed_at'] for s in sources if s['observed_at'] is not None]
        result['cases']={'contract_version':2,'status':status,'coverage':coverage,
            'count_basis':'distinct_incident_id','known_active_count':len(cases) if cases or not unlinked else None,
            'total_active_count':len(cases) if sufficient else None,
            'classification_counts':counts,'classification_count_basis':'distinct_incident_id_per_class',
            'classification_overlap':True,'unlinked_active_item_count':len(unlinked),
            'observation_sufficient':sufficient,'observed_at':min(observed) if len(observed)==len(CASE_SOURCES) else None,
            'observation_basis':'oldest_required_source_report','sources':sources,'items':cases,
            'unlinked_items':unlinked,'reason_codes':reasons}
        result['source_cases']=legacy
        return result
