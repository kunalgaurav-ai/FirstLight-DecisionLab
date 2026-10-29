"""Additive integrity verification; v5.5 and all ancestors remain unchanged."""
from __future__ import annotations
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent

def verify():
    from firstlight_v55.verify import check
    inherited=check()
    manifest=json.loads((ROOT/'FIRST_LIGHT_V551_SOURCE_SHA256.json').read_text())
    if manifest.get('inherited_release')!='v5.5.0':raise ValueError('V551_PARENT_RELEASE_MISMATCH')
    for rel,expected in manifest['sha256_by_path'].items():
        path=(ROOT/rel).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():raise ValueError('V551_MISSING_FILE:'+rel)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('V551_FILE_HASH_MISMATCH:'+rel)
    return {'inherited':inherited,'v551_files_verified':len(manifest['sha256_by_path'])}
if __name__=='__main__':print('FIRST LIGHT v5.5.1 INTEGRITY:',verify())
