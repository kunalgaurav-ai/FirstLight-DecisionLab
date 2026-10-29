"""Prospective LOCAL workflow execution. Never models generated video or human approval.

Execution semantics:
  Ollama model -> storyboard -> model narration -> Mac say -> FFmpeg licensed source
  -> image frame + independent technical diagnostics -> manual blinded review.

Two arms receive the same mandatory checks/repair rules. AIL may only depart
from the incumbent when a separately authorized calibrated policy is loaded;
this release does not accept fictitious action benefit numbers.
"""
from __future__ import annotations
import hashlib, json, math, os, platform, random, shutil, subprocess, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

VERSION='v3.8.0'
MAX_SECONDS=180
MODE='REAL_OLLAMA_SCRIPT__REAL_MAC_SAY__REAL_FFMPEG_ENCODE__EXISTING_SOURCE_VIDEO'
ARMS=('B1_COMPETENT_INCUMBENT','AIL_PIVOT_SAFE_FALLBACK')
# Author-created benchmark briefs with positive and negative facts. Not customer tasks.
CASES=(
 dict(id='c01_archive',client='Marble City History Center',audience='families',topic='a museum welcome video',
      facts=('The Marble City exhibit opens at ten in the morning.','Admission is free on Thursdays.'),
      banned=('opens at six','tickets cost fifty dollars')),
 dict(id='c02_trails',client='Aster Trails Nature Center',audience='new visitors',topic='a nature trail introduction',
      facts=('The Blue Loop trail is three kilometers long.','The trail closes during lightning warnings.'),
      banned=('five kilometers long','remains open during lightning')),
 dict(id='c03_library',client='Willow Public Library',audience='students',topic='an educational service announcement',
      facts=('The maker workshop takes place on Saturdays.','Visitors must register before the workshop.'),
      banned=('takes place on Mondays','walk-ins are guaranteed')),
 dict(id='c04_gallery',client='Harbor Glass Gallery',audience='art lovers',topic='an exhibition highlight',
      facts=('The exhibition features hand-blown glass from local artists.','Photography without flash is permitted.'),
      banned=('flash photography is encouraged','the exhibition sells original paintings')),
)

def utc(): return datetime.now(timezone.utc).isoformat()
def sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<18),b''):h.update(b)
    return h.hexdigest()
def text_sha(s:str):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def bounded(text,n=1000): return text[:n]
def command_version(name):
    p=shutil.which(name)
    if not p:return None
    try:
        opt='-version' if name.startswith('ff') else '--version'
        r=subprocess.run([p,opt],capture_output=True,text=True,timeout=8)
        return {'path':p,'first_line':(r.stdout or r.stderr).splitlines()[0][:140] if (r.stdout or r.stderr) else '', 'exit':r.returncode}
    except Exception as e:return {'path':p,'version_error':type(e).__name__}

def safe_run(argv, timeout=MAX_SECONDS):
    t=time.perf_counter()
    try:
        r=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
        return {'exit':r.returncode,'elapsed_s':round(time.perf_counter()-t,4),
                'stderr_last':bounded(r.stderr[-900:]),'stdout_last':bounded(r.stdout[-900:])}
    except subprocess.TimeoutExpired:
        return {'exit':124,'elapsed_s':round(time.perf_counter()-t,4),'error':'TIMEOUT'}

