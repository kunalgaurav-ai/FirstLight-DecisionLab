"""Actionable prompt-to-artifact pipeline; remote calls are opt-in and never fabricated.

The existing 19-shot plans are immutable. Jobs are serialized with atomic writes,
input receipts and evidence hashes. An interrupted remote job never re-submits
on restart (especially important for billed providers).
"""
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, threading, time, uuid
from datetime import datetime, timezone
from ail_v44 import workbench as wb
from ail_v45.engine import file_sha

LOCK = threading.RLock()
STATES={'BLOCKED_DEPENDENCY','QUEUED','RUNNING','PROVIDER_SUBMITTED','SUCCESS_VERIFIED','FAILED_PROVIDER','FAILED_ARTIFACT','INTERRUPTED','BLOCKED_BUDGET'}


def utc(): return datetime.now(timezone.utc).isoformat()
def atomic(path,obj): wb.write_json(path,obj)
def safe_error(exc):
    err=(type(exc).__name__+': '+str(exc))[:450]
    for key in ('LTXV_API_KEY','HF_TOKEN','HUGGING_FACE_HUB_TOKEN'):
        secret=os.environ.get(key)
        if secret:err=err.replace(secret,'[REDACTED]')
    return err

def readiness():
    try:
        from urllib.request import urlopen
        with urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as r:
            tags=json.loads(r.read(200_000)).get('models',[])
        installed=sorted(t.get('name','') for t in tags)
    except Exception: installed=[]
    import importlib.util
    free_client=importlib.util.find_spec('gradio_client') is not None
    return {'ollama':{'ready':bool(installed),'models':installed,'required':'qwen2.5:1.5b'},
            'speech':{'ready':bool(shutil.which('say') and shutil.which('ffprobe')),'required':'macOS say + ffprobe'},
            'ffmpeg':{'ready':bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))},
            'video_free_probe':{'ready':free_client,'type':'Hugging Face public shared ZeroGPU; unpredictable access; FIVE SECONDS MAX; gradio_client dependency required'},
            'video_production':{'ready':bool(os.environ.get('LTXV_API_KEY')),'required':'LTXV_API_KEY in local environment; billed 8-second shots'},
            'image_provider':{'ready':bool(os.environ.get('HF_TOKEN') and os.environ.get('AIL_ALLOW_BILLED_IMAGE')=='1' and importlib.util.find_spec('huggingface_hub')),'required':'HF_TOKEN plus opt-in AIL_ALLOW_BILLED_IMAGE=1; availability and pricing unknown'}}

def start(run,plan_path):
    run=pathlib.Path(run);run.mkdir(parents=True,exist_ok=True)
    if (run/'jobs.json').exists() or (run/'workflow').exists():raise ValueError('REFUSE_EXISTING_EXECUTION_NO_OVERWRITE')
    wb.init_run(run/'workflow',plan_path)
    atomic(run/'jobs.json',[])
    atomic(run/'meta_v46.json',{'version':'v4.6','started_utc':utc(),'state':'INITIALIZED','external_calls_at_start':0,
                                 'quality_claim':'NONE','incumbent_superiority':'NOT_ESTABLISHED'})
    return run

def jobs(run):return json.loads((pathlib.Path(run)/'jobs.json').read_text())
def modify(run,ident,**updates):
    with LOCK:
        records=jobs(run);record=next((x for x in records if x['id']==ident),None)
        if record is None:raise ValueError('UNKNOWN_JOB')
        if 'status' in updates and updates['status'] not in STATES:raise ValueError('UNKNOWN_STATUS')
        record.update(updates,updated_utc=utc());atomic(pathlib.Path(run)/'jobs.json',records)
        return record.copy()

def create_job(run,kind,task_id,shot_id=None,backend=None):
    with LOCK:
        records=jobs(run)
        if any(x['status'] in ('QUEUED','RUNNING','PROVIDER_SUBMITTED') and
               (x['kind'],x.get('task_id'),x.get('shot_id'))==(kind,task_id,shot_id) for x in records):
            raise ValueError('DUPLICATE_ACTIVE_OPERATION')
        r={'id':uuid.uuid4().hex[:12], 'kind':kind,'task_id':task_id,'shot_id':shot_id,'backend':backend,
           'status':'QUEUED','created_utc':utc(),'updated_utc':utc(),'provider_cost_usd':None,'review':'UNKNOWN'}
        records.append(r);atomic(pathlib.Path(run)/'jobs.json',records);return r

def recover_interrupted(run):
    for j in jobs(run):
        if j['status'] in ('RUNNING','PROVIDER_SUBMITTED','QUEUED'):
            modify(run,j['id'],status='INTERRUPTED',reason='Process restarted; provider job may remain billable. Do not auto-resubmit; reconcile provider job ID.')

