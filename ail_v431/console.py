"""Evidence-hardened v4.3 review console. No automatic model calls.

This wraps v4.3's actual model adapter and immutable prompt set. It imports the
prior receipt and copies only checksum-verified media into an independently
labeled run. Statuses distinguish unrequested from failed and corrupt output.
"""
from __future__ import annotations
import copy, hashlib, json, os, re, shutil, subprocess, threading, time, uuid, webbrowser, zipfile
from datetime import datetime, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from ail_v43 import backend
from ail_v43.engine import task_index, media_probe, file_sha, now, validate_review, save_json, write_zip

VIDEO_ID = re.compile(r'^VID-[0-9]{2}-[A-Z0-9-]{2,50}$')
CLIP_ID = re.compile(r'^clip-[a-f0-9]{12}$')
ACTIVE = ('QUEUED','RUNNING')

def discover(downloads:Path):
    found=[]
    for p in downloads.glob('source-*/agent-intelligence-lab-v4.3-prompt-first-generative/runs/v43_*/generative_receipts_v43.json'):
        if 'ui-recovery' in str(p) or p.stat().st_size>2_000_000:continue
        try:
            d=json.loads(p.read_text())
            if any(r.get('status')=='COMPLETE' for r in d.get('records',[]) if isinstance(r,dict)):
                found.append(p.parent)
        except (OSError,ValueError,TypeError):pass
    return sorted(found,key=lambda p:(p/'generative_receipts_v43.json').stat().st_mtime,reverse=True)

