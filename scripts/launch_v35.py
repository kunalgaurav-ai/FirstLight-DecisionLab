#!/usr/bin/env python3
"""Statistical/economic research harness, never deploys experimental decisions.

Never scans user's folders or initiates paid calls. User supplies optional files
through environment variables, never raw payloads into upload ZIP.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v34.calibration import study
from ail_v35.examples import fixture,unsupported_action
from ail_v35.opportunity import assess_workflow,screen_action
from ail_v35.dashboard import serve


def hashfile(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda:f.read(2**18),b''):h.update(part)
    return h.hexdigest()


def save(p:Path,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')


def reference_data():
    zpath=ROOT/'evidence/archive/UPLOAD_THIS_v34_20261025T013125Z_26c53846.zip'
    with zipfile.ZipFile(zpath) as z:
        old=json.loads(z.read('results_v33_fixture_reexecution.json'))
        cal=json.loads(z.read('calibration_v34.json'))
        audit=json.loads(z.read('user_v33_audit.json'))
    return old,cal,audit,zpath


def main():
    folder=ROOT/'runs'/('v35_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True,exist_ok=False)
    proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,text=True,capture_output=True)
    (folder/'tests_v35.txt').write_text('COMMAND: python -m unittest discover -s tests -v\nEXIT_CODE: '+str(proc.returncode)+'\n'+proc.stdout+proc.stderr,encoding='utf-8')
    print(proc.stdout+proc.stderr,flush=True)
    if proc.returncode:
        print('TESTS FAILED. UPLOAD LOG:',folder/'tests_v35.txt',flush=True);return 2
    ref,refcal,audit,refpath=reference_data()
    a=os.environ.get('AIL_OBSERVED_DATASET','').strip();b=os.environ.get('AIL_DATA_PROVENANCE','').strip()
    if bool(a)!=bool(b):print('FAIL CLOSED: supply both observed dataset AND provenance',flush=True);return 3
    data=Path(a).expanduser() if a else None
    prov=Path(b).expanduser() if b else None
    if a and (not data.is_file() or not prov.is_file()):
        print('FAIL CLOSED: observed dataset/provenance missing',flush=True);return 4
    cal=study(data,prov)
    save(folder/'calibration_v35.json',cal)
    graph_path=os.environ.get('AIL_ECON_GRAPH','').strip()
    if graph_path:
        p=Path(graph_path).expanduser()
        if not p.is_file():print('FAIL CLOSED: AIL_ECON_GRAPH file missing',flush=True);return 5
        graph=json.loads(p.read_text(encoding='utf-8'))
        if graph.get('evidence_class')=='OBSERVED_STAGE_RECEIPTS' and not graph.get('consent_or_permitted_use',False):
            print('FAIL CLOSED: observed graph lacks permission declaration',flush=True);return 6
        graph_source='USER_SUPPLIED_GRAPH_PROVENANCE_SELF_DECLARED_NOT_EXTERNALLY_AUDITED'
    else:
        graph=fixture();graph_source='CONSTRUCTED_REGRESSION_EXAMPLE_ONLY'
    opportunity=assess_workflow(graph)
    act=screen_action(unsupported_action(),opportunity['checkpoints'][0])
    edge={'version':'v3.5.0-edge-research','evidence_kind':graph['evidence_class'],
          'status':'HOLD_NO_CAUSAL_INTERVENTION_EVIDENCE', 'commercial_advantage':'NOT_ESTABLISHED',
          'trained_new_model':False, 'deployed_interventions':0,
          'independent_approvals':'NOT_MEASURED', 'prospective_causal_effect':'NOT_IDENTIFIED',
          'policy_coverage':'NONE_SHADOW_ONLY','graph_source':graph_source,
          'opportunity':opportunity,'scenario_screen':act,
          'blocked_inputs':['strongest_OS S competitor live comparative runs'.replace('OS S','OSS'),
                            'action-specific independent treatment/control outcomes','independently approved finished workflows',
                            'actual customer stage cost receipts','sanctioned multimodal calibration cohorts'],
          'data_permission_verified_externally':False}
    if graph_path:edge['graph_input_sha256']=hashfile(Path(graph_path).expanduser())
    save(folder/'opportunity_v35.json',edge)
    provenance={'version':'v3.5.0','prior_user_v34_report_sha256':hashfile(refpath),
                'source_v32_integrated':False,'reference_v34_mac_calibration_status':refcal['status'],
                'historical_competent_baseline_25_vs_v33_ail_28_operations':True,
                'observed_calibration_supplied':bool(a), 'observed_graph_supplied':bool(graph_path),
                'source_reuse':'preserved v3.4 code + archived v3.4 Mac report'}
    if a:
        provenance['observed_dataset_sha256']=hashfile(data)
        provenance['observed_provenance_sha256']=hashfile(prov)
    save(folder/'input_provenance_v35.json',provenance)
    reportfiles=['tests_v35.txt','calibration_v35.json','opportunity_v35.json','input_provenance_v35.json']
    checks={'source_python_sha256':{str(p.relative_to(ROOT)):hashfile(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts},
            'input_reference_v34_sha256':hashfile(refpath),
            'report_sha256':{r:hashfile(folder/r) for r in reportfiles},
            'quality_acceptance_gate':'HOLD', 'causal_effect_gate':'HOLD', 'commercial_incrementality_gate':'HOLD',
            'local_tests_passed':True,'baseline_only_fixture_reference':True,
            'no_pretend_empirical_training':cal['status'].startswith('HOLD') if not a else cal['policy_eligible'] is False}
    if not checks['no_pretend_empirical_training']:raise AssertionError('calibration proof gate failed')
    save(folder/'manifest_v35.json',checks)
    zipped=folder/('UPLOAD_THIS_'+folder.name+'.zip')
    with zipfile.ZipFile(zipped,'x',zipfile.ZIP_DEFLATED) as z:
        for f in reportfiles+['manifest_v35.json']:z.write(folder/f,f)
    print('CALIBRATION:',cal['status'],flush=True)
    print('OPPORTUNITY:',edge['status'],flush=True)
    print('\nUPLOAD THIS RESULTS ZIP:',zipped,flush=True)
    print('RESULTS DIRECTORY:',folder,flush=True)
    serve(ref,cal,audit,edge,True)
    return 0
if __name__=='__main__':sys.exit(main())