def import_media(run,plan,kind,task_id,path,provider,model,rights,shot_id=None):
    if not isinstance(path,str) or len(path)>2048:raise ValueError('INVALID_PATH')
    p=pathlib.Path(path).expanduser().resolve()
    if not p.is_file() or p.stat().st_size>250_000_000:raise ValueError('SOURCE_MISSING_OR_OVER_250MB')
    # Only user download/working locations. Local API must not serve arbitrary system files.
    home=pathlib.Path.home().resolve()
    if not (p.is_relative_to(home/'Downloads') or p.is_relative_to(pathlib.Path(run).resolve())):
        raise ValueError('IMPORT_FROM_DOWNLOADS_ONLY')
    if rights!='AUTHORIZED_NONCONFIDENTIAL_TEST':raise ValueError('EXPLICIT_RIGHTS_REQUIRED')
    if kind=='video':
        with LOCK:return wb.admit(pathlib.Path(run)/'workflow',plan,task_id,shot_id,p,provider,model,rights)
    if kind=='image':
        with LOCK:return wb.admit_image(pathlib.Path(run)/'workflow',plan,task_id,p,provider,model,rights)
    raise ValueError('UNSUPPORTED_IMPORT_KIND')

def _ollama(prompt,model):
    from ail_v44.workbench import ollama
    return ollama(prompt,model)

