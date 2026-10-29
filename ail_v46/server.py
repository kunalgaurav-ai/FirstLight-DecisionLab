"""One operational localhost dashboard for real prompts, video/image/audio jobs and review."""
from __future__ import annotations
import json, pathlib, re, secrets, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from . import runtime as rt
from .controller import workflow_action
from ail_v44 import workbench as wb
from ail_v45.engine import file_sha
from ail_v44.server import range_parts

ROOT=pathlib.Path(__file__).resolve().parent
PAGE=(ROOT/'index.html').read_bytes() if (ROOT/'index.html').is_file() else b''
JS=(ROOT/'app.js').read_bytes() if (ROOT/'app.js').is_file() else b''

def create_server(run,plan_path,port=0):
    run=pathlib.Path(run).resolve();plan=wb.suite(plan_path);token=secrets.token_hex(24)
    action_lock=threading.RLock();active_actions=set()
    def schedule_unique(key,worker):
        with action_lock:
            if key in active_actions:raise ValueError('DUPLICATE_JOB_SUBMISSION_ALREADY_RUNNING')
            active_actions.add(key)
        def guarded():
            try:worker()
            finally:
                with action_lock:active_actions.discard(key)
        try:threading.Thread(target=guarded,daemon=True).start()
        except Exception:
            with action_lock:active_actions.discard(key)
            raise
    class H(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def respond(self,obj,status=200):
            content=json.dumps(obj,ensure_ascii=False,default=str).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(content)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(content)
        def raw(self,data,mime):
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)
        def file(self,p,sha,mime):
            if not p or not p.is_file() or not p.resolve().is_relative_to(run) or file_sha(p)!=sha:return self.respond({'error':'FILE_MISSING_OR_HASH_MISMATCH'},404)
            size=p.stat().st_size
            if size<1:return self.respond({'error':'EMPTY_FILE'},404)
            a,b,code=range_parts(self.headers.get('Range'),size)
            self.send_response(code);self.send_header('Accept-Ranges','bytes');self.send_header('Content-Type',mime)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            if code==416:
                self.send_header('Content-Length','0');self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            self.send_header('Content-Length',str(b-a+1))
            if code==206:self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
            self.end_headers()
            if self.command=='HEAD':return
            with p.open('rb') as f:
                f.seek(a);remaining=b-a+1
                while remaining:
                    buf=f.read(min(128*1024,remaining))
                    if not buf:break
                    try:self.wfile.write(buf)
                    except (BrokenPipeError,ConnectionResetError):break
                    remaining-=len(buf)
        def do_HEAD(self):self.do_GET()
        def do_GET(self):
            u=urlsplit(self.path).path
            if u=='/':return self.raw(PAGE,'text/html; charset=utf-8')
            if u=='/app.js':return self.raw(JS,'application/javascript; charset=utf-8')
            if u=='/api/health':return self.respond({'ok':True,'version':'4.6'})
            if u=='/api/state':
                st=wb.get(run/'workflow')
                for a in st['artifacts']:a['available']=wb.artifact_valid(run/'workflow',a)
                for im in st.get('images',[]):im['available']=(run/'workflow'/im['path']).is_file() and file_sha(run/'workflow'/im['path'])==im['sha256']
                p=run/'v45_comparison'/'results_v45.json';comp=json.loads(p.read_text()) if p.is_file() else None
                recommendations={}
                for a in st['artifacts']:
                    rv=next((r for r in st['reviews'] if r['artifact_id']==a['id']),None)
                    recommendations[a['id']]=workflow_action(a,rv,rights=a.get('rights'))
                return self.respond({'plan':plan,'state':st,'jobs':rt.jobs(run),'readiness':rt.readiness(),'recommendations':recommendations,'token':token,
                                     'comparison':comp['summary'] if comp else None,
                                     'legacy_clips':json.loads((run/'legacy_clips.json').read_text()) if (run/'legacy_clips.json').is_file() else [],
                                     'categories':wb.CATEGORIES,
                                     'status_warning':'No automatically billed calls. Reviews are not independent acceptance.'})
            m=re.fullmatch(r'/media/(video|image|local|assembly|legacy)/([A-Za-z0-9_-]+)',u)
            if m:
                kind,ident=m.groups()
                if kind=='legacy':
                    clips=json.loads((run/'legacy_clips.json').read_text()) if (run/'legacy_clips.json').is_file() else []
                    a=next((x for x in clips if x['id']==ident),None)
                    return self.file(run/a['path'] if a else None,a['sha256'] if a else '', 'video/mp4')
                if kind=='video':
                    a=next((x for x in wb.get(run/'workflow')['artifacts'] if x['id']==ident),None)
                    return self.file(run/'workflow'/a['path'] if a else None,a['sha256'] if a else '', 'video/mp4')
                if kind=='image':
                    a=next((x for x in wb.get(run/'workflow').get('images',[]) if x['id']==ident),None)
                    return self.file(run/'workflow'/a['path'] if a else None,a['sha256'] if a else '', 'image/'+('jpeg' if a and a['path'].endswith(('.jpg','.jpeg')) else 'webp' if a and a['path'].endswith('.webp') else 'png'))
                if kind=='local':
                    a=next((x for x in rt.jobs(run) if x['id']==ident and x['kind'] in ('text','speech') and x['status']=='SUCCESS_VERIFIED'),None)
                    return self.file(run/a['path'] if a else None,a['sha256'] if a else '', 'audio/aiff' if a and a['kind']=='speech' else 'text/plain; charset=utf-8')
                if kind=='assembly':
                    a=next((x for x in reversed(wb.get(run/'workflow').get('assembled',[])) if x['task_id']==ident),None)
                    return self.file(run/'workflow'/a['output'] if a else None,a['sha256'] if a else '', 'video/mp4')
            return self.respond({'error':'UNKNOWN_ROUTE'},404)
        def do_POST(self):
            try:
                # A same-origin token and JSON content type protect against malicious websites posting to localhost.
                if self.headers.get('X-AIL-Session')!=token:raise PermissionError('LOCAL_SESSION_TOKEN_REQUIRED')
                origin=self.headers.get('Origin','')
                if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':raise PermissionError('CROSS_ORIGIN_REJECTED')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON_ONLY')
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=15000:raise ValueError('PAYLOAD_LIMIT')
                args=json.loads(self.rfile.read(length));u=urlsplit(self.path).path
                if u=='/api/import':
                    kind=args['kind'];task=args['task_id'];path=args['path'];provider=args['provider'];model=args['model'];rights=args['rights']
                    a=rt.import_media(run,plan,kind,task,path,provider,model,rights,args.get('shot_id'))
                    rt.close_reports(run);return self.respond({'ok':True,'artifact':a})
                if u=='/api/review':
                    with rt.LOCK:r=wb.review(run/'workflow',plan,args['artifact_id'],args['ratings'],args['events'])
                    rt.close_reports(run);return self.respond(r)
                if u=='/api/assemble':
                    with rt.LOCK:r=wb.assemble(run/'workflow',plan,args['task_id'])
                    rt.close_reports(run);return self.respond(r)
                if u=='/api/local':
                    kind=args['kind'];prompt=args['prompt'];note=args.get('delivery_instructions','')
                    if kind not in ('text','speech') or type(prompt)!=str or len(prompt)>5000 or type(note)!=str or len(note)>400:raise ValueError('INVALID_LOCAL_INPUT')
                    def worker():rt.execute_local(run,kind,prompt,spoken_instructions=note);rt.close_reports(run)
                    schedule_unique(('local',kind,hash(prompt)),worker)
                    return self.respond({'status':'SUBMITTED_LOCAL_BACKGROUND','note':'Results appear in job ledger; server must remain open.'},202)
                if u=='/api/generate-video':
                    if args.get('backend') not in ('ltx_5s_probe','ltx_v2_8s'):raise ValueError('INVALID_BACKEND')
                    if args.get('ack') is not True:raise ValueError('USER_MUST_ACK_REMOTE_CALL')
                    task=wb.find_task(plan,args['task_id']);wb.find_shot(task,args['shot_id'])
                    backend=args['backend'];rate=args.get('price_per_second_usd')
                    if backend=='ltx_v2_8s' and not rt.readiness()['video_production']['ready']:raise ValueError('SET_LOCAL_LTXV_API_KEY_FIRST')
                    if backend=='ltx_v2_8s' and (type(rate) not in (int,float) or not 0<rate<=10):raise ValueError('USER_CONFIRMED_RATE_REQUIRED')
                    def worker():rt.generate_video(run,plan,args['task_id'],args['shot_id'],backend,True,rate=rate);rt.close_reports(run)
                    schedule_unique(('video',args['task_id'],args['shot_id']),worker)
                    return self.respond({'status':'REQUEST_SCHEDULED','kind':'video','backend':backend},202)
                if u=='/api/generate-image':
                    if args.get('ack') is not True:raise ValueError('USER_MUST_ACK_PROVIDER')
                    if not rt.readiness()['image_provider']['ready'] or __import__('os').environ.get('AIL_ALLOW_BILLED_IMAGE')!='1':raise ValueError('HF_TOKEN_AND_EXPLICIT_BILLING_PERMISSION_REQUIRED')
                    task=wb.find_task(plan,args['task_id'])
                    if task['modality']!='text_to_image':raise ValueError('NOT_IMAGE_TASK')
                    def worker():rt.generate_image(run,plan,args['task_id'],True);rt.close_reports(run)
                    schedule_unique(('image',args['task_id']),worker)
                    return self.respond({'status':'REQUEST_SCHEDULED','kind':'image'},202)
                return self.respond({'error':'UNKNOWN_ROUTE'},404)
            except (ValueError,KeyError,PermissionError,TypeError,RuntimeError) as e:
                return self.respond({'error':rt.safe_error(e)},403 if isinstance(e,PermissionError) else 400)
    srv=ThreadingHTTPServer(('127.0.0.1',port),H)
    return srv

def serve(run,plan_path,port=0,open_browser=True):
    srv=create_server(run,plan_path,port);url=f'http://127.0.0.1:{srv.server_port}/'
    if open_browser:webbrowser.open(url)
    print('AIL v4.6 ACTIONABLE DASHBOARD:',url,flush=True)
    print('No external generation runs without an explicit action. On Ctrl+C results are sealed.',flush=True)
    try:srv.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:pass
    finally:
        srv.server_close();rt.recover_interrupted(run);rt.close_reports(run)
