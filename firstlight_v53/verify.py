import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
    p=json.loads((ROOT/'FIRST_LIGHT_V53_SOURCE_SHA256.json').read_text())
    for rel,dig in p['sha256_by_path'].items():
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():raise RuntimeError('V53_FILE_MISSING:'+rel)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=dig:raise RuntimeError('V53_HASH_MISMATCH:'+rel)
    return len(p['sha256_by_path'])
if __name__=='__main__':print('V5.3 INTEGRITY VERIFIED:',verify(),'files')
