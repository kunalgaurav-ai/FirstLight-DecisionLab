"""Actual-evidence-only First Light website served on localhost."""
import html,http.server,json,sys,webbrowser
from pathlib import Path

def esc(s):return html.escape(str(s),quote=True)

def plot(entries,x_key,heading,xlabel):
    allowed=[r for r in entries if r.get('finished_all_tasks') and r.get('scored',0)>=4 and r.get('diagnostic_rate') is not None]
    w,h=645,300;L,T,R,B=56,22,23,43
    xmax=max([r[x_key] for r in allowed] or [1]) * 1.12 or 1
    colors={'SINGLE_TARGET':'#9299a4','GUARDED_TARGET':'#cc8643','COMPETENT_CHEAP_FIRST':'#15978e',
            'FIRSTLIGHT_CONSTRAINED':'#375fd6','MODEL_SCREEN_ONLY':'#596f93'}
    grid=''.join(f'<line x1="{L}" x2="{w-R}" y1="{T+i*(h-B-T)/4:.1f}" y2="{T+i*(h-B-T)/4:.1f}" stroke="#e4e8ed"/><text x="{L-9}" y="{T+i*(h-B-T)/4+4:.1f}" text-anchor="end" font-size="11" fill="#77838f">{100-i*25}%</text>' for i in range(5))
    plotted=[]
    for r in allowed:
        x=L+(w-L-R)*(r[x_key]/xmax);y=h-B-(h-B-T)*r['diagnostic_rate'];c=colors[r['policy']]
        detail=f"{r['model']} | {r['policy']} | {r['passed']}/{r['scored']} | {xlabel} {r[x_key]}"
        plotted.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.4" fill="{c}" stroke="white" stroke-width="1.7"><title>{esc(detail)}</title></circle>')
    if not plotted:plotted=['<text x="323" y="137" fill="#85919d" font-size="17" text-anchor="middle">No completed matched holdout yet</text>']
    return f'''<article class="chart"><h3>{esc(heading)}</h3><svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(heading)}">{grid}<path d="M{L},{T} V{h-B} H{w-R}" stroke="#a0aab4" fill="none"/>{''.join(plotted)}<text x="{w/2}" y="{h-6}" text-anchor="middle" font-size="12" fill="#596671">{esc(xlabel)} →</text><text x="13" y="149" transform="rotate(-90 13 149)" text-anchor="middle" font-size="11" fill="#596671">Local diagnostic correctness</text></svg><p class="small">Points are real completed observations only. No external frontier model data combined into this local BFCL plot.</p></article>'''


def page(report,early):
    rows=report.get('summary',{});values=list(rows.values())
    table=''.join(f'''<tr><td>{esc(r['model'])}</td><td>{esc(r['policy'])}</td><td>{r['passed']}/{r['scored']}</td><td>{esc('%.1f%%'%(100*r['diagnostic_rate'])) if r.get('diagnostic_rate') is not None else '—'}</td><td>{r['reported_tokens']:,}</td><td>{r['summed_model_wall_s']:.2f}</td><td>{r['summed_stage_wall_s']:.2f}</td><td>{r['inference_calls']}</td></tr>''' for r in sorted(values,key=lambda x:(-x['diagnostic_rate'] if x['diagnostic_rate'] is not None else 1,x['summed_stage_wall_s'])))
    if not table:table='<tr><td colspan="8">No holdout results yet. Configuration must execute on your Mac.</td></tr>'
    count=len(report.get('installed_models',[]));total=len(report.get('model_candidates',[]))
    screen_map=report.get('screen_summary',{})
    screen_rows=list(screen_map.values())
    screen_table=''.join(f'<tr><td>{esc(x["model"])}</td><td>{x["passed"]}/{x["scored"]}</td><td>{esc("%.1f%%"%(100*x["diagnostic_rate"])) if x["diagnostic_rate"] is not None else "—"}</td><td>{x["reported_tokens"]:,}</td><td>{x["summed_stage_wall_s"]:.2f}</td></tr>' for x in screen_rows)
    if not screen_table:screen_table='<tr><td colspan="5">Not executed yet.</td></tr>'
    figs=early.get('figures',{})
    ehtml=''.join(f'<tr><td>{esc(k)}</td><td>{v["incorrect_first_attempts"]}</td><td>{v["incorrect_and_schema_flagged"]}</td><td>{v["incorrect_but_schema_valid"]}</td></tr>' for k,v in figs.items())
    if not ehtml:ehtml='<tr><td colspan="4">No real precommit records yet.</td></tr>'
    paired=report.get('paired',{})
    pairs=''.join(f'<tr><td>{esc(model)}</td><td>{v["matched_scored_tasks"]}/{v["intended_tasks"]}</td><td>{v["firstlight_only_passes"]}</td><td>{v["competent_only_passes"]}</td><td>{esc(v["exact_two_sided_mcnemar_p"])}</td><td>{esc(round(v["firstlight_token_ratio_relative_to_competent"],3) if v["firstlight_token_ratio_relative_to_competent"] is not None else "—")}</td><td>{esc(round(v["firstlight_stage_time_ratio_relative_to_competent"],3) if v["firstlight_stage_time_ratio_relative_to_competent"] is not None else "—")}</td></tr>' for model,v in paired.items())
    if not pairs:pairs='<tr><td colspan="7">No paired heldout observations yet.</td></tr>'
    screen_chart=plot(screen_rows,'reported_tokens','Screening: named model correctness vs tokens','Reported tokens on screening only')
    x=plot(values,'reported_tokens','Task correctness vs total reported tokens','Total model-reported tokens')
    y=plot(values,'summed_stage_wall_s','Task correctness vs stage elapsed time','Aggregated stage seconds (not user latency)')
    missing=', '.join(report.get('missing_models',[])) or 'None'
    status=report.get('state','NOT_EXECUTED')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>First Light · Competitive Research</title><style>
