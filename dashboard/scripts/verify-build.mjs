import { readFileSync, readdirSync, existsSync } from 'node:fs';
const files=readdirSync('dist/assets').filter(n=>n.endsWith('.js'));
const built=files.map(n=>readFileSync(`dist/assets/${n}`,'utf8')).join('\n');
if(built.includes('Open local snapshot'))throw Error('Development file import leaked into production build.');
if(existsSync('private/preview.json')){
 const p=JSON.parse(readFileSync('private/preview.json','utf8'));
 for(const r of p.server?.positions??[])for(const key of ['id','contract']){
  if(typeof r[key]==='string'&&r[key].length>8&&built.includes(r[key]))throw Error('Private captured position found in production bundle.');
 }
}
if(existsSync('private/training-preview.json')){
 const training=JSON.parse(readFileSync('private/training-preview.json','utf8')).home?.training;
 const identifiers=[training?.campaign,...(training?.versions??[]).flatMap(r=>r.sources.map(s=>s.sha256))];
 for(const value of identifiers)if(value&&built.includes(value))throw Error('Private training evidence found in production bundle.');
}
console.log('Production bundle excludes preview controls, captured positions and training evidence.');
