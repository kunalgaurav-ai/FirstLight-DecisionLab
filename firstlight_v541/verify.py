"""Verify additive v5.4.1 files and archived inherited manifests."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent.parent

def verify():
    manifest=json.loads((ROOT/'FIRST_LIGHT_V541_SOURCE_SHA256.json').read_text())
    if not manifest.get('inherits_preserved_v54'):raise ValueError('PRESERVED_V54_NOT_DECLARED')
    for p,expected in manifest['sha256_by_path'].items():
        path=(ROOT/p).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():raise ValueError('MISSING_V541_SOURCE:'+p)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('CORRUPT_V541_SOURCE:'+p)
    from firstlight_v54.verify import verify as previous_verify
    previous_verify()
    return len(manifest['sha256_by_path'])

if __name__=='__main__':print('v5.4.1 additive manifest PASS:',verify())