:root{{--ink:#18252f;--mute:#5b6874;--border:#dce3ea;--bg:#f9fafb}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}header{{background:white;padding:19px max(24px,calc((100vw - 1380px)/2));border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}header strong{{font-size:19px}}header span{{font-size:12px;color:var(--mute)}}main{{max-width:1390px;padding:45px 25px 65px;margin:auto}}h1{{font-size:58px;line-height:1.05;letter-spacing:-2.5px;margin:20px 0 12px}}h2{{font-size:23px;margin:34px 0 17px}}h3{{font-size:17px}}p{{color:var(--mute);line-height:1.55}}.eyebrow{{color:#315fcb;font-weight:700;letter-spacing:.08em;font-size:12px}}.lead{{max-width:940px;font-size:18px}}.status{{border:1px solid var(--border);border-left:4px solid #cc8643;background:#fff;padding:16px;line-height:1.65;border-radius:7px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:24px 0}}.stat,.chart,.data{{background:white;border:1px solid var(--border);border-radius:10px;padding:20px}}.stat b{{font-size:30px;display:block;margin-bottom:8px}}.stat small{{color:var(--mute)}}.charts{{display:grid;grid-template-columns:1fr 1fr;gap:17px}}.chart svg{{width:100%}}.small{{font-size:12px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{font-weight:700;background:#f5f8fa;color:#566575}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #e6ebf0}}.data{{overflow-x:auto}}.legend{{display:flex;flex-wrap:wrap;gap:22px;margin-top:18px;font-size:13px}}.legend i{{display:inline-block;height:10px;width:10px;border-radius:50%;margin-right:6px}}a{{color:#2151b0}}footer{{color:var(--mute);font-size:13px;line-height:1.6;padding-top:30px}}@media(max-width:850px){{.charts{{grid-template-columns:1fr}}.stats{{grid-template-columns:1fr 1fr}}h1{{font-size:39px}}}}</style></head><body>
<header><strong>✳ First Light</strong><span>RESEARCH LAB · VERIFIED EVIDENCE ONLY</span></header><main><div class="eyebrow">RUNTIME ECONOMICS / REPRODUCIBLE BENCHMARKS</div><h1>Research</h1><p class="lead">Risk-aware adaptive runtime control across models, tools, workflows and modalities. Named configurations measured on pinned public tasks, with strong alternative policies and full negative-result disclosure.</p>
<div class="status"><strong>Current study:</strong> BFCL V4 published single-turn subset, local diagnostic only. <strong>Status:</strong> {esc(status)}. <strong>Holdout:</strong> {len(report.get('eval',[]))} measured cases; <strong>Screen:</strong> {len(report.get('screen',[]))} disjoint cases. {count} of {total} candidate models locally installed. {esc(report.get('blocker',''))}<br><strong>Headline First Light versus best OSS / accepted-outcome dollars / official leaderboard grade:</strong> NOT ESTABLISHED.</div>
<div class="stats"><div class="stat"><b>{len(report.get('model_candidates',[]))}</b>Named model candidates<br><small>Only installed models can produce points</small></div><div class="stat"><b>{len(report.get('selection',{}).get('finalists',[]))}</b>Held-out finalist models<br><small>Selected on disjoint screening tasks</small></div><div class="stat"><b>{len(rows)}</b>Scored model × policy arms<br><small>All four policies reported per finalist</small></div><div class="stat"><b>HOLD</b>External superiority claim<br><small>No official BFCL or approved-outcome dollars</small></div></div>
<h2>All named model candidates · actual screening observations</h2>
<div class="charts">{screen_chart}<article class="chart"><h3>Screening scoreboard</h3><div style="overflow-x:auto"><table><thead><tr><th>Named model</th><th>Correct</th><th>Rate</th><th>Reported tokens</th><th>Stage seconds</th></tr></thead><tbody>{screen_table}</tbody></table></div><p class="small">This section is for preliminary model screening, not held-out accuracy or commercial model ranking. Uninstalled candidates are explicitly listed below.</p></article></div>
<h2>Two matched quality–resource frontiers</h2><div class="charts">{x}{y}</div><div class="legend"><span><i style="background:#9299a4"></i>Single model</span><span><i style="background:#cc8643"></i>Guarded retry</span><span><i style="background:#15978e"></i>Competent cheap-first</span><span><i style="background:#375fd6"></i>First Light constrained</span></div>
<h2>Every named configuration, including losses</h2><div class="data"><table><thead><tr><th>Model</th><th>Policy</th><th>Correct</th><th>Diagnostic rate</th><th>Tokens</th><th>Model seconds</th><th>Stage seconds</th><th>Calls</th></tr></thead><tbody>{table}</tbody></table></div><p class="small">Missing/unavailable models: {esc(missing)}. Tokenizers differ across families; token totals are not dollar savings. Optimizer baseline is an implemented competent reference policy, not a verified integration of RouteLLM/FrugalGPT/LiteLLM.</p>
<h2>Increment beyond competent cheap-first</h2><div class="data"><table><thead><tr><th>Target model</th><th>Matched tasks</th><th>First Light-only passes</th><th>Baseline-only passes</th><th>McNemar exact p</th><th>FL / baseline tokens</th><th>FL / baseline stage time</th></tr></thead><tbody>{pairs}</tbody></table><p class="small">A ratio below 1 means lower recorded resources in the First Light arm on matched tasks. This is not independently approved quality, a commercial dollar ratio, or proof of superiority against installed OSS optimizers.</p></div>
<h2>Early warning: actual pre-commitment evidence</h2><div class="data"><p>Structural errors can be detected before a tool call is committed. A schema-valid but semantically incorrect invocation is usually invisible to that simple warning. This graph-ready table reports both, without claiming a prevented multi-step failure.</p><table><thead><tr><th>Policy</th><th>Incorrect first calls</th><th>Flagged by precommit schema check</th><th>Missed (schema-valid)</th></tr></thead><tbody>{ehtml}</tbody></table><p class="small">Long-horizon lead time, causal downstream spending avoided and prospective independent labels: NOT MEASURED. Optional separate annotated-prefix study is exported only when supplied.</p></div>
<h2>Evidence and audit trail</h2><p><a href="/api/results">Raw study JSON</a> · <a href="/api/early">Precommit warning evidence</a> · <a href="/data/holdout.csv">Per-task ledger CSV</a> · <a href="/download/evidence">Content-hashed ZIP</a></p><footer>The study is not SWE-bench, not customer workloads, not an official Berkeley leaderboard entry, and not proof of multi-modal generalization. We will publish giant multipliers only if experimentally supported against comparable incumbents under independent quality and all-in cost accounting.</footer>
</main></body></html>'''


def serve(root,port=0,open_browser=True):
    root=Path(root).resolve()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):
            try:
                p=self.path.split('?',1)[0]
                if p=='/api/health':content=b'{"status":"ok","brand":"First Light","version":"5.4.0"}';mime='application/json'
                elif p=='/api/results':content=(root/'results_v54.json').read_bytes();mime='application/json'
                elif p=='/api/early':content=(root/'early_warning_v54.json').read_bytes();mime='application/json'
                elif p=='/data/holdout.csv':content=(root/'holdout_rows_v54.csv').read_bytes();mime='text/csv'
                elif p=='/download/evidence':
                    choices=sorted(root.glob('UPLOAD_THIS_FIRSTLIGHT_V54_*.zip'))
                    if not choices:self.send_error(404);return
                    content=choices[-1].read_bytes();mime='application/zip'
                elif p=='/':
                    report=json.loads((root/'results_v54.json').read_text())
                    early=json.loads((root/'early_warning_v54.json').read_text())
                    content=page(report,early).encode();mime='text/html; charset=utf-8'
                else:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store')
                self.end_headers();self.wfile.write(content)
            except (OSError,ValueError,KeyError) as ex:self.send_error(500,str(ex)[:200])
    class Server(http.server.ThreadingHTTPServer):allow_reuse_address=True;daemon_threads=True
    httpd=Server(('127.0.0.1',port),Handler)
    url=f'http://127.0.0.1:{httpd.server_port}/'
    print('FIRST LIGHT v5.4 RESEARCH DASHBOARD:',url,flush=True)
    if open_browser:webbrowser.open(url)
    try:httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:pass
    finally:httpd.server_close()

if __name__=='__main__':serve(sys.argv[1],open_browser='--no-browser' not in sys.argv)