def api(base,path,data=None,timeout=12):
    url=base.rstrip('/')+path
    req=urllib.request.Request(url,data=(json.dumps(data).encode() if data is not None else None),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return json.loads(resp.read())

def probe(base,model):
    try:
        d=api(base,'/api/tags')
        names=[m.get('name') or m.get('model') for m in d.get('models',[])]
        if model not in names:return {'ready':False,'reason':'REQUIRED_MODEL_NOT_INSTALLED','models_available':names}
        # /api/show digest metadata is optional; the tag list may contain a digest.
        match=next((m for m in d.get('models',[]) if (m.get('name') or m.get('model'))==model),{})
        return {'ready':True,'model':model,'digest':match.get('digest'),'size_bytes':match.get('size')}
    except Exception as e:return {'ready':False,'reason':'OLLAMA_API_UNREACHABLE','error_type':type(e).__name__}

def call_model(base,model,prompt,seed):
    start=time.perf_counter()
    payload={'model':model,'prompt':prompt,'stream':False,'options':{'num_ctx':2048,'num_predict':230,'temperature':0.2,'seed':seed}}
    response=api(base,'/api/generate',payload,timeout=MAX_SECONDS)
    body=response.get('response','')
    if not isinstance(body,str): raise ValueError('Ollama response missing string')
    metadata={k:response.get(k) for k in ('model','done_reason','prompt_eval_count','prompt_eval_cached_count','eval_count',
      'total_duration','load_duration','prompt_eval_duration','eval_duration')}
    return body,{'time_utc':utc(),'elapsed_wall_s':round(time.perf_counter()-start,4),'prompt_sha256':text_sha(prompt),
      'response_sha256':text_sha(body),'usage':metadata,'actual_ollama_inference':True}

def normalize(t):return ' '.join(''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in t).split())
def content_contract(out,case):
    norm=normalize(out)
    # Anchors are independent user-provided facts. This is narrow literal contract checking, NOT general semantic QA.
    facts=[bool(normalize(x) in norm) for x in case['facts']]
    banned=[x for x in case['banned'] if normalize(x) in norm]
    return {'all_exact_source_facts_in_output':all(facts),'fact_matches':facts,'banned_phrases':banned,
            'narrow_literal_contract_pass':all(facts) and not banned,
            'limitations':'Does not establish factuality outside the supplied facts or creative acceptance'}

def diagnostic(path:Path):
    r=safe_run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],timeout=20)
    if r['exit']:return {'status':'FAIL_FFPROBE','details':r}
    try:
        s=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],
                         capture_output=True,text=True,timeout=20,check=True)
        o=json.loads(s.stdout)
        streams=o.get('streams',[]);formats=o.get('format',{})
        hasv=any(k.get('codec_type')=='video' for k in streams)
        hasa=any(k.get('codec_type')=='audio' for k in streams)
        dur=float(formats.get('duration') or 0)
        return {'status':'VALID_TECHNICAL' if (hasv and hasa and dur>=3) else 'INVALID_TECHNICAL',
          'has_video':hasv,'has_audio':hasa,'duration_s':dur,'streams':[{'type':x.get('codec_type'),
          'codec':x.get('codec_name'),'width':x.get('width'),'height':x.get('height')} for x in streams]}
    except Exception as e:return {'status':'FAIL_MEDIA_METADATA','error':type(e).__name__}

def source_admission(source:Path|None):
    if source is None:return {'admitted':False,'reason':'NO_USER_SOURCE_VIDEO'}
    if not source.is_file():return {'admitted':False,'reason':'SOURCE_NOT_FOUND','path':str(source)}
    try:
        s=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type:format=duration',
                           '-of','json',str(source)],capture_output=True,text=True,timeout=20,check=True)
        o=json.loads(s.stdout);hasv=any(x.get('codec_type')=='video' for x in o.get('streams',[]))
        dur=float(o.get('format',{}).get('duration') or 0)
        return {'admitted':hasv and dur>=4,'reason':'VIDEO_OK' if hasv and dur>=4 else 'INVALID_VIDEO_SOURCE',
                'path':str(source),'sha256':sha(source),'bytes':source.stat().st_size,'duration_s':dur,
                'rights':'USER_SUPPLIED_SOURCE_RIGHTS_MUST_BE_INDEPENDENTLY_VERIFIED_BEFORE_EXTERNAL_USE'}
    except Exception as e:return {'admitted':False,'reason':'VIDEO_PROBE_ERROR','error':type(e).__name__}

def find_video():
    base=Path.home()/'Downloads'/'agent-intelligence-lab-rigorous'/'data'/'open_media'
    return next((p for p in (base/'bbb_480p_30s.mp4',base/'bbb_480p_30s_licensed.mp4') if p.is_file()),None)

def snapshot_system():
    x={'os':platform.platform(),'python':platform.python_version(),'host':platform.node(),
      'ffmpeg':command_version('ffmpeg'),'ffprobe':command_version('ffprobe'),
      'say_exists':bool(shutil.which('say')),'resource_scope':'LOCAL_COMPUTE_ONLY_NO_INVOICE'}
    return x

