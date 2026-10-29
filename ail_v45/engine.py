"""v4.5 live local, policy-matched branch tests. No cloud/video claims.

The fixed text cases have objective *string/length* checks, not human acceptance.
Two branches fork the same observed LLM output; B2 skips that LLM entirely.
All model costs are local resource receipts, not billed USD.
"""
from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,time,uuid,zipfile
from pathlib import Path
from datetime import datetime,timezone
from ail_v44.workbench import ollama

def utc():return datetime.now(timezone.utc).isoformat()
def sha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(65536),b''):h.update(c)
 return h.hexdigest()
def save_json(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
 tmp.write_text(json.dumps(o,indent=2,sort_keys=True,ensure_ascii=False)+'\n');os.replace(tmp,p)
def load_plan(path):
 p=json.loads(Path(path).read_text())
 if p.get('kind')!='AIL_V45_OBSERVED_DECISION_SUITE':raise ValueError('PLAN_TYPE')
 if len(p['texts'])<3 or len(p['audios'])<2:raise ValueError('PLAN_TOO_NARROW')
 seen=set()
 for t in p['texts']:
  if t['task_id'] in seen:raise ValueError('DUPLICATE_ID')
  seen.add(t['task_id'])
  if sha(t['prompt'])!=t['prompt_sha256'] or sha(t['canonical'])!=t['canonical_sha256']:raise ValueError('FROZEN_TEXT_HASH')
  if not (40<=t['min_words']<=t['max_words']<=150):raise ValueError('WORD_BOUNDS')
  if not validate_text(t,t['canonical'])['objective_pass']:raise ValueError('UNSAFE_TOOL_FIRST_CANONICAL:'+t['task_id'])
 for t in p['audios']:
  if t['task_id'] in seen:raise ValueError('DUPLICATE_ID')
  seen.add(t['task_id'])
  if sha(t['spoken_text']+'\n'+t['delivery_instructions'])!=t['prompt_sha256']:raise ValueError('FROZEN_AUDIO_HASH')
  if t['delivery_instructions'].lower() in t['spoken_text'].lower():raise ValueError('SPEAKS_INSTRUCTIONS')
 return p

def wordcount(s):return len(re.findall(r"\b[\w]+(?:['’][\w]+)?\b",s))
def validate_text(task,text):
 # EXACT string presence is a narrow *contract* and not semantic verification.
 low=' '.join(text.casefold().split()); required={x:(' '.join(x.casefold().split()) in low) for x in task['facts']}
 words=wordcount(text);okay=all(required.values()) and task['min_words']<=words<=task['max_words']
 return {'word_count':words,'min_words':task['min_words'],'max_words':task['max_words'],'required_fact_strings_present':required,'objective_pass':okay,
         'independent_approval':'UNKNOWN','semantic_factuality':'NOT_EVALUATED','style_quality':'NOT_EVALUATED'}

def targeted_repair(task,original):
 """Low-risk string insertion/padding, with explicit fallback; never claim creative equivalence."""
 original=original.strip(); check=validate_text(task,original)
 if check['objective_pass']:return original,'NO_REPAIR'
 if wordcount(original)>task['max_words'] or not original:return task['canonical'],'CANONICAL_FALLBACK'
 missing=[s for s,present in check['required_fact_strings_present'].items() if not present]
 candidate=original.rstrip('. ') + ('. ' if original else '') + ' '.join(missing)
 if validate_text(task,candidate)['objective_pass']:return candidate,'TARGETED_FACT_INSERTION'
 # Padding with neutral fixed-source wording, disclosing possible repetition.
 padding=['We hope you enjoy your visit and find the information useful.',
          'Please consult the organizers if you require further clarification.',
          'Thank you for taking the time to review these details.']
 for sentence in padding:
  candidate+=' '+sentence
  if validate_text(task,candidate)['objective_pass']:return candidate,'TARGETED_FACT_AND_PADDING'
  if wordcount(candidate)>task['max_words']:break
 return task['canonical'],'CANONICAL_FALLBACK'

def safe_call(prompt,model,call_fn):
 try:
  d=call_fn(prompt,model)
  if not isinstance(d,dict) or not isinstance(d.get('output'),str) or not d['output'].strip():raise ValueError('EMPTY_MODEL_OUTPUT')
  if any(type(d.get(k)) is not int or d[k]<0 for k in ('prompt_eval_count','eval_count')):raise ValueError('UNVERIFIED_TOKEN_RECEIPT')
  if type(d.get('wall_s')) not in (int,float) or d['wall_s']<0:raise ValueError('UNVERIFIED_WALL_RECEIPT')
  return d,None
 except Exception as e:return None,type(e).__name__+':'+str(e)[:280]

def text_trial(task,run,model,call_fn=ollama):
 run=Path(run);taskdir=run/'artifacts'/'text'/task['task_id'];taskdir.mkdir(parents=True,exist_ok=True)
 t0=time.monotonic();first,err=safe_call(task['prompt'],model,call_fn)
 if err:
  return {'task_id':task['task_id'],'status':'HOLD_NO_REAL_LLM_INPUT','error':err,'arms':{
   'B2_COMPETENT_TOOL_FIRST':render_text(task,task['canonical'],'DIRECT_CANONICAL',taskdir/'b2.txt',[],0)} }
 prefix=first['output'];(taskdir/'shared_original.txt').write_text(prefix)
 prefix_rec=receipt(first,taskdir/'shared_original.txt')
 preflight_t=time.monotonic()
 prefix_check=validate_text(task,prefix)
 preflight_wall_s=time.monotonic()-preflight_t
 # Strict competent retry: only if initial check fails. Shares exactly the same first generated sample with AIL.
 retry=None;retry_err=None
 if not prefix_check['objective_pass']:
  instruction=(task['prompt']+'\n\nThe previous draft did not satisfy the deterministic length or exact-fact-string gate. '
               +'Rewrite in '+str(task['min_words'])+'-'+str(task['max_words'])+' words and include the following sentences verbatim: '
               +' '.join(task['facts'])+'\nPrevious draft:\n'+prefix[:2400])
  retry,retry_err=safe_call(instruction,model,call_fn)
 strict=retry['output'] if retry else prefix
 t2=render_text(task,task['canonical'],'DIRECT_CANONICAL',taskdir/'b2.txt',[],0)
 b1=render_text(task,strict,'LLM_ONE_RETRY' if retry else ('ACCEPT_INITIAL' if prefix_check['objective_pass'] else 'RETRY_UNAVAILABLE'),taskdir/'b1.txt',
                [prefix_rec]+([receipt(retry,taskdir/'b1.txt')] if retry else []),0)
 repair_started=time.monotonic()
 corrected,action=targeted_repair(task,prefix)
 repair_wall_s=time.monotonic()-repair_started
 ail=render_text(task,corrected,action,taskdir/'ail.txt',[prefix_rec],repair_wall_s)
 if retry_err:b1['retry_error']=retry_err
 # Decision is based solely on observed predecision text, not a fitted recovery probability.
 out={'task_id':task['task_id'],'status':'REAL_BRANCH_EXECUTION_COMPLETED','model':model,'common_first_generation':True,
      'predecision_objective':prefix_check,'preflight_wall_s':preflight_wall_s,'initial_receipt':prefix_rec,'arms':{'B1_COMPETENT_LLM_RETRY':b1,'B2_COMPETENT_TOOL_FIRST':t2,'AIL_CONDITIONAL_REPAIR':ail},
      'elapsed_experiment_wall_s':time.monotonic()-t0,'review_status':'UNKNOWN_NO_BLIND_REVIEW',
      'comparison_limitation':'BRANCHES_SHARE_INITIAL_OBSERVED_TEXT; B2_NEEDS_NO_LLM; NO_INDEPENDENT_APPROVAL; NO_VERIFIED_USD'}
 return out

def receipt(call,path):
 return {k:call.get(k) for k in ('model','model_digest','prompt_eval_count','eval_count','provider_ns','wall_s')}

def render_text(task,text,action,path,calls,overhead):
 st=time.monotonic();path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 checker=validate_text(task,text)
 return {'action':action,'output_sha256':file_sha(path),'output_path':str(path), 'validation':checker,
  'input_tokens':sum(x.get('prompt_eval_count',0) for x in calls),'output_tokens':sum(x.get('eval_count',0) for x in calls),
  'llm_call_count':len(calls),'summed_llm_call_wall_s':sum(x.get('wall_s',0) for x in calls),
  'controller_overhead_wall_s':time.monotonic()-st+overhead,'cost_usd':None,'human_acceptance':'UNKNOWN'}

def available_voice():return shutil.which('say') is not None and shutil.which('ffprobe') is not None

def audio_trials(plan,run,synth=None):
 """B1 renders each; B2 and AIL use identical sound caches; no superiority claim."""
 run=Path(run);target=run/'artifacts'/'audio';target.mkdir(parents=True,exist_ok=True)
 if not available_voice() and synth is None:return {'status':'BLOCKED_NATIVE_SPEECH','arms':{},'reason':'MACOS_SAY_AND_FFPROBE_REQUIRED'}
 def native(text,out):
  t=time.monotonic();proc=subprocess.run(['say','-o',str(out),text],capture_output=True,text=True,timeout=100)
  if proc.returncode or not out.exists():raise RuntimeError('MACOS_SAY_FAILED:'+proc.stderr[:100])
  p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(out)],capture_output=True,text=True,timeout=30)
  if p.returncode:raise RuntimeError('FFPROBE_FAILED')
  return time.monotonic()-t,float(json.loads(p.stdout)['format']['duration'])
 synth=synth or native;arms={}
 for arm in ('B1_COMPETENT_NO_CACHE','B2_COMPETENT_EXACT_CACHE','AIL_EXACT_CACHE'):
  cached={};recs=[]
  for task in plan['audios']:
   key=sha(task['spoken_text']+'\0'+task['voice']+'\0'+task['delivery_instructions'])
   out=target/arm/(task['task_id']+'.aiff');out.parent.mkdir(parents=True,exist_ok=True)
   try:
    t0=time.monotonic()
    reuse=arm!='B1_COMPETENT_NO_CACHE' and key in cached
    if reuse:
     shutil.copyfile(cached[key]['path'],out);seconds=cached[key]['duration_s'];call=0;wall=0
    else:
     wall,seconds=synth(task['spoken_text'],out);call=1
     if not out.is_file() or out.stat().st_size<100:raise RuntimeError('SPEECH_FILE_MISSING')
    if arm!='B1_COMPETENT_NO_CACHE' and not reuse:cached[key]={'path':out,'duration_s':seconds}
    recs.append({'task_id':task['task_id'],'status':'REAL_MACOS_TTS' if synth==native else 'TEST_CONTROLLED_SYNTH',
       'transcript':task['spoken_text'],'delivery_instructions_not_spoken':task['delivery_instructions'],
       'cache_hit':reuse,'tts_invocations':call,'tts_wall_s':wall,'elapsed_stage_wall_s':time.monotonic()-t0,
       'duration_s':seconds,'sha256':file_sha(out),'output_path':str(out),'intelligibility':'UNKNOWN_NO_ASR_OR_HUMAN','estimated_usd':None})
   except Exception as e:
    recs.append({'task_id':task['task_id'],'status':'SPEECH_FAILED','reason':type(e).__name__+':'+str(e)[:160]})
  arms[arm]={'records':recs,'actual_tts_calls':sum(r.get('tts_invocations',0) for r in recs),
             'synthesis_wall_s':sum(r.get('tts_wall_s',0) for r in recs),
             'objective_script_separation':all(r.get('transcript')==t['spoken_text'] for t,r in zip(plan['audios'],recs))}
 return {'status':'EXECUTED_SOUND_COMPARISON','arms':arms,'comparison_limitation':'EXACT_CACHE_IS_STANDARD_BASELINE; NOT_AN_AIL_UNIQUE_EDGE; AUDIO_QUALITY_UNREVIEWED'}

