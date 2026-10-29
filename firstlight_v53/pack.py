"""Self-verifying, immutable v5.3 experiment bundle."""
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()

def pack(run):
    root=Path(run).resolve()
    if not (root/'matrix_results.json').is_file():raise ValueError('REPORT_ABSENT')
    paths=('matrix_results.json','matrix_rows.csv','error_report_v53.json',
          'official_data/SOURCE_PROVENANCE.json','regression_tests.txt',
          'source_integrity.txt','model_setup.txt')
    raw={k:(root/k).read_bytes() for k in paths if (root/k).is_file()}
    # Embed immutable historical metadata but never alter or relabel raw evidence.
    manifest={'version':'First Light 5.3','data_type':'LOCAL_MULTI_MODEL_UNOFFICIAL_BFCL_DIAGNOSTIC',
          'official_leaderboard_grade':False,'customer_cost_claim':False,
          'sha256_by_path':{k:sha(v) for k,v in raw.items()}}
    raw['EVIDENCE_MANIFEST.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    out=root/f'UPLOAD_THIS_FIRSTLIGHT_V53_{root.name}.zip'
    tmp=out.with_suffix('.part')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in sorted(raw.items()):z.writestr(k,v)
    tmp.replace(out)
    with zipfile.ZipFile(out) as z:
        for k,dig in manifest['sha256_by_path'].items():
            if sha(z.read(k))!=dig:raise ValueError('EVIDENCE_ZIP_BAD_SHA')
    print('UPLOAD THIS FIRST LIGHT MULTI-MODEL RESULTS ZIP:',out,flush=True)
    return out
if __name__=='__main__':pack(sys.argv[1])
