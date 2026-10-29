"""Independent v5.1 additive-source checksum verifier."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'FIRST_LIGHT_V51_SOURCE_SHA256.json'

def check():
    obj=json.loads(MANIFEST.read_text())
    for rel, digest in obj['sha256_by_path'].items():
        p=BASE/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('FIRST_LIGHT_V51_SOURCE_INTEGRITY_FAILED:'+rel)
    return len(obj['sha256_by_path'])
if __name__=='__main__':print(f'FIRST LIGHT v5.1 SOURCE INTEGRITY PASS: {check()} added files')
