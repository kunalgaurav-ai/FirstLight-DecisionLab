"""Additive v5.2 SHA-256 manifest verification; no inherited checks removed."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'FIRST_LIGHT_V52_SOURCE_SHA256.json'

def check():
    content = json.loads(MANIFEST.read_text())
    for relative, expected in content['sha256_by_path'].items():
        path = (ROOT/relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise RuntimeError('V52_MISSING_OR_UNSAFE_PATH:' + relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('V52_SOURCE_SHA256_MISMATCH:' + relative)
    return len(content['sha256_by_path'])

if __name__ == '__main__':
    print('FIRST LIGHT V5.2 INTEGRITY PASS:', check(), 'added files')
