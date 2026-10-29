"""Read-only executed metrics and explicitly labeled self-review feedback, localhost only."""
from __future__ import annotations
import json,re,threading,webbrowser,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
from .engine import file_sha,save_json,package,utc

PAGE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIL v4.5 · Executed Decision Lab</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:1200px;padding:20px;margin:auto;color:#152238;background:#f4f7fb}h1{margin-bottom:4px}h2{margin-top:27px;font-size:20px}section,.card{background:#fff;border:1px solid #d8e2ed;border-radius:11px;padding:17px;margin:14px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;text-align:left;border-bottom:1px solid #e1e5ea} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}.muted{color:#526376}.pass{color:#166534;font-weight:700}.fail{color:#a12525;font-weight:700}button{padding:8px 13px;margin:4px 7px 4px 0;background:#2059d9;border:0;border-radius:7px;color:white;cursor:pointer}button:disabled{opacity:.4}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f9;padding:12px;border-radius:8px}audio{max-width:100%}a{color:#174a9b}</style></head><body>
<h1>Agent Intelligence Lab · v4.5</h1><p class="muted">Executed local decisions · Competent baselines · Reproducible resource receipts · Longer multimodal workflows preserved</p>
<section><h2>Evidence rules</h2><p>Text checks below are exact-string/length tests, not independent semantic or creative acceptance. Audio generation is not intelligibility grading. Browser reviews are explicitly self-assessments. Local tokens are not cloud invoices. Visual video prompts remain unexecuted unless separately provided with real model receipts.</p></section>
<section><h2>Actual experiment status</h2><div id="summary">Loading actual report…</div></section>
<h2>Text — four observed, forked decisions</h2><div id="texts" class="grid"></div>
<h2>Audio — actual synthesis and cache comparison</h2><div id="audio"></div>
<h2>Multimodal scope still awaiting provider execution</h2><div id="video" class="grid"></div><section><h2>Scientific conclusion</h2><p id="conclusion">Loading…</p></section><script src="/app.js"></script></body></html>'''
JS=r'''const $=s=>document.querySelector(s);
function el(tag,txt,cls){const a=document.createElement(tag);if(txt!==undefined)a.textContent=txt;if(cls)a.className=cls;return a;}
async function api(uri,opts){const r=await fetch(uri,opts);const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x;}
function sumLine(td,txt){td.append(el('p',txt));}
function makeReview(root,task,arm,kind){let wrapper=el('div');const ok=el('button','Mark usable (self-review)'),no=el('button','Mark unusable (self-review)');
 for(const [b,decision] of [[ok,'USABLE'],[no,'UNUSABLE']]){b.onclick=async()=>{try{await api('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,task_id:task,arm,decision})});await load()}catch(e){alert(String(e))}};wrapper.append(b)}
 root.append(wrapper)}
async function load(){try{const d=await api('/api/report');const s=$('#summary');s.replaceChildren();
 const r=d.report;if(!r){s.textContent='No results_v45.json. Consult the launcher diagnostic ZIP.';return;}
 const tab=el('table'),header=el('tr');['Policy','Objective passes','Model calls','Actual reported tokens','Summed model time'].forEach(t=>header.append(el('th',t)));tab.append(header);
 for(const [k,v] of Object.entries(r.summary)){const tr=el('tr');[k,`${v.objective_passes}/${v.tasks_attempted}`,v.model_calls, v.model_input_tokens+v.model_output_tokens,`${v.sum_model_wall_seconds.toFixed(2)} s`].forEach(t=>tr.append(el('td',String(t))));tab.append(tr)}s.append(tab);
 const txt=$('#texts');txt.replaceChildren();for(const t of r.text_trials){const card=el('section');card.append(el('h3',t.task_id));card.append(el('p',t.status,t.status.startsWith('REAL')?'pass':'fail'));if(t.predecision_objective)card.append(el('p',`Initial output: ${t.predecision_objective.word_count} words; objective pass=${t.predecision_objective.objective_pass}`));
 for(const [arm,a] of Object.entries(t.arms)){const div=el('div');div.append(el('strong',arm));div.append(el('p',`Action: ${a.action} · objective: ${a.validation.objective_pass?'PASS':'FAIL'} · ${a.validation.word_count} words · ${a.input_tokens+a.output_tokens} tokens`));
 const link=el('a','Open actual text');link.href='/artifact/text/'+encodeURIComponent(t.task_id)+'/'+encodeURIComponent(arm);link.target='_blank';div.append(link);const key=`TEXT:${t.task_id}:${arm}`;const saved=d.reviews.find(x=>x.key===key);if(saved)div.append(el('p',`Self-review: ${saved.decision}`));else makeReview(div,t.task_id,arm,'TEXT');card.append(div)}txt.append(card)}
 const au=$('#audio');au.replaceChildren();if(r.audio_trials.arms){const table=el('table'),head=el('tr');['Arm','Physical TTS calls','Synthesis time','Exact transcript separation'].forEach(x=>head.append(el('th',x)));table.append(head);
 for(const [arm,v] of Object.entries(r.audio_trials.arms)){const tr=el('tr');[arm,v.actual_tts_calls,`${v.synthesis_wall_s.toFixed(3)} s`,String(v.objective_script_separation)].forEach(x=>tr.append(el('td',String(x))));table.append(tr)}au.append(table);
 for(const [arm,v] of Object.entries(r.audio_trials.arms)){const sec=el('section');sec.append(el('h3',arm));for(const t of v.records){const p=el('div');p.append(el('strong',t.task_id));p.append(el('p',`${t.status} · ${t.cache_hit?'cache reuse':'generated'} · ${t.duration_s?.toFixed(2)||'?'} s · intelligibility not assessed`));
 if(t.sha256){const player=el('audio');player.controls=true;player.src='/artifact/audio/'+encodeURIComponent(t.task_id)+'/'+encodeURIComponent(arm);p.append(player);const key=`AUDIO:${t.task_id}:${arm}`;const rv=d.reviews.find(x=>x.key===key);if(rv)p.append(el('p',`Self-review: ${rv.decision}`));else makeReview(p,t.task_id,arm,'AUDIO')}sec.append(p)}au.append(sec)}}else au.textContent=r.audio_trials.status;
 const vg=$('#video');vg.replaceChildren();for(const x of d.video_campaigns){const c=el('section');c.append(el('strong',x.task_id));c.append(el('p',`${x.shots} required moving shots · ${x.duration_s}s planned · zero new video calls in v4.5`,'muted'));vg.append(c)}
 $('#conclusion').textContent=r.strong_oss_competitive_superiority+' · No independent approvals. Deterministic tool-first and caching comparators are strong applicable alternatives. An AIL token reduction relative to a retry-only baseline does not establish increment over those alternatives.';
 }catch(e){$('#summary').textContent='REPORT ERROR: '+String(e)}}
load();'''

def get_available(run,kind,task,arm):
 st=json.loads((Path(run)/'results_v45.json').read_text())
 if kind=='text':
  rec=next((r for r in st['text_trials'] if r['task_id']==task),None)
  if not rec or arm not in rec['arms']:return None
  expected=rec['arms'][arm]['output_sha256'];p=Path(rec['arms'][arm]['output_path'])
 elif kind=='audio':
  armrec=st['audio_trials'].get('arms',{}).get(arm,{});rec=next((r for r in armrec.get('records',[]) if r['task_id']==task),None)
  if not rec or not rec.get('sha256'):return None
  expected=rec['sha256'];p=Path(rec['output_path'])
 else:return None
 base=(Path(run)/'artifacts').resolve()
 if not p.resolve().is_relative_to(base) or not p.is_file() or file_sha(p)!=expected:return None
 return p

def create_server(run,plan_path,video_plan,port=0):
 run=Path(run);vplan=json.loads(Path(video_plan).read_text())
 vmeta=[{'task_id':t['task_id'],'shots':len(t['shots']),'duration_s':t['target_duration_s']} for t in vplan['tasks'] if t['modality']=='text_to_video']
 class H(BaseHTTPRequestHandler):
  def log_message(self,*a):pass
  def json(self,obj,status=200):
   b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();
   if self.command!='HEAD':self.wfile.write(b)
  def bytes(self,s,ct):
   b=s.encode();self.send_response(200);self.send_header('Content-Type',ct);self.send_header('Content-Length',str(len(b)));self.end_headers();
   if self.command!='HEAD':self.wfile.write(b)
  def do_HEAD(self):self.do_GET()
  def do_GET(self):
   u=urlsplit(self.path).path
   if u=='/':return self.bytes(PAGE,'text/html; charset=utf-8')
   if u=='/app.js':return self.bytes(JS,'application/javascript; charset=utf-8')
   if u=='/api/health':return self.json({'ok':True,'version':'4.5'})
   if u=='/api/report':
    p=run/'results_v45.json';r=json.loads(p.read_text()) if p.exists() else None
    rp=run/'reviews_v45.json';rv=json.loads(rp.read_text()) if rp.exists() else []
    return self.json({'report':r,'reviews':rv,'video_campaigns':vmeta})
   m=re.fullmatch(r'/artifact/(text|audio)/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)',u)
   if m:
    kind,task,arm=m.groups();p=get_available(run,kind,task,arm)
    if p is None:return self.json({'error':'ARTIFACT_NOT_VERIFIED'},404)
    size=p.stat().st_size
    self.send_response(200);self.send_header('Content-Length',str(size));self.send_header('Content-Type','audio/aiff' if kind=='audio' else 'text/plain; charset=utf-8');self.end_headers()
    if self.command!='HEAD':
     with p.open('rb') as f:
      while True:
       part=f.read(65536)
       if not part:break
       try:self.wfile.write(part)
       except (BrokenPipeError,ConnectionResetError):break
    return
   return self.json({'error':'NOT_FOUND'},404)
  def do_POST(self):
   if urlsplit(self.path).path!='/api/review':return self.json({'error':'NOT_FOUND'},404)
   try:
    size=int(self.headers.get('Content-Length','0'))
    if size<1 or size>4096:raise ValueError('PAYLOAD_SIZE')
    o=json.loads(self.rfile.read(size));kind=o['kind'];task=o['task_id'];arm=o['arm'];decision=o['decision']
    if kind not in ('TEXT','AUDIO') or decision not in ('USABLE','UNUSABLE'):raise ValueError('INVALID_REVIEW')
    if not isinstance(task,str) or not isinstance(arm,str):raise ValueError('INVALID_KEYS')
    if not get_available(run,kind.lower(),task,arm):raise ValueError('REVIEW_WITHOUT_VERIFIED_ARTIFACT')
    key=f'{kind}:{task}:{arm}';p=run/'reviews_v45.json';old=json.loads(p.read_text()) if p.is_file() else []
    if any(x['key']==key for x in old):raise ValueError('DUPLICATE_REVIEW')
    review={'key':key,'kind':kind,'task_id':task,'arm':arm,'decision':decision,'reviewer_kind':'SELF_REVIEW_NOT_INDEPENDENT','utc':utc()}
    old.append(review);save_json(p,old);package(run);return self.json(review)
   except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:return self.json({'error':str(e)[:180]},400)
 return ThreadingHTTPServer(('127.0.0.1',port),H)

def serve(run,plan_path,video_plan,port=0,open_browser=True):
 srv=create_server(run,plan_path,video_plan,port);url=f'http://127.0.0.1:{srv.server_port}/'
 if open_browser:webbrowser.open(url)
 print('AIL v4.5 LIVE ECONOMIC DECISION DASHBOARD:',url,flush=True)
 try:srv.serve_forever()
 except KeyboardInterrupt:pass
 finally:srv.server_close()