def execute_local(run,kind,prompt,model='qwen2.5:1.5b',spoken_instructions='',call_fn=None):
    if not isinstance(prompt,str) or not 3<=len(prompt.strip())<=5000:raise ValueError('PROMPT_LENGTH_3_TO_5000')
    if kind not in ('text','speech'):raise ValueError('UNSUPPORTED_LOCAL_KIND')
    j=create_job(run,kind,uuid.uuid4().hex[:8],backend='OLLAMA_LOCAL' if kind=='text' else 'MACOS_SAY')
    modify(run,j['id'],status='RUNNING',prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    dest=pathlib.Path(run)/'local_artifacts';dest.mkdir(exist_ok=True)
    t0=time.monotonic()
    try:
        if kind=='text':
            if model!='qwen2.5:1.5b':raise ValueError('LOCAL_MODEL_NOT_VERIFIED_FOR_THIS_RELEASE')
            res=(call_fn or _ollama)(prompt,model)
            if not isinstance(res,dict) or not isinstance(res.get('output'),str) or not res['output'].strip():raise ValueError('EMPTY_LLM_OUTPUT')
            path=dest/(j['id']+'.txt');path.write_text(res['output'])
            receipt={k:res.get(k) for k in ('model','prompt_eval_count','eval_count','wall_s','provider_ns')}
            if not all(type(receipt.get(k))==int for k in ('prompt_eval_count','eval_count')):raise ValueError('MISSING_ACTUAL_TOKEN_RECEIPT')
        else:
            if not shutil.which('say') or not shutil.which('ffprobe'):raise RuntimeError('MACOS_SAY_OR_FFPROBE_NOT_INSTALLED')
            path=dest/(j['id']+'.aiff')
            # Delivery instructions are metadata, not speech content.
            proc=subprocess.run(['say','-o',str(path),prompt],capture_output=True,text=True,timeout=150)
            if proc.returncode or not path.exists():raise RuntimeError('MACOS_SAY_FAILED:'+proc.stderr[:150])
            receipt={'transcript':prompt,'delivery_instructions_not_spoken':spoken_instructions,'actual_synthesis_calls':1}
        status=modify(run,j['id'],status='SUCCESS_VERIFIED',path=str(path.relative_to(run)),sha256=file_sha(path),bytes=path.stat().st_size,
                      wall_s=round(time.monotonic()-t0,4),receipt=receipt,provider_cost_usd=None)
        return status
    except Exception as e:
        modify(run,j['id'],status='FAILED_PROVIDER',reason=safe_error(e));return next(x for x in jobs(run) if x['id']==j['id'])

def generate_video(run,plan,task_id,shot_id,backend,acknowledge,rate=None,model='ltx-2-5-fast',
                   free_backend=None,paid_backend=None):
    if backend not in ('ltx_5s_probe','ltx_v2_8s'):raise ValueError('BACKEND_NOT_SUPPORTED')
    if acknowledge is not True:raise ValueError('EXPLICIT_REMOTE_GENERATION_ACK_REQUIRED')
    task=wb.find_task(plan,task_id);shot=wb.find_shot(task,shot_id)
    if backend=='ltx_v2_8s':
        if not os.environ.get('LTXV_API_KEY') and paid_backend is None:raise ValueError('LTXV_API_KEY_NOT_SET')
        if type(rate) not in (int,float) or not 0<rate<=10:raise ValueError('CONFIRMED_PRICE_PER_SECOND_REQUIRED')
    # Fail-closed optimization: a reviewed, sufficiently long acceptable shot needs no repeat.
    with LOCK:
        st=wb.get(pathlib.Path(run)/'workflow')
        if any(a['shot_id']==shot_id and a['duration_gate']=='PASS' and wb.artifact_valid(pathlib.Path(run)/'workflow',a)
               and any(r['artifact_id']==a['id'] and r.get('passed_local_rubric') for r in st['reviews'])
               for a in st['artifacts']):
            raise ValueError('ACCEPTED_SHOT_STOP_REGENERATION_REUSE_VERIFIED')
    j=create_job(run,'video',task_id,shot_id,backend)
    modify(run,j['id'],status='RUNNING',prompt_sha256=shot['prompt_sha256'],rights='AUTHORIZED_NONCONFIDENTIAL_TEST')
    dest=pathlib.Path(run)/'generated_media'/(j['id']+'.mp4');dest.parent.mkdir(exist_ok=True)
    try:
        if backend=='ltx_5s_probe':
            if free_backend is None:
                from ail_v43.backend import generate as free_backend
            rec=free_backend(shot['prompt'],dest,seed=42,duration=5)
            origin='VERIFIED_LTX_SPACE_API';name='Hugging Face LTX public demo';name_model=rec.get('model','LTX-2.5')
        else:
            if paid_backend is None:
                from ail_v44.provider_ltx import generate as paid_backend
            def callback(e):
                modify(run,j['id'],status='PROVIDER_SUBMITTED',provider_job_id=e.get('job_id'),
                       user_confirmed_estimate_usd=e.get('cost_estimate_usd'))
            rec=paid_backend(shot['prompt'],dest,model,ack_billable=True,price_usd_per_sec=rate,on_status=callback)
            origin='VERIFIED_PROVIDER_API';name='Official LTX v2';name_model=rec.get('model',model)
        with LOCK:
            admitted=wb.admit(pathlib.Path(run)/'workflow',plan,task_id,shot_id,dest,name,name_model,
                          'AUTHORIZED_NONCONFIDENTIAL_TEST',origin=origin,backend_receipt=rec)
        return modify(run,j['id'],status='SUCCESS_VERIFIED',artifact_id=admitted['id'],
                      duration_gate=admitted['duration_gate'],media=admitted['media'],file_sha256=admitted['sha256'],
                      user_confirmed_estimate_usd=rec.get('inferred_cost_usd'),provider_cost_usd=None)
    except Exception as e:
        reason=safe_error(e);status='FAILED_PROVIDER'
        if 'quota' in reason.lower() or 'zerogpu' in reason.lower():status='BLOCKED_DEPENDENCY'
        if 'MISSING_LTXV_API_KEY' in reason:status='BLOCKED_DEPENDENCY'
        modify(run,j['id'],status=status,reason=reason)
        return next(x for x in jobs(run) if x['id']==j['id'])

def generate_image(run,plan,task_id,acknowledge,model='black-forest-labs/FLUX.1-schnell',client_factory=None):
    if acknowledge is not True:raise ValueError('EXPLICIT_IMAGE_PROVIDER_ACK_REQUIRED')
    if not os.environ.get('HF_TOKEN') and client_factory is None:raise ValueError('HF_TOKEN_REQUIRED')
    if os.environ.get('AIL_ALLOW_BILLED_IMAGE')!='1' and client_factory is None:raise ValueError('AIL_ALLOW_BILLED_IMAGE_NOT_SET')
    task=wb.find_task(plan,task_id)
    if task['modality']!='text_to_image':raise ValueError('NOT_IMAGE_TASK')
    j=create_job(run,'image',task_id,backend='HF_INFERENCE_PROVIDER')
    modify(run,j['id'],status='RUNNING',prompt_sha256=task['source_prompt_sha256'])
    dest=pathlib.Path(run)/'generated_media'/(j['id']+'.png');dest.parent.mkdir(exist_ok=True)
    try:
        if client_factory is None:
            from huggingface_hub import InferenceClient
            client_factory=InferenceClient
        client=client_factory(api_key=os.environ.get('HF_TOKEN','TEST'))
        result=client.text_to_image(task['source_prompt'],model=model)
        result.save(str(dest))
        with LOCK:
            imported=wb.admit_image(pathlib.Path(run)/'workflow',plan,task_id,dest,'Hugging Face inference (client call)',model,'AUTHORIZED_NONCONFIDENTIAL_TEST')
            st=wb.get(pathlib.Path(run)/'workflow')
            for img in st['images']:
                if img['id']==imported['id']:
                    img['origin']='EXECUTED_HF_INFERENCE_CLIENT_LOCAL_RECEIPT_NOT_PROVIDER_INVOICE'
                    img['generation_request_kind']='REMOTE_HF_TEXT_TO_IMAGE_MODEL'
            wb.put(pathlib.Path(run)/'workflow',st)
        return modify(run,j['id'],status='SUCCESS_VERIFIED',artifact_id=imported['id'],sha256=imported['sha256'],
                      note='INFERENCE_CLIENT_SUBMITTED; PROVIDER_INVOICE_UNKNOWN; OUTPUT_NOT_HUMAN_REVIEWED')
    except Exception as e:
        modify(run,j['id'],status='FAILED_PROVIDER',reason=safe_error(e));return next(x for x in jobs(run) if x['id']==j['id'])

def close_reports(run):
    """Atomic lightweight seal. Provider media are local only, never counted as invoices."""
    with LOCK:
        return _close_reports_locked(run)

def _close_reports_locked(run):
    run=pathlib.Path(run);excluded={'MANIFEST_V46.json'};manifest=[]
    for p in sorted(run.rglob('*')):
        if not p.is_file() or p.name in excluded or p.name.startswith('UPLOAD_THIS_v46_'):continue
        if any(seg in ('artifacts','generated_media','local_artifacts','legacy_clips') for seg in p.relative_to(run).parts):continue
        if p.suffix=='.zip':continue
        manifest.append({'path':str(p.relative_to(run)),'sha256':file_sha(p),'bytes':p.stat().st_size})
    atomic(run/'MANIFEST_V46.json',{'files':manifest,'media_excluded':True,'claim':'NO_INDEPENDENT_APPROVAL'})
    import zipfile
    out=run/('UPLOAD_THIS_v46_'+run.name.removeprefix('v46_')+'.zip');tmp=out.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for r in manifest:z.write(run/r['path'],r['path'])
        z.write(run/'MANIFEST_V46.json','MANIFEST_V46.json')
    os.replace(tmp,out);return out

def recover_prior_v43_clips(run,downloads_root=None):
    """Display actual historical 5-second LTX outputs without misattributing shot prompts.

    Read only previous v4.3/v4.3.1 Mac receipts and exact SHA-matching MP4s.
    Original files remain untouched; no provider inference call is made.
    """
    import itertools
    from ail_v43.engine import media_probe
    run=pathlib.Path(run).resolve()
    downloads=pathlib.Path(downloads_root or pathlib.Path.home()/'Downloads').resolve()
    found=[];seen=set();outdir=run/'legacy_clips'
    for label in ('AIL-v431-executions','AIL-v43-executions'):
        base=downloads/label
        if not base.is_dir():continue
        paths=itertools.islice(base.rglob('GENERATIVE_EVIDENCE_V431.json' if label=='AIL-v431-executions' else 'generative_receipts_v43.json'),25)
        for receipt in paths:
            if not receipt.resolve().is_relative_to(downloads):continue
            try:data=json.loads(receipt.read_text());recs=data.get('records',[])
            except Exception:continue
            for rec in recs[:20]:
                if rec.get('status') not in ('COMPLETE_VERIFIED','COMPLETE','SUCCESS','REAL_GENERATION_COMPLETE') or rec.get('error'):
                    continue
                ident=rec.get('clip_id','')
                if not isinstance(ident,str) or not __import__('re').fullmatch('clip-[0-9a-f]{12}',ident) or ident in seen:continue
                path=rec.get('final_media','');sha=rec.get('probe',{}).get('sha256')
                if not isinstance(path,str) or not path.startswith('media/') or not sha:continue
                candidates=[receipt.parent/path]
                if data.get('source_run'):candidates.append(pathlib.Path(data['source_run'])/path)
                src=None
                for candidate in candidates:
                    r=candidate.resolve()
                    if r.is_relative_to(downloads) and r.is_file() and r.stat().st_size<200_000_000 and file_sha(r)==sha:
                        src=r;break
                if src is None:continue
                try:probe=media_probe(src)
                except Exception:continue
                if probe['sha256']!=sha:continue
                outdir.mkdir(exist_ok=True);target=outdir/(ident+'.mp4');shutil.copy2(src,target)
                if file_sha(target)!=sha:target.unlink(missing_ok=True);continue
                seen.add(ident)
                found.append({'id':ident,'path':str(target.relative_to(run)),'sha256':sha,'duration_s':probe['duration_s'],
                              'width':probe['width'],'height':probe['height'],'original_prompt':rec.get('prompt_sent'),
                              'model':rec.get('model'),'origin':'RECOVERED_PRIOR_MAC_LTX_RECEIPT_NOT_INDEPENDENTLY_ATTESTED',
                              'included_in_19_shot_benchmark':False,'independent_quality_approval':None,
                              'source_receipt_sha256':file_sha(receipt),'recovered_utc':utc()})
    atomic(run/'legacy_clips.json',found)
    return found
