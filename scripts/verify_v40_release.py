#!/usr/bin/env python3
"""Verify every immutable shipped source and retained historical module."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'source_integrity_v40.json').read_text())
for n,exp in m['files'].items():
 p=ROOT/n
 if not p.is_file():raise SystemExit('MISSING_SOURCE:'+n)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=exp:raise SystemExit('SOURCE_MISMATCH:'+n)
print('v4.0 inherited + additive source integrity PASS:',len(m['files']),'files',flush=True)
