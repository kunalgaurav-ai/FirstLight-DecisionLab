"""Localhost-only, stdlib HTTP dashboard for actual v3.3 fixture receipts."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML = r'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIL v3.3 | Measured Fixture Execution</title><style>
:root{color-scheme:light}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#f6f8fb;color:#12243a}
header{background:#10263d;color:white;padding:28px 6%}h1{margin:0 0 6px;font-weight:700;font-size:28px}header p{color:#c9d9e8;margin:6px 0}
main{max-width:1240px;margin:auto;padding:22px}.note{background:#fff2ce;border-left:4px solid #d39700;padding:12px 16px;margin:12px 0 22px;line-height:1.5}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:20px}.card{background:white;border:1px solid #dce3ed;border-radius:10px;padding:15px}.card h3{margin:0 0 7px;font-size:13px;color:#42617e}.card b{font-size:24px}
section{background:white;border:1px solid #dce3ed;border-radius:10px;margin:16px 0;padding:17px;overflow:auto}section h2{font-size:18px;margin:2px 0 12px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #e2e7ef;text-align:left;white-space:nowrap}th{background:#f2f6fb}td.num{text-align:right;font-variant-numeric:tabular-nums}
label{font-size:14px;font-weight:600}select,input{margin:0 10px;padding:7px;border:1px solid #bdcad7;border-radius:6px;background:white}button{background:#204b74;color:white;padding:8px 11px;border:0;border-radius:6px;cursor:pointer}
pre{background:#f2f6fa;border:1px solid #dde5ed;border-radius:8px;padding:12px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-size:12px}
footer{margin:20px 0;color:#596d7e;font-size:12px}</style></head><body>
<header><h1>Agent Intelligence Lab · v3.3 companion</h1><p>Actual local execution on constructed cases · No model calls · No customer spend or approval</p></header>
<main><div class="note"><b>Evidence status: HOLD for commercial claims.</b> The B1 baseline already performs competent early verification and selective repair. Constructed resource units are not invoices. Rights checks are mandatory. The HMM remains untrained and excluded from decisions. There is no integrated v3.2 source in this release.</div>
<div id="stats" class="cards"></div>
<section><h2>Per-arm comparison</h2><div id="summary"></div></section>
<section><h2>Task decisions and verified local outputs</h2><label for="arm">Arm</label><select id="arm"><option value="ALL">All</option></select><label for="q">Task</label><input id="q" placeholder="Filter task id"><div id="tasks" style="margin-top:14px"></div></section>
<section><h2>Selected executed stage receipts</h2><p id="selected">Select a task row to inspect its stage receipts.</p><pre id="receipts">No task selected</pre></section>
<section><h2>Evidence gates and limitations</h2><pre id="gates"></pre></section>
<footer>The report is loaded from a local JSON file via a localhost-only Python server. No analytics or external connections.</footer></main>
<script>
(async()=>{
const r=await fetch('/api/report').then(x=>x.json());const esc=s=>String(s??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const arm=document.getElementById('arm'), q=document.getElementById('q');
for(const a of r.arms){const o=document.createElement('option');o.value=a;o.textContent=a;arm.appendChild(o)}
const counts=r.per_arm;const cards=[['Cases per arm',counts[r.arms[0]].total_cases],['Arms executed',r.arms.length],['Output SHA parity',r.parity_exact_package_sha_across_arms?'PASS':'FAIL'],['Commercial gate',r.commercial_gate]];
document.getElementById('stats').innerHTML=cards.map(c=>`<div class="card"><h3>${esc(c[0])}</h3><b style="font-size:${String(c[1]).length>19?'13':'22'}px">${esc(c[1])}</b></div>`).join('');
const table=(head,rows)=>'<table><thead><tr>'+head.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(a=>'<tr>'+a.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
document.getElementById('summary').innerHTML=table(['Arm','Stage operations','Check calls early','Check calls late','Written bytes','Technically passed','Blocked','Independent approvals'],r.arms.map(a=>[a,counts[a].stage_ops_executed,counts[a].early_check_calls,counts[a].late_check_calls,counts[a].bytes_written,counts[a].technically_passed,counts[a].blocked_rights,'UNOBSERVED']));
function refresh(){const rows=r.task_rows.filter(t=>(arm.value==='ALL'||t.arm===arm.value)&&t.task_id.toLowerCase().includes(q.value.toLowerCase()));
let html='<table><thead><tr><th>Task</th><th>Arm</th><th>Decision</th><th>Stage ops</th><th>Result</th><th>Inspect</th></tr></thead><tbody>';
rows.forEach(t=>{const ix=r.task_rows.indexOf(t);html+=`<tr><td>${esc(t.task_id)}</td><td>${esc(t.arm)}</td><td>${esc(t.decision.decision)}</td><td>${t.stage_ops}</td><td>${esc(t.status)}</td><td><button data-row="${ix}">Receipts</button></td></tr>`});html+='</tbody></table>';
const el=document.getElementById('tasks');el.innerHTML=html;el.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{const t=r.task_rows[Number(b.dataset.row)];document.getElementById('selected').textContent=t.task_id+' — '+t.arm+' — '+t.status;document.getElementById('receipts').textContent=JSON.stringify({decision:t.decision,frontier:t.frontier,events:r.events.filter(e=>e.task_id===t.task_id&&e.arm===t.arm)},null,2)}))}
arm.onchange=refresh;q.oninput=refresh;refresh();
document.getElementById('gates').textContent=JSON.stringify({study_kind:r.study_kind,commercial_gate:r.commercial_gate,source_integration:r.source_integration,oss_comparator:r.license_comparator,hmm:r.hmm_challenger,notes:r.notes},null,2);
})();</script></body></html>'''


def serve(report: Path, open_browser: bool = True) -> None:
    report = report.resolve(strict=True)
    data = json.loads(report.read_text())
    if data.get("schema_version") != "ail.v33.companion.report.1":
        raise ValueError("unexpected report schema")
    encoded = json.dumps(data, sort_keys=True).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                content, content_type = HTML.encode(), "text/html; charset=utf-8"
            elif self.path == "/api/report":
                content, content_type = encoded, "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' 'self'; connect-src 'self'")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, fmt, *args):
            sys.stdout.write("[localhost] " + (fmt % args) + "\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Dashboard: {url}", flush=True)
    print("Press Ctrl+C to stop the local server.", flush=True)
    if open_browser:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(url)
        except OSError as exc:
            print(f"Browser opening failed ({exc}); navigate manually to {url}", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        print("Local dashboard stopped", flush=True)
    finally:
        server.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    serve(args.report, not args.no_browser)


if __name__ == "__main__":
    main()
