"""Registro SQLite de revisões administrativas. Autenticação pertence ao backend chamador."""
import json
import sqlite3
from .core import decide,need
from harpisense_contracts import fingerprint,validate,validate_links
from harpisense_contracts.validation import timestamp


class ApprovalStore:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, state TEXT NOT NULL, result TEXT)')
        self.db.commit()

    def close(self):self.db.close()

    def register(self,bundle):
        d=bundle['decision'];validate(d);validate(bundle['incident'])
        need(d['status']=='REQUEST_APPROVAL','Somente pendências podem ser registradas')
        raw=json.dumps(bundle,sort_keys=True,allow_nan=False)
        with self.db:
            row=self.db.execute('SELECT snapshot FROM reviews WHERE id=?',(d['decision_id'],)).fetchone()
            if row:need(row[0]==raw,'Conflito no ID de decisão')
            else:self.db.execute('INSERT INTO reviews VALUES (?,?,?,NULL)',(d['decision_id'],raw,'PENDING'))
        return d['decision_id']

    def review(self,decision_id,*,ctx,now,mode,principal,allow,current_incident_revision,config=None):
        # principal é produzido pela autenticação admin do backend, NÃO por campos da requisição/LLM.
        need(type(principal) is str and principal.strip(),'Administrador autenticado obrigatório')
        need(type(allow) is bool,'Revisão inválida')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT snapshot,state FROM reviews WHERE id=?',(decision_id,)).fetchone()
            need(row is not None and row[1]=='PENDING','Pedido ausente ou já revisado')
            old=json.loads(row[0]);d=old['decision'];i=old['incident']
            need(type(current_incident_revision) is int and current_incident_revision==i['revision'],'Revisão atual diverge do pedido')
            need(timestamp(d['created_at'])<=timestamp(now)<timestamp(d['valid_until']),'Pedido expirado')
            fresh=decide(ctx,mode=mode,now=now,config=config,proposal=d['action'])
            n=fresh['decision']
            need(mode==d['autonomy_mode'] and n['policy_version']==d['policy_version'],'Modo/política alterado')
            need(fresh['audit']['context_fingerprint']==old['audit']['context_fingerprint'],'Contexto mudou; criar nova decisão')
            need(n['status']=='REQUEST_APPROVAL' and n['action_fingerprint']==d['action_fingerprint'],'Revalidação falhou')
            # Preserva a revisão originalmente apresentada; backend deve invalidar pendências ao revisar incidente.
            fresh['incident']=i;n['incident_revision']=i['revision'];n['supersedes_decision_id']=decision_id
            n['valid_until']=min(timestamp(n['valid_until']),timestamp(d['valid_until'])).isoformat()
            n['decision_id']='dec-'+fingerprint([decision_id,principal,now,allow])
            n['status']='AUTHORIZED' if allow else 'DENIED';n['reason_codes']=['ADMIN_APPROVED' if allow else 'ADMIN_REJECTED']
            if allow:n['approval']=dict(approval_id='approval-'+fingerprint([decision_id,principal,now]),decision_id=n['decision_id'],
                action_fingerprint=n['action_fingerprint'],policy_version=n['policy_version'],approved_by=principal,
                approved_at=now,expires_at=n['valid_until'])
            validate_links(detections=ctx['detections'],explanations=ctx['explanations'],incidents=[i],decisions=[n])
            self.db.execute('UPDATE reviews SET state=?,result=? WHERE id=?',('APPROVED' if allow else 'REJECTED',json.dumps(fresh,sort_keys=True),decision_id))
            self.db.commit();return fresh
        except Exception:
            self.db.rollback();raise

    def invalidate(self,decision_id):
        with self.db:self.db.execute("UPDATE reviews SET state='INVALIDATED' WHERE id=? AND state='PENDING'",(decision_id,))
