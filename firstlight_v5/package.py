"""Evidence bundle with canonical manifest. Never write over raw observations."""
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from .dashboard import csv_report
from .core import json_dump,sha

def pack(run):
    run=Path(run).resolve();run.mkdir(parents=True,exist_ok=True)
    want=['benchmark_results.json','error_report.json','official_data/SOURCE_PROVENANCE.json',
          'source_integrity.txt','regression_tests.txt']
    raw={}
    for f in want:
        p=run/f
        if p.is_file(): raw[f]=p.read_bytes()
    raw['results.csv']=csv_report(run)
    manifest={'brand':'First Light','version':'5.0.0','evidence_kind':'OFFICIAL_SOURCE_LOCAL_DIAGNOSTIC_PILOT',
              'not_official_leaderboard':True,'not_verified_customer_dollars':True,
              'sha256_by_path':{n:sha(d) for n,d in raw.items()}}
    raw['EVIDENCE_MANIFEST.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    archive=run/f'UPLOAD_THIS_FIRST_LIGHT_V5_{run.name}.zip'
    tmp=archive.with_suffix('.zip.part')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for key,blob in sorted(raw.items()): z.writestr(key,blob)
    tmp.replace(archive)
    with zipfile.ZipFile(archive) as z:
        for n,dig in manifest['sha256_by_path'].items():
            if sha(z.read(n))!=dig: raise ValueError('EVIDENCE_ZIP_FAILED_SELF_VERIFY')
    print('UPLOAD RESULTS ZIP:',archive,flush=True)
    return archive

if __name__=='__main__': pack(sys.argv[1])
