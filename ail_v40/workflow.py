"""v4.0 real visual-first stock-footage editing (two-image motion montage per brief).

No AI image/video synthesizer. Commons still images are illustrative B-roll only;
photos do not depict the fictional clients and source tags do not replace vision QA.
A competent tool-first arm receives the same photos and hard quality gates as AIL.
"""
from __future__ import annotations
import json,math,subprocess,time,textwrap
from pathlib import Path
from ail_v38.workflow import (call_model,content_contract,diagnostic,safe_run,sha,utc)
from ail_v39.workflow import (factual_narration,narration_prompt,storyboard_prompt)
from ail_v41.captions import caption_png

ARMS=('B1_COMPETENT_TOOL_FIRST','AIL_EXPERIMENTAL_CONDITIONAL_NARRATION')
VERSION='v4.1.0'

def clip_command(photo:Path,caption:Path,clip:Path,seconds:float):
    """Compatibility path: core FFmpeg overlay; never invokes optional drawtext.

    The caption itself is rasterized to a real RGBA PNG in Python, with an
    optional Pillow renderer and a guaranteed standard-library fallback.
    """
    overlay_png=Path(caption).with_suffix('.overlay.png')
    caption_png(Path(caption),overlay_png)
    vf=("[0:v]scale=760:450:force_original_aspect_ratio=increase,"
        "crop=760:450,scale=810:480,"
        "zoompan=z='min(zoom+0.0004,1.045)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
        "d=1:s=640x360:fps=24[base];"
        "[base][1:v]overlay=0:0:shortest=1,format=yuv420p[composed]")
    return ['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-threads','2',
            '-loop','1','-framerate','24','-i',str(photo),
            '-loop','1','-framerate','24','-i',str(overlay_png),
            '-t',f'{seconds:.3f}', '-filter_complex',vf, '-map','[composed]',
            '-an','-c:v','libx264','-preset','ultrafast','-crf','29',
            '-pix_fmt','yuv420p','-r','24',str(clip)]

def stage_receipt(stage,exec_result,**more):return {'stage':stage,'execution':exec_result,**more}

def create_media(run:Path,out:Path,assets:list,task:dict,narration:str,receipts:list):
    audio=out/'voice.aiff'
    a=safe_run(['say','-r','185','-o',str(audio),narration],timeout=110)
    receipts.append(stage_receipt('mac_say_real_speech',a))
    if a['exit'] or not audio.exists():return {'status':'FAILED_SAY'}
    try:
        p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(audio)],capture_output=True,text=True,timeout=20,check=True)
        duration=float(json.loads(p.stdout)['format']['duration'])
    except Exception:return {'status':'FAILED_AUDIO_DURATION_PROBE'}
    if not 4<=duration<=39 or not math.isfinite(duration):return {'status':'BLOCKED_AUDIO_DURATION','duration':duration}
    per=max(3.5,(duration+0.8)/2)
    clips=[]
    for ix,(asset,fact) in enumerate(zip(assets,task['facts'])):
        pic=Path(asset['local_path'])
        # Fact overlays couple the visible scene to the specific narration contract;
        # still does not mean depicted institution is the fictional institution.
        txt='\n'.join(textwrap.wrap(fact,width=47))+'\nIllustrative footage — not the named venue'
        caption=out/f'caption_{ix}.txt';caption.write_text(txt,encoding='utf-8')
        clip=out/f'scene_{ix}.mp4'
        rr=safe_run(clip_command(pic,caption,clip,per),timeout=160)
        receipts.append(stage_receipt('ffmpeg_render_grounded_scene',rr,scene_index=ix,asset_id=asset['asset_id'],asset_sha256=asset['inspection']['sha256'],caption_sha256=sha(caption),caption_overlay_sha256=sha(caption.with_suffix('.overlay.png'))))
        if rr['exit'] or not clip.exists():return {'status':'FAILED_SCENE_RENDER','scene_index':ix}
        clips.append(clip)
    listing=out/'concat.txt'
    listing.write_text(''.join("file '"+str(c).replace("'","'\\''")+"'\n" for c in clips))
    silent=out/'silent_joined.mp4';final=out/'rendered_video.mp4'
    concat=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f','concat','-safe','0','-i',str(listing),'-c:v','copy',str(silent)],timeout=80)
    receipts.append(stage_receipt('ffmpeg_join_distinct_scenes',concat))
    if concat['exit']:return {'status':'FAILED_CONCAT'}
    mux=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-i',str(silent),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','64k','-t',f'{duration+0.8:.3f}','-movflags','+faststart',str(final)],timeout=100)
    receipts.append(stage_receipt('ffmpeg_audio_video_mux',mux))
    if mux['exit'] or not final.is_file():return {'status':'FAILED_MUX'}
    diag=diagnostic(final)
    dec=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-i',str(final),'-f','null','-'],timeout=120)
    receipts.append(stage_receipt('ffmpeg_complete_decode',dec))
    stills=[]
    for ix in range(2):
        f=out/f'frame_{ix}.png';ss=str(ix*per+1.0)
        rr=safe_run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-ss',ss,'-i',str(final),'-frames:v','1',str(f)],timeout=30)
        receipts.append(stage_receipt('ffmpeg_visual_frame_evidence',rr,scene_index=ix))
        if rr['exit'] or not f.is_file():return {'status':'FAILED_FRAME_EXTRACT'}
        stills.append(str(f.relative_to(run)))
    if diag['status']!='VALID_TECHNICAL' or dec['exit']:
        return {'status':'FAILED_FULL_DECODE','technical':diag}
    return {'status':'COMPLETE_TECHNICALLY','technical':diag,'video_path':str(final.relative_to(run)),
            'frame_paths':stills,'audio_path':str(audio.relative_to(run)),
            'output_sha256':sha(final),'scene_asset_ids':[x['asset_id'] for x in assets],
            'scene_source_sha256':[x['inspection']['sha256'] for x in assets],
            'narration_duration_s':round(duration,3)}

