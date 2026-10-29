"""Functional localhost review console; server calls only official public model on user action/start."""
from __future__ import annotations
import json, os, shutil, subprocess, threading, time, traceback, uuid, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from html import escape
from . import backend
from .engine import (task_index,now,save_json,media_probe,file_sha,write_zip,validate_review,decision,action_prompt,
                     CRITERIA,SPACE)

STYLE='''body{font:15px system-ui,-apple-system,Arial;background:#f3f6fb;color:#172338;margin:0}
main{max-width:1050px;margin:45px auto;padding:0 16px}h1{font-size:27px}h2{font-size:19px}
.card{background:white;border:1px solid #dce3ed;border-radius:12px;padding:20px;margin:18px 0}
label{display:block;font-weight:550;margin:10px 0 5px}button,select,input,textarea{font:inherit}
button{background:#204bd2;color:white;border:0;border-radius:9px;padding:12px 17px;cursor:pointer}
button:disabled{opacity:.4} .secondary{background:#364555}select,input,textarea{padding:8px;border-radius:6px;border:1px solid #ced6e2}
textarea{width:95%;min-height:60px} video{width:100%;max-height:430px;background:black}
small,.muted{color:#55677d}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}
.status{font-weight:600} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:13px}
fieldset{border:1px solid #ddd;border-radius:10px} .question{margin:9px 0;padding:6px}
.btnline{display:flex;gap:9px;flex-wrap:wrap} .warn{color:#933300} .good{color:#126630}
'''
HTML='''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIL v4.3 · Genuine Prompt-to-Video</title><style>'''+STYLE+'''</style></head><body><main>
<h1>Agent Intelligence Lab · v4.3</h1><p><b>Genuine text-to-video generation</b> via the official public Lightricks LTX-2.5 model Space.
No stock images, still-image animation, or synthetic stand-in generation. Free/shared ZeroGPU availability is not guaranteed.</p>
<div class="card"><h2>Evidence and rights controls</h2><p>Video appearance, frame differences and successful decoding do not establish prompt adherence.
Only a documented real model invocation can create a generative-video receipt. Human ratings are not independently verified.</p>
<p class="muted">Backend: <a href="https://huggingface.co/spaces/Lightricks/LTX-2.5" target="_blank" rel="noopener">Official LTX-2.5 Space</a>.
Public benchmark prompts only. Unauthenticated shared-GPU quota by default. No billed API is invoked; provider cost unknown.
The 8 GB Mac does not load large video-generation weights.</p></div>
<div class="card"><h2>Run a frozen prompt</h2><label for="task">Prompt</label><select id="task"></select><pre id="prompt" class="muted"></pre>
<div class="btnline"><button id="b1" onclick="create('B1_FIRST')">Generate competent baseline</button><button class="secondary" id="retry" onclick="create('B1_COMPETENT_RETRY')">Competent review-guided retry</button><button id="ail" onclick="create('AIL_SELECTIVE')">Execute AIL conditional action</button></div>
<p class="muted">Each generation may consume shared GPU quota. AIL will refuse unnecessary regeneration and require a completed quality review.</p></div>
<div class="card"><h2>Current execution status</h2><div class="status" id="summary">Loading receipts…</div><pre id="logs"></pre></div>
<div class="card"><h2>Generated videos and reviews</h2><div id="clips"></div></div>
<div class="card"><h2>Reproducibility and results</h2><p>All media remains in the Mac run directory. Reports update after every completion or review. ZIP excludes media and any credentials.
<strong>Generated videos are never automatically marked approved.</strong></p><p id="zip"></p></div></main>
<script>
let state={},tasks={},revs={};
function h(s){return String(s??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));}
async function getState(){try{let r=await fetch('/api/state');state=await r.json();tasks=state.task_specs;document.getElementById('summary').textContent=state.status+' | '+state.completed_calls+' real model generation calls | '+state.records.length+' attempts';
document.getElementById('logs').textContent=(state.events||[]).slice(-9).map(x=>x.time+' '+x.text).join('\n');
document.getElementById('zip').textContent=state.result_zip||'Not packaged';
let sel=document.getElementById('task');let curr=sel.value;if(sel.options.length!==Object.keys(tasks).length){sel.innerHTML=Object.keys(tasks).filter(x=>x.startsWith('VID')).map(x=>`<option value="${h(x)}">${h(x)}</option>`).join('');sel.value=tasks[curr]?curr:'VID-03-LIBRARY-HANDOFF';sel.onchange=showPrompt;}
showPrompt();renderClips();}catch(e){document.getElementById('summary').textContent='Dashboard request error: '+e}}
function showPrompt(){let k=document.getElementById('task').value;document.getElementById('prompt').textContent=(tasks[k]||{}).prompt||''}
async function create(arm){let task=document.getElementById('task').value;if(!confirm('Send frozen public prompt to external LTX-2.5 ZeroGPU service? This may use your available GPU quota.'))return;
let resp=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:task,arm})});let out=await resp.json();if(!resp.ok)alert(out.error||'Generation refused');await getState();}
function reviewForm(r){let eventlist=(tasks[r.task_id]||{}).events_in_order||[];
let rows=['prompt_elements','event_order','subject_motion','identity_continuity','visual_quality','safety_constraints']
.map(k=>`<label>${h(k.replace(/_/g,' '))} <select id="sc-${r.clip_id}-${k}">${[0,1,2,3,4].map(v=>`<option value="${v}" ${v===2?'selected':''}>${v}</option>`).join('')}</select></label>`).join('');
let ev=eventlist.map((x,i)=>`<div class="question">${h(x)} <select id="ev-${r.clip_id}-${i}"><option value="uncertain">Uncertain</option><option value="present">Present</option><option value="partial">Partial</option><option value="missing">Missing</option></select></div>`).join('');
return `<details><summary>Score prompt adherence and motion (0 = absent; 4 = correct)</summary><div class="grid">${rows}</div><fieldset><legend>Required events in order</legend>${ev}</fieldset>
<label>Review notes</label><textarea id="note-${r.clip_id}"></textarea><label><input type="checkbox" id="ext-${r.clip_id}"> I am an external reviewer (self-report only)</label>
<p><button onclick="submitReview('${r.clip_id}')">Submit quality review</button></p></details>`;}
function renderClips(){let sig=(state.records||[]).map(r=>r.clip_id+':'+r.status+':'+Boolean(r.review)).join('|');if(sig===window._renderSig)return;window._renderSig=sig;let box=document.getElementById('clips');box.innerHTML=(state.records||[]).map(r=>`<section class="card"><h3>${h(r.task_id)} · anonymous clip ${h(r.clip_id)}</h3>
<p class="muted">Status: ${h(r.status)} | Model: ${h(r.model||'pending')} | Duration: ${h(r.probe?.duration_s||'pending')} s</p>
${r.status==='COMPLETE' ? `<video controls preload="metadata" src="/media/${encodeURIComponent(r.clip_id)}"></video>${reviewForm(r)}`:''}
${r.error?`<pre class="warn">${h(r.error)}</pre>`:''}
${r.review?`<p class="good">Review received (${h(r.review.reviewer_kind)}). Next-action assessment: ${h(r.decision?.action||'unknown')}</p>`:''}
</section>`).join('')||'<p>No model-generated video yet. An unavailable public GPU does not create synthetic results.</p>';}
async function submitReview(id){let r=state.records.find(x=>x.clip_id===id);let events={};
(r.task_specs?.events_in_order || tasks[r.task_id]?.events_in_order||[]).forEach((e,i)=>events[e]=document.getElementById(`ev-${id}-${i}`).value);
let scores={};['prompt_elements','event_order','subject_motion','identity_continuity','visual_quality','safety_constraints'].forEach(k=>scores[k]=Number(document.getElementById(`sc-${id}-${k}`).value));
let data={clip_id:id,scores,events,notes:document.getElementById('note-'+id).value,external_reviewer:document.getElementById('ext-'+id).checked};
let resp=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let out=await resp.json();if(!resp.ok)alert(out.error);await getState();}
getState();setInterval(getState,4000);
</script></body></html>'''