class EvidenceConsole:
    def __init__(self,source_run:Path,run:Path,prompts:Path,max_new_calls=3, generator=None):
        self.source_run=Path(source_run).resolve();self.run=Path(run).resolve();self.run.mkdir(parents=True,exist_ok=False)
        self.tasks={k:v for k,v in task_index(prompts).items() if v.get('modality')=='text_to_video'}
        self.lock=threading.RLock();self.generator=generator or backend.generate
        self.max_new_calls=int(max_new_calls)
        if not 0<=self.max_new_calls<=10:raise ValueError('CALL_BUDGET_RANGE_0_TO_10')
        self.new_calls_started=0;self.new_calls_completed=0;self.events=[];self.records=[]
        self.source_receipt_sha=None
        f=self.source_run/'generative_receipts_v43.json'
        if not f.is_file() or f.stat().st_size>2_000_000:raise ValueError('ORIGINAL_RECEIPT_MISSING_OR_OVERSIZE')
        original=json.loads(f.read_text());self.source_receipt_sha=file_sha(f)
        for old in original.get('records',[]):
            if not isinstance(old,dict) or old.get('task_id') not in self.tasks:continue
            r=copy.deepcopy(old)
            r['provenance']='RECOVERED_ORIGINAL_V43'
            if r.get('status')=='COMPLETE':
                r=self._admit_old_media(r)
            elif r.get('status') in ACTIVE:
                r['status']='INTERRUPTED_ORIGINAL';r['error']='Original generation no longer running in this process; no output attested'
            self.records.append(r)
        self._log('Original v4.3 evidence imported; no generation invoked')
        self.persist()

    def _log(self,text):self.events.append({'time':now(),'text':str(text)[:500]})

    def _admit_old_media(self,r):
        try:
            rel=Path(r['final_media'])
            if rel.is_absolute() or len(rel.parts)<3 or rel.parts[0]!='media' or '..' in rel.parts:raise ValueError('UNSAFE_MEDIA_PATH')
            source=(self.source_run/rel).resolve()
            if not source.is_relative_to(self.source_run/'media'):raise ValueError('UNSAFE_MEDIA_RESOLUTION')
            expected=r.get('probe',{}).get('sha256')
            if not expected or not source.is_file() or file_sha(source)!=expected:raise ValueError('MISSING_OR_SHA_MISMATCH')
            target=self.run/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            if file_sha(target)!=expected:raise ValueError('COPY_SHA_MISMATCH')
            r['status']='COMPLETE_VERIFIED';r['video_bytes']=target.stat().st_size
            r['source_media_sha256_verified']=expected
        except (OSError,KeyError,TypeError,ValueError) as e:
            r['status']='MEDIA_MISSING_OR_CORRUPT';r['error']='Recovered video cannot be verified: '+str(e)[:180]
            r.pop('final_media',None)
        return r

    def tasks_overview(self):
        out=[]
        for task_id, spec in self.tasks.items():
            rs=[r for r in self.records if r.get('task_id')==task_id]
            visible=[]
            for r in rs:
                d={k:r.get(k) for k in ('clip_id','status','error','review','probe','provenance','completed_utc')}
                if d['status']=='COMPLETE_VERIFIED' and self.media_for(d['clip_id']) is None:
                    d['status']='MEDIA_MISSING_OR_CORRUPT'
                    d['error']='Video was removed or changed after admission. Playback withheld.'
                visible.append(d)
            if not visible:label='NOT_REQUESTED'
            elif any(r.get('status') in ACTIVE for r in visible):label='GENERATING'
            elif any(r.get('status')=='COMPLETE_VERIFIED' for r in visible):label='VIDEO_AVAILABLE'
            elif any(r.get('status')=='MEDIA_MISSING_OR_CORRUPT' for r in visible):label='MEDIA_MISSING_OR_CORRUPT'
            else:label='PROVIDER_FAILED_OR_INTERRUPTED'
            out.append({'task_id':task_id,'prompt':spec['prompt'],'events_in_order':spec.get('events_in_order',[]),
                        'status':label,'clips':visible, 'generation_attempted':bool(rs)})
        return out

    def public(self):
        with self.lock:
            return {'kind':'V431_REAL_PROVIDER_EVIDENCE_REVIEW','new_calls_started':self.new_calls_started,
                    'new_calls_completed':self.new_calls_completed,'remaining_new_calls':self.max_new_calls-self.new_calls_started,
                    'source_receipt_sha256':self.source_receipt_sha,'tasks':self.tasks_overview(),
                    'events':self.events[-30:],'upload_zip':str(self.upload) if self.upload else None,
                    'declaration':'One verified source clip is not evidence other prompts were generated; technical video integrity is not prompt approval',
                    'independent_customer_approval':'UNKNOWN','commercial_savings':'NOT_ESTABLISHED'}

    def persist(self):
        with self.lock:
            save_json(self.run/'GENERATIVE_EVIDENCE_V431.json',{'created_utc':now(), 'source_run':str(self.source_run),
                'source_receipt_sha256':self.source_receipt_sha,'original_generations_not_reissued':True,
                'new_calls_started':self.new_calls_started,'new_calls_completed':self.new_calls_completed,
                'max_new_calls':self.max_new_calls,'records':self.records,'events':self.events,
                'tasks':[{'id':x['task_id'],'status':x['status']} for x in self.tasks_overview()],
                'provider_invoices':'NOT_OBSERVED', 'quality_approval':'NOT_INDEPENDENTLY_VERIFIED'})
            files=[p for p in self.run.iterdir() if p.is_file() and p.name not in ('REPORT_SHA256_MANIFEST_V431.json',) and not p.name.endswith('.zip')]
            save_json(self.run/'REPORT_SHA256_MANIFEST_V431.json', {'evidence_class':'REAL_PRIOR_MODEL_RECEIPT_PLUS_OPTIONAL_EXPLICIT_NEW_CALLS',
                'files':[{'file':p.name,'bytes':p.stat().st_size,'sha256':file_sha(p)} for p in files],
                'note':'No MP4s included; each must be independently inspected on the Mac.'})
            self.upload=self.run/('UPLOAD_THIS_v431_'+self.run.name.removeprefix('v431_')+'.zip')
            tmp=self.upload.with_suffix('.zip.tmp')
            with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for p in files+[self.run/'REPORT_SHA256_MANIFEST_V431.json']:
                    z.write(p,p.name)
            tmp.replace(self.upload)

    def media_for(self,clip_id):
        with self.lock:
            if not CLIP_ID.fullmatch(clip_id):return None
            for r in self.records:
                if r.get('clip_id')==clip_id and r.get('status')=='COMPLETE_VERIFIED':
                    rel=Path(r.get('final_media',''))
                    if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0]!='media':return None
                    p=(self.run/rel).resolve()
                    if not p.is_relative_to(self.run/'media') or not p.is_file():return None
                    if file_sha(p)!=r.get('probe',{}).get('sha256'):return None
                    return p
        return None

    def start(self,task_id):
        with self.lock:
            if task_id not in self.tasks or not VIDEO_ID.fullmatch(task_id):raise ValueError('UNKNOWN_VIDEO_PROMPT')
            if any(r.get('status') in ACTIVE for r in self.records):raise ValueError('OTHER_GENERATION_IN_PROGRESS')
            existing=[r for r in self.records if r.get('task_id')==task_id]
            if any(r.get('status')=='COMPLETE_VERIFIED' for r in existing):raise ValueError('VIDEO_ALREADY_AVAILABLE_NO_IMPLICIT_REGENERATION')
            if self.new_calls_started>=self.max_new_calls:raise ValueError('SESSION_GENERATION_BUDGET_EXHAUSTED')
            clip_id='clip-'+uuid.uuid4().hex[:12]
            r={'clip_id':clip_id,'task_id':task_id,'status':'QUEUED','created_utc':now(),
               'prompt_sent':self.tasks[task_id]['prompt'],'seed':42,'provider':'Lightricks/LTX-2.5',
               'model':backend.MODEL,'provenance':'NEW_EXPLICIT_USER_REQUEST','error':None,'review':None}
            self.records.append(r);self.new_calls_started+=1
            self._log(f'User initiated real provider call for {task_id}; reserved {self.new_calls_started}/{self.max_new_calls}')
            self.persist()
            threading.Thread(target=self._generate,args=(r,),daemon=True).start()
            return clip_id

    def _generate(self,r):
        try:
            with self.lock:r['status']='RUNNING';self.persist()
            path=self.run/'media'/r['clip_id']/'generated_0.mp4'
            receipt=self.generator(r['prompt_sent'],path,seed=42,duration=min(5,max(1,float(self.tasks[r['task_id']].get('duration_target_s',5)))))
            probe=media_probe(path)
            with self.lock:
                self.new_calls_completed+=1
                r.update(status='COMPLETE_VERIFIED',receipt=receipt,probe=probe,final_media=str(path.relative_to(self.run)),
                         completed_utc=now(),video_bytes=path.stat().st_size)
                self._log(f'Generated verified MP4 for {r["task_id"]}; prompt adherence not reviewed')
                self.persist()
        except Exception as ex:
            with self.lock:
                r['status']='PROVIDER_FAILED';r['error']=type(ex).__name__+':'+str(ex)[:250]
                self._log('Provider or media validation failed: '+r['error']);self.persist()

    def review(self,data):
        with self.lock:
            cid=data.get('clip_id')
            r=next((x for x in self.records if x.get('clip_id')==cid and x.get('status')=='COMPLETE_VERIFIED'),None)
            if r is None:raise ValueError('NO_VERIFIED_CLIP_FOR_REVIEW')
            if self.media_for(cid) is None:raise ValueError('VIDEO_MISSING_OR_HASH_MISMATCH')
            if r.get('review') is not None:raise ValueError('REVIEW_ALREADY_PRESENT')
            rev=validate_review(data,self.tasks[r['task_id']])
            r['review']=rev
            self._log(f'Review submitted for {cid}; reviewer independence not verified')
            self.persist()
            return {'recorded':True,'approval':'NOT_INDEPENDENTLY_VERIFIED'}


