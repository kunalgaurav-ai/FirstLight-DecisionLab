#!/usr/bin/env python3
"""Independent digest audit for the full v4.2 inherited+additive tree."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'source_integrity_v42.json').read_text())
for name,expected in d['files'].items():
 p=root/name
 if not p.is_file():raise SystemExit('MISSING_V42_SOURCE:'+name)
 observed=hashlib.sha256(p.read_bytes()).hexdigest()
 if observed!=expected:raise SystemExit('CHANGED_V42_SOURCE:'+name)
print('v4.2 complete source integrity PASS:',len(d['files']),'files',flush=True)
