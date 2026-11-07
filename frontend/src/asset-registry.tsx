import {useEffect,useState,type FormEvent} from 'react';
import {object} from './api';
import {Panel} from './components';

type Request=(path:string,method?:string,body?:unknown)=>Promise<unknown>;
type Asset={device_id:string;revision:number;document:{name:string;firmware_id:string;mqtt_topic:string;enabled:boolean}};
export function AssetRegistry({request}:{request:Request}){
 const [assets,setAssets]=useState<Asset[]>([]),[device,setDevice]=useState(''),[name,setName]=useState(''),[topic,setTopic]=useState('');
 const [profile,setProfile]=useState(''),[profiles,setProfiles]=useState<string[]>([]),[topics,setTopics]=useState<string[]>([]);
 const [revision,setRevision]=useState(0),[enabled,setEnabled]=useState(true),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){setBusy(true);setError('');try{
  const [rows,catalog]=await Promise.all([request('/api/v1/config/assets'),request('/api/v1/config/catalog')]);
  if(!Array.isArray(rows)||rows.some(r=>!object(r)||typeof r.device_id!=='string'||!Number.isInteger(r.revision)||!object(r.document))||!object(catalog))throw new Error('Cadastro de ativos em formato incompatível.');
  setAssets(rows as Asset[]);const firmware=Array.isArray(catalog.firmware_profiles)?catalog.firmware_profiles.filter(object).map(f=>String(f.id)):[];setProfiles(firmware);setProfile(p=>p||firmware[0]||'');
  const mqtt=object(catalog.mqtt)?catalog.mqtt:{};const constraints=object(mqtt.constraints)?mqtt.constraints:{};const allowed=Array.isArray(constraints.topics)?constraints.topics:[];setTopics(allowed.map(String));setTopic(t=>t||String(allowed[0]||''));setReady(true);
 }catch(e){setReady(false);setError((e as Error).message)}finally{setBusy(false)}}
 useEffect(()=>{void load()},[request]);
 async function save(e:FormEvent){e.preventDefault();setBusy(true);setError('');setNotice('');try{
  await request('/api/v1/config/assets','POST',{device_id:device,expected_revision:revision,document:{name,firmware_id:profile,mqtt_topic:topic,enabled}});
  await load();setDevice('');setName('');setRevision(0);setNotice('Ativo salvo e consultado novamente no servidor.');
 }catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <Panel title="Cadastro permanente de ativos IoT"><p>O mesmo cadastro atende o primeiro uso e alterações posteriores. Registrar não grava firmware, cria credenciais MQTT nem comprova que o dispositivo está conectado. A conectividade é consultada nos estados MQTT.</p>
 <button onClick={()=>void load()} disabled={busy}>Consultar ativos cadastrados</button>{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 <ul>{assets.map(a=><li key={a.device_id}><strong>{a.document.name}</strong> · {a.device_id} · revisão {a.revision} · {a.document.enabled?'Habilitado no cadastro':'Desabilitado no cadastro'} <button onClick={()=>{setDevice(a.device_id);setName(a.document.name);setProfile(a.document.firmware_id);setTopic(a.document.mqtt_topic);setEnabled(a.document.enabled);setRevision(a.revision);setNotice('Editando cadastro existente.');}}>Editar ativo</button></li>)}</ul>
 {ready&&!assets.length&&<p>Nenhum ativo cadastrado nesta instalação.</p>}
 <form onSubmit={save}><label>Identificador do ativo<input required maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" disabled={revision>0} value={device} onChange={e=>setDevice(e.target.value)}/></label>
 <label>Nome do ativo<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Perfil de firmware<select value={profile} onChange={e=>setProfile(e.target.value)}>{profiles.map(p=><option key={p}>{p}</option>)}</select></label>
 <label>Tópico MQTT do ativo<input required list="asset-topics" value={topic} onChange={e=>setTopic(e.target.value)}/><datalist id="asset-topics">{topics.map(t=><option key={t} value={t}/>)}</datalist></label>
 <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Habilitado no cadastro</label>
 <button disabled={busy||!ready}>Salvar ativo</button><button type="button" onClick={()=>{setDevice('');setName('');setRevision(0);setEnabled(true);}}>Novo ativo</button></form></Panel>;
}
