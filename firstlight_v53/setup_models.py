"""Explicit opt-in, serial Ollama HTTP model pulls; no PATH assumption and no API keys."""
import argparse
import json
import urllib.error
import urllib.request
from .matrix import DEFAULT_MODELS
from firstlight_v5.runner import ollama_models

BASE='http://127.0.0.1:11434'

def pull(model):
    req=urllib.request.Request(BASE+'/api/pull',
      data=json.dumps({'model':model,'stream':True}).encode(),
      headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=900) as response:
            last=''
            for line in response:
                if not line.strip():continue
                val=json.loads(line)
                if val.get('error'):raise RuntimeError(str(val['error'])[:280])
                status=str(val.get('status',''))
                if status!=last and ('pulling manifest' in status or 'success' in status or 'verifying' in status):
                    print(model,status,flush=True)
                last=status
    except (OSError,ValueError,RuntimeError,urllib.error.URLError) as e:
        print('MODEL_PULL_FAILED',model,str(e)[:350],flush=True)
        return False
    return model in ollama_models()

def run(args=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--install-missing',action='store_true')
    ap.add_argument('--models',default=','.join(DEFAULT_MODELS))
    a=ap.parse_args(args)
    names=[s.strip() for s in a.models.split(',') if s.strip()]
    present=ollama_models()
    missing=[m for m in names if m not in present]
    print('REQUESTED MODEL MATRIX:',', '.join(names),flush=True)
    print('LOCALLY AVAILABLE:',', '.join(sorted(present)) or '(none)',flush=True)
    if not missing:return 0
    if not a.install_missing:
        print('MISSING MODELS:',', '.join(missing))
        print('To download named models, rerun launcher with --install-models (licenses apply).')
        return 2
    for name in missing:
        print('EXPLICIT OPT-IN SERIAL PULL:',name,flush=True)
        if not pull(name):return 2
    if any(m not in ollama_models() for m in names):
        print('MODEL_CONFIRMATION_FAILED');return 2
    print('ALL MATRIX MODELS CONFIRMED');return 0

if __name__=='__main__':raise SystemExit(run())