def new_report(run,plan_path,model='qwen2.5:1.5b',call_fn=ollama,synth=None):
 run=Path(run)
 if run.exists():
  if (run/'results_v45.json').exists() or (run/'FROZEN_DECISION_SUITE_V45.json').exists():
   raise ValueError('EXPERIMENT_RUN_ALREADY_EXECUTED_NO_OVERWRITE')
 else:run.mkdir(parents=True,exist_ok=False)
 plan=load_plan(plan_path);save_json(run/'FROZEN_DECISION_SUITE_V45.json',plan)
 start=time.monotonic();rows=[]
 for task in plan['texts']:
  r=text_trial(task,run,model,call_fn);rows.append(r)
  save_json(run/'progress_v45.json',{'completed_text_cases':len(rows),'total_text_cases':len(plan['texts']),'phase':'TEXT'})
 aud=audio_trials(plan,run,synth)
 summary={}
 for arm in ('B1_COMPETENT_LLM_RETRY','B2_COMPETENT_TOOL_FIRST','AIL_CONDITIONAL_REPAIR'):
  found=[r['arms'][arm] for r in rows if arm in r['arms']]
  summary[arm]={'tasks_attempted':len(found),'objective_passes':sum(x['validation']['objective_pass'] for x in found),
                'model_input_tokens':sum(x['input_tokens'] for x in found),'model_output_tokens':sum(x['output_tokens'] for x in found),
                'model_calls':sum(x['llm_call_count'] for x in found),'sum_model_wall_seconds':sum(x['summed_llm_call_wall_s'] for x in found),
                'measured_controller_and_write_wall_s':sum(x['controller_overhead_wall_s'] for x in found)}
 result={'kind':'AIL_V45_EXECUTED_MATCHED_BRANCH_STUDY','version':'4.5.0', 'utc':utc(),
  'source_data':'FOUR_AUTHOR_CONSTRUCTED_PUBLIC_TEXT_CASES_THREE_AUDIO_CASES',
  'parent_v44_original_evidence_preserved':True,'text_trials':rows,'audio_trials':aud,'summary':summary,
  'actual_elapsed_experiment_wall_s':time.monotonic()-start,'provider_cost_usd':None,
  'independently_approved_outcomes':None,'strong_oss_competitive_superiority':'NOT_ESTABLISHED',
  'economics_limitation':'LOCALE_TOKENS_ARE_NOT_INVOICE; DETERMINISTIC_BASELINE_CAN_BE_FREE; FULL_DEPLOYMENT_OVERHEAD_NOT_MEASURED',
  'video':'NO_NEW_GENERATION_19_SHOTS_STILL_REQUIRE_AUTHORIZED_BACKEND',
  'image':'NO_VERIFIED_IMAGE_GENERATION_IN_THIS_EXPERIMENT',
  'coding':'PARENT_V44_CONTROLLED_TOOL_REPAIR_NOT_AUTONOMOUS_AGENT'}
 save_json(run/'results_v45.json',result)
 (run/'README_RESULTS.txt').write_text('Observed text branch experiments; actual local speech and exact cache. '+
    'Text objective checks are string and word-count only. No independent quality or USD superiority.\n')
 return result

def package(run):
 run=Path(run);manifest=[]
 for f in sorted(run.rglob('*')):
  if not f.is_file() or 'artifacts' in f.parts or f.name.startswith('UPLOAD_THIS_') or f.name=='MANIFEST_V45.json':continue
  manifest.append({'path':str(f.relative_to(run)),'sha256':file_sha(f),'size':f.stat().st_size})
 save_json(run/'MANIFEST_V45.json',{'files':manifest,'raw_artifacts_excluded':True})
 dest=run/('UPLOAD_THIS_v45_'+run.name.removeprefix('v45_')+'.zip');tmp=dest.with_suffix('.tmp')
 with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
  for rec in manifest:z.write(run/rec['path'],rec['path'])
  z.write(run/'MANIFEST_V45.json','MANIFEST_V45.json')
 os.replace(tmp,dest);return dest
