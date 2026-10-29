'use strict';
const $ = s=>document.querySelector(s);
const el=(tag,text,cls)=>{let x=document.createElement(tag);if(text!==undefined&&text!==null)x.textContent=String(text);if(cls)x.className=cls;return x;};
let token='',cached=null;
function labelledInput(parent,title,value='',placeholder=''){
 const lab=el('label',title), inp=el('input');inp.className='long';inp.value=value;inp.placeholder=placeholder;lab.append(inp);parent.append(lab);return inp;
}
function button(parent,label,cb,disabled=false){const b=el('button',label);b.disabled=disabled;b.onclick=async()=>{b.disabled=true;try{await cb();await refresh();}catch(e){alert(String(e.message||e));}finally{b.disabled=disabled;}};parent.append(b);return b;}
async function read(path){const resp=await fetch(path);const data=await resp.json();if(!resp.ok)throw Error(data.error||resp.status);return data;}
async function action(path,data){if(!token)throw Error('Local session not ready');const resp=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-AIL-Session':token},body:JSON.stringify(data)});const body=await resp.json();if(!resp.ok)throw Error(body.error||resp.status);return body;}
const truth=x=>x===true?'Ready':'Not configured';
function providerState(s){const r=s.readiness,h=$('#health');h.replaceChildren();
 const tab=el('table'),head=el('tr');['Execution backend','Current status','Meaning'].forEach(t=>head.append(el('th',t)));tab.append(head);
 const items=[['Local Qwen',r.ollama.ready&&r.ollama.models.includes('qwen2.5:1.5b'),r.ollama.models.join(', ')||'Start Ollama and install qwen2.5:1.5b'],['Mac speech',r.speech.ready,r.speech.required],['FFmpeg media tooling',r.ffmpeg.ready,'Mandatory for verified video/image review'],['Public short-video proof',r.video_free_probe.ready,r.video_free_probe.type],['Production 8s video',r.video_production.ready,r.video_production.required],['Image generation',r.image_provider.ready,r.image_provider.required]];
 for(const [name,ok,note] of items){const tr=el('tr');tr.append(el('td',name),el('td',truth(ok),ok?'good':'bad'),el('td',note));tab.append(tr);}h.append(tab);
}
function historical(s){const root=$('#historical');root.replaceChildren();if(!(s.legacy_clips||[]).length){root.append(el('p','No earlier v4.3 MP4 with matching source receipt found under ~/Downloads. Existing media have not been overwritten or regenerated.','muted'));return;}
 for(const c of s.legacy_clips){const card=el('div',null,'panel');card.append(el('h3',`${c.model} · ${c.duration_s.toFixed(2)} sec`));card.append(el('p',c.original_prompt||'Prompt not recorded'));const v=el('video');v.controls=true;v.preload='metadata';v.src='/media/legacy/'+c.id;card.append(v);card.append(el('p','Original local generation receipt and SHA verified. NOT an accepted production shot.','muted'));root.append(card);}}
function comparison(s){const out=$('#comparison');out.replaceChildren();if(!s.comparison){out.append(el('p','No completed v4.5 local benchmark in this run; inspect test/receipt diagnostics.','bad'));return;}
 const tab=el('table'),head=el('tr');['Policy','Exact checks passed','Ollama calls','Reported tokens','Model seconds'].forEach(v=>head.append(el('th',v)));tab.append(head);
 for(const [key,v] of Object.entries(s.comparison)){const tr=el('tr');[key,`${v.objective_passes}/${v.tasks_attempted}`,v.model_calls,v.model_input_tokens+v.model_output_tokens,(v.sum_model_wall_seconds||0).toFixed(2)].forEach(x=>tr.append(el('td',x)));tab.append(tr)}out.append(tab);
}
function videoShot(s,task,shot){const node=el('div',null,'shot');node.append(el('h4',shot.shot_id),el('p',shot.prompt));
 const records=s.state.artifacts.filter(a=>a.shot_id===shot.shot_id),last=s.jobs.filter(j=>j.kind==='video'&&j.shot_id===shot.shot_id).at(-1);
 if(!records.length)node.append(el('p','NO VERIFIED GENERATION YET · '+(last?`Last provider job ${last.status}`:'Never requested'),'bad'));
 for(const a of records){const p=el('p',`${a.origin} · ${a.model} · ${a.media.duration_s.toFixed(2)}s · ${a.duration_gate} · ${a.available?'SHA verified':'MISSING OR TAMPERED'}`,a.available?'good':'bad');node.append(p);
   if(s.recommendations && s.recommendations[a.id]){const d=s.recommendations[a.id];node.append(el('p','Controller: '+d.action+' · '+d.reason,'muted'))}if(!a.available)continue;const video=el('video');video.controls=true;video.preload='metadata';video.src='/media/video/'+a.id;node.append(video);
   const review=s.state.reviews.find(r=>r.artifact_id===a.id);
   if(review){node.append(el('p',review.passed_local_rubric?'SELF-REVIEW PASS (not independent)':'SELF-REVIEW DID NOT PASS','status'));continue;}
   const f=el('div');f.append(el('h4','Quality review · this actual clip'));const ratings={},events={};
   for(const k of s.categories){const lab=el('label',k+' (0–4)');const select=el('select');for(let n=0;n<=4;n++){const op=el('option',n);op.value=n;select.append(op);}ratings[k]=select;lab.append(select);f.append(lab)}
   for(const event of shot.events_covered){const lab=el('label',event);const select=el('select');for(const opt of ['uncertain','present','partial','missing']){const op=el('option',opt);op.value=opt;select.append(op)}events[event]=select;lab.append(select);f.append(lab)}
   button(f,'Submit actual shot review',async()=>{await action('/api/review',{artifact_id:a.id,ratings:Object.fromEntries(Object.entries(ratings).map(([k,v])=>[k,Number(v.value)])),events:Object.fromEntries(Object.entries(events).map(([k,v])=>[k,v.value]))})});node.append(f);
 }
 if(last)node.append(el('p',`Latest attempt: ${last.status} ${last.provider_job_id?'· remote job '+last.provider_job_id:''} ${last.reason||''}`,last.status==='SUCCESS_VERIFIED'?'good':'muted'));
 const ctl=el('div');const file=labelledInput(ctl,'Import genuine MP4: absolute file path in ~/Downloads','','/Users/.../Downloads/scene.mp4');
 const provider=labelledInput(ctl,'Actual generator/provider name','Google Flow · user-attested');const model=labelledInput(ctl,'Actual model','Veo · specify actual variant');
 button(ctl,'Import and verify MP4',async()=>{if(!confirm('I have rights to this test clip and am accurately declaring its origin. Import and SHA-check it?'))return;await action('/api/import',{kind:'video',task_id:task.task_id,shot_id:shot.shot_id,path:file.value,provider:provider.value,model:model.value,rights:'AUTHORIZED_NONCONFIDENTIAL_TEST'});});
 button(ctl,'Generate 5s free LTX proof (quota)',async()=>{if(!confirm('This consumes shared GPU quota and cannot satisfy an 8-second shot. Submit a real five-second model generation?'))return;await action('/api/generate-video',{task_id:task.task_id,shot_id:shot.shot_id,backend:'ltx_5s_probe',ack:true});}, !s.readiness.video_free_probe.ready);
 const rate=labelledInput(ctl,'For billed LTX API ONLY: confirmed USD per video second','', 'Confirm current provider price in your own account');
 button(ctl,'Generate 8s via billed LTX API',async()=>{const n=Number(rate.value);if(!n||n<=0)throw Error('Enter confirmed current USD-per-second rate.');if(!confirm(`AUTHORIZE REAL BILLABLE LTX CALL: 8 seconds × $${n}/s; theoretical $${(8*n).toFixed(2)} before taxes/other fees, not an invoice. Proceed?`))return;await action('/api/generate-video',{task_id:task.task_id,shot_id:shot.shot_id,backend:'ltx_v2_8s',ack:true,price_per_second_usd:n});},!s.readiness.video_production.ready);
 node.append(ctl);return node;
}
function videos(s){const root=$('#videos');root.replaceChildren();for(const task of s.plan.tasks.filter(t=>t.modality==='text_to_video')){const card=el('section');card.append(el('h3',task.task_id),el('p',task.source_prompt),el('p',`${task.shots.length} shots · ${task.target_duration_s} seconds total (planned; NOT generated)`,'status'));
 for(const shot of task.shots)card.append(videoShot(s,task,shot));
 const assembled=(s.state.assembled||[]).find(a=>a.task_id===task.task_id);
 if(assembled){const v=el('video');v.controls=true;v.src='/media/assembly/'+task.task_id;card.append(el('h4','Assembled reviewed moving shots'),v)}
 button(card,'Assemble only fully reviewed, duration-valid moving shots',async()=>{const z=await action('/api/assemble',{task_id:task.task_id});alert('Genuine FFmpeg assembly: '+z.output);});root.append(card);}}
function images(s){const root=$('#images');root.replaceChildren();for(const task of s.plan.tasks.filter(t=>t.modality==='text_to_image')){const card=el('section');card.append(el('h3',task.task_id),el('p',task.source_prompt));const imgs=(s.state.images||[]).filter(x=>x.task_id===task.task_id);
 if(!imgs.length)card.append(el('p','NOT GENERATED OR IMPORTED','bad'));
 for(const a of imgs){card.append(el('p',`${a.provider} · ${a.model} · ${a.available?'SHA VERIFIED':'FILE INVALID'} · independent approval unknown`,a.available?'good':'bad'));if(a.available){const img=el('img');img.src='/media/image/'+a.id;img.alt='Observed generated artifact: independent fidelity unreviewed';card.append(img)}}
 const p=labelledInput(card,'Generated image path in ~/Downloads','','/Users/.../Downloads/render.png');const provider=labelledInput(card,'Actual provider','User-attested generator');const model=labelledInput(card,'Actual model','');
 button(card,'Import and verify generated image',async()=>{if(!confirm('I have rights to this nonconfidential test image. Import?'))return;await action('/api/import',{kind:'image',task_id:task.task_id,path:p.value,provider:provider.value,model:model.value,rights:'AUTHORIZED_NONCONFIDENTIAL_TEST'});});
 button(card,'Generate real image (HF provider; may bill)',async()=>{if(!confirm('Authorize an external Hugging Face inference generation. It may incur charges or fail due to quota. No rate was verified. Continue?'))return;await action('/api/generate-image',{task_id:task.task_id,ack:true})},!(s.readiness.image_provider.ready));root.append(card)}}
function localJobs(s){const root=$('#localJobs');root.replaceChildren();for(const j of s.jobs.filter(j=>j.kind==='text'||j.kind==='speech').slice(-10).reverse()){const card=el('div',null,'panel');card.append(el('p',`${j.kind.toUpperCase()} · ${j.status} · ${j.id}`,j.status==='SUCCESS_VERIFIED'?'good':'bad'));
 if(j.reason)card.append(el('p',j.reason,'muted'));
 if(j.status==='SUCCESS_VERIFIED'){card.append(el('p',`${j.wall_s}s · ${j.bytes} bytes · SHA ${j.sha256.slice(0,16)}…`));if(j.kind==='speech'){const p=el('audio');p.controls=true;p.src='/media/local/'+j.id;card.append(p)}else{const a=el('a','Open observed text');a.href='/media/local/'+j.id;a.target='_blank';card.append(a)}if(j.receipt)card.append(el('pre',JSON.stringify(j.receipt,null,2)))}root.append(card)}}
function ledger(s){const root=$('#ledger');root.replaceChildren();if(!s.jobs.length)root.append(el('p','No new-generation requests. Existing v4.5 comparisons remain available above.'));
 for(const j of s.jobs.slice().reverse()){const p=el('p',`${j.updated_utc} · ${j.kind} ${j.task_id||''} ${j.shot_id||''} · ${j.status}${j.reason?' · '+j.reason:''}`,j.status==='SUCCESS_VERIFIED'?'good':'muted');root.append(p)}}
async function refresh(){try{const s=await read('/api/state');token=s.token;cached=s;providerState(s);historical(s);comparison(s);videos(s);images(s);localJobs(s);ledger(s);}catch(e){$('#health').textContent='ERROR LOADING API: '+String(e)}}
$('#runLocal').onclick=async()=>{const btn=$('#runLocal');btn.disabled=true;try{const res=await action('/api/local',{kind:$('#localKind').value,prompt:$('#localPrompt').value,delivery_instructions:$('#delivery').value});$('#localStatus').textContent=res.status+'; open job ledger for final result';await refresh()}catch(e){$('#localStatus').textContent='ERROR: '+String(e)}finally{btn.disabled=false}};
refresh();setInterval(refresh,12000);
