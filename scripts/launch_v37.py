#!/usr/bin/env python3
"""AIL v3.7: regressions, historical graded joins, exploratory models and dashboard."""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v37.observed import join,evaluate
from ail_v36.fallback import fixture_parity
from ail_v35.dashboard import HTML as HISTORICAL_HTML
from ail_v35.opportunity import assess_workflow,screen_action
from ail_v35.examples import fixture,unsupported_action

SUBMISSION='20260901_mini-v2.4.2_gemini-3-5-flash'

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(262144),b''):h.update(block)
    return h.hexdigest()

def save(out,obj):
    with out.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n')

def sources():
    t=os.environ.get('AIL_V37_TRACE_DIR','').strip()
    g=os.environ.get('AIL_V37_GRADE_FILE','').strip()
    if bool(t)!=bool(g):raise ValueError('Both AIL_V37_TRACE_DIR and AIL_V37_GRADE_FILE required for override')
    if t:return Path(t).expanduser(),Path(g).expanduser(),'EXPLICIT_USER_PATH'
    base=Path.home()/'Downloads'/'agent-intelligence-lab-rigorous'/'data'
    for td in (base/'rich_traces',base/'rich_traces'/'trajectories'):
        for gp in (base/'token_waste_labeled_calls.jsonl',base/'official_grades.jsonl'):
            if td.is_dir() and gp.is_file():return td,gp,'EXISTING_AIL_WORKSPACE'
    return None,None,'NOT_FOUND'

def server(report,parity,source,show_browser):
    script='''<section id="observed37"><h2>v3.7 | Real graded trajectory recovery</h2><p>Existing v3.3–v3.5 analytical pages remain available. v3.7 predictions are retrospective and are NOT cost savings or independently approved customer results.</p><pre id="v37status"></pre><pre id="v37metrics"></pre></section>'''
    js='''<script>fetch('/api/v37').then(x=>x.json()).then(x=>{document.getElementById('v37status').textContent=JSON.stringify({status:x.observed.status,cohorts:x.observed.cohort_counts,trained_models:x.observed.models_fitted,schema_rejections:x.observed.data_provenance?.label_source?.rejected,competent_baseline_ops:x.fallback.incumbent_operations,ail_fallback_ops:x.fallback.ail_safe_fallback_operations},null,2);document.getElementById('v37metrics').textContent=JSON.stringify(x.observed.landmarks,null,2);});</script>'''
    page=HISTORICAL_HTML.replace('</main>',script+'</main>').replace('</body>',js+'</body>')
    # Preserve and service every inherited dashboard tab. Do not render inert widgets.
    ref=ROOT/'evidence/archive/UPLOAD_THIS_v34_20261025T013125Z_26c53846.zip'
    with zipfile.ZipFile(ref) as prior:
        original=json.loads(prior.read('results_v33_fixture_reexecution.json'))
        calibration=json.loads(prior.read('calibration_v34.json'))
        useraudit=json.loads(prior.read('user_v33_audit.json'))
    graph=assess_workflow(fixture())
    edge={'version':'v3.7-retained-v35-fixture','status':'HOLD_CONSTRUCTED_ECONOMIC_GRAPH',
          'commercial_advantage':'NOT_ESTABLISHED','trained_new_model':False,
          'opportunity':graph,'scenario_screen':screen_action(unsupported_action(),graph['checkpoints'][0]),
          'prospective_causal_effect':'NOT_IDENTIFIED','policy_coverage':'SHADOW_ONLY'}
    api={'/api/v37':{'observed':report,'fallback':parity,'source':source},
         '/api/report':original,'/api/calibration':calibration,
         '/api/user-v33-audit':useraudit,'/api/edge':edge}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/index.html'):data=page.encode();typ='text/html; charset=utf-8'
            elif self.path in api:data=json.dumps(api[self.path]).encode();typ='application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self,*a):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{http.server_port}/'
    print('DASHBOARD:',url,flush=True)
    if show_browser and sys.platform=='darwin':subprocess.Popen(['open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Ctrl+C ends the dashboard; the report ZIP is already complete.',flush=True)
    try:http.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:http.server_close()

def main():
    now=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run=ROOT/'runs'/f'v37_{now}_{uuid.uuid4().hex[:8]}'
    run.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-v']
    t=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (run/'tests_v37.txt').write_text('COMMAND: '+repr(cmd)+'\nEXIT: '+str(t.returncode)+'\n'+t.stdout+t.stderr,encoding='utf-8')
    if t.returncode:
        print('TESTS FAILED. LOG:',run/'tests_v37.txt',flush=True);return 2
    parity=fixture_parity(run/'fixture_artifacts')
    if not parity['baseline_parity']:raise RuntimeError('Fixture baseline regression')
    save(run/'fallback_v37.json',parity)
    lookup={'status':'NOT_FOUND'}
    try:
        td,gp,origin=sources()
        if td and gp:
            episode,lookup=join(td,gp,SUBMISSION)
            report=evaluate(episode,lookup)
        else:
            report=evaluate([],lookup)
        lookup_status=origin
    except Exception as e:
        # fail-closed with diagnostic reason; do not silently manufacture grade matches
        report=evaluate([],{ 'status':'INTEGRITY_OR_FORMAT_FAILURE', 'error_type':type(e).__name__, 'error_classification':str(e)[:200]})
        lookup_status='BLOCKED_INPUT'
    save(run/'observed_study_v37.json',report)
    discovery={'version':'v3.7','lookup_status':lookup_status,
               'joined_episodes':report['data_provenance'].get('joined_episodes',0),
               'label_counts':report['data_provenance'].get('label_source',{}).get('outcome_source_counts',{}),
               'schema_diagnostics':report['data_provenance'].get('label_source',{}).get('schema_type_counts',{}),
               'raw_trajectory_export':False,'user_workspace_mutated':False,
               'old_v32_source_integrated':False}
    save(run/'source_audit_v37.json',discovery)
    names=['tests_v37.txt','fallback_v37.json','observed_study_v37.json','source_audit_v37.json']
    manifest={'version':'v3.7.0','time_utc':now,'code_lineage':'v3.6_companion_plus_strict_original_grade_schema',
              'inherited_previous_source_retained':True,'test_pass':True,
              'data_evidence_label':report['evidence_kind'],'status':report['status'],
              'source_checksums':{str(p.relative_to(ROOT)):digest(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts},
              'report_checksums':{n:digest(run/n) for n in names}}
    save(run/'manifest_v37.json',manifest)
    name=f'UPLOAD_THIS_v37_{now}_{run.name.split("_")[-1]}.zip'
    out=run/name
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
        for n in names+['manifest_v37.json']:z.write(run/n,n)
    print('REGRESSION TESTS: PASS',flush=True)
    print('REAL TRAJECTORIES JOINED:',report['data_provenance'].get('joined_episodes',0),flush=True)
    print('OBSERVED MODEL STATUS:',report['status'],flush=True)
    print('PHYSICAL FIXTURE PARITY:',parity['ail_safe_fallback_operations'],parity['incumbent_operations'],flush=True)
    print('UPLOAD THIS SINGLE RESULTS ZIP:',out,flush=True)
    print('RUN FOLDER:',run,flush=True)
    if '--no-dashboard' not in sys.argv:server(report,parity,discovery,True)
    if sys.platform=='darwin' and '--no-dashboard' not in sys.argv:
        subprocess.Popen(['open','-R',str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return 0
if __name__=='__main__':sys.exit(main())
