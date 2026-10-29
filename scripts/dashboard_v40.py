"""Local read-only media serving plus concrete human visual/audio review input."""
import html,json,mimetypes,os,random,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit

def dashboard(run,report,cards):
    elements=[]
    for c in cards:
        pics=''.join(f'<img width="170" alt="Real source frame {i+1}" src="/review-media/{c["review_id"]}/frame/{i}">' for i,_ in enumerate(c.get('frame_paths') or []))
        video=('<video controls preload="metadata" width="640" src="/review-media/'+c['review_id']+'/video"></video>') if c.get('video_path') else '<p>Stopped before media rendering.</p>'
        elements.append(f'''<article><h3>Brief {html.escape(c['task_id'])} · Review {html.escape(c['review_id'])}</h3>
        {video}<div class="frames">{pics}</div><p><strong>Factual requirements:</strong> {html.escape(' / '.join(c['facts']))}</p>
        <p><strong>Visual scope:</strong> Illustrative thematic photos, NOT footage of the fictional named venue. Do the frames match the <em>subject</em>? The captions show approved facts but do not prove depicted content.</p>
        <form data-id="{c['review_id']}"><label>Reviewer identifier <input required name="reviewer" maxlength="60" placeholder="blind_reviewer_01"></label>
        <label>Visual relevance (1–5) <input name="visual" type="number" min="1" max="5" value="3" required></label>
        <label>Narrative factual fit (1–5) <input name="factual" type="number" min="1" max="5" value="3" required></label>
        <label>Creative suitability (1–5) <input name="creative" type="number" min="1" max="5" value="3" required></label>
        <label>Audio suitability (1–5) <input name="audio" type="number" min="1" max="5" value="3" required></label>
        <label>Independent approval <select name="approved"><option value="false">Reject</option><option value="true">Approve</option></select></label>
        <label>Reason / failure notes <input name="feedback" maxlength="600"></label><button>Save review</button></form></article>''')
    page='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIL v4.0 Visual Review</title><style>
body{font:15px system-ui;background:#f5f7fb;color:#1e2738;margin:auto;max-width:1160px;padding:30px}h1{letter-spacing:-1px}
article,section{border:1px solid #dce1ea;background:white;border-radius:12px;padding:22px;margin:20px 0}
.frames{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}video{max-width:100%;border-radius:8px}form{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:16px}
label{display:flex;flex-direction:column;font-size:13px;gap:4px}input,select,button{padding:10px;border:1px solid #bbc5d4;border-radius:7px}button{background:#122e57;color:white;font-weight:650;cursor:pointer}small{color:#56657a}
pre{white-space:pre-wrap;word-break:break-word}a{color:#174b90}
</style></head><body><h1>AIL 4.0 · Real visually grounded workflow</h1><p>Actual local Ollama → licensed photo selection → speech synthesis → two real FFmpeg scene encodes → completed MP4. This is <strong>NOT a text-to-video generator</strong> and photos do <strong>not</strong> show the named fictional clients.</p>
<section><h2>Evidence controls</h2><p>Blind IDs hide the execution policy until review. Technical file validity and metadata do not prove visual relevance. Reviewers must inspect the actual final MP4 and scene frames. No independent review = no accepted commercial outcome.</p>
<small>All output photos: Wikimedia Commons CC0 samples; inspect LICENSE_AND_VISUAL_LIMITATIONS.md. All prices/invoices are unknown.</small></section>'''+''.join(elements)+'''
<script>document.querySelectorAll('form[data-id]').forEach(f=>f.addEventListener('submit',async e=>{e.preventDefault();let d=Object.fromEntries(new FormData(f));d.review_id=f.dataset.id;d.approved=d.approved==='true';for(let k of ['visual','factual','creative','audio']) d[k]=Number(d[k]);let r=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}),j=await r.json();alert(r.ok?'Review saved to local JSONL':j.error||'Failed');}));</script></body></html>'''
    ids={c['review_id'] for c in cards}
    by_id={c['review_id']:c for c in cards}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,obj,code=200):
            data=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            name=unquote(urlsplit(self.path).path)
            if name in ('/','/index.html'):
                data=page.encode();self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if name=='/api/status':self.respond({'status':report['status'],'approval':'UNKNOWN_UNTIL_INDEPENDENT_REVIEW'});return
            if name.startswith('/review-media/'):
                pieces=name.strip('/').split('/')
                if len(pieces)<3 or pieces[1] not in by_id:self.send_error(404);return
                card=by_id[pieces[1]]
                if len(pieces)==3 and pieces[2]=='video': rel=card.get('video_path')
                elif len(pieces)==4 and pieces[2]=='frame' and pieces[3].isdigit():
                    i=int(pieces[3]);frames=card.get('frame_paths') or []
                    rel=frames[i] if 0<=i<len(frames) else None
                else: rel=None
                if not rel:self.send_error(404);return
                f=(run/rel).resolve();base=(run/'media').resolve()
                if not f.is_file() or not f.is_relative_to(base):self.send_error(404);return
                total=f.stat().st_size;first=0;last=total-1;rg=self.headers.get('Range','')
                if rg.startswith('bytes='):
                    try:
                        lo,hi=rg[6:].split('-',1);first=int(lo or 0);last=min(int(hi),total-1) if hi else last
                        if first<0 or last<first or first>=total:raise ValueError()
                    except ValueError:self.send_error(416);return
                self.send_response(206 if rg else 200)
                self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
                self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(last-first+1))
                if rg:self.send_header('Content-Range',f'bytes {first}-{last}/{total}')
                self.end_headers()
                with f.open('rb') as stream:
                    stream.seek(first);remain=last-first+1
                    while remain:
                        chunk=stream.read(min(65536,remain))
                        if not chunk:break
                        try:self.wfile.write(chunk)
                        except (BrokenPipeError,ConnectionResetError):break
                        remain-=len(chunk)
                return
            self.send_error(404)
        def do_POST(self):
            if self.path!='/api/review':self.send_error(404);return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=3000:raise ValueError('INVALID_REQUEST_SIZE')
                d=json.loads(self.rfile.read(n))
                if d.get('review_id') not in ids:raise ValueError('UNKNOWN_REVIEW_ID')
                if not isinstance(d.get('reviewer'),str) or not 2<=len(d['reviewer'])<=60:raise ValueError('REVIEWER_REQUIRED')
                if type(d.get('approved')) is not bool:raise ValueError('APPROVAL_BOOL_REQUIRED')
                if any(type(d.get(k)) is not int or not 1<=d[k]<=5 for k in ('visual','factual','creative','audio')):raise ValueError('SCORES_OUT_OF_RANGE')
                rec={'time_utc':datetime.now(timezone.utc).isoformat(),'review_id':d['review_id'],'reviewer':d['reviewer'],'approved':d['approved'],'scores':{k:d[k] for k in ('visual','factual','creative','audio')},'feedback':str(d.get('feedback',''))[:600],'independence_not_verified_automatically':True}
                with (run/'reviews.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(rec)+'\n')
                self.respond({'saved':True})
            except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:self.respond({'error':str(e)},400)
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    address=f'http://127.0.0.1:{http.server_port}/'
    print('VISUAL REVIEW DASHBOARD:',address,flush=True)
    if sys.platform=='darwin':subprocess.Popen(['open',address],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:http.serve_forever(.2)
    except KeyboardInterrupt:pass
    finally:http.server_close()
