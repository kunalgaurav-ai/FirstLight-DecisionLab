#!/usr/bin/env python3
"""Local prospective precommit benchmark with independent blind review and receipts."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,random,shutil,subprocess,sys,time,uuid,zipfile
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit
import mimetypes
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v38.workflow import (CASES, utc, sha, probe, source_admission, find_video, snapshot_system, setup_review_cards)
from ail_v39.workflow import VERSION,ARMS,run_pipeline,summarize
from scripts.launch_v38 import historical

def save(path,obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def zip_reports(run):
    p=run/f'UPLOAD_THIS_v39_{run.name[4:]}.zip'
    files=['tests_v39.txt','source_audit_v39.json','historical_observed_v39.json',
        'grade_schema_probe_v39.json','runtime_evidence_v39.json','manifest_v39.json',
        'review_cards_public.json','frozen_briefs_v39.json']
    if (run/'reviews.jsonl').is_file():files.append('reviews.jsonl')
    temp=p.with_suffix('.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if (run/f).is_file():z.write(run/f,f)
    temp.replace(p)
    return p

def grade_schema_probe():
    """Only key/type diagnostics: never override or infer official grade evidence."""
    p=Path.home()/'Downloads'/'agent-intelligence-lab-rigorous'/'data'/'token_waste_labeled_calls.jsonl'
    if not p.is_file():return {'status':'DATASET_MISSING','observations':0}
    seen={};source_kinds={};n=0
    try:
        with p.open(encoding='utf-8') as f:
            for line in f:
                if not line.strip():continue
                row=json.loads(line);n+=1
                source=row.get('outcome_source')
                name=type(source).__name__;source_kinds[name]=source_kinds.get(name,0)+1
                if isinstance(source,dict):
                    for k,v in source.items():
                        if isinstance(k,str):seen[k]=type(v).__name__
                if n>=2000:break
    except (ValueError,UnicodeDecodeError) as e:
        return {'status':'SCHEMA_PROBE_FAILED','error_type':type(e).__name__}
    return {'status':'OBSERVED_SCHEMA_ONLY_NO_GRADE_INFERENCE','sample_records':n,
            'source_value_type_counts':source_kinds,'nested_source_value_types':seen,
            'prohibited':'DO_NOT_INFER_GRADE_FROM_BOOLEAN_WITHOUT_OFFICIAL_PROVENANCE'}
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
    page='''<!doctype html><html><head><meta charset="utf-8"/><title>AIL v3.9 real execution review</title><style>
body{font:15px system-ui;max-width:1100px;margin:auto;padding:24px;color:#152033;background:#f6f8fc}
article,section{padding:20px;border:1px solid #d2dbe9;border-radius:12px;margin:16px 0;background:white}
form{display:flex;flex-wrap:wrap;gap:12px}label{display:flex;flex-direction:column;gap:5px}input,select,button{padding:9px;border:1px solid #a6b4c7;border-radius:6px}button{background:#173964;color:white}video{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><h1>AIL v3.9 — actual local workflow evidence</h1><p><strong>Videos use preexisting source footage plus model-written narration; NOT generative AI footage.</strong>
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
    parser=argparse.ArgumentParser(description='AIL v3.9 real model/media precommit experiment')
    parser.add_argument('--source',help='Existing licensed video path. Source rights remain unverified')
    parser.add_argument('--model',default='qwen2.5:1.5b')
    parser.add_argument('--ollama',default='http://127.0.0.1:11434')
    parser.add_argument('--task-limit',type=int,default=4)
    parser.add_argument('--no-dashboard',action='store_true')
    parser.add_argument('--skip-historical',action='store_true')
    args=parser.parse_args()
    if not 1<=args.task_limit<=len(CASES):parser.error('task-limit must be 1 to 4')
    run=ROOT/'runs'/('v39_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
    run.mkdir(parents=True,exist_ok=False)
    t=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,
                     capture_output=True,text=True)
    (run/'tests_v39.txt').write_text('EXIT '+str(t.returncode)+'\n'+t.stdout+t.stderr,encoding='utf-8')
    print('UNIT TESTS:', 'PASS' if t.returncode==0 else 'FAIL',flush=True)
    source=Path(args.source).expanduser() if args.source else find_video()
    admission=source_admission(source)
    model=probe(args.ollama,args.model)
    system=snapshot_system()
    env={'source':admission,'model':model,'system':system,'software_tests_passed':t.returncode==0,
         'workload':'ACTUAL_LOCAL_MODEL_AND_MEDIA_NO_GENERATIVE_IMAGE_OR_VIDEO',
         'model_downloads':'NONE','real_paid_provider':'NONE'}
    save(run/'source_audit_v39.json',env)
    observation=historical(run) if not args.skip_historical else {'status':'SKIPPED_BY_USER'}
    save(run/'historical_observed_v39.json',observation)
    save(run/'grade_schema_probe_v39.json',grade_schema_probe())
    tasks=list(CASES[:args.task_limit]); rows=[];t0=time.perf_counter()
    manifest={'tasks':tasks,'source_digest':admission.get('sha256'),'model_digest':model.get('digest'),
              'experimental_arms':ARMS,'orders':{},'benchmark_seed':20261025,
              'approval_status':'UNKNOWN_UNTIL_EXTERNAL_BLIND_REVIEW'}
    allowed=(t.returncode==0 and admission.get('admitted') and model.get('ready') and
             system.get('ffmpeg') and system.get('ffprobe') and system.get('say_exists') and
             platform.system()=='Darwin')
    if allowed:
        for j,task in enumerate(tasks):
            order=list(ARMS);random.Random(20261025+j).shuffle(order)
            manifest['orders'][task['id']]=order
            print('REAL WORKFLOW',task['id'],'arm order',order,flush=True)
            for arm in order:
                result=run_pipeline(run,source,args.model,args.ollama,task,arm,seed=6000+j)
                rows.append(result)
                print('COMPLETED',task['id'],arm,result['status'],round(result['wall_s'],2),'s',flush=True)
        status='REAL_EXECUTION_COMPLETE_WITH_POSSIBLE_STOPS'
    else:
        print('REAL WORKFLOW BLOCKED; inspect source_audit_v39.json',flush=True)
        status='BLOCKED_NO_FAKE_MODE'
    save(run/'frozen_briefs_v39.json',manifest)
    cards=setup_review_cards(rows,run)
    public=[{'review_id':c['review_id'],'task_id':c['task_id'],'status':c['status']} for c in cards]
    save(run/'review_cards_public.json',public)
    report={'version':VERSION,'run_id':run.name,'timestamp_utc':utc(),
            'status':status,'total_wall_s':round(time.perf_counter()-t0,3),
            'experiment_kind':'ACTUAL_PARALLEL_ARM_CONTINUATIONS_ON_CONSTRUCTED_CASES',
            'baseline_arms':ARMS[:2],'experimental_arm':ARMS[2],
            'policy_learning':'NONE_NO_ACTION_CONDITIONED_CALIBRATION',
            'source_video':admission,'model':model,
            'no_generated_image_or_video':True,'independent_final_approval':'UNKNOWN',
            'quality_claim':'LITERAL_FACTS_ONLY_HUMAN_CREATIVE_REVIEW_REQUIRED',
            'commercial_costs':'NOT_MEASURED','competitor_advantage':'NOT_ESTABLISHED',
            'competitive_comparison':'B2_TOOL_FIRST_MUST_BE_BEAT_AT_ACCEPTANCE_PARITY',
            'frozen_task_manifest_sha256':sha(run/'frozen_briefs_v39.json'),
            'aggregate':summarize(rows),'trials':rows}
    save(run/'runtime_evidence_v39.json',report)
    names=['tests_v39.txt','source_audit_v39.json','historical_observed_v39.json',
           'grade_schema_probe_v39.json','runtime_evidence_v39.json','review_cards_public.json',
           'frozen_briefs_v39.json']
    checksum={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts}
    m={'version':VERSION,'created_utc':utc(),'tests_passed':t.returncode==0,
       'execution_status':status,'v32_source_integrated':False,
       'report_sha256':{n:sha(run/n) for n in names},'source_sha256':checksum,
       'reviews':'NOT_VERIFIED','independent_approval':'NOT_VERIFIED'}
    save(run/'manifest_v39.json',m)
    upload=zip_reports(run)
    print('RESULT REPORT ZIP:',upload,flush=True)
    print('REAL ARTIFACTS:',run/'media',flush=True)
    if not args.no_dashboard:dashboard(run,report,json.loads((run/'review_index.json').read_text()))
    if (run/'reviews.jsonl').is_file():
        m['review_sha256']=sha(run/'reviews.jsonl')
        m['review_count']=sum(1 for s in (run/'reviews.jsonl').read_text().splitlines() if s.strip())
        save(run/'manifest_v39.json',m)
    upload=zip_reports(run)
    print('UPLOAD THIS RESULTS ZIP:',upload,flush=True)
    if sys.platform=='darwin' and not args.no_dashboard:
        subprocess.Popen(['open','-R',str(upload)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return 0 if t.returncode==0 else 2
if __name__=='__main__':sys.exit(main())
