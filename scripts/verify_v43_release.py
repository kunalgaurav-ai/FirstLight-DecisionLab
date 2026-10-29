#!/usr/bin/env python3
"""Verify shipped source bytes; never include generated model outputs, venvs or caches."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'RELEASE_SHA256_MANIFEST_V43.json'
if not source.exists():raise SystemExit('Missing release manifest V43')
m=json.loads(source.read_text())
problems=[]
for rel,sha in m['tracked_sha256'].items():
    path=(ROOT/rel).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():problems.append('MISSING:'+rel);continue
    got=hashlib.sha256(path.read_bytes()).hexdigest()
    if got!=sha:problems.append('CHANGED:'+rel)
if problems:raise SystemExit('v4.3 source integrity FAIL: '+'; '.join(problems[:15]))
print('v4.3 source integrity PASS:',len(m['tracked_sha256']),'files; added code and inherited source verified')
