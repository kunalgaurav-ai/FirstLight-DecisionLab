"""Curated illustrative visual admission. Never infer actual customer visual accuracy from tags."""
from __future__ import annotations
import hashlib,json,mimetypes,os,subprocess,time,urllib.request
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES=12_000_000

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1<<18),b''):h.update(b)
 return h.hexdigest()

def load_catalog(path):
 d=json.loads(Path(path).read_text())
 a=d.get('assets',[])
 if len(a)!=8 or len({x['asset_id'] for x in a})!=8:raise ValueError('REQUIRES_EIGHT_DISTINCT_VISUAL_ASSETS')
 for r in a:
  if r.get('license')!='CC0_1.0' or r.get('depicts_actual_client') is not False:raise ValueError('INVALID_RIGHTS_OR_CLIENT_MATCH_CLAIM')
  if not r['page'].startswith('https://commons.wikimedia.org/wiki/File:'):raise ValueError('UNAUTHORIZED_ASSET_PAGE')
  if urlparse(r['download_url']).hostname!='commons.wikimedia.org':raise ValueError('UNAUTHORIZED_FETCH_HOST')
 return a

def inspect_image(path):
 p=Path(path)
 if not p.is_file() or p.stat().st_size>MAX_BYTES or p.stat().st_size<1000: return {'admitted':False,'reason':'FILE_MISSING_OR_SIZE_INVALID'}
 with p.open('rb') as f: b=f.read(16)
 if not (b.startswith(b'\xff\xd8\xff') or b.startswith(b'\x89PNG\r\n\x1a\n')):return {'admitted':False,'reason':'NOT_JPEG_OR_PNG'}
 try:
  s=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,codec_name','-of','json',str(p)],capture_output=True,text=True,timeout=15,check=True)
  st=json.loads(s.stdout)['streams'][0];w=int(st['width']);h=int(st['height'])
  if w<480 or h<300:return {'admitted':False,'reason':'LOW_RESOLUTION','width':w,'height':h}
  return {'admitted':True,'reason':'DECODED_IMAGE_DIMENSIONS','width':w,'height':h,'sha256':sha(p),'bytes':p.stat().st_size}
 except Exception as e:return {'admitted':False,'reason':'IMAGE_PROBE_FAILED','error_type':type(e).__name__}

def fetch_one(asset,path,timeout=45):
 u=asset['download_url']
 req=urllib.request.Request(u,headers={'User-Agent':'AIL-v4.0-Research/1.0 (Wikimedia attribution preserved; local demo)','Accept':'image/jpeg,image/png,image/*;q=0.8'})
 tmp=path.with_suffix('.download')
 try:
  with urllib.request.urlopen(req,timeout=timeout) as resp, tmp.open('wb') as w:
   if not resp.geturl().startswith('https://') or urlparse(resp.geturl()).hostname not in ('upload.wikimedia.org','commons.wikimedia.org'):
    raise ValueError('UNEXPECTED_DOWNLOAD_REDIRECT')
   typ=resp.headers.get('Content-Type','')
   if not typ.lower().startswith('image/'):raise ValueError('NON_IMAGE_RESPONSE')
   count=0
   while True:
    b=resp.read(1<<16)
    if not b:break
    count+=len(b)
    if count>MAX_BYTES:raise ValueError('TOO_LARGE')
    w.write(b)
  tmp.replace(path)
  return {'downloaded':True}
 except Exception as e:
  tmp.unlink(missing_ok=True)
  return {'downloaded':False,'reason':'FETCH_FAILED','error_type':type(e).__name__,'message':str(e)[:160]}

def prepare_assets(catalog,asset_root,fetch=False):
 root=Path(asset_root);root.mkdir(parents=True,exist_ok=True)
 rows=[]
 for a in catalog:
  p=root/a['filename']
  fetch_result={'downloaded':False,'reason':'EXISTING_LOCAL_ONLY'}
  if not p.is_file() and fetch:
   t0=time.perf_counter();fetch_result=fetch_one(a,p);fetch_result['elapsed_s']=round(time.perf_counter()-t0,4)
  check=inspect_image(p)
  sidecar=p.with_suffix('.source.json')
  if fetch_result.get('downloaded') and check['admitted']:
   sidecar.write_text(json.dumps({'sha256':check['sha256'],'download_url':a['download_url'],'asset_id':a['asset_id'],'page':a['page'],'license_reported_by_page':a['license']},indent=2)+'\n')
  sourced=False
  if sidecar.exists() and check.get('admitted'):
   try:
    meta=json.loads(sidecar.read_text())
    sourced=(meta.get('sha256')==check['sha256'] and meta.get('download_url')==a['download_url'] and meta.get('asset_id')==a['asset_id'])
   except (ValueError,KeyError):pass
  check['provenance_sidecar_match']=sourced
  rows.append({**a,'local_path':str(p),'fetch':fetch_result,'inspection':check,'status':'READY_ILLUSTRATIVE_ONLY' if check['admitted'] and sourced else 'BLOCKED_ASSET_PROVENANCE_OR_IMAGE'})
 return rows

def task_assets(rows,task):
 a=[r for r in rows if r['task_id']==task]
 if len(a)!=2 or any(x['status']!='READY_ILLUSTRATIVE_ONLY' for x in a):return None
 if len({x['inspection']['sha256'] for x in a})!=2: return None
 return a
