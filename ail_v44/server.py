"""Read-heavy dashboard: actions mutate actual quality reviews/technical assemblies."""
from __future__ import annotations
import json, mimetypes, re, threading, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from .workbench import suite,get,review,assemble,artifact_valid,package,CATEGORIES

PAGE=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIL v4.4 Workflow Evidence</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;background:#f4f7fb;color:#162133;max-width:1180px;margin:25px auto;padding:0 15px}h1{font-size:25px}h2{font-size:20px}section,.card{border:1px solid #d7e0ea;background:white;border-radius:10px;padding:15px;margin:12px 0} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}video{max-width:100%;width:100%;border-radius:9px}pre{white-space:pre-wrap;word-break:break-word;background:#eef2f7;padding:11px;border-radius:8px}small,.muted{color:#586579}button{border:0;border-radius:8px;padding:9px 12px;background:#2354d9;color:white;cursor:pointer}button:disabled{background:#989eac}select,textarea{border:1px solid #cbd5df;border-radius:6px;padding:6px;max-width:100%}label{display:block;margin:7px 0}.status{font-weight:700;color:#315773}.good{color:#086e45}.warn{color:#b14817}</style></head>
<body><h1>Agent Intelligence Lab v4.4 · Multimodal Workflows</h1><p>Six 24–32-second video storyboards plus image, audio, text and tool-agent prompts. No video provider calls run automatically. Generated footage must be imported with model/rights provenance; photo slideshows do not count.</p>
<section><h2>Measured execution and evidence status</h2><div id="overview">Loading recorded receipts…</div><p class="muted">No independent acceptance or provider-dollar savings are inferred from technical validity. User-attested model origin is not a verified provider receipt.</p></section>
<h2>Prompt-to-video campaigns · 6 distinct scenarios</h2><div id="videos" class="grid"></div><h2>Other modalities</h2><div id="other" class="grid"></div><section><h2>Results and limitations</h2><div id="results"></div></section>
<script src="/app.js"></script></body></html>'''
JS=r'''const el=(tag, text, cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
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
'''

def range_parts(h,size):
    if not h:return (0,size-1,200)
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',h.strip())
    if not m:return(None,None,416)
    aa,bb=m.groups();
    if not aa and not bb:return(None,None,416)
    if not aa:
        n=int(bb)
        if n<=0:return(None,None,416)
        return(max(0,size-n),size-1,206)
    a=int(aa);b=int(bb) if bb else size-1
    if a>=size or b<a:return(None,None,416)
    return(a,min(b,size-1),206)

def create_server(run,plan_path,port=0):
    run=Path(run);plan=suite(plan_path)
    class H(BaseHTTPRequestHandler):
        def log_message(self,*x):pass
        def json_response(self,obj,status=200):
            b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def send_bytes(self,b,ctype):
            self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def streaming(self,p):
            if not p or not p.is_file():return self.json_response({'error':'MEDIA_UNAVAILABLE_OR_CHECKSUM_MISMATCH'},404)
            size=p.stat().st_size;a,b,status=range_parts(self.headers.get('Range'),size)
            self.send_response(status);self.send_header('Accept-Ranges','bytes');self.send_header('Content-Type','video/mp4')
            if status==416:self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            self.send_header('Content-Length',str(b-a+1))
            if status==206:self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
            self.end_headers()
            if self.command=='HEAD':return
            with open(p,'rb') as f:
                f.seek(a);remain=b-a+1
                while remain:
                    buf=f.read(min(128*1024,remain))
                    if not buf:break
                    try:self.wfile.write(buf)
                    except BrokenPipeError:break
                    remain-=len(buf)
        def do_HEAD(self):return self.do_GET()
        def do_GET(self):
            url=urlsplit(self.path).path
            if url=='/':return self.send_bytes(PAGE.encode(),'text/html; charset=utf-8')
            if url=='/app.js':return self.send_bytes(JS.encode(),'application/javascript; charset=utf-8')
            if url=='/api/health':return self.json_response({'ok':True,'run':run.name})
            if url=='/api/state':
                st=get(run)
                for x in st['artifacts']:x['available']=artifact_valid(run,x)
                return self.json_response({'plan':plan,'state':st,'categories':CATEGORIES})
            if url.startswith('/media/'):
                cid=url[len('/media/'):]
                if not re.fullmatch(r'[0-9a-f]{12}',cid):return self.json_response({'error':'BAD_ID'},404)
                a=next((x for x in get(run)['artifacts'] if x['id']==cid),None)
                return self.streaming(run/a['path'] if a and artifact_valid(run,a) else None)
            if url.startswith('/assembly/'):
                tid=url[len('/assembly/'):]
                if not re.fullmatch(r'VID-[0-9]{2}-[A-Z0-9-]+',tid):return self.json_response({'error':'BAD_ID'},404)
                a=next((x for x in reversed(get(run).get('assembled',[])) if x['task_id']==tid),None)
                p=run/a['output'] if a else None
                if p is None or not p.is_file() or file_sha(p)!=a['sha256']:p=None
                return self.streaming(p)
            return self.json_response({'error':'UNKNOWN_ENDPOINT'},404)
        def do_POST(self):
            try:
                if int(self.headers.get('Content-Length','0'))>16000:raise ValueError('OVERSIZE_PAYLOAD')
                data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                url=urlsplit(self.path).path
                if url=='/api/review':
                    r=review(run,plan,data['artifact_id'],data['ratings'],data['events']);package(run);return self.json_response(r)
                if url=='/api/assemble':
                    r=assemble(run,plan,data['task_id']);package(run);return self.json_response(r)
                return self.json_response({'error':'UNKNOWN_ENDPOINT'},404)
            except (ValueError,KeyError,TypeError,RuntimeError) as e:return self.json_response({'error':type(e).__name__+':'+str(e)[:200]},400)
    return ThreadingHTTPServer(('127.0.0.1',port),H)

def serve(run,plan_path,port=0,open_browser=True):
    srv=create_server(run,plan_path,port)
    url=f'http://127.0.0.1:{srv.server_port}/'
    if open_browser:webbrowser.open(url)
    print('AIL v4.4 MULTIMODAL DASHBOARD:',url,flush=True)
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:srv.server_close()
