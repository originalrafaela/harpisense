import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const url='http://127.0.0.1:5186';
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export default async function start(){
 // Refuse an occupied port: never test against another agent's development server.
 let occupied=false;
 try{const response=await fetch(url,{signal:AbortSignal.timeout(500)});await response.body?.cancel();occupied=true}catch{}
 if(occupied)throw new Error('A porta isolada 5186 já está ocupada.');
 const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5186','--strictPort'],{
  cwd:fileURLToPath(new URL('..',import.meta.url)),stdio:'ignore',windowsHide:true,
 });
 let stopped=false;
 server.once('exit',()=>{stopped=true});
 const stop=async()=>{
  if(stopped)return;
  const exited=new Promise(resolve=>server.once('exit',resolve));
  server.kill('SIGTERM');
  if(!await Promise.race([exited.then(()=>true),wait(3000).then(()=>false)])){
   server.kill('SIGKILL');await Promise.race([exited,wait(3000)]);
  }
  if(!stopped)throw new Error('Servidor isolado não encerrou.');
 };
 try{
  for(let i=0;i<100;i++){
   if(stopped)throw new Error('Servidor isolado encerrou na inicialização.');
   try{const response=await fetch(url,{signal:AbortSignal.timeout(500)});await response.body?.cancel();if(response.ok)return stop}catch{}
   await wait(100);
  }
  throw new Error('Servidor isolado não iniciou.');
 }catch(error){await stop();throw error}
}
