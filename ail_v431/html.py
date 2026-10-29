PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AIL Evidence Review · v4.3.1</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Arial;color:#1e293b;background:#f5f7fa}body{margin:0}
main{max-width:1120px;margin:28px auto;padding:0 20px 65px}h1{font-size:25px;letter-spacing:-.5px}h2{font-size:18px}
.card{border:1px solid #d8dee8;background:white;border-radius:12px;padding:18px;margin:14px 0}
.tile{border:1px solid #e1e7ef;border-radius:10px;padding:15px;background:#fff} .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}
.small{font-size:13px;color:#526176}.status{font-weight:700} .success{color:#176344}.bad{color:#942e21}.muted{color:#58677a}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.4 ui-monospace,Consolas,monospace;background:#f6f8fb;padding:9px;border-radius:6px}
video{display:block;width:100%;min-height:120px;max-height:300px;background:#15171c;border-radius:8px}
button{font:inherit;border:1px solid #c5cedc;background:#fff;border-radius:8px;padding:10px 12px;cursor:pointer;margin:6px 5px 6px 0}button.primary{color:white;background:#2353c6;border-color:#2353c6}button:disabled{opacity:.5;cursor:not-allowed}
label{display:block;margin:8px 0}.flex{display:flex;gap:10px;align-items:center;flex-wrap:wrap}select,input,textarea{font:inherit;border:1px solid #bfc9d8;border-radius:5px;padding:6px}textarea{width:96%;height:65px}
.kpi{font-size:21px;font-weight:700} summary{cursor:pointer}a{color:#164bb6} .note{border-left:3px solid #bd8d2a;padding-left:12px}
</style><script src="/app.js" defer></script></head><body><main>
<h1>Agent Intelligence Lab · v4.3.1</h1>
<p>Prompt-to-video evidence viewer and execution ledger. <strong>A prompt that has never been sent is not a failed video.</strong> Generated outputs are from real provider calls; no slideshow substitutes are allowed.</p>
<div class="card"><h2>What this run establishes</h2><div class="flex"><div><div class="kpi" id="available">—</div><div class="small">Verified clips</div></div><div><div class="kpi" id="pending">—</div><div class="small">Unrequested prompts</div></div><div><div class="kpi" id="budget">—</div><div class="small">Optional new GPU calls remaining</div></div></div>
<p class="small">Only user-initiated additional prompts call the public LTX-2.5 provider; shared quota, latency and availability are not guaranteed. No cloud provider invoice or customer approval established.</p>
<p class="status" id="connection">Connecting to local evidence server…</p></div>
<div class="card"><h2>Frozen text-to-video prompts</h2><p class="note">For each task, check its actual execution state. <strong>Not requested</strong> means no video exists. <strong>Failed</strong> means an attempted provider or media operation failed. Video players appear only for checksum-verified files.</p><div class="grid" id="tasks"></div></div>
<div class="card"><h2>Audit and handoff</h2><p class="small" id="source"></p><p class="small" id="zip"></p><details><summary>Execution events</summary><pre id="events"></pre></details><p class="small">Video quality, movement, temporal order and prompt adherence require real review. Reviewer self-attestations do not establish independent approval or commercial savings.</p></div>
</main></body></html>'''
