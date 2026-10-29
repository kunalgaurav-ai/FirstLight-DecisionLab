"""Live localhost v3.4 calibration audit plus original v3.3 trajectory dashboard."""
from __future__ import annotations
import json
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import webbrowser,sys,subprocess
from ail_v33.dashboard import HTML as OLD_HTML

CAL_HTML = '''<section id="calsection"><h2>v3.4 Empirical calibration registry (decision-gated)</h2>
<p>The controller CANNOT auto-deploy learned probabilities. Models here are shadow-only and require independently observed, chronological labels. Calibration-in-the-large is not full probabilistic or policy-value validation.</p>
<div id="calstatus" class="note">Loading...</div><div id="calgroups"></div><pre id="calaudit"></pre></section>
<section><h2>Actual user v3.3 Mac audit</h2><pre id="macaudit"></pre></section>
'''
CAL_JS = r'''<script>
(async()=>{
const esc=x=>String(x??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const [r,a]=await Promise.all([fetch('/api/calibration').then(x=>x.json()),fetch('/api/user-v33-audit').then(x=>x.json())]);
document.getElementById('calstatus').textContent='STATUS: '+r.status+' | policy eligible: '+r.policy_eligible+' | causal value: '+r.causal_intervention_value;
document.getElementById('calaudit').textContent=JSON.stringify({split_design:r.design,episodes:r.total_episodes??null,reason:r.reason??null,source:r.source_description??null,independent_approval:r.quality_noninferiority,hmm:r.hmm_gate},null,2);
document.getElementById('macaudit').textContent=JSON.stringify(a,null,2);
const g=r.groups??[];document.getElementById('calgroups').innerHTML=g.length?'<table><thead><tr><th>Modality / stage / failure / version / checkpoint</th><th>Train / calibration / test</th><th>Test Brier</th><th>Baseline Brier</th><th>Gate</th></tr></thead><tbody>'+g.map(v=>'<tr><td>'+esc(v.group)+'</td><td>'+esc(v.counts.train)+' / '+esc(v.counts.calibration)+' / '+esc(v.counts.test)+'</td><td>'+esc(v.predictive_model?.brier)+'</td><td>'+esc(v.incumbent_prevalence_baseline?.brier)+'</td><td>'+esc(v.status)+'</td></tr>').join('')+'</tbody></table>':'<p>No eligible empirical calibration groups loaded. No fictional calibration shown.</p>';
})();</script>'''
HTML=OLD_HTML.replace('</main>',CAL_HTML+'</main>').replace('</body>',CAL_JS+'</body>').replace('v3.3 companion</h1>','v3.4 calibration lab · retained v3.3 execution</h1>')


def serve(execution_path:Path, calibration_path:Path, audit_path:Path, open_browser:bool=True):
    base=json.loads(execution_path.read_text());cal=json.loads(calibration_path.read_text());audit=json.loads(audit_path.read_text())
    assert base['schema_version']=='ail.v33.companion.report.1'
    paths={'/api/report':base,'/api/calibration':cal,'/api/user-v33-audit':audit}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/index.html'):content=HTML.encode();ctype='text/html; charset=utf-8'
            elif self.path in paths:content=json.dumps(paths[self.path],sort_keys=True).encode();ctype='application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',ctype)
            self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' 'self'; connect-src 'self'")
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def log_message(self,fmt,*args):sys.stdout.write('[localhost] '+fmt%args+'\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}/';print('Dashboard:',url,flush=True)
    if open_browser:
        if sys.platform=='darwin':subprocess.Popen(['open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:webbrowser.open(url)
    print('Ctrl+C stops dashboard. Reports remain saved.',flush=True)
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:server.server_close()
