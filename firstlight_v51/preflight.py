"""Self-test platform prerequisites before the full inherited regression suite.

Do not substitute a dummy PIL module: actual Pillow is required by inherited
image-admission integration tests and the remote image provider contract.
"""
from __future__ import annotations
import importlib.util, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path


def dependency_status():
    result = {'python':sys.version.split()[0], 'executable':str(Path(sys.executable).resolve()),
              'pillow_installed':False, 'pillow_version':None,
              'ffmpeg_installed':bool(shutil.which('ffmpeg')),
              'ffprobe_installed':bool(shutil.which('ffprobe')),
              'ollama_available':False,'ollama_models':[],
              'firstlight_version':'5.1.0'}
    try:
        from PIL import Image, __version__
        with __import__('io').BytesIO() as f:
            Image.new('RGB',(2,2),'orange').save(f,'PNG')
            assert f.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'
        result['pillow_installed']=True;result['pillow_version']=__version__
    except (ImportError, AssertionError, OSError, ValueError) as e:
        result['pillow_error']=type(e).__name__+': '+str(e)[:180]
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=3) as resp:
            result['ollama_models']=sorted(x['name'] for x in json.load(resp).get('models',[]) if 'name' in x)
            result['ollama_available']=True
    except (OSError,ValueError,KeyError,TimeoutError):pass
    return result


def require_pillow():
    state=dependency_status()
    if not state['pillow_installed']:
        raise RuntimeError('PILLOW_MISSING_IN_ACTIVE_VENV: Pillow is required by inherited image-provider tests; no synthetic substitute is allowed')
    if not state['ffmpeg_installed'] or not state['ffprobe_installed']:
        raise RuntimeError('FFMPEG_FFPROBE_MISSING: inherited real-media regression tests require both')
    return state


def main():
    try:
        state=require_pillow()
    except RuntimeError as e:
        print('PREFLIGHT FAILED:',str(e),flush=True)
        return 2
    print('FIRST LIGHT PREFLIGHT:',json.dumps(state,sort_keys=True),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