def run_pipeline(run:Path,source:Path,model:str,base:str,task:dict,arm:str,seed:int):
    outdir=run/'media'/task['id']/arm
    outdir.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    receipts=[]
    # Mandatory incumbent preflight applies identically to both arms.
    policy={'selected':'B1_COMPETENT_EARLY_CHECK','ail_deviation':'NONE_NO_CALIBRATED_ACTION_VALUE',
            'permission':'LOCAL_ONLY','quality_gate':'CHECK_BEFORE_NONREFUNDABLE_STAGE'}
    facttext=' '.join(task['facts'])
    prompt=(f'You are preparing a precise 20-second promotional video storyboard for {task["client"]}. '
      f'Audience: {task["audience"]}. Topic: {task["topic"]}. '
      f'You must repeat BOTH of these exact factual sentences without inventing anything: {facttext} '
      'Create a short shot plan. Keep all factual statements exactly as given. No unrelated claims.')
    try:
        storyboard,r=call_model(base,model,prompt,seed)
        receipts.append({'stage':'ollama_storyboard',**r})
        (outdir/'storyboard.txt').write_text(storyboard,encoding='utf-8')
        c=content_contract(storyboard,task)
        if not c['narrow_literal_contract_pass']:
            receipts.append({'stage':'precommit_decision','checkpoint':'AFTER_STORYBOARD_BEFORE_VOICE_AND_VIDEO','signal':'MISSING_OR_CONFLICTING_SOURCE_FACT', 'action':'REASK_STORYBOARD','reason':'MANDATORY_INCUMBENT_SOURCE_CONTRACT', 'relative_to_incumbent':'NO_INCREMENTAL_CLAIM'})
            repair_prompt='Revise ONLY to include the following two exact sentences, unchanged. '+facttext+'\nInitial plan:\n'+storyboard[:1300]
            storyboard,r=call_model(base,model,repair_prompt,seed+10000)
            receipts.append({'stage':'ollama_storyboard_repair',**r})
            (outdir/'storyboard_repaired.txt').write_text(storyboard,encoding='utf-8')
        plan_contract=content_contract(storyboard,task)
        # Model-generated continuation uses previous model's actual plan as input.
        narration_prompt=(f'Write a coherent short spoken video narration for {task["client"]}. '
           'Keep EXACTLY the two source sentences somewhere in the narration, copied verbatim. '
           f'Source facts: {facttext}\nOriginal model-written plan:\n{storyboard[:1200]}\n'
           'Do not invent opening hours, prices or medical advice. Write approximately 35 to 50 words. Output narration only.')
        narration,r=call_model(base,model,narration_prompt,seed+20000)
        receipts.append({'stage':'ollama_narration',**r})
        (outdir/'narration.txt').write_text(narration,encoding='utf-8')
        narration_contract=content_contract(narration,task)
        # Never treat a literal fact check as a creative evaluator.
        if not narration_contract['narrow_literal_contract_pass']:
            receipts.append({'stage':'precommit_decision','checkpoint':'AFTER_NARRATION_BEFORE_VOICE_AND_VIDEO','signal':'MISSING_OR_CONFLICTING_SOURCE_FACT', 'action':'REASK_NARRATION','reason':'MANDATORY_INCUMBENT_SOURCE_CONTRACT', 'relative_to_incumbent':'NO_INCREMENTAL_CLAIM'})
            repair_prompt='Return narration using exactly these verified facts, word for word: '+facttext+'\nDraft: '+narration[:800]
            narration,r=call_model(base,model,repair_prompt,seed+30000)
            receipts.append({'stage':'ollama_narration_repair',**r})
            (outdir/'narration_repaired.txt').write_text(narration,encoding='utf-8')
            narration_contract=content_contract(narration,task)
        # This is actual macOS speech output, NOT a fake sine-wave audio file.
        saypath=outdir/'voice.aiff'
        rs=safe_run(['say','-r','185','-o',str(saypath),narration[:650]],timeout=120)
        receipts.append({'stage':'mac_say_speech','execution':rs})
        if rs['exit'] or not saypath.is_file():raise RuntimeError('say audio synthesis failed')
        # Commit to video render only after measuring TTS length: never silently chop speech.
        meta=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(saypath)],
                    capture_output=True,text=True,timeout=20,check=True)
        speech_seconds=float(json.loads(meta.stdout)['format']['duration'])
        if not math.isfinite(speech_seconds) or speech_seconds<=0 or speech_seconds>40:
            raise ValueError('NARRATION_OUTSIDE_ACCEPTABLE_40_SECOND_RUNTIME_BUDGET')
        render_seconds=max(10,min(41,math.ceil(speech_seconds+1)))
        receipts.append({'stage':'tts_duration_precommit_check','measured_s':round(speech_seconds,3),
                         'selected_video_duration_s':render_seconds,'prevents_truncated_audio':True})
        mp4=outdir/'rendered_video.mp4'
        argv=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-threads','2','-stream_loop','-1',
              '-i',str(source),'-i',str(saypath),'-map','0:v:0','-map','1:a:0','-t',str(render_seconds),'-vf','scale=640:360,fps=24',
              '-af','apad','-c:v','libx264','-preset','ultrafast','-crf','30','-pix_fmt','yuv420p',
              '-c:a','aac','-b:a','64k','-movflags','+faststart',str(mp4)]
        rr=safe_run(argv,timeout=180)
        receipts.append({'stage':'ffmpeg_actual_video_encoding','execution':rr})
        if rr['exit'] or not mp4.is_file():raise RuntimeError('ffmpeg media assembly failed')
        image=outdir/'frame.png'
        re=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-ss','1','-i',str(mp4),
                     '-frames:v','1',str(image)],timeout=50)
        receipts.append({'stage':'actual_video_frame_extraction','execution':re})
        technical=diagnostic(mp4)
        decode=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-i',str(mp4),'-f','null','-'],timeout=90)
        receipts.append({'stage':'decode_entire_output','execution':decode})
        good=technical['status']=='VALID_TECHNICAL' and decode['exit']==0 and image.is_file()
        return {'task_id':task['id'],'arm':arm,'policy':policy,'status':'COMPLETE' if good else 'FAILED_TECHNICAL',
           'source_facts':task['facts'],'storyboard_contract':plan_contract,'narration_contract':narration_contract,
           'creative_approval':'UNKNOWN_PENDING_BLIND_INDEPENDENT_REVIEW','image_generation':'NOT_PERFORMED',
           'video_generation_model':'NOT_PERFORMED','media_process':'EDITED_EXISTING_VIDEO',
           'video_path':str(mp4.relative_to(run)),'frame_path':str(image.relative_to(run)),
           'audio_path':str(saypath.relative_to(run)),'media_sha256':sha(mp4),
           'technical':technical,'wall_s':round(time.perf_counter()-start,4),'receipts':receipts}
    except Exception as e:
        return {'task_id':task['id'],'arm':arm,'policy':policy,'status':'FAILED_EXECUTION',
          'reason_type':type(e).__name__,'reason_text':str(e)[:250],'creative_approval':'UNKNOWN',
          'wall_s':round(time.perf_counter()-start,4),'receipts':receipts}

