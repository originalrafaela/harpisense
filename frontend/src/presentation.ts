import {useSyncExternalStore} from 'react';
type View={display_name:string;timezone:string;status:string};
let view:View={display_name:'HarpiSense',timezone:'UTC',status:'not_loaded'};
const listeners=new Set<()=>void>();
export function setPresentation(value:any){
 const p=value?.parameters;
 let next:View={display_name:'HarpiSense',timezone:'UTC',status:'unknown'};
 if(value?.verified===true&&typeof p?.display_name==='string'&&typeof p?.timezone==='string'){
  try{new Intl.DateTimeFormat('pt-BR',{timeZone:p.timezone});next={...p,status:value.status}}catch{/* Never silently use the browser's local timezone. */}
 }
 view=next;listeners.forEach(listener=>listener());
}
export function usePresentation(){return useSyncExternalStore(listener=>{listeners.add(listener);return()=>listeners.delete(listener)},()=>view)}
export function formatTime(value:unknown){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)||!Number.isFinite(Date.parse(value)))return String(value??'Não informado');
 return new Intl.DateTimeFormat('pt-BR',{timeZone:view.timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'shortOffset'}).format(new Date(value));
}
