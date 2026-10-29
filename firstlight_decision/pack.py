"""Hash-verifiable result archive, no overwrite of original user benchmarks."""
from __future__ import annotations
import hashlib,json,pathlib,zipfile,sys

def hash_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def pack(path):
 p=pathlib.Path(path).resolve()
 if not (p/'results.json').is_file():raise RuntimeError('MISSING_RESULTS')
 paths=sorted(f for f in p.rglob('*') if f.is_file() and not f.name.startswith('UPLOAD_THIS_') and f.name!='EVIDENCE_SHA256_MANIFEST.json' and f.stat().st_size<20_000_000)
 hashes={f.relative_to(p).as_posix():hash_file(f) for f in paths}
 m=p/'EVIDENCE_SHA256_MANIFEST.json'
 m.write_text(json.dumps({'evidence_scope':'FIRST_LIGHT_RESEARCH_NO_COMMERCIAL_CLAIMS','sha256_by_path':hashes},indent=2)+'\n')
 dest=p/'UPLOAD_THIS_FIRSTLIGHT_DECISION.zip'
 if dest.exists():raise RuntimeError('NO_OVERWRITE_EXISTING_EVIDENCE')
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for f in paths+[m]:z.write(f,f.relative_to(p).as_posix())
 verify(dest)
 return dest

def verify(path):
 with zipfile.ZipFile(path) as z:
  m=json.loads(z.read('EVIDENCE_SHA256_MANIFEST.json'))
  for k,v in m['sha256_by_path'].items():
   if hashlib.sha256(z.read(k)).hexdigest()!=v:raise ValueError('HASH_MISMATCH:'+k)
 return True

if __name__=='__main__':print('UPLOAD THIS FIRST LIGHT DECISION ZIP:',pack(sys.argv[1]))
