"""v4.5 code integrity; older source verified by its own manifest/utility."""
import json,hashlib,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
m=root/'RELEASE_SHA256_MANIFEST_V45.json'
if not m.exists():raise SystemExit('V45_MANIFEST_MISSING')
j=json.loads(m.read_text());errs=[]
for rec in j['files']:
 p=(root/rec['path']).resolve()
 if not p.is_relative_to(root.resolve()) or not p.is_file():errs.append('MISSING:'+rec['path']);continue
 if hashlib.sha256(p.read_bytes()).hexdigest()!=rec['sha256']:errs.append('CHANGED:'+rec['path'])
if errs:print('V45_SOURCE_INTEGRITY_FAILED',errs[:15]);sys.exit(1)
print('V45_SOURCE_INTEGRITY_PASS:',len(j['files']),'tracked files, original v44 unchanged')
