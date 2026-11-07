"""Structured, session-authorized incident reads and immutable human assessments.

No inference, BitNet, approval, executor, mode mutation or model reclassification.
Only exact persisted references are resolved. Missing state remains explicit.
"""
from datetime import datetime
from collections import Counter
import json

import psycopg
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from typing import Literal

from admin_auth.api import PrivateRoute
from harpisense_contracts import validate, validate_links
from harpisense_contracts.execution import validate_execution_links
from xai_api.store import XAIStore, Missing
from .controls import LOCK_ID


class Conflict(ValueError):
    pass


def json_row(row):
    return {k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in row.items()}


class IncidentDossier:
    def __init__(self, store, installation_id):
        self.store, self.installation_id = store, installation_id
        self.xai = XAIStore(store._connect,installation_id,'device_id')

    @staticmethod
    def linked(cur, kind, references, missing):
        if not isinstance(references,list) or len(references)>128 or any(not isinstance(i,str) for i in references):
            missing.append({'kind':kind,'reason':'INVALID_REFERENCES'})
            return []
        result=[]
        for identifier in references:
            rows=XAIStore.rows(cur,kind,identifier)
            if len(rows)!=1:
                missing.append({'kind':kind,'id':identifier,'reason':'MISSING_OR_UNPINNED'})
            else:
                result.append(rows[0])
        return result

    @staticmethod
    def unique_rows(rows, kind, missing):
        counts=Counter(r['id'] for r in rows)
        result=[]
        for row in rows:
            if counts[row['id']]!=1:
                if not any(m.get('id')==row['id'] and m.get('kind')==kind for m in missing):
                    missing.append({'kind':kind,'id':row['id'],'reason':'UNPINNED_REVISION'})
            else:
                result.append(row)
        return result

    def dossier(self, identifier, revision=None):
        with self.store._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            incident=self.xai.select_incident(cur,identifier,revision)
            revision=incident['revision'];missing=[]
            incident_row=next(r for r in self.xai.rows(cur,'incident',identifier) if r['revision']==revision)
            origin=incident_row['source']
            records={kind:[] for kind in ('detection','window','evidence','network_event','decision','approval','execution','verification')}
            detections=self.linked(cur,'detection',incident['detection_refs'],missing)
            for row in detections:
                try:
                    validate(row['data'])
                    if row['data']['detection_id']!=row['id']:raise ValueError('Identity mismatch')
                    records['detection'].append(row)
                except (ValueError,TypeError,KeyError):
                    missing.append({'kind':'detection','id':row['id'],'reason':'INVALID_RECORD'})
            records['evidence']=self.linked(cur,'evidence',incident['evidence_refs'],missing)
            window_refs=list(dict.fromkeys(r['data']['window']['window_id'] for r in records['detection']))
            records['window']=self.linked(cur,'window',window_refs,missing)
            # Logs are explicit evidence links, never a search for another device's last log.
            event_refs=list(incident.get('network_event_refs',[]))
            for row in records['evidence']:
                refs=row['data'].get('network_event_refs',[])
                if isinstance(refs,list):event_refs.extend(refs)
            records['network_event']=self.linked(cur,'network_event',list(dict.fromkeys(event_refs)),missing)
            cur.execute("SELECT id,revision,source,data FROM projections WHERE kind='decision' "
                        "AND data->>'incident_id'=%s AND data->>'incident_revision'=%s ORDER BY id,revision",
                        (identifier,str(revision)))
            decisions=self.unique_rows(cur.fetchall(),'decision',missing)
            for row in decisions:
                try:
                    validate_links(detections=[r['data'] for r in records['detection']],explanations=[],
                                   incidents=[{**incident,'explanation_refs':[]}],decisions=[row['data']])
                    if row['data']['decision_id']!=row['id']:raise ValueError('Identity mismatch')
                    records['decision'].append(row)
                except (ValueError,TypeError,KeyError):
                    missing.append({'kind':'decision','id':row['id'],'reason':'INVALID_RECORD_OR_LINK'})
            decision_ids=[r['id'] for r in records['decision']]
            for kind in ('approval','execution'):
                cur.execute("SELECT id,revision,source,data FROM projections WHERE kind=%s AND data->>'decision_id'=ANY(%s) ORDER BY id,revision",
                            (kind,decision_ids))
                rows=self.unique_rows(cur.fetchall(),kind,missing)
                for row in rows:
                    decision=next(d['data'] for d in records['decision'] if d['id']==row['data']['decision_id'])
                    if row['data'].get('action_fingerprint')!=decision.get('action_fingerprint'):
                        missing.append({'kind':kind,'id':row['id'],'reason':'ACTION_LINK_MISMATCH'});continue
                    if kind=='execution':
                        try:validate_execution_links([row['data']],[decision])
                        except (ValueError,TypeError,KeyError):
                            missing.append({'kind':kind,'id':row['id'],'reason':'INVALID_RECORD'});continue
                    records[kind].append(row)
            for decision in records['decision']:
                approval=decision['data'].get('approval')
                if approval and not any(r['id']==approval['approval_id'] for r in records['approval']):
                    records['approval'].append({'id':approval['approval_id'],'revision':decision['revision'],
                        'source':decision['source'],'data':approval})
            execution_ids=[r['id'] for r in records['execution']]
            cur.execute("SELECT id,revision,source,data FROM projections WHERE kind='verification' "
                        "AND data->>'execution_id'=ANY(%s) ORDER BY id,revision",(execution_ids,))
            records['verification']=self.unique_rows(cur.fetchall(),'verification',missing)
            # Exact-revision sidecars, not the current controls/configuration.
            records['profile']=[];records['policy']=[]
            for decision in records['decision']:
                cur.execute('SELECT historical_profile,policy,origin FROM hs_decision_snapshot '
                            'WHERE decision_id=%s AND decision_revision=%s',
                            (decision['id'],decision['revision']))
                snapshot=cur.fetchone()
                if snapshot and snapshot['origin']==decision['source']:
                    for kind,key in (('profile','historical_profile'),('policy','policy')):
                        records[kind].append({'id':decision['id'],'revision':decision['revision'],
                            'source':snapshot['origin'],'data':snapshot[key]})
                else:
                    missing.append({'kind':'decision_snapshot','id':decision['id'],
                                    'reason':'NO_LINKED_PROFILE_POLICY_SNAPSHOT'})
            cur.execute('SELECT id,source,source_revision,record_id,origin,data,at FROM hs_activity_event '
                        "WHERE data->'incident_ref'->>'id'=%s AND data->'incident_ref'->>'revision'=%s ORDER BY id",
                        (identifier,str(revision)))
            activity=[json_row(r) for r in cur.fetchall()]
            cur.execute('SELECT * FROM hs_incident_assessment WHERE incident_id=%s AND incident_revision=%s ORDER BY id DESC',
                        (identifier,revision))
            assessments=[json_row(r) for r in cur.fetchall()]
            assessment=assessments[0] if assessments else None
            analysis=[self.xai.detection_view(cur,ref,incident) for ref in incident['detection_refs']]
            technical=[]
            for item in analysis:
                for explanation in item['explanations']:
                    if explanation['in_incident_explanation_refs'] is not True:continue
                    r=explanation['record'];w=item['window']
                    main=max(r['contributions'],key=lambda c:abs(c['contribution']),default=None)
                    text=(f"{main['feature']}: contribuição {main['contribution']:+.6g} na saída registrada."
                          if main else 'Sem contribuições registradas.')
                    technical.append({'incident_ref':{'id':identifier,'revision':revision},
                        'detection_id':item['detection_id'],'asset':item['asset'],
                        'window':{'id':w['window_id'],'start':w['start'],'end':w['end'],
                            'collection_session_id':w['collection_session_id'],'sensor_id':w['sensor_id']},
                        'model':item['model'],'method':r['method'],'explainer_version':r['explainer_version'],
                        'output':{'kind':r['target']['output'],'class_label':r['target']['class_label']},
                        'reference':{'ref':r['reference_ref'],'value':r['base_value']},'result':{'value':r['output_value']},
                        'principal_contribution':main,'summary':text,'summary_source':'deterministic',
                        'explanation':{'id':explanation['id'],'projection_revision':explanation['projection_revision'],
                                       'in_incident_explanation_refs':True,'record':r},
                        'risk_mapping':explanation['risk_mapping'],
                        'source':'persisted_xai'})
            accepted_ids={c['explanation']['id'] for c in technical}
            for ref in incident['explanation_refs']:
                if ref not in accepted_ids:
                    missing.append({'kind':'xai','id':ref,'reason':'MISSING_INVALID_OR_UNPINNED_EXPLANATION'})
            assets={a['asset']['technical_id']:a['asset'] for a in analysis if isinstance(a.get('asset'),dict)}
            asset=next(iter(assets.values())) if len(assets)==1 else {'technical_id':None,'display_name':None}
            if len(assets)!=1:missing.append({'kind':'asset','reason':'MISSING_OR_MULTIPLE_ASSETS'})
            modes={d['data']['autonomy_mode'] for d in records['decision']}
            mode='M'+str(next(iter(modes))) if len(modes)==1 else None
            if mode is None:missing.append({'kind':'operational_mode','reason':'NO_UNAMBIGUOUS_DECISION_SNAPSHOT'})
            observations=[]
            for row in records['detection']:
                d=row['data']
                observations.append({'detection_id':row['id'],'classification':d['classification'],'anomaly':d['anomaly']})
            if not records['execution']:missing.append({'kind':'execution','reason':'NO_LINKED_EXECUTION_RECORD'})
            card={'incident_id':identifier,'occurred_at':incident['created_at'],'asset':asset,
                'origin':{'value':origin,'source':'incident_projection'},
                'anomaly':{'state':'recorded' if observations else 'unknown','observations':observations},
                'attack_assessment':({'state':assessment['assessment'],'assessment_id':str(assessment['id']),
                    'actor':assessment['actor'],'at':assessment['at'],'reason':assessment['reason']} if assessment else
                    {'state':'unassessed','assessment_id':None,'actor':None,'at':None,'reason':None}),
                'attack_situation':{'state':'recorded','value':incident['status'],'source':'incident.status'},
                'defense_decision':{'state':'recorded' if records['decision'] else 'missing','records':records['decision']},
                'defense_execution':{'state':'recorded' if records['execution'] else 'missing','records':records['execution']},
                'operational_mode':{'state':'recorded' if mode else 'unknown','value':mode}}
            for kind in records:
                if not records[kind] and not any(m['kind']==kind for m in missing):
                    missing.append({'kind':kind,'reason':'NO_LINKED_RECORD'})
            if not technical:missing.append({'kind':'xai','reason':'EXPLANATION_NOT_AVAILABLE'})
            latest=sorted(technical,key=lambda c:c['explanation']['record']['created_at'],reverse=True)[:3]
            return {'incident_ref':{'id':identifier,'revision':revision},'incident_card':card,'technical_cards':technical,
                'records':records,'logs':records['network_event'],'log_references':[r['data'].get('source_ref') for r in records['evidence'] if r['data'].get('source_ref')],
                'missing_links':missing,'assessments':assessments,'latest_explanations':latest,
                'activity':activity,'analysis_states':[{'detection_id':a['detection_id'],
                    'state':a['state'],'reason_code':a['reason_code']} for a in analysis],
                'commands':{'assessment_available':True,'approval_available':False,'execution_available':False,
                            'defense_unavailable_reason':'Admissão e executor operacional ainda não integrados.'},'read_only':True}

    def assess(self, identifier, revision, assessment, reason, actor):
        if assessment not in ('confirmed','discarded','inconclusive') or not 3<=len(reason.strip())<=1000:
            raise ValueError('INVALID_ASSESSMENT')
        with self.store._connect() as conn,conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_ID,))
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                        (json.dumps(['incident',identifier]),))
            incident=self.xai.select_incident(cur,identifier,None)
            if incident['revision']!=revision:raise Conflict('INCIDENT_REVISION_CONFLICT')
            rows=self.xai.rows(cur,'incident',identifier)
            origin=next(r['source'] for r in rows if r['revision']==revision)
            if origin not in ('synthetic','trusted-service'):origin='unknown'
            cur.execute('INSERT INTO hs_incident_assessment(incident_id,incident_revision,assessment,reason,actor,origin) '
                        'VALUES(%s,%s,%s,%s,%s,%s) RETURNING *',(identifier,revision,assessment,reason.strip(),actor,origin))
            event=json_row(cur.fetchone());event['id']=str(event['id'])
            cur.execute('INSERT INTO hs_control_audit(actor,operation,details) VALUES(%s,%s,%s)',
                        (actor,'INCIDENT_ASSESSED',Jsonb(event)))
        return {'assessment':event,'side_effects':{'profile_changed':False,'defense_approved':False,'defense_dispatched':False}}


