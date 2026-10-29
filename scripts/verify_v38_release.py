#!/usr/bin/env python3
"""Fail closed on source tampering; preserve old archived evidence untouched."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<18),b''):h.update(b)
 return h.hexdigest()
def main():
 manifest=json.loads((ROOT/'RELEASE_SHA256_MANIFEST_V38.json').read_text())
 bad=[]
 for rel,digest in manifest['files_sha256'].items():
  p=ROOT/rel
  if not p.is_file() or sha(p)!=digest:bad.append(rel)
 if bad:
  print('INTEGRITY CHECK FAILED:',bad[:10],file=sys.stderr);return 4
 print('v3.8 source integrity PASS:',len(manifest['files_sha256']),'files');return 0
if __name__=='__main__':sys.exit(main())