def range_spec(value,size):
    if not value:return 0,size-1,200
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',value.strip())
    if not m:return None,None,416
    a,b=m.groups()
    if not a and not b:return None,None,416
    if not a:
        n=int(b)
        if n<=0:return None,None,416
        start=max(0,size-n);end=size-1
    else:
        start=int(a);end=int(b) if b else size-1
        if start>=size or end<start:return None,None,416
        end=min(end,size-1)
    return start,end,206


def serve(console:EvidenceConsole,js_path:Path,port=0,open_browser=True):
    script=Path(js_path).read_bytes()
    from .html import PAGE
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def reply(self,status,data,ctype='application/json',method='GET'):
            blob=data if isinstance(data,bytes) else data.encode()
            self.send_response(status);self.send_header('Content-Type',ctype)
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(blob)));self.end_headers()
            if method!='HEAD':self.wfile.write(blob)
        def stream_media(self,method):
            cid=urlsplit(self.path).path.removeprefix('/video/')
            p=console.media_for(cid)
            if p is None:return self.reply(404,json.dumps({'error':'VIDEO_NOT_AVAILABLE_OR_HASH_MISMATCH'}),method=method)
            size=p.stat().st_size; a,b,code=range_spec(self.headers.get('Range'),size)
            if code==416:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            self.send_response(code);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(b-a+1))
            self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if code==206:self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
            self.end_headers()
            if method=='HEAD':return
            with p.open('rb') as f:
                f.seek(a);left=b-a+1
                while left:
                    ch=f.read(min(left,131072))
                    if not ch:break
                    try:self.wfile.write(ch)
                    except (BrokenPipeError,ConnectionResetError):break
                    left-=len(ch)
        def dispatch(self,method):
            path=urlsplit(self.path).path
            if path=='/':return self.reply(200,PAGE,'text/html; charset=utf-8',method)
            if path=='/app.js':return self.reply(200,script,'application/javascript; charset=utf-8',method)
            if path=='/api/state':return self.reply(200,json.dumps(console.public()),method=method)
            if path=='/api/health':return self.reply(200,json.dumps({'ok':True,'source_receipt_sha256':console.source_receipt_sha}),method=method)
            if path.startswith('/video/'):return self.stream_media(method)
            return self.reply(404,json.dumps({'error':'NOT_FOUND'}),method=method)
        def do_GET(self):return self.dispatch('GET')
        def do_HEAD(self):return self.dispatch('HEAD')
        def do_POST(self):
            n=self.headers.get('Content-Length')
            if not n or not n.isdecimal() or not 1<=int(n)<=24000:return self.reply(413,json.dumps({'error':'INVALID_PAYLOAD_SIZE'}))
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,json.dumps({'error':'JSON_REQUIRED'}))
            try:
                o=json.loads(self.rfile.read(int(n)))
                if not isinstance(o,dict):raise ValueError('OBJECT_REQUIRED')
                if self.path=='/api/generate':result={'queued_clip_id':console.start(o.get('task_id'))}
                elif self.path=='/api/review':result=console.review(o)
                else:return self.reply(404,json.dumps({'error':'NOT_FOUND'}))
                return self.reply(200,json.dumps(result))
            except (ValueError,KeyError,TypeError) as ex:return self.reply(409,json.dumps({'error':str(ex)[:250]}))
            except Exception as ex:return self.reply(500,json.dumps({'error':'INTERNAL_ERROR_'+type(ex).__name__}))
    srv=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    url=f'http://127.0.0.1:{srv.server_address[1]}/'
    print('AUDITED REVIEW DASHBOARD:',url,flush=True)
    print('NEW RESULTS ZIP:',console.upload,flush=True)
    if open_browser:webbrowser.open(url)
    return srv,url
