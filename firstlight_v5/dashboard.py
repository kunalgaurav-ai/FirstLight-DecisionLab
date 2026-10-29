"""Offline-safe research site with unambiguous benchmark provenance and real endpoints."""
import csv
import io
import json
import mimetypes
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .core import json_dump

ROOT=Path(__file__).resolve().parent


def site_state(run):
    p=Path(run)/'benchmark_results.json'
    if p.exists():
        data=json.loads(p.read_text(encoding='utf8'))
    else: data={'state':'NOT_STARTED','results':[],'summary':None}
    hist={'source':'v4.5 historical Mac results from user uploads; not a BFCL score',
          'text':{'AIL_conditional_repair':{'passes':4,'cases':4,'tokens':501,'model_seconds':6.74},
                  'competent_retry':{'passes':0,'cases':4,'tokens':1377,'model_seconds':9.27},
                  'prewritten_tool_first':{'passes':4,'cases':4,'tokens':0,'model_seconds':0}},
          'audio':{'ail_cache_calls':2,'competent_cache_calls':2,'uncached_calls':3}}
    return {'benchmark':data,'historical_local':hist,
            'claim_status':'NO_PUBLIC_COMPETITIVE_SUPERIORITY_ESTABLISHED',
            'brand':'First Light','phase':'Local benchmark pilot; complete workflows not yet evaluated'}


def csv_report(run):
    dat=site_state(run)['benchmark'];s=io.StringIO()
    w=csv.writer(s)
    w.writerow(['task_id','group','policy','scoring_status','strict_diagnostic_pass','calls','input_tokens','output_tokens','wall_s','model_trace'])
    for r in dat.get('results',[]):
        for name,a in r.get('arms',{}).items():
            w.writerow([r['id'],r['group'],name,a.get('diagnostic',{}).get('status'),a.get('diagnostic',{}).get('pass'),
                        len(a.get('calls',[])),a.get('input_tokens'),a.get('output_tokens'),round(a.get('wall_s',0),5),
                        ';'.join(c.get('model',c.get('template_model','')) for c in a.get('calls',[]))])
    return s.getvalue().encode('utf8')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path
        if path in ('/','/index.html'):
            self.reply((ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
        elif path=='/style.css':
            self.reply((ROOT/'style.css').read_bytes(),'text/css; charset=utf-8')
        elif path=='/app.js':
            self.reply((ROOT/'app.js').read_bytes(),'text/javascript; charset=utf-8')
        elif path=='/api/state':
            self.reply(json.dumps(site_state(self.server.run_path)).encode(),'application/json')
        elif path=='/api/health':
            self.reply(b'{"ok":true,"brand":"First Light","mode":"offline_research"}','application/json')
        elif path=='/download/benchmark.json':
            self.reply(json.dumps(site_state(self.server.run_path)['benchmark'],indent=2).encode(),'application/json',
                       'attachment; filename="firstlight_benchmark.json"')
        elif path=='/download/benchmark.csv':
            self.reply(csv_report(self.server.run_path),'text/csv; charset=utf-8',
                       'attachment; filename="firstlight_benchmark.csv"')
        else:
            self.reply(b'Not found','text/plain',status=404)
    def reply(self,data,mime,content=None,status=200):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('Content-Length',str(len(data)))
        if content:self.send_header('Content-Disposition',content)
        self.end_headers()
        self.wfile.write(data)


def start(run,open_browser=True):
    srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    srv.run_path=str(Path(run).resolve())
    url=f'http://127.0.0.1:{srv.server_address[1]}/'
    print('FIRST LIGHT RESEARCH DASHBOARD:',url,flush=True)
    if open_browser:
        threading.Timer(0.5,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: pass
    finally: srv.server_close()
