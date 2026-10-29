"""Verifies immutable additive research branch; old manifests verified separately."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent

def verify():
 m=json.loads((ROOT/'FIRSTLIGHT_DECISION_SHA256.json').read_text())
 for rel,digest in m['sha256_by_path'].items():
  p=ROOT/rel
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
   raise RuntimeError('DECISION_SOURCE_TAMPER:'+rel)
 return len(m['sha256_by_path'])
if __name__=='__main__':print('ADDITIVE DECISION SOURCE INTEGRITY: PASS',verify())
