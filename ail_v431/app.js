'use strict';
const names=['prompt_elements','event_order','subject_motion','identity_continuity','visual_quality','safety_constraints'];
const $=id=>document.getElementById(id);
function h(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
let lastSignature=''; let state=null; let inFlight=false;
async function refresh(){
 try {
  const res=await fetch('/api/state',{cache:'no-store'});
  if(!res.ok)throw Error('HTTP '+res.status);
  const d=await res.json();state=d;
  const available=d.tasks.filter(x=>x.status==='VIDEO_AVAILABLE').length;
  const pending=d.tasks.filter(x=>x.status==='NOT_REQUESTED').length;
  $('available').textContent=String(available);$('pending').textContent=String(pending);
  $('budget').textContent=String(d.remaining_new_calls);
  $('connection').textContent='Connected · '+d.tasks.length+' frozen video prompts · '+d.new_calls_completed+' additional completed model calls';
  $('connection').className='status success';
  $('source').textContent='Original signed receipt SHA-256: '+d.source_receipt_sha256;
  $('zip').textContent='Current report ZIP: '+d.upload_zip;
  $('events').textContent=(d.events||[]).map(x=>x.time+' '+x.text).join('\n');
  const signature=JSON.stringify(d.tasks.map(x=>[x.task_id,x.status,x.clips.map(c=>[c.clip_id,c.status,Boolean(c.review)])]));
  if(signature!==lastSignature){lastSignature=signature;render(d);}
 } catch(err){$('connection').textContent='Evidence connection failed: '+err.message;$('connection').className='status bad';}
}
function badge(task){
 const statuses={NOT_REQUESTED:'Not requested',GENERATING:'Provider generation running',VIDEO_AVAILABLE:'Verified video available',MEDIA_MISSING_OR_CORRUPT:'Original video missing or integrity failed',PROVIDER_FAILED_OR_INTERRUPTED:'Generation failed or was interrupted'};
 return statuses[task.status]||'Unknown execution status';
}
function reviewHTML(c,task){
 if(c.review)return `<p class="small success">Review recorded; independent approval remains unverified.</p>`;
 const fields=names.map(name=>`<label>${h(name.replaceAll('_',' '))} <select data-score="${name}">${[0,1,2,3,4].map(v=>`<option value="${v}" ${v===2?'selected':''}>${v} / 4</option>`).join('')}</select></label>`).join('');
 const events=(task.events_in_order||[]).map((ev,i)=>`<label>${h(ev)} <select data-event="${i}"><option value="uncertain">Uncertain</option><option value="present">Present</option><option value="partial">Partial</option><option value="missing">Missing</option></select></label>`).join('');
 return `<details data-review="${h(c.clip_id)}"><summary>Review actions, motion and quality</summary>${fields}${events}<label>Observations<textarea data-notes placeholder="What did the actual video show?"></textarea></label><label><input type="checkbox" data-external> External reviewer (self-reported only)</label><button data-submit="${h(c.clip_id)}">Submit review</button></details>`;
}
function render(d){
 $('tasks').innerHTML=d.tasks.map(t=>{
  const available=t.clips.filter(c=>c.status==='COMPLETE_VERIFIED');
  const failures=t.clips.filter(c=>c.status!=='COMPLETE_VERIFIED'&&c.status!=='QUEUED'&&c.status!=='RUNNING');
  const media=available.map(c=>`<div class="card"><p class="small">Clip ${h(c.clip_id)} · Verified provider output · ${h(c.probe?.duration_s||'?')} sec</p><video controls preload="metadata" playsinline src="/video/${encodeURIComponent(c.clip_id)}"></video>${reviewHTML(c,t)}</div>`).join('');
  const errors=failures.map(c=>`<p class="bad small">${h(c.status)}: ${h(c.error||'No media output confirmed')}</p>`).join('');
  const canGenerate=(t.status==='NOT_REQUESTED'||t.status==='PROVIDER_FAILED_OR_INTERRUPTED'||t.status==='MEDIA_MISSING_OR_CORRUPT')&&d.remaining_new_calls>0;
  const button=canGenerate?`<button class="primary" data-generate="${h(t.task_id)}">${t.status==='NOT_REQUESTED'?'Generate this prompt (real provider)':'Retry manually (uses GPU quota)'}</button>`:'';
  return `<section class="tile"><h2>${h(t.task_id)}</h2><p class="status ${t.status==='VIDEO_AVAILABLE'?'success':''}">${h(badge(t))}</p><details><summary>Exact frozen prompt</summary><pre>${h(t.prompt)}</pre></details>${button}${media}${errors}${t.status==='NOT_REQUESTED'?'<p class="small">No inference request has been made for this prompt; nothing to play.</p>':''}</section>`;
 }).join('');
 $('tasks').querySelectorAll('[data-generate]').forEach(b=>b.addEventListener('click',()=>generate(b.dataset.generate)));
 $('tasks').querySelectorAll('[data-submit]').forEach(b=>b.addEventListener('click',()=>submitReview(b.dataset.submit)));
}
async function post(url,data){
 const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const out=await res.json();if(!res.ok)throw Error(out.error||'Request failed');return out;
}
async function generate(task){
 if(inFlight)return;
 if(!window.confirm('Submit '+task+' to public Lightricks/LTX-2.5? This sends its public prompt to a third party, uses shared GPU quota and may fail. No paid API configured.'))return;
 inFlight=true;
 try{await post('/api/generate',{task_id:task});await refresh();}
 catch(ex){window.alert('Generation not started: '+ex.message);}
 finally{inFlight=false;}
}
async function submitReview(cid){
 const form=[...document.querySelectorAll('[data-review]')].find(e=>e.dataset.review===cid);
 const t=state.tasks.find(t=>t.clips.some(c=>c.clip_id===cid));
 if(!form||!t)return;
 const scores={};names.forEach(n=>scores[n]=Number(form.querySelector('[data-score="'+n+'"]').value));
 const events={};(t.events_in_order||[]).forEach((e,i)=>events[e]=form.querySelector('[data-event="'+i+'"]').value);
 const body={clip_id:cid,scores,events,notes:form.querySelector('[data-notes]').value,external_reviewer:form.querySelector('[data-external]').checked};
 try{await post('/api/review',body);await refresh();}catch(ex){window.alert('Review was not saved: '+ex.message);}
}
refresh();setInterval(refresh,4000);
