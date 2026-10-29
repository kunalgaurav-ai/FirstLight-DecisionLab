"""Real-results-only SVG research dashboard, downloadable evidence and local HTTP service."""
import html
import json
import math
import os
import sys
import threading
import webbrowser
import http.server
import socketserver
from pathlib import Path
from .matrix import STRATEGIES, key


def esc(x): return html.escape(str(x),quote=True)

def _plot(summary,xkey,title,xlabel):
    arms=list((summary or {}).get('arms',{}).values())
    eligible=[a for a in arms if a.get('rate') is not None and a.get('completed')==a.get('attempted') and a.get('scored')==a.get('attempted') and a.get('attempted')>0]
    width,height=650,310;left,top,right,bottom=63,32,28,49
    x0=left;x1=width-right;y0=height-bottom;y1=top
    xmax=max([float(a[xkey]) for a in eligible] or [1])*1.07 or 1
    ticks=''.join(f'<line x1="{left}" x2="{x1}" y1="{top+(y0-top)*i/4:.1f}" y2="{top+(y0-top)*i/4:.1f}" stroke="#e4eaf1"/><text x="{left-10}" y="{top+(y0-top)*i/4+4:.1f}" text-anchor="end" font-size="11" fill="#54606e">{int(100-25*i)}%</text>' for i in range(5))
    pts=''
    palette={'SINGLE':'#9ba7b4','GUARDED':'#f59e0b','FIRSTLIGHT':'#1a65d7'}
    for i,a in enumerate(eligible):
        x=x0+(a[xkey]/xmax)*(x1-x0);y=y0-(a['rate'])*(y0-y1)
        color=palette.get(a['strategy'],'#555')
        label=a['model']+' / '+a['strategy']
        pts+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" stroke="white" stroke-width="1.5"><title>{esc(label)} | pass {a["passes"]}/{a["attempted"]} | {xkey}: {a[xkey]}</title></circle>'
    if not pts:pts=f'<text x="325" y="143" text-anchor="middle" font-size="16" fill="#7a8593">Awaiting actual model × policy executions</text>'
    return f'''<section class="figure"><h3>{esc(title)}</h3><svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}"><rect width="{width}" height="{height}" fill="white"/>{ticks}<path d="M{left} {top} V{y0} H{x1}" stroke="#919dab" fill="none"/>{pts}<text x="{(left+x1)//2}" y="{height-7}" text-anchor="middle" font-size="12" fill="#566578">{esc(xlabel)} →</text><text x="15" y="155" transform="rotate(-90 15 155)" text-anchor="middle" font-size="12" fill="#566578">Diagnostic accuracy (%)</text></svg><p class="disclaimer">Each dot is a separately measured configuration. Colors: gray single-pass, amber guarded retry, blue First Light. Hover for model names.</p></section>'''


def html_page(report,history=None):
    summary=report.get('summary') or {}
    arms=summary.get('arms',{})
    rows=''.join(f'<tr><td>{esc(a["model"])}</td><td>{esc(a["strategy"])}</td><td>{a["passes"]}/{a["scored"] if a["scored"] else "—"}</td><td>{"%.1f"%(100*a["rate"]) if a["rate"] is not None else "—"}%</td><td>{a["reported_tokens"]:,}</td><td>{a["summed_call_wall_s"]:.2f}</td><td>{a["calls"]}</td></tr>' for a in arms.values())
    if not rows:rows='<tr><td colspan="7">No measured comparisons yet.</td></tr>'
    status=report.get('state','UNKNOWN')
    hist=''
    if history:
        hist=f'<p class="notice">Historical v5.2 Mac pilot (separate experiment): guarded Qwen2.5 1.5B and First Light adaptive both scored 18/24 (75%) with 10,574 vs 8,953 reported tokens and 25.55 vs 10.73 seconds summed model-call time. Do not merge those 24 tasks with the v5.3 cohort.</p>'
    x=_plot(summary,'reported_tokens','Quality vs reported token count','Reported tokens (model-dependent)')
    y=_plot(summary,'summed_call_wall_s','Quality vs local inference time','Summed Ollama call wall time (seconds)')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>First Light — Competitive Research</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8fafc;color:#1c2632;margin:0}}main{{max-width:1400px;margin:0 auto;padding:35px 25px 65px}}header{{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #dce3eb;padding:14px 32px;background:white}}header strong{{font-size:20px}}.tag{{border:1px solid #9aaaca;background:#f3f6ff;padding:7px 11px;border-radius:20px;font-size:12px}}h1{{font-size:52px;letter-spacing:-2px;margin:22px 0 12px}}h2{{font-size:23px;margin:32px 0 14px}}p{{line-height:1.55;color:#536276}}.charts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.figure,.board{{border:1px solid #dce3eb;border-radius:12px;background:white;padding:18px}}.figure h3{{font-size:17px;margin:4px 0 10px}}svg{{width:100%;height:auto}}.disclaimer{{font-size:11px;margin:0}}.status{{background:#eef3ff;border-left:3px solid #4776d8;padding:12px;border-radius:6px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;padding:11px;border-bottom:1px solid #e6ebf1}}th{{background:#f4f7fa;color:#536276}}.notice{{background:#f5f6f7;padding:14px;border-left:3px solid #8896a5;border-radius:6px}}a{{color:#164fbd}}.links{{display:flex;gap:20px;flex-wrap:wrap}}@media(max-width:850px){{.charts{{grid-template-columns:1fr}}h1{{font-size:35px}}}}
