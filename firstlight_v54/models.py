"""Explicit opt-in to local model pulls. No remote paid model usage."""
import argparse,json,shutil
from .experiment import CANDIDATES
from firstlight_v5.runner import ollama_models
from firstlight_v53.setup_models import pull

def setup(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--install-missing',action='store_true')
    ap.add_argument('--models',default='all')
    args=ap.parse_args(argv)
    requested=list(CANDIDATES) if args.models=='all' else list(dict.fromkeys(x.strip() for x in args.models.split(',') if x.strip()))
    if any(x not in CANDIDATES for x in requested) or not requested:raise ValueError('UNREGISTERED_MODEL')
    installed=ollama_models()
    missing=[x for x in requested if x not in installed]
    print('FIRST LIGHT 11-MODEL REGISTRY:',','.join(CANDIDATES),flush=True)
    print('MISSING FROM OLLAMA:',','.join(missing) or 'none',flush=True)
    if not args.install_missing:
        print('NO MODEL DOWNLOADS WITHOUT --install-models; run installed subset only',flush=True)
        return 0
    disk=shutil.disk_usage(__import__('pathlib').Path.home()).free
    if disk<12_000_000_000:
        print('DOWNLOAD_BLOCKED_LOW_DISK_FREE_BYTES:',disk, 'need >=12 GB safety headroom',flush=True)
        return 2
    for model in missing:
        print('AUTHORIZED MODEL PULL (SERIAL):',model,flush=True)
        if not pull(model):
            print('STOP_MODEL_PULL_FAILED_NOT_SILENTLY_SKIPPING',model,flush=True)
            return 3
    print('ALL REQUESTED OLLAMA MODELS CONFIRMED',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(setup())
