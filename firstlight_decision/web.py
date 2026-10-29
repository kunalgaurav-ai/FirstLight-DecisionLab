"""Minimal truthful, data-bound research dashboard; stdlib only."""
import http.server,json,pathlib,sys,webbrowser,threading
INDEX='''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>First Light · Economic Decision Lab</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{background:#0f1520;color:#e9edf8;font-family:system-ui,-apple-system,sans-serif;margin:0}main{max-width:1180px;margin:50px auto;padding:0 22px}h1{font-size:2rem;letter-spacing:-.04em}h2{margin-top:36px;font-size:1.2rem}p,small{color:#aab5c6;line-height:1.6}.muted{color:#aab5c6}.kpis,.arms{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.tile{background:#1a2433;border:1px solid #334154;border-radius:12px;padding:18px}.big{font-size:2rem;font-weight:700}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{border-bottom:1px solid #344254;padding:10px;text-align:left;font-size:13px}th{color:#aab5c6}a{color:#9ec7f1}.failure{color:#ffb6ab}.passed{color:#b1ebc4}#table-wrap{overflow:auto}code{font-family:ui-monospace,monospace}svg{max-width:100%}footer{margin:50px 0}</style></head><body><main><small>FIRST LIGHT · RESEARCH EVIDENCE · NOT CUSTOMER DATA</small><h1>Economic Decision Lab</h1><p>Actual local Qwen repair continuations. A task is accepted only when all published benchmark testcases pass. Monitoring overhead is included. This is not SWE-bench, cloud dollars, or strongest-OSS superiority.</p><div class="kpis" id="kpis"></div><h2>Holdout performance — matched repair policies</h2><div class="arms" id="arms"></div><p id="uncertainty" class="muted">Awaiting executed holdout scores.</p><h2>Quality versus model tokens</h2><div class="tile"><svg id="frontier" viewBox="0 0 660 260" role="img" aria-label="Measured quality versus model tokens"></svg><small>Only executed configurations are plotted. Fewer tokens and higher accuracy are better. No monetization inferred.</small></div><h2>Per-task evidence</h2><div id="table-wrap"></div><p><a href="/results.json">Raw evidence JSON</a> · <a href="/per_task.csv">Task CSV</a> · <a href="/evidence.zip">Checksum-verified evidence ZIP</a></p><footer><small>Calibration: exploratory only. Strongest applicable OSS comparison: not executed. Official grading: not established. Multistage causal savings: not established. Do not make investor claims from the local pilot.</small></footer></main><script>
fetch('/results.json').then(r=>r.json()).then(d=>{
const hold=d.cohorts?.HOLDOUT;const k=document.getElementById('kpis');
function tile(a,b){return `<div class="tile"><div class="big">${a}</div><small>${b}</small></div>`}
k.innerHTML=tile(d.status,d.records.length+' measured tasks')+tile(d.model,'actual local model')+tile(hold?hold.fl_vs_competent.token_difference:'N/A','FL vs competent tokens (signed)')+tile(hold?hold.fl_vs_competent.paired_quality_delta:'N/A','FL-only minus baseline-only successes');
const arms=document.getElementById('arms');
let u=hold?.paired_uncertainty; if(u){const q=u.quality_delta_per_task,t=u.baseline_minus_fl_tokens_per_task;document.getElementById('uncertainty').textContent='Paired task bootstrap: quality Δ 95% interval '+(q?q.low_95.toFixed(3)+' to '+q.high_95.toFixed(3):'N/A')+'; tokens saved per task 95% interval '+(t?t.low_95.toFixed(1)+' to '+t.high_95.toFixed(1):'N/A')+'. Exact discordance p='+u.two_sided_exact_discordance_p.toFixed(4)+'. Exploratory small-sample statistics, not a commercial superiority gate.'}
let points=[];
for(const [name,v] of Object.entries(hold?.policies||{})){arms.innerHTML+=`<div class="tile"><b>${name.replaceAll('_',' ')}</b><p><strong>${v.accepted}/${v.tasks}</strong> accepted<br>${v.tokens.toLocaleString()} model tokens<br>${v.calls} model calls · ${v.extra_checks} extra probes</p></div>`;points.push({n:name,x:v.tokens,y:v.accepted/v.tasks})}
const svg=document.getElementById('frontier');if(points.length){const xmin=Math.min(...points.map(x=>x.x)),xmax=Math.max(...points.map(x=>x.x))+1;function esc(s){return s.replaceAll('&','&amp;').replaceAll('<','&lt;')}let out=`<path d="M52 16 V216 H633" fill="none" stroke="#7b8da9"/>`;
points.forEach((p,i)=>{let x=70+(p.x-xmin)/(xmax-xmin)*540,y=210-178*p.y;out+=`<circle cx="${x}" cy="${y}" r="6" fill="${['#93c5fd','#fde68a','#a7f3d0'][i]}"/><text x="${x+6}" y="${y-10}" font-size="9" fill="#dce5f2">${esc(p.n)}</text>`});out+=`<text x="290" y="246" fill="#9bacbf" font-size="12">Model-reported tokens →</text><text transform="translate(18,190) rotate(-90)" fill="#9bacbf" font-size="12">Acceptance ↑</text>`;svg.innerHTML=out}else svg.innerHTML='<text x="100" y="120" fill="#dbe6f6">No executed holdout scores</text>';
}
const rows=d.records||[];document.getElementById('table-wrap').innerHTML='<table><thead><tr><th>Task</th><th>Cohort</th><th>Policy</th><th>Accepted</th><th>Tokens</th><th>Calls</th><th>Extra checks</th></tr></thead><tbody>'+rows.flatMap(r=>Object.entries(r.arms).map(([n,a])=>`<tr><td>${r.task}</td><td>${r.cohort}</td><td>${n}</td><td class="${a.final_grade.accepted?'passed':'failure'}">${a.final_grade.accepted?'PASS':'FAIL'}</td><td>${a.usage.total_tokens}</td><td>${a.model_calls}</td><td>${a.extras_run}</td></tr>`)).join('')+'</tbody></table>';
}).catch(e=>{document.getElementById('kpis').textContent='Evidence loading failed: '+String(e)});
</script></body></html>'''

def serve(run):
    path=pathlib.Path(run).resolve()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path=='/':payload=INDEX.encode();mime='text/html; charset=utf-8'
            else:
                file={ '/results.json':'results.json','/per_task.csv':'per_task.csv','/evidence.zip':'UPLOAD_THIS_FIRSTLIGHT_DECISION.zip'}.get(self.path)
                if not file or not (path/file).is_file():self.send_error(404);return
                payload=(path/file).read_bytes();mime='application/json' if file.endswith('.json') else 'text/csv' if file.endswith('.csv') else 'application/zip'
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}/'
    print('FIRST LIGHT DECISION RESEARCH DASHBOARD:',url,flush=True)
    threading.Timer(.7,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':serve(sys.argv[1])
