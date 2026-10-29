const el=(tag, text, cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
async function api(path,opts){const r=await fetch(path,opts);const j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j;}
function showError(err){alert(String(err));}
async function load(){let d;try{d=await api('/api/state')}catch(e){document.getElementById('overview').textContent='REPORT ERROR: '+e;return;}
 const {plan,state}=d;document.getElementById('overview').textContent=`${state.artifacts.length} imported/generated shot assets; ${state.reviews.length} submitted shot reviews; ${state.local_executions.length} local modality records; ${plan.tasks.filter(t=>t.modality==='text_to_video').length} distinct video stories. Provider dollar cost: UNKNOWN.`;
 const vids=document.getElementById('videos');vids.replaceChildren();const oth=document.getElementById('other');oth.replaceChildren();
 for(const task of plan.tasks){const card=el('section');card.append(el('h3',task.task_id));card.append(el('p',task.source_prompt));if(task.modality==='text_to_video'){
  card.append(el('p',`Target continuous story: ${task.target_duration_s}s across ${task.shots.length} generated moving shots.`,'status'));
  for(const shot of task.shots){const box=el('div');box.className='card';box.append(el('h4',shot.shot_id));box.append(el('p',shot.prompt));
   const assets=state.artifacts.filter(a=>a.shot_id===shot.shot_id);if(!assets.length)box.append(el('p','NOT GENERATED/IMPORTED — no video player','warn'));
   for(const a of assets){let good=a.available===true;box.append(el('p',`${a.origin} | ${a.model} | ${a.media.duration_s.toFixed(2)}s | ${a.duration_gate} | file ${good?'verified':'missing/tampered'}`,good?'good':'warn'));
    if(good){const v=document.createElement('video');v.controls=true;v.preload='metadata';v.src='/media/'+a.id;box.append(v);const r=state.reviews.find(x=>x.artifact_id===a.id);
     if(r)box.append(el('p',`Reviewed: ${r.passed_local_rubric?'local rubric passed':'local rubric not passed'}; independent approval UNKNOWN`,'status'));
     else{const f=el('div');f.append(el('h4','Review this actual shot'));let inputs={};for(const k of d.categories){const lab=el('label',k+' (0–4): ');const s=document.createElement('select');for(let n=0;n<=4;n++){const o=el('option',String(n));o.value=n;s.append(o)}s.value=0;lab.append(s);f.append(lab);inputs[k]=s;}
       let ev={};for(const item of shot.events_covered){const lab=el('label',item+': ');const s=document.createElement('select');for(const n of ['uncertain','present','partial','missing']){const opt=el('option',n);opt.value=n;s.append(opt)}lab.append(s);f.append(lab);ev[item]=s;}
       const b=el('button','Submit local review');b.onclick=async()=>{try{await api('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({artifact_id:a.id,ratings:Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,Number(v.value)])),events:Object.fromEntries(Object.entries(ev).map(([k,v])=>[k,v.value]))})});await load()}catch(e){showError(e)}};f.append(b);box.append(f);}
    }
   }card.append(box);
  }
  const b=el('button','Assemble reviewed moving shots');b.onclick=async()=>{try{const out=await api('/api/assemble',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:task.task_id})});alert('Real FFmpeg assembly complete: '+out.output);await load()}catch(e){showError(e)}};card.append(b);
  card.append(el('p','Import externally generated, model-documented clips using the CLI commands in README_V44.md. Google Flow is a manual creator interface, not a sanctioned AIL automation API.','muted'));
  vids.append(card);
 } else {const rs=state.local_executions.filter(x=>x.task_id===task.task_id);card.append(el('p','Modality: '+task.modality));const imgs=(state.images||[]).filter(x=>x.task_id===task.task_id);for(const im of imgs){card.append(el('p',`Imported image ${im.dimensions.width}×${im.dimensions.height} · ${im.origin} · human approval UNKNOWN`,'status'));}card.append(el('p',rs.length?rs.at(-1).status:'NOT EXECUTED — provider missing or no authorized adapter','status'));if(rs.length){const pre=el('pre',JSON.stringify(rs.at(-1),null,2));card.append(pre)}oth.append(card);}}
 const res=document.getElementById('results');res.replaceChildren();res.append(el('p','No verified commercial improvement or independent approval. Local tests, media integrity and user scores are different evidence classes.'));
 const ab=state.assembled||[];for(const a of ab){const d=el('p',`${a.task_id} assembly ${a.duration_s.toFixed(2)}s · ${a.status} · independently approved: NO`);res.append(d);const v=document.createElement('video');v.controls=true;v.src='/assembly/'+encodeURIComponent(a.task_id);res.append(v);}}
load();setInterval(load,12000);
