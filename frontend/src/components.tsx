import {useState,type ReactNode} from 'react';
import type {Row} from './api';
export const show=(v:unknown):string=>v===null||v===undefined?'Não informado':typeof v==='object'?JSON.stringify(v):String(v);
export function Panel({title,children}:{title:string;children:ReactNode}){return <section className="panel"><h2>{title}</h2>{children}</section>}
export function Badge({children}:{children:ReactNode}){return <span className="badge">{children}</span>}
export function Empty({children='Sem registros nesta consulta.'}:{children?:ReactNode}){return <p className="empty">ⓘ {children}</p>}
export function Records({rows,columns}:{rows:Row[];columns:[string,string][]}){
 const [query,setQuery]=useState('');const [selected,setSelected]=useState<Row|null>(null);
 const filtered=rows.filter(r=>JSON.stringify(r).toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')));
 return <><label className="search">Filtrar registros<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="ID, dispositivo, estado ou cenário"/></label>
 <div className="table-wrap" tabIndex={0} aria-label="Tabela com rolagem horizontal"><table><thead><tr>{columns.map(([key,label])=><th key={key}>{label}</th>)}<th>Consulta</th></tr></thead><tbody>{filtered.map(r=><tr key={r.id}>{columns.map(([key])=><td key={key}>{show(key==='id'?r.id:key==='source'?r.source:key==='data.source'?r.data.source:r.data[key])}</td>)}<td><button onClick={()=>setSelected(r)}>Detalhes</button></td></tr>)}</tbody></table></div>
 {!filtered.length&&<Empty/>}{selected&&<section className="detail" aria-label="Detalhes do registro"><div className="section-head"><h3>Registro {selected.id}</h3><button onClick={()=>setSelected(null)}>Fechar detalhes</button></div><p>Origem: {show(selected.source)} · Revisão: {show(selected.revision)}</p><pre>{JSON.stringify(selected.data,null,2)}</pre></section>}</>;
}
export function Disabled({label,reason='A API consultada não oferece esta operação.'}:{label:string;reason?:string}){return <div className="disabled"><button disabled aria-describedby={'reason-'+label}>{label}</button><small id={'reason-'+label}>{reason}</small></div>}