def execute(run:Path,task:dict,arm:str,assets:list,model:str,base:str,seed:int):
    if arm not in ARMS:raise ValueError('UNKNOWN_ARM')
    out=run/'media'/task['id']/arm
    out.mkdir(parents=True,exist_ok=False)
    begin=time.perf_counter();receipts=[];facts=None;decision=None
    def finish(status,reason=None,media=None):
        data={'task_id':task['id'],'arm':arm,'status':status,'reason':reason,
            'wall_s':round(time.perf_counter()-begin,4),'fact_contract':facts,
            'policy_action':decision,'receipts':receipts,'independent_visual_relevance':'UNKNOWN_PENDING_REVIEW',
            'independent_creative_approval':'UNKNOWN_PENDING_REVIEW','video_generation_model':'NONE',
            'media_process':'TWO_CC0_STILL_PHOTOS_ANIMATED_BY_FFMPEG'}
        if media:data.update(media)
        return data
    if len(assets)!=2 or len({x['inspection']['sha256'] for x in assets})!=2:
        return finish('BLOCKED_PRECOMMIT_VISUAL','MISSING_DISTINCT_LICENSED_THEME_ASSETS')
    try:
        storyboard,rec=call_model(base,model,storyboard_prompt(task),seed)
        receipts.append({'stage':'ollama_real_storyboard',**rec})
        (out/'storyboard.txt').write_text(storyboard,encoding='utf-8')
        check=content_contract(storyboard,task)
        if check['banned_phrases']:
            return finish('BLOCKED_PRECOMMIT_STORYBOARD','BANNED_FACT_IN_STORYBOARD')
        # Model is not permitted to hallucinate visual filenames. The curated, verified
        # shot board defines which photos can be used. This is conventional tool safety.
        board={'visual_match_level':'BROAD_TOPIC_ONLY_NOT_CLIENT_LOCATION',
               'captions_are_source_facts':list(task['facts']),
               'asset_ids':[x['asset_id'] for x in assets],
               'asset_descriptions':[x['description'] for x in assets],
               'model_plan_used_as_fact_or_asset_authority':False}
        (out/'shot_board.json').write_text(json.dumps(board,indent=2)+'\n')
        receipts.append({'stage':'curated_visual_preflight','result':'PASS_BROAD_TOPIC_ONLY','asset_ids':board['asset_ids'],
            'automatic_semantic_visual_validation':False})
        if arm==ARMS[0]:
            narration=factual_narration(task)
            decision='COMPETENT_DETERMINISTIC_NARRATION'
        else:
            narration,rec=call_model(base,model,narration_prompt(task,storyboard),seed+20000)
            receipts.append({'stage':'ollama_real_narration',**rec})
            draftcheck=content_contract(narration,task)
            decision='KEEP_LLM_CREATIVE_DRAFT' if draftcheck['narrow_literal_contract_pass'] else 'CONDITIONAL_TOOL_REPAIR'
            if not draftcheck['narrow_literal_contract_pass']:
                narration=factual_narration(task)
        (out/'narration.txt').write_text(narration,encoding='utf-8')
        facts=content_contract(narration,task)
        receipts.append({'stage':'hard_precommit_narration','result':'PASS' if facts['narrow_literal_contract_pass'] else 'BLOCK'})
        if not facts['narrow_literal_contract_pass']:return finish('BLOCKED_PRECOMMIT_NARRATION','FAILED_FACT_CONTRACT')
        media=create_media(run,out,assets,task,narration,receipts)
        return finish(media['status'],None if media['status']=='COMPLETE_TECHNICALLY' else media['status'],media)
    except Exception as e:
        return finish('FAILED_EXECUTION',type(e).__name__)

def aggregate(rows):
    result={}
    for arm in ARMS:
        rr=[x for x in rows if x['arm']==arm]
        actual=[t for r in rr for t in r.get('receipts',[]) if t.get('actual_ollama_inference')]
        result[arm]={'task_count':len(rr),'technical_complete':sum(x['status']=='COMPLETE_TECHNICALLY' for x in rr),
            'unknown_quality_review':len(rr),'model_calls':len(actual),
            'input_tokens':sum(int(t.get('usage',{}).get('prompt_eval_count') or 0) for t in actual),
            'output_tokens':sum(int(t.get('usage',{}).get('eval_count') or 0) for t in actual),
            'wall_s':round(sum(x['wall_s'] for x in rr),3),
            'video_scenes_encoded':sum(t['stage']=='ffmpeg_render_grounded_scene' for x in rr for t in x.get('receipts',[])),
            'cost_per_independently_approved_video':None}
    return result
