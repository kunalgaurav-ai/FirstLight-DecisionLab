"""v3.9 prospective comparison: stronger quality gates and 3 candid policy arms.

B1_STRICT_REASK = competent LLM drafting + one retry + HARD precommit block.
B2_TOOL_FIRST = competent deterministic fact assembly after real LLM storyboard.
AIL_CONDITIONAL_REPAIR_EXPERIMENTAL = LLM narration, then deterministic safe
  fact-assembly upon failed check; exploratory and NOT deployment-eligible.

Simple deterministic assembly is not proprietary optimization. All source
facts are constructed task inputs; literal preservation is not semantic QA.
"""
from __future__ import annotations
from pathlib import Path
import json, math, subprocess, time
from ail_v38.workflow import (CASES, MODE, MAX_SECONDS, call_model, content_contract,
   safe_run, diagnostic, sha, utc)

VERSION='v3.9.0'
ARMS=('B1_STRICT_REASK','B2_TOOL_FIRST','AIL_CONDITIONAL_REPAIR_EXPERIMENTAL')

def factual_narration(task):
    """Explicit, inspectable source-preserving fallback; not an LLM."""
    facts=' '.join(task['facts'])
    return f'Welcome to {task["client"]}. {facts} Thank you for joining us.'

def storyboard_prompt(task):
    facts=' '.join(task['facts'])
    return (f'Create 3 concise visual shot ideas for a short {task["topic"]} for '
        f'{task["client"]}, intended for {task["audience"]}. '
        'Use only visual descriptions, do not make up claims, do not repeat source '
        f'facts unnecessarily. Authorized source information: {facts} '
        'Format: 3 lines, numbered 1-3. No markdown preamble.')

def narration_prompt(task, storyboard):
    return (f'Write spoken narration of 35-65 words for {task["client"]}. '
        'Copy the following two verified factual sentences EXACTLY as written '
        'with no paraphrase. Include both once, in the narration, and do not '
        f'invent additional facts: {" ".join(task["facts"])} '
        'Do not state unsupported opening hours, prices or policies. '
        'Keep the narration concise and engaging; output only narration. '
        f'Shot plan context (not an additional factual source): {storyboard[:650]}')

def decide_after_draft(arm, task, draft, first_check):
    """Returns action before any downstream media, not an economic value estimate."""
    if arm=='B2_TOOL_FIRST':
        return 'DETERMINISTIC_SOURCE_ASSEMBLY'
    if first_check.get('narrow_literal_contract_pass'):
        return 'ACCEPT_LLM_NARRATION'
    if arm=='AIL_CONDITIONAL_REPAIR_EXPERIMENTAL':
        return 'DETERMINISTIC_REPAIR_NO_EXTRA_LLM'
    return 'ONE_LLM_REASK'

def model_call(base,model,prompt,seed,stage,receipts):
    text, rec=call_model(base,model,prompt,seed)
    receipts.append({'stage':stage,**rec})
    return text

