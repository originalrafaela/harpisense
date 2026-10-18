import type {Row} from './api';
const at=new Date().toISOString();
const row=(id:string,data:Record<string,unknown>):Row=>({id,revision:1,source:'synthetic',created_at:at,data});
export const demo:Record<string,Row[]>={
 asset:[row('poste-1',{device_id:'harpisense.poste.1',name:'Poste 1',type:'Físico · ESP32',components:['LED','LDR']}),row('poste-2',{device_id:'harpisense.poste.2',name:'Poste 2',type:'Simulado · Ubuntu',components:['Simulador de telemetria']})],
 telemetry:[row('demo-t1',{device_id:'harpisense.poste.1',observed_at:at,measurements:{ldr_raw:640},status:{led:true}}),row('demo-t2',{device_id:'harpisense.poste.2',observed_at:at,measurements:{temperature_c:23},status:{}})],
 incident:[row('inc-demo',{incident_id:'inc-demo',scenario_id:'C01',status:'OPEN',device_id:'harpisense.poste.2',risk:{score:null,level:'UNKNOWN'},evidence_refs:[],decision_status:'OBSERVE_ONLY'})],
 approval:[], execution:[], decision:[], detection:[], xai:[],risk:[], evidence:[],verification:[],
 network_event:[row('evt-demo',{observed_at:at,event_type:'network_event',source_ip:'Origem de exemplo',destination_ip:'Broker de exemplo',protocol:'TCP',status:'Exemplo sintético'})],
 bitnet:[row('explain-demo',{incident_id:'inc-demo',source:'deterministic_fallback',text:'Exemplo de explicação: a classificação e o risco não foram fornecidos. Não há autorização de execução.'})]
};
export const demoHealth={api:'unknown',projection_store:'unknown',broker:'unknown',rf:'unknown',if:'unknown',bitnet:'not_verified',executor:'unknown'};
