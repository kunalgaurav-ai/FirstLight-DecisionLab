'use strict';
const SVGNS='http://www.w3.org/2000/svg';
const id=x=>document.getElementById(x);
const el=(tag,attrs={},text)=>{const n=document.createElementNS(SVGNS,tag);for(let [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=String(text);return n;};
function chart(svgId, data, kind, noteId){
 const svg=id(svgId);svg.replaceChildren();const x0=67,x1=514,y0=20,y1=285;
 const good=data.filter(d=>Number.isFinite(d[kind])&&Number.isFinite(d.rate));
 if(!good.length){svg.append(el('text',{x:270,y:160,'text-anchor':'middle',fill:'#8e98a1','font-size':'14'},'Awaiting verified benchmark execution'));return;}
 const maxX=Math.max(...good.map(d=>d[kind]),1)*1.2;
 const xx=v=>x0+v/maxX*(x1-x0),yy=v=>y1-v*(y1-y0);
 for(let i=0;i<=4;i++){
   let y=y1-(i/4)*(y1-y0);
   svg.append(el('line',{x1:x0,x2:x1,y1:y,y2:y,stroke:'#edf0f2'}));
   svg.append(el('text',{x:x0-12,y:y+4,'text-anchor':'end',fill:'#69747f','font-size':'12'},Math.round(i*25)+'%'));
 }
 for(let i=0;i<=4;i++){
   let x=x0+(i/4)*(x1-x0);
   svg.append(el('line',{x1:x,x2:x,y1:y0,y2:y1,stroke:'#f0f2f4'}));
   const label=(maxX*i/4).toFixed(kind==='tokens'?0:1);
   svg.append(el('text',{x:x,y:303,'text-anchor':'middle',fill:'#69747f','font-size':'12'},label));
 }
 svg.append(el('line',{x1:x0,y1:y0,x2:x0,y2:y1,stroke:'#7e8991'}));
 svg.append(el('line',{x1:x0,y1:y1,x2:x1,y2:y1,stroke:'#7e8991'}));
 good.forEach((d,i)=>{
  let x=xx(d[kind]),y=yy(d.rate);let c=i===0?'#a9793d':'#235a8b';
  svg.append(el('circle',{cx:x,cy:y,r:6,fill:c}));
  svg.append(el('text',{x:Math.min(x+11,434),y:Math.max(y-9,15),fill:'#20272d','font-size':'11'},d.short));
 });
 svg.append(el('text',{x:290,y:337,'text-anchor':'middle',fill:'#69747f','font-size':'12'},kind==='tokens'?'Total model-reported tokens →':'Summed model wall time, seconds →'));
 id(noteId).textContent='Local strict scorer · '+data[0].count+' attempted matched cases · not official BFCL accuracy';
}
function render(doc){
 const b=doc.benchmark||{}, s=b.summary;id('status').textContent=b.state||'NO_RUN';id('count').textContent=(b.results||[]).length+' cases';
 if(b.blocking_error)id('blocker').textContent='BLOCKED: '+b.blocking_error+' — The research page stays usable; no benchmark score was invented.';
 const policies=s?.arms;
 let points=[];
 if(policies){
  const a=policies.COMPETENT_LLM_GUARDED,f=policies.FIRSTLIGHT_ADAPTIVE;
  points=[{short:'Qwen guarded',rate:a.diagnostic_rate,tokens:a.tokens,time:a.summed_wall_s,count:a.attempted},
          {short:'First Light routing',rate:f.diagnostic_rate,tokens:f.tokens,time:f.summed_wall_s,count:f.attempted}];
  id('b-rate').textContent=a.diagnostic_rate===null?'Not scored':(100*a.diagnostic_rate).toFixed(1)+'%';
  id('fl-rate').textContent=f.diagnostic_rate===null?'Not scored':(100*f.diagnostic_rate).toFixed(1)+'%';
  id('b-context').textContent=a.diagnostic_passes+'/'+a.diagnostic_scored+' locally diagnostic-scored';
  id('fl-context').textContent=f.diagnostic_passes+'/'+f.diagnostic_scored+' locally diagnostic-scored';
  id('paired').textContent=String(s.matched_cases);
 }
 chart('tokens-plot',points,'tokens','tokens-note');chart('time-plot',points,'time','time-note');
 const rows=b.results||[];const box=id('rows');box.replaceChildren();
 if(!rows.length){let msg=document.createElement('p');msg.className='muted';msg.textContent='No public benchmark cases executed yet. See the run blocker above and BENCHMARK_README_FIRST_LIGHT.md.';box.append(msg);return;}
 const t=document.createElement('table');const head=document.createElement('tr');
 ['Task','Group','Guarded local grade','First Light local grade','Reported tokens (B / FL)'].forEach(v=>{let th=document.createElement('th');th.textContent=v;head.append(th);});t.append(head);
 rows.forEach(r=>{
   const a=r.arms?.COMPETENT_LLM_GUARDED||{},f=r.arms?.FIRSTLIGHT_ADAPTIVE||{};
   const fmt=x=>x.diagnostic?.status!=='SCORED_DIAGNOSTIC'?'Unscored':(x.diagnostic.pass?'Pass':'Fail');
   const vals=[r.id,r.group,fmt(a),fmt(f),String((a.input_tokens||0)+(a.output_tokens||0))+' / '+String((f.input_tokens||0)+(f.output_tokens||0))];
   const tr=document.createElement('tr');vals.forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td);});t.append(tr);
 });box.append(t);
}
fetch('/api/state',{cache:'no-store'}).then(x=>{if(!x.ok)throw Error('HTTP '+x.status);return x.json();}).then(render).catch(e=>{id('status').textContent='Dashboard data unavailable';id('blocker').textContent=String(e);});