class Session:
    def __init__(self,root,prompts_path,auto_task='VID-03-LIBRARY-HANDOFF',max_calls=4):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.tasks=task_index(prompts_path);self.lock=threading.RLock()
        self.max_calls=int(max_calls);self.calls_started=0;self.completed_calls=0;self.records=[];self.events=[];self.status='READY'
        self.auto_task=auto_task;self.upload=None
        self._log('Session initialized, official remote generation only; independent approval not yet established')
        self.persist()
    def _log(self,s):
        self.events.append({'time':now(),'text':str(s)[:420]})
    def _raw(self):
        return {'status':self.status,'records':self.records,'events':self.events,'calls_started':self.calls_started,
                'completed_calls':self.completed_calls,'task_specs':{k:v for k,v in self.tasks.items() if v['modality']=='text_to_video'},
                'result_zip':str(self.upload) if self.upload else None}
    def persist(self):
        with self.lock:
            save_json(self.root/'generative_receipts_v43.json',{'run_id':self.root.name,'utc':now(),'provider':SPACE,
                'status':self.status,'calls_started':self.calls_started,'completed_calls':self.completed_calls,
                'records':self.records,'events':self.events,
                'claim':'EXPERIMENTAL_REAL_VIDEO_OUTPUT_ONLY_WHEN_RECEIPT_AND_MP4_PRESENT',
                'customer_outcomes':'NOT_MEASURED','cost_usd':'UNKNOWN_NO_BILLING_RECEIPT',
                'competitive_superiority':'NOT_ESTABLISHED'})
            self.upload=write_zip(self.root)
    def public(self):
        with self.lock:return json.loads(json.dumps(self._raw()))
    def latest_review(self,task_id):
        for r in reversed(self.records):
            if r['task_id']==task_id and r.get('review'):return r['review']
        return None
    def start(self,task_id,arm):
        with self.lock:
            if task_id not in self.tasks or self.tasks[task_id]['modality']!='text_to_video':raise ValueError('UNKNOWN_VIDEO_PROMPT')
            if arm not in ('B1_FIRST','B1_COMPETENT_RETRY','AIL_SELECTIVE'):raise ValueError('UNKNOWN_POLICY_ARM')
            if any(r['status'] in ('RUNNING','QUEUED') for r in self.records):raise ValueError('MODEL_GENERATION_ALREADY_RUNNING')
            review=self.latest_review(task_id)
            needed=1;decision_record=None
            if arm!='B1_FIRST':
                if not review:raise ValueError('REVIEW_REQUIRED_BEFORE_INTERVENTION')
                dec=decision(self.tasks[task_id],review,self.max_calls-self.calls_started)
                if arm=='AIL_SELECTIVE':
                    if dec['action'] in ('STOP_NO_REGEN','HOLD_BUDGET','HOLD_BUDGET_MULTISHOT','HOLD_REVIEW_UNKNOWN'):
                        self._log('AIL action not spent: '+dec['action']);self.persist()
                        raise ValueError(dec['action']+':'+dec.get('reason',''))
                    if dec['action']=='GENERATE_MULTISHOT':needed=dec['needed_calls']
                decision_record=dec
            if self.calls_started+needed>self.max_calls:raise ValueError('GENERATION_CALL_BUDGET_EXHAUSTED')
            if arm=='B1_FIRST': prompt=self.tasks[task_id]['prompt']
            elif arm=='B1_COMPETENT_RETRY':prompt=action_prompt(self.tasks[task_id],review,arm)
            else: prompt=action_prompt(self.tasks[task_id],review,'AIL_STRUCTURED_REPAIR') if needed==1 else None
            clip_id='clip-'+uuid.uuid4().hex[:12]
            r={'clip_id':clip_id,'task_id':task_id,'arm_hidden_for_review':arm,'status':'QUEUED','created_utc':now(),
               'prompt_sent':prompt,'seed':42,'generation_call_budget':needed,'model':backend.MODEL,
               'decision_before_action':decision_record,'receipt':None,'probe':None,'review':None,'error':None}
            self.records.append(r);self.calls_started+=needed;self.status='GENERATING';self._log(f'Queued {arm} on {task_id} ({needed} actual provider call(s) reserved)')
            self.persist()
            thread=threading.Thread(target=self._execute,args=(r,),daemon=True);thread.start()
            return r['clip_id']
    def _execute(self,r):
        clips=[]; task=self.tasks[r['task_id']]; count=r['generation_call_budget']
        try:
            with self.lock:r['status']='RUNNING';self.persist()
            for j in range(count):
                if count>1:
                    sub=task['shot_decomposition_option'][j]; prompt=sub['prompt'];dur=min(5,max(1,sub.get('duration_target_s',3)))
                else:
                    prompt=r['prompt_sent'];dur=min(5,max(1,float(task.get('duration_target_s',5))))
                out=self.root/'media'/r['clip_id']/f'generated_{j}.mp4'
                received=backend.generate(prompt,out,seed=r['seed'],duration=dur)
                self.completed_calls+=1
                probe=media_probe(out)
                clips.append({'receipt':received,'probe':probe,'file':str(out.relative_to(self.root))})
                with self.lock:self._log(f'Model returned verified video {r["clip_id"]} shot {j+1}/{count}: {probe["duration_s"]:.2f}s');self.persist()
            if count>1:
                concat=self.root/'media'/r['clip_id']/'concat.txt'
                concat.write_text(''.join("file '"+Path(c['file']).name+"'\n" for c in clips))
                final=self.root/'media'/r['clip_id']/'generated_final.mp4'
                x=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),
                    '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(final)],capture_output=True,text=True,timeout=180)
                if x.returncode:raise ValueError('MULTISHOT_CONCAT_FAILED:'+x.stderr[:180])
                final_probe=media_probe(final)
            else:final=self.root/clips[0]['file'];final_probe=clips[0]['probe']
            with self.lock:
                r['status']='COMPLETE';r['final_media']=str(final.relative_to(self.root));r['probe']=final_probe;r['receipt']=clips;r['completed_utc']=now()
                self._log('Real model-generated MP4 saved. Semantic approval unknown.');self.status='READY';self.persist()
        except Exception as e:
            with self.lock:
                r['status']='BLOCKED_NO_MODEL_OUTPUT';r['error']=type(e).__name__+':'+str(e)[:340]
                r['partial_provider_clips']=clips;self.status='BLOCKED_PROVIDER_OR_CAPABILITY'
                self._log('Model path blocked: '+r['error']);self.persist()
    def review(self,data):
        with self.lock:
            clip=next((r for r in self.records if r['clip_id']==data.get('clip_id') and r['status']=='COMPLETE'),None)
            if clip is None:raise ValueError('UNKNOWN_OR_INCOMPLETE_CLIP')
            if clip.get('review'):raise ValueError('REVIEW_ALREADY_SUBMITTED')
            rv=validate_review(data,self.tasks[clip['task_id']]);clip['review']=rv
            clip['decision']=decision(self.tasks[clip['task_id']],rv,self.max_calls-self.calls_started)
            self._log('Review received for '+clip['clip_id']+'; recommendation '+clip['decision']['action'])
            self.persist();return clip['decision']
    def video_for(self,clip_id):
        with self.lock:
            c=next((r for r in self.records if r['clip_id']==clip_id and r['status']=='COMPLETE'),None)
            if not c:return None
            path=(self.root/c['final_media']).resolve()
            if not path.is_relative_to(self.root/'media') or not path.exists():return None
            return path


