#!/usr/bin/env python3
"""One launcher: frozen tests, local physical parity experiment, historical graded traces.

Uses local user-owned public trajectories only; exports aggregates/schema/hashes,
never exports raw prompts, commands or local customer material.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,uuid,zipfile,html
from datetime import datetime,timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v36.trajectories import load_episodes,study,sha
from ail_v36.fallback import fixture_parity
from ail_v35.dashboard import HTML as OLD_HTML
from ail_v35.opportunity import assess_workflow,screen_action
from ail_v35.examples import fixture,unsupported_action
from ail_v34.calibration import study as legacy_calibration

SUBMISSION='20260901_mini-v2.4.2_gemini-3-5-flash'

def save(path,obj):
    with path.open('x',encoding='utf-8') as f:
        json.dump(obj,f,sort_keys=True,indent=2)
        f.write('\n')

def source_candidates():
    manual=os.environ.get('AIL_V36_TRACE_DIR','').strip()
    manualgrade=os.environ.get('AIL_V36_GRADE_FILE','').strip()
    if bool(manual)!=bool(manualgrade):
        raise ValueError('AIL_V36_TRACE_DIR and AIL_V36_GRADE_FILE must be supplied together')
    if manual:
        return Path(manual).expanduser(),Path(manualgrade).expanduser(),'EXPLICIT_LOCAL_INPUT'
    base=Path.home()/'Downloads'/'agent-intelligence-lab-rigorous'/'data'
    dirs=[base/'rich_traces',base/'rich_traces'/'trajectories']
    grades=[base/'token_waste_labeled_calls.jsonl',base/'official_grades.jsonl',base/'official_grades.json']
    for d in dirs:
        for g in grades:
            if d.is_dir() and g.is_file():return d,g,'DISCOVERED_PREVIOUS_AIL_LOCAL_WORKSPACE'
    return None,None,'NO_MATCHING_TRACES_AND_OFFICIAL_GRADES_IN_STANDARD_WORKSPACE'

def sample_schema(grade_path):
    if not grade_path or not grade_path.is_file():return None
    try:
        p=grade_path
        with p.open('r',encoding='utf-8') as f:
            txt=f.readline() if p.suffix=='.jsonl' else f.read(16000)
        x=json.loads(txt)
        if isinstance(x,dict):return {'first_record_field_names':sorted(x.keys()),'source_sha256':sha(p)}
        if isinstance(x,list) and x and isinstance(x[0],dict):return {'first_record_field_names':sorted(x[0].keys()),'source_sha256':sha(p)}
    except (OSError,ValueError,UnicodeDecodeError):pass
    return {'first_record_field_names':'UNREADABLE_OR_UNSUPPORTED','source_sha256':sha(p)}

def dashboard(cal,fall,discovery,open_browser=True):
    section='''<section id="v36"><h2>v3.6 | Observed agent trajectories and baseline parity</h2><p>Historical agent grades are observational. No policy intervention savings are identifiable from this test. Existing v3.3–v3.5 dashboards are retained.</p><pre id="v36summary"></pre><pre id="v36details"></pre></section>'''
    script='''<script>fetch('/api/v36').then(r=>r.json()).then(x=>{document.querySelector('#v36summary').textContent=JSON.stringify({trace_status:x.trajectory.status,episode_count:x.trajectory.joined_episodes,competent_baseline_operations:x.fallback.incumbent_operations,ail_fallback_operations:x.fallback.ail_safe_fallback_operations,baseline_parity:x.fallback.baseline_parity},null,2);document.querySelector('#v36details').textContent=JSON.stringify(x.trajectory.landmarks||[],null,2);});</script>'''
    page=OLD_HTML.replace('</main>',section+'</main>').replace('</body>',script+'</body>')
    reference=ROOT/'evidence/archive/UPLOAD_THIS_v34_20261025T013125Z_26c53846.zip'
    with zipfile.ZipFile(reference) as z:
        old_report=json.loads(z.read('results_v33_fixture_reexecution.json'))
        old_calibration=json.loads(z.read('calibration_v34.json'))
        old_audit=json.loads(z.read('user_v33_audit.json'))
    opportunity={'version':'v3.6-retained-v35-example','status':'HOLD_CONSTRUCTED_ECONOMIC_GRAPH',
                 'commercial_advantage':'NOT_ESTABLISHED','trained_new_model':False,
                 'opportunity':assess_workflow(fixture()),
                 'scenario_screen':screen_action(unsupported_action(),assess_workflow(fixture())['checkpoints'][0]),
                 'prospective_causal_effect':'NOT_IDENTIFIED','policy_coverage':'SHADOW_ONLY'}
    contents={'/api/v36':{'trajectory':cal,'fallback':fall,'discovery':discovery},
              '/api/trajectory':cal,'/api/fallback':fall,
              '/api/report':old_report,'/api/calibration':old_calibration,
              '/api/user-v33-audit':old_audit,'/api/edge':opportunity}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/index.html'):data=page.encode('utf-8');ctype='text/html; charset=utf-8'
            elif self.path in contents:data=json.dumps(contents[self.path]).encode();ctype='application/json'
            else:self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type',ctype)
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def log_message(self,fmt,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url='http://127.0.0.1:'+str(server.server_port)+'/'
    print('DASHBOARD:',url,flush=True)
    if open_browser:
        if sys.platform=='darwin':subprocess.Popen(['open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:
            import webbrowser
            webbrowser.open(url)
    print('Ctrl+C stops dashboard. Reports ZIP already saved.',flush=True)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()

def main():
    now=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run=ROOT/'runs'/('v36_'+now+'_'+uuid.uuid4().hex[:8])
    run.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-v']
    test=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (run/'tests_v36.txt').write_text('COMMAND: '+repr(cmd)+'\nEXIT: '+str(test.returncode)+'\n'+test.stdout+test.stderr,encoding='utf-8')
    if test.returncode:
        print('TEST FAILURE - LOG:',run/'tests_v36.txt',flush=True)
        return 2
    print('TESTS PASS:',test.stderr.split('Ran ')[-1].splitlines()[0].strip(),flush=True)
    fallback=fixture_parity(run/'local_fixture_artifacts')
    save(run/'fallback_v36.json',fallback)
    if not fallback['baseline_parity']:raise RuntimeError('Known 28-versus-25 regression not eliminated')
    try:
        tr,gd,source=source_candidates()
        if tr:
            if not tr.is_dir() or not gd.is_file():raise ValueError('Explicit observed trace/grade files missing')
            episode,info=load_episodes(tr,gd,SUBMISSION)
            report=study(episode,info)
        else:
            info={'status':'NO_LOCAL_DATA_PATH_FOUND'}
            report=study([],info)
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        source='INPUT_FORMAT_OR_IDENTITY_BLOCKED'
        info={'status':'UNUSABLE_TRACE_DATA','reason':str(exc)[:500]}
        report=study([],info)
    discovery={'version':'v3.6','source_lookup':source,'input_inventory':info,
               'grade_schema':sample_schema(gd) if 'gd' in locals() else None,
               'v32_source_archive_merged':False,
               'purpose':'ACTUAL_GRADED_AGENT_TRAJECTORY_PREDICTION_AND_INCUMBENT_PARITY',
               'data_never_exported':'RAW_PROMPTS_COMMANDS_TRAJECTORIES_NOT_INCLUDED_IN_RESULTS_ZIP'}
    save(run/'trace_study_v36.json',report)
    save(run/'source_discovery_v36.json',discovery)
    report_names=['tests_v36.txt','fallback_v36.json','trace_study_v36.json','source_discovery_v36.json']
    manifest={'version':'v3.6.0','utc_created':now,'test_pass':True,'baseline_fixture_parity':True,
              'trace_status':report['status'],'grade_source':source,
              'source_module_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts},
              'reports_sha256':{n:sha(run/n) for n in report_names},
              'scope':'HISTORICAL_PREDICTION_PLUS_CONSTRUCTED_FALLBACK_PARITY_NOT_CAUSAL_CUSTOMER_SAVINGS'}
    save(run/'manifest_v36.json',manifest)
    upload=run/('UPLOAD_THIS_'+run.name+'.zip')
    with zipfile.ZipFile(upload,'x',zipfile.ZIP_DEFLATED) as zipf:
        for name in report_names+['manifest_v36.json']:zipf.write(run/name,arcname=name)
    print('COMPETENT BASELINE PARITY:',fallback['incumbent_operations'],fallback['ail_safe_fallback_operations'])
    print('OBSERVED TRAJECTORY STATUS:',report['status'])
    print('TRAJECTORIES MATCHED:',report.get('joined_episodes',0))
    print('UPLOAD THIS RESULTS ZIP:',upload,flush=True)
    print('RUN REPORT DIRECTORY:',run,flush=True)
    if '--no-dashboard' not in sys.argv:dashboard(report,fallback,discovery,True)
    return 0
if __name__=='__main__':sys.exit(main())
