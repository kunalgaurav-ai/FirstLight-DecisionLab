"""Bound local evidence server with data-bound plots and archive access."""
import html,json,pathlib,urllib.parse,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
PAGE='''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>First Light · Executed Intervention Research</title>
<style>
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#eceef4;background:#0e1420;font-synthesis:none}*{box-sizing:border-box}body{margin:0}header{padding:34px max(28px,6vw);border-bottom:1px solid #344154;background:#141e30}h1{font-size:36px;letter-spacing:-1.5px;margin:7px 0 15px}h2{font-size:20px}p{color:#aebcce;line-height:1.6;max-width:1100px}.wrap{margin:auto;max-width:1330px;padding:25px 28px 80px}.eyebrow{font-size:12px;letter-spacing:2px;color:#92b4f9;text-transform:uppercase}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}.card,.panel{background:#182436;border:1px solid #344154;border-radius:14px;padding:20px}.value{font-size:29px;font-weight:700;margin:8px 0}.sub{font-size:12px;color:#9baac0}.panel{margin-top:18px}.columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}.bar{display:flex;align-items:center;gap:12px;margin:16px 0}.bar label{width:200px;font-size:12px;color:#aebcce}.track{background:#34435b;height:15px;border-radius:4px;flex:1;overflow:hidden}.fill{height:15px;background:#81b0f6}.num{width:85px;text-align:right;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #344154;padding:12px 9px;text-align:left}th{color:#9fb9d5}table{display:block;overflow-x:auto}a{color:#a9caff}small{color:#aebcce}.hold{color:#ffd0a3}code{word-break:break-all}footer{padding:25px 0;color:#889ab3;font-size:12px}</style></head><body><header><div class="eyebrow">First Light · v5.5 · Public Program-Repair Research</div><h1>Executed early-intervention economics</h1><p>Matched continuations from one shared model proposal. Actual public QuixBugs repairs, local Ollama inference, bounded execution and independently evaluated final testcases. This is not SWE-bench, customer data, commercial cost reduction, or an OSS superiority result.</p><a href="/download/results">Download checksum-verified evidence ZIP</a></header>
<div class="wrap"><div id="status"></div><div class="grid" id="kpis"></div><div class="columns"><section class="panel"><h2>Approved tasks by policy</h2><div id="approvals"></div></section><section class="panel"><h2>Reported inference tokens by policy</h2><div id="tokens"></div></section></div><section class="panel"><h2>Matched task evidence</h2><div id="tasks"></div></section><section class="panel"><h2>Precommit error detection</h2><p>Post-hoc failure labels from public testcases, not signals available to the online controller. Lead time is zero for precommit checks; avoiding a downstream cascade has not been demonstrated.</p><div id="warnings"></div></section><section class="panel"><h2>Claim gates and methodology</h2><div id="limits"></div></section><footer>Results loaded from the local execution archive; missing and blocked experiments produce no invented points.</footer></div>
<script>
const E=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const node=id=>document.getElementById(id);
function bar(id,arms,key){let max=Math.max(1,...Object.values(arms).map(a=>a[key]||0));node(id).innerHTML=Object.entries(arms).map(([name,a])=>`<div class="bar"><label>${E(name)}</label><div class="track"><div class="fill" style="width:${100*(a[key]||0)/max}%"></div></div><span class="num">${E(a[key])}</span></div>`).join('')}
fetch('/api/results').then(r=>r.json()).then(x=>{node('status').innerHTML=`<p class="${x.status==='BLOCKED'?'hold':''}">Status: <b>${E(x.status)}</b> · Local model: ${E(x.model)} · Executed tasks: ${x.records.length} ${x.blocker?' · Blocker: '+E(x.blocker):''}</p>`;
const s=x.summary;if(!s){node('limits').textContent='No complete experiment: missing model, source or external access. No score generated.';return}
const b=s.arms.COMPETENT_TEST_REPAIR,f=s.arms.FIRSTLIGHT_PRECOMMIT,p=s.paired;
const cards=[['Competent approved',b.fully_correct+'/'+b.tasks_attempted],['First Light approved',f.fully_correct+'/'+f.tasks_attempted],['Incremental tokens',p.absolute_token_difference_baseline_minus_fl],['First Light-only successes',p.fl_only_approved],['Baseline-only successes',p.baseline_only_approved],['Measured causal $ savings','Unestablished']];node('kpis').innerHTML=cards.map(([k,v])=>`<div class="card"><div class="sub">${E(k)}</div><div class="value">${E(v)}</div></div>`).join('');bar('approvals',s.arms,'fully_correct');bar('tokens',s.arms,'total_reported_tokens');
node('tasks').innerHTML='<table><thead><tr><th>Public task</th><th>Competent tests</th><th>First Light tests</th><th>Competent tokens</th><th>First Light tokens</th><th>FL extra probe?</th></tr></thead><tbody>'+x.records.map(r=>{let a=r.arms.COMPETENT_TEST_REPAIR,b=r.arms.FIRSTLIGHT_PRECOMMIT;return `<tr><td>${E(r.task)}</td><td>${a.independent_final_cases.passed}/${a.independent_final_cases.total}</td><td>${b.independent_final_cases.passed}/${b.independent_final_cases.total}</td><td>${a.reported_usage.total_tokens}</td><td>${b.reported_usage.total_tokens}</td><td>${b.extra_precommit_used?'Yes':'No'}</td></tr>`}).join('')+'</tbody></table>';
node('warnings').innerHTML='<table><thead><tr><th>Policy</th><th>True alarms</th><th>False alarms</th><th>Missed initial errors</th><th>Correct no alarm</th></tr></thead><tbody>'+Object.entries(s.initial_proposal_warning_analysis).map(([k,a])=>`<tr><td>${E(k)}</td><td>${a.tp}</td><td>${a.fp}</td><td>${a.fn}</td><td>${a.tn}</td></tr>`).join('')+'</tbody></table>';
node('limits').innerHTML=`<p>QuixBugs source: <code>${E(x.source_provenance?.git_commit||'UNPINNED EXTERNAL SOURCE')}</code>. Checker: separately authored fixed probes; final public JSON cases withheld from policies. Both arms share the initial model output. The extra First Light probes are rule-based, not calibrated.</p><p><b>Competitive gate: HOLD.</b> Not the best OSS baseline, not independent human approval, not production all-in cost, and not SWE-bench. Reported Ollama tokens are not invoices. The number of tasks is too small for a superiority claim.</p>`}).catch(err=>node('status').textContent='Report read failed: '+err);
</script></body></html>'''

def serve(run,port=0,open_browser=True):
    run=pathlib.Path(run).resolve()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route=urllib.parse.urlsplit(self.path).path
            if route=='/': content=PAGE.encode();typ='text/html; charset=utf-8'
            elif route=='/api/results':content=(run/'results.json').read_bytes();typ='application/json'
            elif route=='/download/results':
                choices=list(run.glob('UPLOAD_THIS_FIRSTLIGHT_V55_*.zip'))
                if not choices:self.send_error(404);return
                content=choices[0].read_bytes();typ='application/zip'
            elif route=='/download/csv':
                p=run/'task_results.csv'
                if not p.exists():self.send_error(404);return
                content=p.read_bytes();typ='text/csv'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def log_message(self,*a):pass
    with ThreadingHTTPServer(('127.0.0.1',port),Handler) as server:
        url=f'http://127.0.0.1:{server.server_port}/';print('FIRST LIGHT v5.5 RESEARCH DASHBOARD:',url,flush=True)
        if open_browser:webbrowser.open(url)
        try:server.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('run');a=ap.parse_args();serve(a.run)
