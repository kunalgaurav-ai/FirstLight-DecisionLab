"""Verify this additive release without rewriting inherited raw source manifests."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];manifest=root/'RELEASE_SHA256_MANIFEST_V46.json'
if not manifest.is_file():raise SystemExit('V46_MANIFEST_MISSING')
obj=json.loads(manifest.read_text());errs=[]
for r in obj['files']:
 p=(root/r['path']).resolve()
 if not p.is_relative_to(root.resolve()) or not p.is_file():errs.append('MISSING '+r['path']);continue
 if p.stat().st_size!=r['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errs.append('CORRUPT '+r['path'])
if errs:print('V46_INTEGRITY_FAIL',errs[:20]);sys.exit(1)
print('V46_SOURCE_INTEGRITY_PASS',len(obj['files']),'tracked files; inherited source unchanged')
