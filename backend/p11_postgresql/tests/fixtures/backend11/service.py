"""Read-only projection API for trusted domain writers. No policy or executor logic."""
import os, hmac, json, hashlib, sqlite3
from datetime import datetime,timezone
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from .bitnet import explanation, fallback
security=HTTPBasic(auto_error=False)
KINDS={'asset','telemetry','network_event','window','detection','xai','evidence','incident','risk','decision','approval','execution','verification','bitnet'}
class Record(BaseModel):
 id:str
 revision:int=1
 source:str
 data:dict
class Store:
 def __init__(self,path):
  self.path=path
  self.db=sqlite3.connect(path,check_same_thread=False,timeout=10)
  self.db.execute('PRAGMA busy_timeout=10000')
  self.db.executescript('CREATE TABLE IF NOT EXISTS projections(kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,source TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(kind,id,revision));CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,operation TEXT,entity TEXT,at TEXT);')
  self.db.commit()
 def insert(self,kind,item):
  if kind not in KINDS:raise ValueError('unknown kind')
  if not item.id or item.revision<1 or item.source not in {'synthetic','trusted-service'}:raise ValueError('invalid record')
  payload=json.dumps(item.data,sort_keys=True,ensure_ascii=False,separators=(',',':'))
  with self.db:
   existing=self.db.execute('SELECT data,source FROM projections WHERE kind=? AND id=? AND revision=?',(kind,item.id,item.revision)).fetchone()
   if existing:
    if existing==(payload,item.source):return False
    raise ValueError('immutable revision conflict')
   latest=self.db.execute('SELECT MAX(revision) FROM projections WHERE kind=? AND id=?',(kind,item.id)).fetchone()[0]
   if latest is not None and item.revision!=latest+1:raise ValueError('revision gap or stale update')
   if latest is None and item.revision!=1:raise ValueError('first revision must be 1')
   self.db.execute('INSERT INTO projections VALUES(?,?,?,?,?,?)',(kind,item.id,item.revision,item.source,payload,datetime.now(timezone.utc).isoformat()))
  return True
 def list(self,kind,limit=50,offset=0):
  if kind not in KINDS:raise ValueError('unknown kind')
  rows=self.db.execute('SELECT p.id,p.revision,p.source,p.data,p.created_at FROM projections p WHERE p.kind=? AND p.revision=(SELECT MAX(q.revision) FROM projections q WHERE q.kind=p.kind AND q.id=p.id) ORDER BY p.created_at DESC,p.id LIMIT ? OFFSET ?',(kind,limit,offset)).fetchall()
  return [dict(id=r[0],revision=r[1],source=r[2],data=json.loads(r[3]),created_at=r[4]) for r in rows]
 def history(self,kind,id):
  return [dict(revision=r[0],source=r[1],data=json.loads(r[2])) for r in self.db.execute('SELECT revision,source,data FROM projections WHERE kind=? AND id=? ORDER BY revision',(kind,id))]

def create_app(store,username=None,password=None,service_token=None):
 username=username or os.getenv('HARPISENSE_ADMIN_USER');password=password or os.getenv('HARPISENSE_ADMIN_PASSWORD')
 service_token=service_token or os.getenv('HARPISENSE_PROJECTION_SERVICE_TOKEN')
 if not username or not password:raise RuntimeError('Admin credentials required')
 app=FastAPI(title='HarpiSense P11 Read-only Projection API')
 def admin(c:HTTPBasicCredentials|None=Depends(security)):
  if not c or not (hmac.compare_digest(c.username,username) and hmac.compare_digest(c.password,password)):raise HTTPException(401,'Admin authentication required',headers={'WWW-Authenticate':'Basic'})
  return c.username
 @app.get('/api/v1/p11/health')
 def health(a=Depends(admin)):
  return {'api':'available','projection_store':'available','rf':'unknown','if':'unknown','broker':'unknown','executor':'unknown','bitnet':'not_verified'}
 @app.get('/api/v1/p11/{kind}')
 def records(kind:str,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),a=Depends(admin)):
  if kind not in KINDS:raise HTTPException(404)
  return store.list(kind,limit,offset)
 @app.get('/api/v1/p11/{kind}/{id}/history')
 def history(kind:str,id:str,a=Depends(admin)):
  if kind not in KINDS:raise HTTPException(404)
  return store.history(kind,id)
 @app.post('/api/v1/p11/ingest/{kind}',status_code=201)
 def ingest(kind:str,item:Record,x_service_token:str|None=Header(default=None),a=Depends(admin)):
  # Administrative basic auth alone is deliberately insufficient for service-origin writes.
  if not service_token or not x_service_token or not hmac.compare_digest(x_service_token,service_token):raise HTTPException(403,'Trusted service token required')
  if item.source!='trusted-service':raise HTTPException(422,'Only trusted-service input allowed')
  try:created=store.insert(kind,item)
  except ValueError as e:raise HTTPException(409,str(e))
  return {'created':created,'id':item.id,'revision':item.revision}
 @app.get('/api/v1/p11/explain/{incident_id}')
 def explain(incident_id:str,a=Depends(admin)):
  records=store.history('incident',incident_id)
  if not records:raise HTTPException(404)
  latest=records[-1]
  return explanation({'incident_id':incident_id,'revision':latest['revision'],'facts':latest['data']})
 return app
