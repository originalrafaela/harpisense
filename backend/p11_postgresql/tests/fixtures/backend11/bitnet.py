"""Deterministic fallback; optional local HTTP BitNet adapter, no tools/actions."""
import os,json,time,urllib.request,urllib.parse

def fallback(context):
 facts=context.get('facts',{})
 return {'source':'deterministic_fallback','text':'Incidente '+str(context.get('incident_id'))+'; revisão '+str(context.get('revision'))+'. Estado registrado: '+str(facts.get('status','não informado'))+'. Consulte os dados estruturados para risco, evidências e execução.','revision':context.get('revision')}

def explanation(context,transport=None):
 base=fallback(context)
 endpoint=os.getenv('HARPISENSE_BITNET_LOCAL_ENDPOINT','')
 if not endpoint or not endpoint.startswith('http://127.0.0.1:'):
  return {**base,'bitnet_status':'not_configured'}
 # Never send commands, credentials or arbitrary logs. Restrict to allowlisted scalar fields.
 facts=context.get('facts',{})
 safe={k:facts[k] for k in ('status','scenario_id','risk_level','decision_status') if k in facts and isinstance(facts[k],(str,int,float,bool))}
 payload=json.dumps({'prompt':'Explique somente os fatos; não autorize ações: '+json.dumps(safe,ensure_ascii=False),'max_tokens':160}).encode()
 try:
  if transport is None:
   req=urllib.request.Request(endpoint,data=payload,headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=3) as resp:result=json.loads(resp.read(8192))
  else:result=transport(payload)
  answer=result.get('text')
  if not isinstance(answer,str) or not answer.strip() or len(answer)>3000:raise ValueError('invalid output')
  return {'source':'bitnet_unverified_text','text':answer,'revision':context.get('revision'),'bitnet_status':'responded_unverified'}
 except Exception:
  return {**base,'bitnet_status':'unavailable_or_timeout'}
