"""Verify v4.4 code and source provenance without rewriting any release files."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
manifest=ROOT/'RELEASE_SHA256_MANIFEST_V44.json'
if not manifest.is_file():raise SystemExit('SOURCE_MANIFEST_MISSING')
source=json.loads(manifest.read_text())
errors=[]
for item in source['files']:
    p=(ROOT/item['path']).resolve()
    if not p.is_relative_to(ROOT.resolve()) or not p.is_file():errors.append('MISSING:'+item['path']);continue
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:errors.append('CHANGED:'+item['path'])
if errors:
    print('v4.4 source integrity FAIL:',errors[:20]);sys.exit(1)
print('v4.4 source integrity PASS:',len(source['files']),'source files, inherited versions preserved')
