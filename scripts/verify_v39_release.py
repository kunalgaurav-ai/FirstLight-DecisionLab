#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_integrity_v39.json').read_text())
for n,expect in manifest['files'].items():
 p=ROOT/n
 if not p.is_file():raise SystemExit('MISSING_SOURCE '+n)
 actual=hashlib.sha256(p.read_bytes()).hexdigest()
 if actual!=expect:raise SystemExit('SOURCE_HASH_MISMATCH '+n)
print('v3.9 source integrity PASS:',len(manifest['files']),'files')