def summarise(rows):
    summ={}
    for arm in ARMS:
        a=[x for x in rows if x['arm']==arm]
        tokens_in=tokens_out=0; totalwall=0
        for x in a:
            totalwall+=x.get('wall_s',0)
            for s in x.get('receipts',[]):
                u=s.get('usage',{});tokens_in+=u.get('prompt_eval_count') or 0;tokens_out+=u.get('eval_count') or 0
        summ[arm]={'attempts':len(a),'technical_valid':sum(x.get('status')=='COMPLETE' for x in a),
           'literal_contract_pass':sum(x.get('narration_contract',{}).get('narrow_literal_contract_pass',False) for x in a),
           'ollama_input_tokens_reported':tokens_in,'ollama_output_tokens_reported':tokens_out,
           'total_wall_s':round(totalwall,3),'independently_approved':None,'cost_per_approved_result':None}
    return summ

def setup_review_cards(rows,run):
    rng=random.Random(20261025)
    cards=[{'task_id':x['task_id'],'arm':x['arm'],'video_path':x.get('video_path'),
            'source_facts':list(x.get('source_facts',[])),
            'status':x.get('status'),'review_id':f'R{i:03}'} for i,x in enumerate(rows)]
    rng.shuffle(cards)
    for j,c in enumerate(cards):c['review_id']=f'R{j+1:03}'
    (run/'review_index.json').write_text(json.dumps(cards,indent=2),encoding='utf-8')
    # This index remains local to the run; actual independent reviews are recorded by the dashboard.
    return [{'review_id':x['review_id'],'task_id':x['task_id'],'status':x['status']} for x in cards]
