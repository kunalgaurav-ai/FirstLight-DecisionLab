#!/usr/bin/env python3
"""Run old regressions + new empirical-calibrator tests + fixture execution + immutable reports."""
from __future__ import annotations
import datetime as dt,hashlib,json,os,subprocess,sys,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v33.benchmark import run_all
from ail_v34.calibration import study
from ail_v34.dashboard import serve


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,sort_keys=True,indent=2);f.write('\n')

def main():
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_id='v34_'+stamp+'_'+uuid.uuid4().hex[:8]
    folder=ROOT/'runs'/run_id;folder.mkdir(parents=True,exist_ok=False)
    print('Immutable execution directory:',folder,flush=True)
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    with (folder/'tests_v34.txt').open('x',encoding='utf-8') as f:
        f.write('COMMAND: python -m unittest discover -s tests -v\nEXIT_CODE: '+str(test.returncode)+'\n'+test.stdout+test.stderr)
    print(test.stdout+test.stderr,flush=True)
    if test.returncode:print('FAIL CLOSED: test failure. Upload tests_v34.txt.',flush=True);return 2
    old=run_all(folder/'executed_cases');old['run_id']=run_id
    save(folder/'results_v33_fixture_reexecution.json',old)
    data_name=os.environ.get('AIL_OBSERVED_DATASET','').strip()
    prov_name=os.environ.get('AIL_DATA_PROVENANCE','').strip()
    if bool(data_name)!=bool(prov_name):
        print('FAIL CLOSED: BOTH dataset and provenance paths required.',flush=True);return 3
    data=Path(data_name).expanduser() if data_name else ROOT/'data/private/observed_checkpoints.jsonl'
    prov=Path(prov_name).expanduser() if prov_name else ROOT/'data/private/dataset_provenance.json'
    if data_name and (not data.is_file() or not prov.is_file()):
        print('FAIL CLOSED: requested observed dataset or provenance not found.',flush=True);return 4
    if data.exists() != prov.exists():
        print('FAIL CLOSED: a local observed dataset and provenance must BOTH exist.',flush=True);return 4
    cal=study(data if data.exists() else None,prov if prov.exists() else None)
    save(folder/'calibration_v34.json',cal)
    audit=json.loads((ROOT/'docs/V33_MAC_RUN_EVIDENCE_AUDIT.json').read_text())
    save(folder/'user_v33_audit.json',audit)
    save(folder/'hmm_gate_v34.json',{'trained':False,'reason':'No qualified multi-sequence benchmark with distinct train/cal/test and approved action decisions','gate':'HOLD_NO_EMPIRICAL_HMM_SUPERIORITY'})
    inputs={'observed_data_supplied':data.is_file(),'provenance_supplied':prov.is_file(),
            'data_is_fixture':False if data.is_file() else None,'external_v32_integrated':False,
            'v33_mac_results_audit_sha256':sha(ROOT/'docs/V33_MAC_RUN_EVIDENCE_AUDIT.json')}
    if data.is_file():inputs['dataset_sha256']=sha(data)
    if prov.is_file():inputs['provenance_sha256']=sha(prov)
    save(folder/'input_inventory_v34.json',inputs)
    reports=['tests_v34.txt','results_v33_fixture_reexecution.json','calibration_v34.json','user_v33_audit.json','hmm_gate_v34.json','input_inventory_v34.json']
    hashes={name:sha(folder/name) for name in reports}
    invariants={'baseline_parity':old['parity_exact_package_sha_across_arms'],
                'no_unauthorized_stage_execution':all(row['stage_ops']==0 for row in old['task_rows'] if row['status']=='BLOCKED_UNAUTHORIZED'),
                'calibration_never_autodeploy':cal['policy_eligible'] is False,
                'no_claimed_causal_effect':cal['causal_intervention_value']=='NOT_IDENTIFIED'}
    manifest={'version':'3.4.0-calibration-lab','run_id':run_id,'status':cal['status'],
              'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*.py')) if 'runs' not in p.parts},
              'report_sha256':hashes,'invariants':invariants,'comparators':'B0_AND_B1_CONSTRUCTED_NOT_EXTERNAL_OSS',
              'quality_evidence':'NONE_NO_INDEPENDENT_APPROVAL', 'commercial_value':'NOT_ESTABLISHED'}
    save(folder/'manifest_v34.json',manifest)
    if not all(invariants.values()):print('FAIL CLOSED: invariants violated',flush=True);return 5
    pack=folder/('UPLOAD_THIS_'+run_id+'.zip')
    with zipfile.ZipFile(pack,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in reports+['manifest_v34.json']:z.write(folder/name,name)
    print('\nCALIBRATION GATE:',cal['status'],flush=True)
    print('Actual independently approved outcomes: NOT OBSERVED',flush=True)
    print('Incremental OSS+AIL economic advantage: NOT ESTABLISHED',flush=True)
    print('\nUPLOAD THIS SINGLE ZIP TO CHATGPT:\n'+str(pack),flush=True)
    print('RESULTS DIRECTORY:\n'+str(folder),flush=True)
    serve(folder/'results_v33_fixture_reexecution.json',folder/'calibration_v34.json',folder/'user_v33_audit.json',True)
    return 0
if __name__=='__main__':sys.exit(main())
