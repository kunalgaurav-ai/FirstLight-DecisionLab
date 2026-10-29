"""Fail-closed experiment evidence packaging with per-file content hashes."""
import hashlib,json,sys,zipfile
from pathlib import Path

def digest(blob):return hashlib.sha256(blob).hexdigest()
def package(path):
    root=Path(path).resolve()
    if not (root/'results_v54.json').is_file():raise ValueError('MISSING_BENCHMARK_RESULT')
    candidates=['results_v54.json','holdout_rows_v54.csv','early_warning_v54.json',
        'trace_prefix_results_v54.json','source_integrity.txt','regression_tests.txt',
        'preflight.txt','models.txt','official_data/SOURCE_PROVENANCE.json',
        'official_data/BFCL_v4_simple_python.json','official_data/BFCL_v4_multiple.json',
        'official_data/possible_answer/BFCL_v4_simple_python.json','official_data/possible_answer/BFCL_v4_multiple.json']
    blob={k:(root/k).read_bytes() for k in candidates if (root/k).is_file()}
    manifest={'version':'5.4.0','kind':'FIRST_LIGHT_PUBLIC_BFCL_LOCAL_DIAGNOSTIC',
        'not_official_leaderboard':True,'no_verified_usd_or_customer_acceptance':True,
        'sha256_by_file':{k:digest(v) for k,v in blob.items()}}
    blob['EVIDENCE_MANIFEST.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    output=root/f'UPLOAD_THIS_FIRSTLIGHT_V54_{root.name}.zip';temp=output.with_suffix('.part')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in sorted(blob.items()):z.writestr(k,v)
    temp.replace(output)
    with zipfile.ZipFile(output) as z:
        for k,v in manifest['sha256_by_file'].items():
            if digest(z.read(k))!=v:raise ValueError('ZIP_DATA_CORRUPTED')
    print('UPLOAD THIS FIRST LIGHT RESULTS ZIP:',output,flush=True)
    return output
if __name__=='__main__':package(sys.argv[1])
