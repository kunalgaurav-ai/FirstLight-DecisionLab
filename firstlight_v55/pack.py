"""Immutable SHA-checked evidence bundle; excludes virtualenv and git metadata."""
import datetime as dt,hashlib,json,pathlib,zipfile

def sha(b):return hashlib.sha256(b).hexdigest()

def pack(run):
    run=pathlib.Path(run).resolve()
    if not (run/'results.json').is_file():raise ValueError('EVIDENCE_REPORT_MISSING')
    relative=[]
    for p in run.rglob('*'):
        if not p.is_file() or '.git' in p.relative_to(run).parts:continue
        if p.name.startswith('UPLOAD_THIS_') or p.name=='EVIDENCE_SHA256_MANIFEST.json':continue
        if p.stat().st_size>10_000_000:continue
        relative.append(p.relative_to(run).as_posix())
    manifest={'version':'5.5.0','evidence_type':'LOCAL_RESEARCH_NOT_COMMERCIAL','sha256_by_path':{rel:sha((run/rel).read_bytes()) for rel in sorted(relative)}}
    manifest_path=run/'EVIDENCE_SHA256_MANIFEST.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    z=run/f'UPLOAD_THIS_FIRSTLIGHT_V55_{run.name}.zip'
    if z.exists():raise ValueError('UPLOAD_ARCHIVE_ALREADY_EXISTS_NO_OVERWRITE')
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as out:
        for rel in sorted(relative)+[manifest_path.name]:out.write(run/rel,arcname=rel)
    check(z)
    return z

def check(path):
    with zipfile.ZipFile(path) as f:
        m=json.loads(f.read('EVIDENCE_SHA256_MANIFEST.json'))
        if not m['sha256_by_path']:raise ValueError('EMPTY_EVIDENCE_MANIFEST')
        for name,digest in m['sha256_by_path'].items():
            if sha(f.read(name))!=digest:raise ValueError('EVIDENCE_HASH_MISMATCH:'+name)
    return True

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('run');arg=parser.parse_args()
    print('EVIDENCE_ZIP_VERIFIED:',pack(arg.run))
