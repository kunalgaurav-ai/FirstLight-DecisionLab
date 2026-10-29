"""Verify new First Light v5 source and preserved historical inputs; inherited v4.6 has own manifest."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'FIRST_LIGHT_RELEASE_SHA256.json'
if not p.is_file():raise SystemExit('FIRST_LIGHT_V5_MANIFEST_MISSING')
m=json.loads(p.read_text())
errors=[]
for x in m['files']:
 f=(root/x['path']).resolve()
 if not f.is_relative_to(root.resolve()) or not f.is_file(): errors.append('MISSING '+x['path']);continue
 b=f.read_bytes()
 if len(b)!=x['bytes'] or hashlib.sha256(b).hexdigest()!=x['sha256']:errors.append('CORRUPT '+x['path'])
if errors:raise SystemExit('FIRST_LIGHT_V5_MANIFEST_FAILED: '+str(errors[:10]))
print('FIRST_LIGHT_V5_MANIFEST_PASS',len(m['files']),'new tracked files')