def serve(session,port=0,auto_generate=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):return
        def send(self,code,data,mimetype='application/json'):
            payload=data if isinstance(data,bytes) else data.encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',mimetype)
            self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            p=urlsplit(self.path).path
            if p=='/':return self.send(200,HTML,'text/html; charset=utf-8')
            if p=='/api/state':return self.send(200,json.dumps(session.public()))
            if p.startswith('/media/'):
                z=session.video_for(p.removeprefix('/media/'))
                if not z:return self.send(404,json.dumps({'error':'NOT_FOUND'}))
                # Use normal reads. Keep media on localhost; no traversal of untrusted paths.
                self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(z.stat().st_size));self.end_headers()
                with z.open('rb') as f:shutil.copyfileobj(f,self.wfile)
                return
            return self.send(404,json.dumps({'error':'NOT_FOUND'}))
        def do_POST(self):
            n=int(self.headers.get('Content-Length','0'))
            if n<2 or n>50000:return self.send(413,json.dumps({'error':'INVALID_REQUEST_SIZE'}))
            try: body=json.loads(self.rfile.read(n))
            except (ValueError,UnicodeError):return self.send(400,json.dumps({'error':'INVALID_JSON'}))
            try:
                if self.path=='/api/generate':
                    c=session.start(body.get('task_id'),body.get('arm'));return self.send(200,json.dumps({'queued_clip_id':c}))
                if self.path=='/api/review':
                    dec=session.review(body);return self.send(200,json.dumps({'decision':dec}))
                return self.send(404,json.dumps({'error':'UNKNOWN_ENDPOINT'}))
            except ValueError as e:return self.send(409,json.dumps({'error':str(e)}))
            except Exception as e:return self.send(500,json.dumps({'error':'SERVER_FAILED:'+type(e).__name__}))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    host=f'http://127.0.0.1:{server.server_address[1]}/'
    print('PROMPT-FIRST DASHBOARD:',host,flush=True)
    print('RESULTS ZIP:',session.upload,flush=True)
    if auto_generate:
        try:session.start(session.auto_task,'B1_FIRST')
        except ValueError as e:print('AUTO_GENERATION_BLOCKED:',e,flush=True)
    try:
        if os.environ.get('AIL_NO_BROWSER')!='1':
            import webbrowser
            webbrowser.open(host)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:
        session.persist();server.server_close()
        print('FINAL SEALED RESULTS ZIP:',session.upload,flush=True)
