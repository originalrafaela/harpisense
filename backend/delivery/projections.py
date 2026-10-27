"""Read-only projection API for trusted domain writers. No policy or executor logic."""
import os, hmac
from datetime import datetime,timezone
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

security=HTTPBasic(auto_error=False)
KINDS={'asset','telemetry','network_event','window','detection','xai','evidence','incident','risk','decision','approval','execution','verification','bitnet'}
class Record(BaseModel):
 id:str
 revision:int=1
 source:str
 data:dict
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
  raise HTTPException(503, 'Deterministic HarpIA adapter required')
 return app
