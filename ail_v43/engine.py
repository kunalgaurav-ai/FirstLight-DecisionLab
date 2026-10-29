"""Frozen task validation, cautious action selection, records, and actual MP4 probes."""
from __future__ import annotations
import hashlib, json, os, re, subprocess, time, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path

SPACE = 'Lightricks/LTX-2.5'
MODEL = 'Lightricks/LTX-2.5 distilled (official public Space)'
CRITERIA = ('prompt_elements', 'event_order', 'subject_motion', 'identity_continuity', 'visual_quality', 'safety_constraints')

def now(): return datetime.now(timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def save_json(p,obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n');tmp.replace(p)

def task_index(path):
    document=json.loads(Path(path).read_text())
    out={}
    for t in document['tasks']:
        if hashlib.sha256(t['prompt'].encode('utf-8')).hexdigest()!=t['prompt_sha256']:
            raise ValueError('FROZEN_PROMPT_HASH_MISMATCH:'+t['id'])
        if t['id'] in out: raise ValueError('DUPLICATE_PROMPT_ID')
        out[t['id']]=t
    return out

def validate_review(payload,task):
    scores=payload.get('scores')
    if not isinstance(scores,dict) or set(scores)!=set(CRITERIA): raise ValueError('REVIEW_REQUIRES_ALL_CRITERIA')
    if any(isinstance(v,bool) or not isinstance(v,int) or not 0<=v<=4 for v in scores.values()):
        raise ValueError('INVALID_REVIEW_SCORE')
    events=payload.get('events',{})
    allowed=set(task.get('events_in_order',[]))
    if set(events)!=allowed or any(v not in ('present','partial','missing','uncertain') for v in events.values()):
        raise ValueError('INVALID_EVENT_ANNOTATIONS')
    return {'scores':scores,'events':events,'reviewer_kind':('external' if payload.get('external_reviewer') is True else 'self_reported'),
            'notes':str(payload.get('notes',''))[:1000], 'review_utc':now()}

def decision(task,review,remaining_calls=1):
    if review is None: return {'action':'HOLD_REVIEW_UNKNOWN','reason':'No post-output annotated quality information'}
    scores=review['scores']; events=review['events']
    missing=[s for s,r in events.items() if r not in ('present',)]
    weak=[k for k,v in scores.items() if v < 3]
    if not missing and not weak:
        return {'action':'STOP_NO_REGEN','reason':'All annotated criteria passed, no justified extra calls',
                'approval': 'REVIEWED_BUT_NOT_INDEPENDENT' if review['reviewer_kind']!='external' else 'REVIEWER_DECLARED_EXTERNAL_NOT_VERIFIED'}
    if remaining_calls<1: return {'action':'HOLD_BUDGET','reason':'No generation-call budget'}
    if task['id']=='VID-01-LION-TEMPORAL' and len(task.get('shot_decomposition_option',[]))>1:
        if remaining_calls>=len(task['shot_decomposition_option']):
            return {'action':'GENERATE_MULTISHOT','reason':'Three distinct moving-event segments requested; each needs an actual generation',
                    'needed_calls':len(task['shot_decomposition_option']), 'missing':missing,'weak':weak}
        return {'action':'HOLD_BUDGET_MULTISHOT','needed_calls':len(task['shot_decomposition_option']),
                'reason':'Do not truncate the three-event story to an unlabeled short shot'}
    return {'action':'REGENERATE_STRUCTURED_PROMPT','reason':'Targeted correction after observed quality deficiencies',
            'missing':missing,'weak':weak}

def action_prompt(task,review,arm):
    original=task['prompt']; missing=[k for k,v in review['events'].items() if v!='present']
    weak=[k for k,v in review['scores'].items() if v<3]
    if arm=='B1_COMPETENT_RETRY':
        return (original+'\n\nCorrection for another full attempt: ' +
                ('Show the missed actions: '+ '; '.join(missing)+'. ' if missing else '')+
                ('Improve: '+', '.join(weak)+'. ' if weak else '')+
                'Ensure the finished moving video meets every original requirement; do not use still images.')
    if arm=='AIL_STRUCTURED_REPAIR':
        return (original+'\n\nSHOT EXECUTION CONTRACT: Start with the specified characters and environment. '
                'Perform these actions visibly in the exact order: '+ ' -> '.join(task.get('events_in_order',[]))+'. '
                'Maintain object and character identity between actions, show actual motion and subject interactions, '
                'and correct these observed omissions: '+('; '.join(missing) or 'none')+'. '
                'Focus on the missing motion/action, not an artistic title card. '
                'Other weak criteria: '+(', '.join(weak) or 'none')+'.')
    raise ValueError('UNSUPPORTED_INTERVENTION_ARM')

def media_probe(media_path,ffprobe='ffprobe',ffmpeg='ffmpeg'):
    p=Path(media_path)
    if not p.is_file() or p.stat().st_size<4096:raise ValueError('EMPTY_OR_MISSING_GENERATED_MP4')
    q=subprocess.run([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(p)],capture_output=True,text=True,timeout=45)
    if q.returncode:raise ValueError('FFPROBE_FAILED:'+q.stderr[:300])
    meta=json.loads(q.stdout); streams=[x for x in meta.get('streams',[]) if x.get('codec_type')=='video']
    if not streams:raise ValueError('GENERATED_FILE_HAS_NO_VIDEO_STREAM')
    s=streams[0];dur=float(meta.get('format',{}).get('duration') or s.get('duration') or 0)
    if dur<=0:raise ValueError('INVALID_DURATION')
    width,height=int(s['width']),int(s['height'])
    if width<128 or height<128:raise ValueError('VIDEO_RESOLUTION_TOO_SMALL')
    # Three decoded frame samples: an image difference is only a proxy for visual change.
    marks=[min(dur*.15,max(0,dur-.1)), dur*.50, dur*.85]
    frames=[]
    for sec in marks:
        f=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-ss',str(sec),'-i',str(p),
                          '-frames:v','1','-vf','scale=48:48','-pix_fmt','gray','-f','rawvideo','-'],
                         capture_output=True,timeout=45)
        frames.append(f.stdout if f.returncode==0 and len(f.stdout)==48*48 else b'')
    differences=[]
    for a,b in zip(frames,frames[1:]):
        differences.append(round(sum(abs(x-y) for x,y in zip(a,b))/len(a),4) if a and b else None)
    return {'sha256':file_sha(p),'bytes':p.stat().st_size,'duration_s':dur,'width':width,'height':height,
            'codec':s.get('codec_name'),'fps':s.get('r_frame_rate'),'decoded_frame_sample_luma_diffs':differences,
            'moving_image_semantics_verified':False,'disclaimer':'Frame differences may result from camera motion/noise and cannot prove prompt compliance.'}

def write_zip(run):
    run=Path(run);up=run/('UPLOAD_THIS_v43_'+run.name.removeprefix('v43_')+'.zip');tmp=up.with_suffix('.zip.tmp')
    files=sorted([p for p in run.iterdir() if p.is_file() and p.name!='UPLOAD_THIS_v43_'+run.name.removeprefix('v43_')+'.zip' and not p.name.endswith('.tmp')])
    receipts=[]
    for f in files:
        if f.name.startswith('media_') or f.name=='REPORT_SHA256_MANIFEST_V43.json':continue
        receipts.append({'file':f.name,'sha256':file_sha(f),'bytes':f.stat().st_size})
    save_json(run/'REPORT_SHA256_MANIFEST_V43.json',{'created_utc':now(),'files':receipts,'generated_media_files_not_in_zip':True})
    files=[p for p in files if not p.name.startswith('media_') and p.name!='REPORT_SHA256_MANIFEST_V43.json']+[run/'REPORT_SHA256_MANIFEST_V43.json']
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.name)
    tmp.replace(up);return up
