import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {InstallationEntry} from '../src/installation-entry';
import {ConfigManager} from '../src/config-manager';
import {ApiError} from '../src/api';
import type {InstallationClient} from '../src/installation-state';

// Test harness only: production uses Client.get and its authenticated transport.
function makeClient():InstallationClient{return {get:async(path,method='GET',body)=>{
 const response=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok)throw new ApiError(response.status===401?'unauthorized':response.status===409?'conflict':'error','Fixture query failed');
 return response.json();
}}}
function Harness(){
 const [client,setClient]=useState(makeClient);
 const [opened,setOpened]=useState(0);
 const [visible,setVisible]=useState(true);
 const manager=new URLSearchParams(location.search).has('manager');
 const optional=new URLSearchParams(location.search).has('noCallback');
 return <><h1>Dashboard disponível</h1><button onClick={()=>setOpened(n=>n+1)}>Função operacional disponível</button><p>Interações: {opened}</p>
 <button onClick={()=>setVisible(v=>!v)}>Alternar montagem</button>
 <button onClick={()=>setClient(makeClient())}>Trocar cliente</button>
 {visible&&(manager?<ConfigManager client={client} request={client.get} logout={()=>setVisible(false)}/>:
 <InstallationEntry client={client} onOpenSettings={optional?undefined:()=>setOpened(n=>n+1)}/>)}</>;
}
createRoot(document.getElementById('root')!).render(<Harness/>);