class Assessment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    incident_revision:StrictInt=Field(ge=1)
    assessment:Literal['confirmed','discarded','inconclusive']
    reason:str=Field(min_length=3,max_length=1000,pattern=r'\S')


def install_incident_api(app, store, installation_id):
    interface=IncidentDossier(store,installation_id)
    def private(response:Response):response.headers['Cache-Control']='no-store'
    router=APIRouter(prefix='/api/v1/p11',route_class=PrivateRoute,
                     dependencies=[Depends(app.state.require_admin_session),Depends(private)])
    def invoke(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except Missing as exc:return JSONResponse({'error':{'code':str(exc)}},404,headers={'Cache-Control':'no-store'})
        except Conflict as exc:return JSONResponse({'error':{'code':str(exc)}},409,headers={'Cache-Control':'no-store'})
        except (psycopg.Error,ValueError,KeyError,TypeError):
            return JSONResponse({'error':{'code':'INCIDENT_DATA_UNAVAILABLE'}},503,headers={'Cache-Control':'no-store'})
    @router.get('/incidents/{incident_id}/dossier')
    def dossier(incident_id:str,incident_revision:int|None=Query(None,ge=1)):
        return invoke(interface.dossier,incident_id,incident_revision)
    @router.post('/incidents/{incident_id}/assessments')
    def assess(incident_id:str,body:Assessment,actor=Depends(app.state.require_admin_session)):
        return invoke(interface.assess,incident_id,body.incident_revision,body.assessment,body.reason,actor)
    app.include_router(router)
    from .action_api import install_action_api
    install_action_api(app,store)
    app.state.incident_dossier=interface
    return interface
