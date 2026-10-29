"""v4.4: executable, conservative, multimodal production/evidence workbench.

All video origins require receipts. User-attested imports are NOT provider-verified.
Provider costs and acceptance are unknown unless independently documented.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, tempfile, time, uuid, zipfile
from pathlib import Path
from datetime import datetime, timezone
from urllib import request
from ail_v43.engine import media_probe, file_sha

CATEGORIES = ('motion','prompt_adherence','continuity','safety','creative_quality')
ACCEPT = 3

def utc():return datetime.now(timezone.utc).isoformat()
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def write_json(path, data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n');os.replace(tmp,p)

def suite(path):
    data=json.loads(Path(path).read_text())
    if data['kind']!='AIL_V44_PRECOMMITTED_MULTIMODAL_SUITE':raise ValueError('UNAUTHORIZED_PLAN')
    seen=set()
    for task in data['tasks']:
        if task['task_id'] in seen:raise ValueError('DUPLICATE_TASK')
        seen.add(task['task_id'])
        if digest(task['source_prompt'])!=task['source_prompt_sha256']:raise ValueError('MODIFIED_FROZEN_PROMPT')
        for s in task.get('shots',[]):
            if digest(s['prompt'])!=s['prompt_sha256']:raise ValueError('MODIFIED_SHOT_PROMPT')
            if s['min_accepted_duration_s']>s['target_duration_s']:raise ValueError('INVERTED_DURATION')
    return data

def init_run(run, plan):
    run=Path(run);run.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(plan,run/'WORKFLOW_SUITE_V44.json')
    st={'kind':'AIL_V44_WORKFLOW_EVIDENCE','created_utc':utc(),'events':[], 'artifacts':[], 'local_executions':[], 'decisions':[], 'reviews':[], 'all_in_provider_cost_usd':None,'independent_approval_count':None,'comparison_status':'NOT_ESTABLISHED_NO_MATCHED_INDEPENDENT_OUTCOMES'}
    write_json(run/'state.json',st)
    return run

def get(run):return json.loads((Path(run)/'state.json').read_text())
def put(run,st):write_json(Path(run)/'state.json',st)
def emit(st,tag, **kwargs):st['events'].append({'utc':utc(),'event':tag,**kwargs})
def find_task(plan,task_id):
    for t in plan['tasks']:
        if t['task_id']==task_id:return t
    raise ValueError('UNKNOWN_TASK')
def find_shot(task,shot_id):
    for s in task.get('shots',[]):
        if s['shot_id']==shot_id:return s
    raise ValueError('UNKNOWN_SHOT')

def artifact_valid(run,rec):
    path=Path(run)/rec['path']
    if not path.resolve().is_relative_to((Path(run)/'artifacts').resolve()):return False
    return path.is_file() and file_sha(path)==rec['sha256']

def admit(run,plan,task_id,shot_id,mp4,provider,model,rights,origin='USER_ATTESTED',backend_receipt=None):
    task=find_task(plan,task_id);shot=find_shot(task,shot_id)
    p=Path(mp4)
    if not p.is_file():raise ValueError('NO_INPUT_VIDEO')
    if rights!='AUTHORIZED_NONCONFIDENTIAL_TEST':raise ValueError('VIDEO_RIGHTS_UNVERIFIED')
    if not provider or not model:raise ValueError('MODEL_AND_PROVIDER_REQUIRED')
    if origin not in ('USER_ATTESTED','VERIFIED_LTX_SPACE_API','VERIFIED_PROVIDER_API'):raise ValueError('UNKNOWN_PROVENANCE')
    if origin in ('VERIFIED_LTX_SPACE_API','VERIFIED_PROVIDER_API'):
        if not isinstance(backend_receipt,dict) or backend_receipt.get('generation_mode')!='REAL_REMOTE_TEXT_TO_VIDEO_MODEL':
            raise ValueError('ACTUAL_PROVIDER_RECEIPT_REQUIRED')
        if origin=='VERIFIED_PROVIDER_API' and (backend_receipt.get('provider')!='LTXV_V2_OFFICIAL_BILLED_API' or not backend_receipt.get('provider_job_id')):
            raise ValueError('OFFICIAL_JOB_RECEIPT_REQUIRED')
        if origin=='VERIFIED_LTX_SPACE_API' and backend_receipt.get('provider')!='HF_SPACES_ZEROGPU':
            raise ValueError('OFFICIAL_SPACE_RECEIPT_REQUIRED')
    if origin=='USER_ATTESTED' and backend_receipt is not None:raise ValueError('UNTRUSTED_EXTERNAL_RECEIPT_ATTEMPT')
    m=media_probe(p)
    run=Path(run);st=get(run)
    tag=uuid.uuid4().hex[:12]
    dest=run/'artifacts'/task_id/shot_id/(tag+p.suffix.lower())
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    if file_sha(dest)!=m['sha256']:raise ValueError('COPY_INTEGRITY_FAILURE')
    r={'id':tag,'task_id':task_id,'shot_id':shot_id,'path':str(dest.relative_to(run)),'sha256':file_sha(dest),'media':m,
       'model':model,'provider':provider,'rights':rights,'origin':origin,'recorded_utc':utc(),
       'original_prompt_sha256':task['source_prompt_sha256'],'shot_prompt_sha256':shot['prompt_sha256'],
       'request_duration_s':shot['target_duration_s'],'duration_gate':'PASS' if m['duration_s']>=shot['min_accepted_duration_s'] else 'SHORT_FOR_TARGET',
       'source_provenance':'PROVIDER_RECEIPT_VERIFIED' if origin in ('VERIFIED_LTX_SPACE_API','VERIFIED_PROVIDER_API') else 'USER_DECLARED_NOT_INDEPENDENTLY_VERIFIED',
       'receipt':backend_receipt,'billing_usd':None,'approval':'UNKNOWN_NO_INDEPENDENT_REVIEW'}
    st['artifacts'].append(r);emit(st,'VIDEO_ADMITTED',task_id=task_id,shot_id=shot_id,artifact_id=tag,duration_gate=r['duration_gate'])
    put(run,st);return r

def review(run,plan,artifact_id,ratings,events,reviewer_kind='SELF_REVIEW'):
    st=get(run);item=next((a for a in st['artifacts'] if a['id']==artifact_id),None)
    if item is None or not artifact_valid(run,item):raise ValueError('VIDEO_NOT_VERIFIED_FOR_REVIEW')
    if any(r['artifact_id']==artifact_id for r in st['reviews']):raise ValueError('DUPLICATE_REVIEW')
    task=find_task(plan,item['task_id']);shot=find_shot(task,item['shot_id'])
    if set(ratings)!=set(CATEGORIES) or any(type(v)!=int or v<0 or v>4 for v in ratings.values()):raise ValueError('INVALID_RATINGS')
    allowed=shot['events_covered']
    if set(events)!=set(allowed) or any(v not in ('present','partial','missing','uncertain') for v in events.values()):
        raise ValueError('INVALID_EVENTS')
    if reviewer_kind not in ('SELF_REVIEW','DECLARED_EXTERNAL_UNVERIFIED'):raise ValueError('REVIEWER_KIND')
    passed=all(v>=ACCEPT for v in ratings.values()) and all(v=='present' for v in events.values()) and item['duration_gate']=='PASS'
    rev={'artifact_id':artifact_id,'task_id':item['task_id'],'shot_id':item['shot_id'],'scores':ratings,'events':events,'reviewer_kind':reviewer_kind,
         'passed_local_rubric':passed,'independent_approval':'UNKNOWN','utc':utc()}
    st['reviews'].append(rev);emit(st,'CLIP_REVIEWED',artifact_id=artifact_id,passed=passed)
    put(run,st);return rev

def decision(st,artifact_id,predicted=None):
    item=next((a for a in st['artifacts'] if a['id']==artifact_id),None)
    if not item:return {'action':'HOLD','reason':'NO_OBSERVED_ARTIFACT'}
    rev=next((r for r in st['reviews'] if r['artifact_id']==artifact_id),None)
    if item['duration_gate']!='PASS':return {'action':'HOLD_REVIEW_OR_REGENERATE','reason':'SHORT_FOR_TARGET; NO_COST_CLAIM'}
    if rev is None:return {'action':'HOLD_REVIEW','reason':'NO_POST_GENERATION_QUALITY_EVIDENCE'}
    if rev['passed_local_rubric']:return {'action':'REUSE_IF_SCOPED_AND_AUTHORIZED','reason':'PASS_LOCAL_RUBRIC_NOT_INDEPENDENTLY_APPROVED'}
    # No action-specific failure/recovery data: do not convert a score into economic savings.
    if not predicted or predicted.get('evidence_kind')!='PROSPECTIVE_ACTION_LOG' or predicted.get('n',0)<20:
        return {'action':'HOLD_FOR_CORRECTIVE_PROPOSAL','reason':'CAUSAL_COST_AND_RECOVERY_UNKNOWN; MAY_PERFORM_HUMAN_AUTHORIZED_RETRY'}
    return {'action':'HOLD_EXPERIMENTAL_POLICY','reason':'NO_AUTODEPLOY_FROM_OBSERVATIONAL_PREDICTIONS'}

def cvar(values,alpha=.9):
    if len(values)<20:raise ValueError('CVaR_MIN_N_20')
    if any(type(v) not in (float,int) or v<0 for v in values):raise ValueError('BAD_COST')
    vals=sorted(values);k=max(1,int(len(vals)*(1-alpha)+.999999));return sum(vals[-k:])/k

def voi(check_cost, p_fail_lb, avoidable_loss_lb, overhead_lb=0):
    if any(type(x) not in (int,float) or x<0 for x in (check_cost,p_fail_lb,avoidable_loss_lb,overhead_lb)) or p_fail_lb>1:
        raise ValueError('INVALID_ECONOMICS')
    return p_fail_lb*avoidable_loss_lb-check_cost-overhead_lb

def assemble(run,plan,task_id):
    run=Path(run);task=find_task(plan,task_id)
    if task['modality']!='text_to_video':raise ValueError('NOT_VIDEO_TASK')
    st=get(run);selected=[]
    for shot in task['shots']:
        artifacts=[a for a in st['artifacts'] if a['shot_id']==shot['shot_id']]
        approved=[]
        for a in artifacts:
            rev=next((r for r in st['reviews'] if r['artifact_id']==a['id'] and r['passed_local_rubric']),None)
            if rev and artifact_valid(run,a):approved.append(a)
        if not approved:raise ValueError('MISSING_VALID_REVIEWED_SHOT:'+shot['shot_id'])
        selected.append(approved[-1])
    full=run/'artifacts'/task_id/'assembled.mp4';full.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        normalized=[]
        for i,a in enumerate(selected):
            out=Path(td)/f's{i}.mp4'
            q=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(run/a['path']),'-an','-vf','fps=24,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2','-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast',str(out)],capture_output=True,text=True,timeout=240)
            if q.returncode:raise RuntimeError('NORMALIZE_FAILED:'+q.stderr[:200])
            normalized.append(out)
        lst=Path(td)/'list.txt'
        # All files in our temp dir have predictable names; this is not user-supplied arbitrary path interpolation.
        lst.write_text(''.join("file '"+str(f)+"'\n" for f in normalized))
        started=time.monotonic()
        q=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy',str(full)],capture_output=True,text=True,timeout=180)
        if q.returncode:raise RuntimeError('CONCAT_FAILED:'+q.stderr[:200])
        wall=time.monotonic()-started
    result=media_probe(full)
    if result['duration_s']<task['target_duration_s']*.8:raise ValueError('FINAL_VIDEO_TOO_SHORT_FOR_PLAN')
    receipt={'task_id':task_id,'output':str(full.relative_to(run)),'sha256':result['sha256'],'duration_s':result['duration_s'],
      'shot_ids':[x['id'] for x in selected],'concat_wall_seconds':wall,'independently_approved':False,'status':'TECHNICAL_ASSEMBLY_PASS_QUALITY_ONLY_SELF_REVIEWED'}
    st['assembled']=st.get('assembled',[])+[receipt];emit(st,'VIDEO_ASSEMBLED',task_id=task_id);put(run,st)
    return receipt

def ollama(prompt,model='qwen2.5:1.5b',timeout=150):
    req=request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0,'num_predict':256}}).encode(),headers={'Content-Type':'application/json'},method='POST')
    t=time.monotonic()
    with request.urlopen(req,timeout=timeout) as r:d=json.loads(r.read(10_000_000))
    if d.get('error') or not isinstance(d.get('response'),str) or not d['response'].strip():raise ValueError('OLLAMA_FAILED:'+str(d.get('error','EMPTY_RESPONSE')))
    return {'output':d['response'],'model':model,'model_digest':d.get('model'), 'prompt_eval_count':d.get('prompt_eval_count'), 'eval_count':d.get('eval_count'),
            'provider_ns':{'total_duration':d.get('total_duration'),'eval_duration':d.get('eval_duration'),'prompt_eval_duration':d.get('prompt_eval_duration')},'wall_s':time.monotonic()-t}

def local_modality_execution(run,plan,model='qwen2.5:1.5b'):
    run=Path(run);st=get(run)
    byid={t['task_id']:t for t in plan['tasks']}
    for tid in ('TEXT-01-FACTS','AUD-01-SPEECH','AGENT-01-REPAIR','IMG-01-COMPOSITION','IMG-02-TYPE-SAFETY'):
        t=byid[tid];res={'task_id':tid,'modality':t['modality'],'prompt_sha256':t['source_prompt_sha256'],'utc':utc()}
        if tid=='TEXT-01-FACTS':
            try:
                ans=ollama(t['source_prompt'],model)
                f=run/'artifacts'/'text_generated.txt';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(ans['output'])
                low=ans['output'].lower();tokens=len(ans['output'].split())
                # checks are proxies; do not declare independent factual completion.
                res.update(status='REAL_LOCAL_LLM_COMPLETED',text_path=str(f.relative_to(run)),sha256=file_sha(f),receipt={k:v for k,v in ans.items() if k!='output'},
                           structural_checks={'65_85_words':65<=tokens<=85,'thursday':('thursday' in low),'photo_no_flash':('flash' in low),'ten':('ten' in low or '10' in low)},independent_approval='UNKNOWN')
            except Exception as e:res.update(status='BLOCKED_LOCAL_LLM',error=type(e).__name__+':'+str(e)[:220])
        elif tid=='AUD-01-SPEECH':
            if shutil.which('say') and shutil.which('ffprobe'):
                out=run/'artifacts'/'tts_actual.aiff';out.parent.mkdir(parents=True,exist_ok=True)
                # Exact spoken content from frozen task; speech synthesis not independently judged.
                speech=t['source_prompt'].split('Read aloud exactly:',1)[1].strip() if 'Read aloud exactly:' in t['source_prompt'] else t['source_prompt']
                tt=time.monotonic()
                try:
                    q=subprocess.run(['say','-o',str(out),speech],capture_output=True,text=True,timeout=100)
                    if q.returncode or not out.is_file():raise ValueError('SAY_FAILED:'+q.stderr[:120])
                    meta=subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(out)],timeout=30)
                    secs=float(json.loads(meta)['format']['duration'])
                    res.update(status='REAL_MACOS_TTS_COMPLETED',wav_path=str(out.relative_to(run)),sha256=file_sha(out),duration_s=secs,wall_s=time.monotonic()-tt,transcript=speech,independent_intelligibility='UNKNOWN')
                except Exception as e:res.update(status='BLOCKED_TTS',error=str(e)[:180])
            else:res.update(status='BLOCKED_DEPENDENCY',reason='MACOS_SAY_AND_FFPROBE_REQUIRED')
        elif tid=='AGENT-01-REPAIR':
            # Sandboxed, deterministic microtask with failing then passing independent tests.
            # Not presented as an autonomous generative agent success.
            wd=run/'artifacts'/'tool_repair';wd.mkdir(parents=True,exist_ok=True)
            (wd/'calc.py').write_text('def average(xs):\n    return sum(xs) // len(xs)\n')
            (wd/'test_calc.py').write_text('from calc import average\n\ndef test_fraction():\n    assert average([1,2]) == 1.5\n')
            def check():return subprocess.run([shutil.which('python3') or 'python3','-m','unittest','discover','-s',str(wd)],capture_output=True,text=True,timeout=30)
            # Use isolated -c to run objective assertion; pytest may not exist.
            testcmd=[shutil.which('python3') or 'python3','-c','import sys;sys.path.insert(0,sys.argv[1]);from calc import average;assert average([1,2]) == 1.5',str(wd)]
            first=subprocess.run(testcmd,capture_output=True,text=True,timeout=30)
            before=file_sha(wd/'calc.py')
            (wd/'calc.py').write_text('def average(xs):\n    return sum(xs) / len(xs)\n')
            second=subprocess.run(testcmd,capture_output=True,text=True,timeout=30)
            res.update(status='EXECUTED_CONTROLLED_TOOL_REPAIR' if first.returncode!=0 and second.returncode==0 else 'FAILED_CONTROLLED_TOOL_REPAIR',
                       initial_returncode=first.returncode,final_returncode=second.returncode,original_sha256=before,new_sha256=file_sha(wd/'calc.py'),
                       generation_kind='DETERMINISTIC_TEST_HARNESS_NOT_AUTONOMOUS_AGENT',independent_task_approval='NOT_APPLICABLE')
        else:res.update(status='AWAITING_REAL_GENERATIVE_IMAGE_PROVIDER',reason='NO_INSTALLED_AUTHORIZED_TEXT_TO_IMAGE_BACKEND_VERIFIED; NO_FAKE_IMAGES')
        st['local_executions'].append(res);emit(st,'LOCAL_MODALITY',task_id=tid,status=res['status']);put(run,st)
    return st['local_executions']


def admit_image(run,plan,task_id,image_path,provider,model,rights):
    task=find_task(plan,task_id)
    if task['modality']!='text_to_image':raise ValueError('NOT_IMAGE_PROMPT')
    if rights!='AUTHORIZED_NONCONFIDENTIAL_TEST':raise ValueError('RIGHTS_UNVERIFIED')
    if not provider or not model:raise ValueError('PROVIDER_MODEL_REQUIRED')
    src=Path(image_path)
    if not src.is_file() or src.stat().st_size<100:raise ValueError('MISSING_IMAGE')
    if src.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('INVALID_IMAGE_EXTENSION')
    if not shutil.which('ffprobe'):raise ValueError('FFPROBE_REQUIRED')
    q=subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(src)],capture_output=True,text=True,timeout=30)
    if q.returncode:raise ValueError('INVALID_IMAGE_DECODING')
    streams=json.loads(q.stdout).get('streams',[])
    pics=[x for x in streams if x.get('codec_type')=='video' and int(x.get('width',0))>=128 and int(x.get('height',0))>=128]
    if not pics:raise ValueError('NO_DECODABLE_IMAGE')
    st=get(run);dest=Path(run)/'artifacts'/task_id/(uuid.uuid4().hex[:12]+src.suffix.lower());dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,dest)
    r={'id':dest.stem,'task_id':task_id,'shot_id':None,'path':str(dest.relative_to(run)), 'sha256':file_sha(dest),
       'provider':provider,'model':model,'origin':'USER_ATTESTED_NOT_PROVIDER_VERIFIED','rights':rights,
       'dimensions':{'width':pics[0]['width'],'height':pics[0]['height']}, 'approval':'UNKNOWN_NO_INDEPENDENT_REVIEW',
       'prompt_sha256':task['source_prompt_sha256'],'billing_usd':None,'recorded_utc':utc()}
    st['images']=st.get('images',[])+[r];emit(st,'IMAGE_IMPORTED',task_id=task_id);put(run,st);return r

def package(run):
    run=Path(run);manifest=[]
    for p in sorted(run.rglob('*')):
        if not p.is_file() or 'artifacts' in p.parts or p.name.startswith('UPLOAD_THIS_') or p.name=='MANIFEST_V44.json':continue
        manifest.append({'file':str(p.relative_to(run)),'sha256':file_sha(p),'bytes':p.stat().st_size})
    write_json(run/'MANIFEST_V44.json',{'files':manifest,'media_excluded_from_zip':True})
    dest=run/('UPLOAD_THIS_v44_'+run.name.removeprefix('v44_')+'.zip');tmp=dest.with_suffix('.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for r in manifest+[{'file':'MANIFEST_V44.json'}]:z.write(run/r['file'],r['file'])
    os.replace(tmp,dest);return dest
