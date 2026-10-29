"""Release manifest verifier independent of mutable results outputs."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def verify():
    state=json.loads((ROOT/'FIRST_LIGHT_V54_SOURCE_SHA256.json').read_text())
    for rel,digest in state['sha256_by_path'].items():
        f=(ROOT/rel).resolve()
        if not f.is_relative_to(ROOT.resolve()) or not f.is_file():raise ValueError('SOURCE_FILE_MISSING:'+rel)
        if hashlib.sha256(f.read_bytes()).hexdigest()!=digest:raise ValueError('SOURCE_HASH_MISMATCH:'+rel)
    return len(state['sha256_by_path'])
if __name__=='__main__':print('FIRST LIGHT v5.4 SOURCE INTEGRITY PASS',verify(),'files')
