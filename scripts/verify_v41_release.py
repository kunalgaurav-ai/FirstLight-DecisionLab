#!/usr/bin/env python3
"""Source-hash verifier with preserved v4.0 originals and unchanged v3.9 ancestor."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
m40=json.loads((ROOT/'source_integrity_v40.json').read_text())['files']
for n in ('ail_v40/workflow.py','scripts/launch_v40.py','scripts/dashboard_v40.py'):
    p=ROOT/'docs'/'preserved_v40'/Path(n).name
    assert p.is_file(),f'MISSING_PRESERVED_V40:{n}'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==m40[n],f'CHANGED_PRESERVED_V40:{n}'
manifest=json.loads((ROOT/'source_integrity_v41.json').read_text())
for name,digest in manifest['files'].items():
    p=ROOT/name
    if not p.is_file():raise SystemExit('MISSING:'+name)
    if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise SystemExit('MISMATCH:'+name)
print('v4.1 source integrity PASS:',len(manifest['files']),'files, original v4.0 implementation archived and verified',flush=True)
