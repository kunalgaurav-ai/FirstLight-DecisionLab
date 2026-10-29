"""Retains original v3.3/3.4 dashboard, adds v3.5 research audit tab."""
import json,subprocess,sys,webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from ail_v34.dashboard import HTML as OLD_HTML

SECTION='''<section id="edgeresearch"><h2>v3.5 Economic opportunity screen · conditional, not commercial savings</h2>
<p>Source: verified constructed DAG arithmetic or optional authorized, user-supplied stage receipts. No new agent outcome labels, causal effect or quality acceptance created here. Competent early checks/caching/repair are credited to the baseline.</p>
<div class="note" id="edgestatus">Loading conditional opportunity...</div>
<div id="edgetable"></div><pre id="edgeaudit"></pre>
</section>'''
SCRIPT=r'''<script>
(async()=>{
const esc=s=>String(s??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
let r=await fetch('/api/edge').then(x=>x.json());
document.getElementById('edgestatus').textContent='STATUS: '+r.status+' | economic advantage: '+r.commercial_advantage+' | model trained: '+r.trained_new_model;
const o=r.opportunity||{};
document.getElementById('edgetable').innerHTML=(o.checkpoints?.length ? '<table><thead><tr><th>Checkpoint</th><th>Distinct eligible stages</th><th>Conditional opportunity range</th><th>Evidence</th></tr></thead><tbody>' + o.checkpoints.map(x=>'<tr><td>'+esc(x.checkpoint)+'</td><td>'+esc(x.total_eligible_nodes)+'</td><td>'+esc(x.avoidable_downstream_work_interval.join(' to '))+' '+esc(o.cost_unit)+'</td><td>'+esc(o.evidence_class)+'</td></tr>').join('')+'</tbody></table>' : '<p>No cost-opportunity stage graph available.</p>');
document.getElementById('edgeaudit').textContent=JSON.stringify({status:r.status,scenario_value:r.scenario_screen,independent_approvals:r.independent_approvals,prospective_causal_effect:r.prospective_causal_effect,coverage:r.policy_coverage,blocked_inputs:r.blocked_inputs},null,2);
})();
</script>'''
HTML=OLD_HTML.replace('</main>',SECTION+'</main>').replace('</body>',SCRIPT+'</body>').replace('v3.4 calibration lab · retained v3.3 execution</h1>','v3.5 edge research · v3.4 calibration preserved</h1>')

def serve(reference_report,cal_report,audit_report,edge_report,open_browser=True):
    paths={'/api/report':reference_report,'/api/calibration':cal_report,'/api/user-v33-audit':audit_report,'/api/edge':edge_report}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/index.html'):
                raw=HTML.encode();typ='text/html; charset=utf-8'
            elif self.path in paths:
                raw=json.dumps(paths[self.path],sort_keys=True).encode();typ='application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' 'self'; connect-src 'self'")
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,fmt,*args):sys.stdout.write('[127.0.0.1] '+fmt%args+'\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}/'
    print('DASHBOARD:',url,flush=True)
    if open_browser:
        if sys.platform=='darwin':subprocess.Popen(['open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:webbrowser.open(url)
    print('Ctrl+C stops localhost. Result ZIP already saved.',flush=True)
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:server.server_close()
