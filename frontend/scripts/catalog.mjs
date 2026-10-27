import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const source=readFileSync(new URL('../../backend/domain/harpisense_catalog.py',import.meta.url),'utf8');
const rows=[...source.matchAll(/\('(C\d+)','([^']+)','([^']+)',(\d+),'([^']+)',\[([^\]]+)\]\)/g)].map(m=>({id:m[1],group:m[2],name:m[3],impact:Number(m[4]),evidence:m[5],actions:[...m[6].matchAll(/'([^']+)'/g)].map(x=>x[1])}));
if(rows.length!==9)throw Error('Catálogo oficial incompatível');
writeFileSync(new URL('../src/catalog.json',import.meta.url),JSON.stringify({source:'backend/domain/harpisense_catalog.py',sha256:createHash('sha256').update(source).digest('hex'),rows},null,2)+'\n');