def run_pipeline(run:Path, source:Path, model:str, base:str, task:dict, arm:str, seed:int):
    if arm not in ARMS:raise ValueError('invalid arm')
    outdir=run/'media'/task['id']/arm
    outdir.mkdir(parents=True,exist_ok=False)
    receipts=[];started=time.perf_counter()
    policy={'arm':arm,'permission':'LOCAL_ONLY',
      'experimental':arm=='AIL_CONDITIONAL_REPAIR_EXPERIMENTAL',
      'quality_rule':'STRICT_NARRATION_LITERAL_PRECOMMIT',
      'counterfactual_causal_gain':'NOT_IDENTIFIED'}
    def finish(status, plan_check=None, narr_check=None, reason=None, **extra):
        o={'task_id':task['id'],'arm':arm,'status':status,'reason':reason,
          'policy':policy,'source_facts':task['facts'],'storyboard_contract':plan_check,
          'narration_contract':narr_check,'creative_approval':'UNKNOWN_PENDING_BLIND_REVIEW',
          'media_process':'EDITED_EXISTING_VIDEO' if status=='COMPLETE' else 'NOT_RENDERED',
          'image_generation':'NOT_PERFORMED','video_generation_model':'NOT_PERFORMED',
          'wall_s':round(time.perf_counter()-started,4),'receipts':receipts}
        o.update(extra);return o
    plan_check=None;narr_check=None
    try:
        plan=model_call(base,model,storyboard_prompt(task),seed,'ollama_storyboard',receipts)
        (outdir/'storyboard.txt').write_text(plan,encoding='utf-8')
        # A storyboard is not itself a published narration. Record, don't require
        # verbatim facts in it. However, banned text is a serious warning.
        plan_check=content_contract(plan,task)
        if plan_check['banned_phrases']:
            receipts.append({'stage':'precommit_decision','action':'STOP_UNSUPPORTED_STORYBOARD',
                 'reason':'BANNED_ASSERTION_IN_INTERNAL_PLAN'})
            return finish('STOPPED_PRECOMMIT_STORYBOARD',plan_check,None,'BANNED_ASSERTION')
        if arm=='B2_TOOL_FIRST':
            narration=factual_narration(task)
            receipts.append({'stage':'precommit_decision','action':'TOOL_FIRST_SOURCE_ASSEMBLY',
              'reason':'COMPETENT_DETERMINISTIC_BASELINE','no_model_narration':True})
        else:
            narration=model_call(base,model,narration_prompt(task,plan),seed+20000,'ollama_narration',receipts)
            initial=content_contract(narration,task)
            action=decide_after_draft(arm,task,narration,initial)
            receipts.append({'stage':'precommit_decision','action':action,
                             'fact_check_before_action':initial['narrow_literal_contract_pass']})
            if action=='ONE_LLM_REASK':
                prompt=('Rewrite narration of 35 to 65 words. EXACT, unmodified '
                      f'source statements MUST appear: {" ".join(task["facts"])} '
                       'If necessary, copy them first. Remove unsupported factual '
                       f'claims. Earlier draft: {narration[:650]}')
                narration=model_call(base,model,prompt,seed+30000,'ollama_narration_reask',receipts)
            elif action=='DETERMINISTIC_REPAIR_NO_EXTRA_LLM':
                narration=factual_narration(task)
        (outdir/'narration_final.txt').write_text(narration,encoding='utf-8')
        narr_check=content_contract(narration,task)
        receipts.append({'stage':'hard_precommit_gate','result':'PASS' if narr_check['narrow_literal_contract_pass'] else 'BLOCK',
          'before':['mac_say_speech','ffmpeg_actual_video_encoding'],
          'reason':'LITERAL_FACTS_AND_BANNED_PHRASES'})
        if not narr_check['narrow_literal_contract_pass']:
            return finish('STOPPED_PRECOMMIT_NARRATION',plan_check,narr_check,'FAILED_NARRATION_CONTRACT_AFTER_ALLOWED_REPAIR')
        audio=outdir/'voice.aiff'
        rs=safe_run(['say','-r','185','-o',str(audio),narration],timeout=120)
        receipts.append({'stage':'mac_say_speech','execution':rs})
        if rs['exit'] or not audio.is_file():raise RuntimeError('SPEECH_SYNTHESIS_FAILED')
        s=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(audio)],
          capture_output=True,text=True,check=True,timeout=20)
        seconds=float(json.loads(s.stdout)['format']['duration'])
        if not math.isfinite(seconds) or not 0<seconds<=40:
            return finish('STOPPED_PRECOMMIT_DURATION',plan_check,narr_check,'AUDIO_DURATION_OUTSIDE_BUDGET')
        render_seconds=max(10,min(41,math.ceil(seconds+1)))
        receipts.append({'stage':'tts_duration_precommit_check','measured_s':round(seconds,3),'selected_video_duration_s':render_seconds})
        mp4=outdir/'rendered_video.mp4'
        argv=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-threads','2','-stream_loop','-1',
              '-i',str(source),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-t',str(render_seconds),
              '-vf','scale=640:360,fps=24','-af','apad','-c:v','libx264','-preset','ultrafast',
              '-crf','30','-pix_fmt','yuv420p','-c:a','aac','-b:a','64k','-movflags','+faststart',str(mp4)]
        rr=safe_run(argv,timeout=180)
        receipts.append({'stage':'ffmpeg_actual_video_encoding','execution':rr})
        if rr['exit'] or not mp4.is_file():raise RuntimeError('VIDEO_ENCODE_FAILED')
        image=outdir/'frame.png'
        ri=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-ss','1','-i',str(mp4),'-frames:v','1',str(image)],timeout=50)
        receipts.append({'stage':'actual_video_frame_extraction','execution':ri})
        tech=diagnostic(mp4)
        rd=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-i',str(mp4),'-f','null','-'],timeout=90)
        receipts.append({'stage':'decode_entire_output','execution':rd})
        if not (tech['status']=='VALID_TECHNICAL' and rd['exit']==0 and image.is_file()):
            return finish('FAILED_TECHNICAL',plan_check,narr_check,'FFMPEG_VALIDATION_FAILED',technical=tech)
        return finish('COMPLETE',plan_check,narr_check,None,technical=tech,media_sha256=sha(mp4),
          video_path=str(mp4.relative_to(run)),frame_path=str(image.relative_to(run)),audio_path=str(audio.relative_to(run)))
    except Exception as e:
        return finish('FAILED_EXECUTION',plan_check,narr_check,type(e).__name__,error_type=type(e).__name__)

def summarize(rows):
    out={}
    for arm in ARMS:
        ts=[t for t in rows if t['arm']==arm]
        calls=[r for t in ts for r in t.get('receipts',[]) if r.get('actual_ollama_inference')]
        stages=[r for t in ts for r in t.get('receipts',[])]
        out[arm]={
          'attempts':len(ts),'technical_valid':sum(t['status']=='COMPLETE' for t in ts),
          'precommit_stopped':sum(t['status'].startswith('STOPPED_PRECOMMIT') for t in ts),
          'narration_contract_pass':sum(bool((t.get('narration_contract') or {}).get('narrow_literal_contract_pass')) for t in ts),
          'model_calls':len(calls),
          'input_tokens_reported':sum(int(r['usage'].get('prompt_eval_count') or 0) for r in calls),
          'output_tokens_reported':sum(int(r['usage'].get('eval_count') or 0) for r in calls),
          'llm_length_terminations':sum(r['usage'].get('done_reason')=='length' for r in calls),
          'say_executions':sum(r['stage']=='mac_say_speech' for r in stages),
          'video_encode_executions':sum(r['stage']=='ffmpeg_actual_video_encoding' for r in stages),
          'total_wall_s':round(sum(t['wall_s'] for t in ts),3),
          'cost_per_approved_result':None,'independently_approved':None}
    return out