</style></head><body><header><strong>✦ First Light</strong><span class="tag">Independent benchmark research • Not a leaderboard submission</span></header><main><h1>Research</h1><p>Risk-sensitive, quality-constrained runtime optimization across agents, models and modalities. This page presents the first local public-task experiment; it does not claim universal economic superiority.</p><p class="status"><strong>Experiment status:</strong> {esc(status)} · Benchmark: BFCL V4 single-turn diagnostic · {len(report.get('rows',[]))} matched tasks · {len(report.get('requested_models',[]))} requested models. <strong>Customer cost savings and official BFCL accuracy: NOT ESTABLISHED.</strong> {esc(report.get('blocker',''))}</p>{hist}<h2>Named model × policy comparisons</h2><div class="charts">{x}{y}</div><h2>Full results table</h2><div class="board" style="overflow-x:auto"><table><thead><tr><th>Model</th><th>Execution policy</th><th>Passed</th><th>Pass rate</th><th>Reported tokens</th><th>Model seconds</th><th>Calls</th></tr></thead><tbody>{rows}</tbody></table></div><h2>Evidence and reproducibility</h2><div class="links"><a href="/api/results">Raw JSON</a><a href="/data/matrix_rows.csv">Per-task CSV</a><a href="/download/evidence">Evidence ZIP</a><a href="https://gorilla.cs.berkeley.edu/leaderboard">Official BFCL results (context only)</a></div><p>No fabricated comparisons to Claude, GPT, Gemini, or ReasonBlocks. Those models and optimizers require separately executed matched baselines, official evaluation, permissions and all-in cost accounting. The current local diagnostic is not directly comparable with Berkeley's overall leaderboard.</p><p>Model-family token counts differ. Token totals must not be interpreted as cross-provider dollars. Summed inference time excludes download, setup, data validation and evaluation overhead. Confidence intervals and paired results are in the raw report.</p></main></body></html>'''


def serve(root,port=0,open_browser=True):
    root=Path(root).resolve()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def do_GET(self):
            p=self.path.split('?',1)[0]
            if p=='/api/health':
                blob=b'{"status":"ok","brand":"First Light"}';typ='application/json'
            elif p=='/api/results':
                blob=(root/'matrix_results.json').read_bytes();typ='application/json'
            elif p=='/data/matrix_rows.csv':
                blob=(root/'matrix_rows.csv').read_bytes();typ='text/csv'
            elif p=='/download/evidence':
                found=sorted(root.glob('UPLOAD_THIS_FIRSTLIGHT_V53_*.zip'))
                if not found:self.send_error(404);return
                blob=found[-1].read_bytes();typ='application/zip'
            elif p=='/':
                d=json.loads((root/'matrix_results.json').read_text())
                blob=html_page(d,history=True).encode();typ='text/html; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',typ)
            self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(blob)
    class Server(http.server.ThreadingHTTPServer):allow_reuse_address=True;daemon_threads=True
    server=Server(('127.0.0.1',port),Handler)
    url=f'http://127.0.0.1:{server.server_port}/'
    print('FIRST LIGHT MULTI-MODEL RESEARCH DASHBOARD:',url,flush=True)
    if open_browser:webbrowser.open(url)
    try:server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':
    serve(sys.argv[1],open_browser=('--no-browser' not in sys.argv))
