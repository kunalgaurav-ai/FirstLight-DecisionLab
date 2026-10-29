#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'RELEASE_SHA256_MANIFEST_V431.json').read_text())
fail=[]
for obj in manifest['files']:
 p=root/obj['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=obj['sha256']:fail.append(obj['path'])
if fail:sys.exit('v4.3.1 source integrity FAIL: '+', '.join(fail[:20]))
print('v4.3.1 source integrity PASS:',len(manifest['files']),'source files')
