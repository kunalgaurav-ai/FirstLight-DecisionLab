#!/usr/bin/env python3
"""Single-launch real agent+audio+media benchmark, independent review UI, archive."""
from __future__ import annotations
import argparse, hashlib, json, mimetypes, os, platform, random, shutil, subprocess, sys, time, uuid, zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v38.workflow import (VERSION,ARMS,CASES,MODE,utc,sha,probe,source_admission,find_video,
                              run_pipeline,summarise,setup_review_cards,snapshot_system)
from ail_v37.observed import join,evaluate

SOURCE_SUBMISSION='20260901_mini-v2.4.2_gemini-3-5-flash'

def save(path,obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def discover_old():
    base=Path.home()/'Downloads'/'agent-intelligence-lab-rigorous'/'data'
    t=base/'rich_traces';g=base/'token_waste_labeled_calls.jsonl'
    return (t,g) if t.is_dir() and g.is_file() else (None,None)

def historical(out):
    t,g=discover_old()
    if t is None:return {'status':'HOLD_NO_HISTORICAL_TRAJECTORY_INPUT','value_claim':'NO_CAUSAL_SAVINGS'}
    try:
        episodes,meta=join(t,g,SOURCE_SUBMISSION)
        result=evaluate(episodes,meta)
        result['scope']='EXPLORATORY_HISTORICAL_PREDICTION_NOT_INTERVENTION';return result
    except Exception as e:
        return {'status':'REJECT_HISTORICAL_IMPORT','error_type':type(e).__name__,
                'error':str(e)[:250],'value_claim':'NO_CAUSAL_SAVINGS'}

def zip_reports(run):
    zpath=run/f'UPLOAD_THIS_v38_{run.name[4:]}.zip'
    includes=['tests_v38.txt','runtime_evidence_v38.json','historical_observed_v38.json',
              'source_audit_v38.json','review_cards_public.json','manifest_v38.json']
    # Include reviews after dashboard is closed. Never export raw model prompts or private media.
    if (run/'reviews.jsonl').is_file():includes.append('reviews.jsonl')
    tmp=zpath.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for n in includes:
            if (run/n).is_file():z.write(run/n,n)
    tmp.replace(zpath)
    return zpath

def dashboard(run,report,cards):
    import html
    body=[]
    for c in cards:
        if c['status']!='COMPLETE' or not c.get('video_path'):continue
        path='/'+c['video_path'].replace('\\','/')
        body.append(f'''<article><h3>{html.escape(c['review_id'])} — {html.escape(c['task_id'])}</h3>
<video controls preload="metadata" width="460" src="{html.escape(path,quote=True)}"></video>
<p>Check source statements: {html.escape(' / '.join(c['source_facts']))}</p>
<form data-id="{html.escape(c['review_id'])}"><label>Reviewer code (not a password) <input name="reviewer" required maxlength="60" placeholder="independent_rater_1"></label>
<label>Factual fit (1–5) <input type="number" name="factual" min="1" max="5" value="3" required></label>
<label>Creative fit (1–5) <input type="number" name="creative" min="1" max="5" value="3" required></label>
<label>Audio suitability (1–5) <input type="number" name="audio" min="1" max="5" value="3" required></label>
<label>Final decision <select name="approved"><option value="false">Reject</option><option value="true">Approve</option></select></label>
<label>Feedback <input name="feedback" maxlength="400"></label><button>Save independent review</button></form></article>''')
    page='''<!doctype html><html><head><meta charset="utf-8"/><title>AIL v3.8 real execution review</title><style>
body{font:15px system-ui;max-width:1100px;margin:auto;padding:24px;color:#152033;background:#f6f8fc}
article,section{padding:20px;border:1px solid #d2dbe9;border-radius:12px;margin:16px 0;background:white}
form{display:flex;flex-wrap:wrap;gap:12px}label{display:flex;flex-direction:column;gap:5px}input,select,button{padding:9px;border:1px solid #a6b4c7;border-radius:6px}button{background:#173964;color:white}video{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><h1>AIL v3.8 — actual local workflow evidence</h1><p><strong>Videos use preexisting source footage plus model-written narration; NOT generative AI footage.</strong>
Cards hide which arm produced the output. Technical validation is not creative approval. Only qualified reviewers not involved in output production can provide independent approval.</p><section><h2>Execution metrics</h2><pre id="stats">Loading…</pre></section><section><h2>Blind review</h2><p>Reviews are stored locally. Close this server with Ctrl+C to include them in the results ZIP. If no review is recorded, commercial approval remains UNKNOWN.</p></section>'''+''.join(body)+'''<script>
fetch('/api/results').then(r=>r.json()).then(x=>document.querySelector('#stats').textContent=JSON.stringify({status:x.status,aggregate:x.aggregate,source_video:x.source_video,claims:x.claims},null,2));
document.querySelectorAll('form[data-id]').forEach(f=>f.addEventListener('submit',async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(f));d.review_id=f.dataset.id;d.approved=d.approved==='true';for(const k of ['factual','creative','audio'])d[k]=Number(d[k]);try{const r=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const j=await r.json();if(!r.ok)throw new Error(j.error||'Save failed');alert('Review saved locally.');}catch(err){alert(err.message)}}));
</script></body></html>'''
    ids={c['review_id'] for c in cards}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,obj,status=200):
            b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            path=unquote(urlsplit(self.path).path)
            if path in ('/','/index.html'):
                b=page.encode('utf-8');self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            elif path=='/api/results':self.respond({'status':report['status'],'run_id':report['run_id'],'exec_mode':report['exec_mode'],'source_video':{'reason':report['source_video'].get('reason'),'duration_s':report['source_video'].get('duration_s')},'aggregate':'WITHHELD_UNTIL_REVIEW_COMPLETES_TO_PRESERVE_BLINDING','claims':report['claims']})
            elif path.startswith('/media/'):
                f=(run/path[1:]).resolve();base=(run/'media').resolve()
                if not (str(f).startswith(str(base)+os.sep) and f.is_file()):self.send_error(404);return
                total=f.stat().st_size;start=0;stop=total-1
                hr=self.headers.get('Range','')
                if hr.startswith('bytes='):
                    try:
                        a,b=hr[6:].split('-',1);start=int(a or 0);stop=min(int(b),total-1) if b else total-1
                        if start<0 or start>stop:raise ValueError()
                    except ValueError:self.send_error(416);return
                self.send_response(206 if hr else 200);self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(stop-start+1))
                if hr:self.send_header('Content-Range',f'bytes {start}-{stop}/{total}')
                self.end_headers()
                with f.open('rb') as s:
                    s.seek(start);n=stop-start+1
                    while n>0:
                        data=s.read(min(n,65536));
                        if not data:break
                        try:self.wfile.write(data)
                        except BrokenPipeError:break
                        n-=len(data)
            else:self.send_error(404)
        def do_POST(self):
            if self.path!='/api/review':self.send_error(404);return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=3000:raise ValueError('Invalid review length')
                d=json.loads(self.rfile.read(n))
                if d.get('review_id') not in ids:raise ValueError('Unknown review ID')
                if not isinstance(d.get('reviewer'),str) or not 2<=len(d['reviewer'])<=60:raise ValueError('Reviewer code required')
                if type(d.get('approved')) is not bool:raise ValueError('Explicit approval required')
                if any(type(d.get(k)) is not int or not 1<=d[k]<=5 for k in ('factual','creative','audio')):raise ValueError('Scores must be integers 1-5')
                d['feedback']=str(d.get('feedback',''))[:400]
                obj={'time_utc':utc(),'review_id':d['review_id'],'reviewer':d['reviewer'],
                     'approved':d['approved'],'scores':{k:d[k] for k in ('factual','creative','audio')},'feedback':d['feedback'],
                     'independence_not_verified_automatically':True}
                with (run/'reviews.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obj)+'\n')
                self.respond({'saved':True})
            except (ValueError,TypeError,json.JSONDecodeError) as e:self.respond({'error':str(e)},400)
    srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{srv.server_port}/'
    print('DASHBOARD AND BLIND REVIEW:',url,flush=True)
    if sys.platform=='darwin':subprocess.Popen(['open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Press Ctrl+C to seal updated review reports ZIP.',flush=True)
    try:srv.serve_forever(.25)
    except KeyboardInterrupt:pass
    finally:srv.server_close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',help='Rights-cleared existing dynamic video; not generated footage')
    parser.add_argument('--model',default='qwen2.5:1.5b')
    parser.add_argument('--ollama',default='http://127.0.0.1:11434')
    parser.add_argument('--task-limit',type=int,default=4)
    parser.add_argument('--no-dashboard',action='store_true')
    parser.add_argument('--skip-historical',action='store_true')
    a=parser.parse_args()
    if not 1<=a.task_limit<=len(CASES):parser.error('task-limit must be 1 to 4')
    now=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run=ROOT/'runs'/f'v38_{now}_{uuid.uuid4().hex[:8]}'
    run.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-v']
    t=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (run/'tests_v38.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(t.returncode)+'\n'+t.stdout+t.stderr,encoding='utf-8')
    print('UNIT TESTS:', 'PASS' if t.returncode==0 else 'FAIL',flush=True)
    source=Path(a.source).expanduser() if a.source else find_video()
    admitted=source_admission(source)
    model=probe(a.ollama,a.model)
    system=snapshot_system()
    env={'model':model,'source':admitted,'system':system,'task_count':a.task_limit,
         'cannot_validate_image_or_t2v_model':'NO_AUTHORIZED_GENERATIVE_IMAGE_OR_VIDEO_BACKEND',
         'software_tests_passed':t.returncode==0,
         'workload':'REAL_LOCAL_INFERENCE_AND_MEDIA_NOT_CUSTOMER_DATA'}
    save(run/'source_audit_v38.json',env)
    old=historical(run) if not a.skip_historical else {'status':'SKIPPED_BY_USER'}
    save(run/'historical_observed_v38.json',old)
    tasks=list(CASES[:a.task_limit]); task_manifest={'version':VERSION,'tasks':tasks,'orders':{},'model':a.model}
    rows=[];started=time.perf_counter()
    allowed=t.returncode==0 and admitted.get('admitted') and model.get('ready') and system['ffmpeg'] and system['ffprobe'] and system['say_exists'] and platform.system()=='Darwin'
    if allowed:
        for j,task in enumerate(tasks):
            arms=list(ARMS);random.Random(20261025+j).shuffle(arms)
            task_manifest['orders'][task['id']]=arms
            print('REAL WORKFLOW:',task['id'],'policies',arms,flush=True)
            for arm in arms:
                result=run_pipeline(run,source,a.model,a.ollama,task,arm,seed=6000+j)
                rows.append(result)
                print('COMPLETED:',task['id'],arm,result['status'],round(result['wall_s'],2),'seconds',flush=True)
        status='REAL_EXECUTION_COMPLETE_WITH_POSSIBLE_TASK_FAILURES'
    else:
        status='BLOCKED_NO_FAKE_MODE'
        print('REAL WORKFLOW BLOCKED (no synthetic replacement). Inspect source_audit_v38.json',flush=True)
    save(run/'frozen_briefs_v38.json',task_manifest)
    cards=setup_review_cards(rows,run)
    public=[{'review_id':c['review_id'],'task_id':c['task_id'],'status':c['status']} for c in cards]
    save(run/'review_cards_public.json',public)
    aggregate=summarise(rows)
    verdict={'status':status,'run_id':run.name,'version':VERSION,'exec_mode':MODE,
      'timestamp_utc':utc(),'duration_wall_s':round(time.perf_counter()-started,2),
      'reference_baseline':'B1_COMPETENT_INCUMBENT','ail_policy':'INCUMBENT_PRESERVED_NO_SUPPORTED_DEVIATION',
      'source_video':admitted,'model':model,'aggregate':aggregate,'trials':rows,
      'frozen_task_manifest_sha256':sha(run/'frozen_briefs_v38.json'),
      'independent_final_approval':'UNKNOWN_UNTIL_BLIND_HUMAN_REVIEWS',
      'no_real_text_to_video_model':True,'no_real_text_to_image_model':True,
      'claims':{'generative_video_provider_savings':'NOT_TESTED','independent_quality':'PENDING',
        'oss_advantage':'NOT_TESTED','external_cost_savings':'NOT_MEASURED',
        'cost_per_approved_result':'UNDEFINED_UNTIL_APPROVALS',
        'script_generation':'REAL_OLLAMA_IF_COMPLETED','speech_synthesis':'REAL_MAC_SAY_IF_COMPLETED',
        'video_processing':'REAL_FFMPEG_ON_EXISTING_FOOTAGE_IF_COMPLETED'}}
    save(run/'runtime_evidence_v38.json',verdict)
    checks=['tests_v38.txt','source_audit_v38.json','historical_observed_v38.json',
            'runtime_evidence_v38.json','review_cards_public.json','frozen_briefs_v38.json']
    source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts}
    manifest={'version':VERSION,'created_utc':utc(),'code_scope':'V37_COMPANION_INHERITED_PLUS_REAL_WORKFLOW_HARNESS',
        'v32_source_integrated':False,'tests_passed':t.returncode==0,'execution_status':status,
        'observed_study_status':old.get('status'),
        'report_sha256':{n:sha(run/n) for n in checks},'source_sha256':source_hashes,
        'independent_approval':'NOT_VERIFIED'}
    save(run/'manifest_v38.json',manifest)
    z=zip_reports(run)
    print('RESULT REPORT ZIP:',z,flush=True)
    print('REAL ARTIFACTS:',run/'media',flush=True)
    if not a.no_dashboard:dashboard(run,verdict,json.loads((run/'review_index.json').read_text()))
    # Refresh the reports ZIP to include reviews added interactively.
    if (run/'reviews.jsonl').is_file():
        manifest['review_sha256']=sha(run/'reviews.jsonl')
        manifest['review_count']=sum(1 for ln in (run/'reviews.jsonl').read_text().splitlines() if ln.strip())
        save(run/'manifest_v38.json',manifest)
    z=zip_reports(run)
    print('UPLOAD THIS RESULTS ZIP:',z,flush=True)
    if sys.platform=='darwin' and not a.no_dashboard:subprocess.Popen(['open','-R',str(z)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return 0 if t.returncode==0 else 2
if __name__=='__main__':sys.exit(main())
