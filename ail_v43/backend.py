"""Official Lightricks/LTX-2.5 Hugging Face Space API. No model mock or silent fallback."""
from __future__ import annotations
import os, time, shutil
from pathlib import Path
from .engine import SPACE, MODEL

class GenerationUnavailable(RuntimeError): pass

def unwrap_video(result):
    """Extract only a Gradio-downloaded *local* file from API results."""
    head=result[0] if isinstance(result,(tuple,list)) and result else result
    if isinstance(head,dict):
        if isinstance(head.get('video'),(dict,str)):head=head['video']
        if isinstance(head,dict):head=head.get('path') or head.get('name')
    if not isinstance(head,str):raise GenerationUnavailable('UNRECOGNIZED_GRADIO_OUTPUT_NO_LOCAL_FILE')
    p=Path(head).expanduser().resolve()
    if not p.is_file():raise GenerationUnavailable('GENERATED_VIDEO_NOT_DOWNLOADED_LOCALLY')
    if p.suffix.lower() not in ('.mp4','.mov','.webm'):raise GenerationUnavailable('MODEL_RETURNED_NOT_A_VIDEO_FILE')
    return p

def generate(prompt,destination,seed=42,duration=5.0,height=512,width=768,client_factory=None):
    if not prompt or not isinstance(prompt,str):raise ValueError('PROMPT_REQUIRED')
    if not 1.0<=duration<=5.0:raise ValueError('OFFICIAL_SPACE_DURATION_OUT_OF_RANGE_1_TO_5')
    if width%64 or height%64 or min(width,height)<512:raise ValueError('INVALID_MULTIPLE_64_DIMENSIONS')
    if client_factory is None:
        try:
            from gradio_client import Client
        except ImportError as e:raise GenerationUnavailable('GRADIO_CLIENT_NOT_INSTALLED_INSTALL_DEPENDENCY') from e
        client_factory=Client
    authenticated=os.environ.get('AIL_USE_HF_TOKEN','0')=='1'
    token=os.environ.get('HF_TOKEN') if authenticated else None
    if authenticated and not token:raise GenerationUnavailable('AIL_USE_HF_TOKEN_SET_BUT_HF_TOKEN_UNSET')
    factory=client_factory
    start=time.monotonic()
    try:
        client=factory(SPACE,token=token)
        # Must verify the live endpoint: never guess or route to another Space.
        api=client.view_api(return_format='dict',print_info=False)
        if isinstance(api,dict):
            named=api.get('named_endpoints',{})
            endpoint='/run' if '/run' in named else ('/generate' if '/generate' in named else None)
            if endpoint is None:raise GenerationUnavailable('OFFICIAL_SPACE_RUN_ENDPOINT_NOT_ADVERTISED')
            paramlen=len(named[endpoint].get('parameters',[]))
            if paramlen!=10:raise GenerationUnavailable('OFFICIAL_SPACE_SCHEMA_CHANGED_EXPECTED_10_GOT_'+str(paramlen))
        else:raise GenerationUnavailable('CANNOT_VERIFY_GRADIO_ENDPOINT_SCHEMA')
        # Exact published _INPUTS order: prompt,image,height,width,duration,seed,decoder,auto_len,randomize_seed,do_enhance.
        result=client.predict(prompt,None,height,width,float(duration),int(seed),'conv',False,False,False,
                              api_name=endpoint)
    except GenerationUnavailable: raise
    except Exception as exc:
        error_text=str(exc)
        for secret in (os.environ.get('HF_TOKEN'),):
            if secret:error_text=error_text.replace(secret,'[REDACTED_TOKEN]')
        raise GenerationUnavailable('REMOTE_GENERATION_ERROR:'+type(exc).__name__+':'+error_text[:240]) from exc
    src=unwrap_video(result)
    dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dest)
    if dest.stat().st_size<4096:raise GenerationUnavailable('REMOTE_MODEL_OUTPUT_INVALID_SIZE')
    used_prompt=result[1] if isinstance(result,(tuple,list)) and len(result)>1 else None
    used_seed=result[2] if isinstance(result,(tuple,list)) and len(result)>2 else None
    return {'provider':'HF_SPACES_ZEROGPU','space':SPACE,'model':MODEL,'api':endpoint,
            'authenticated':authenticated,'request':{'prompt':prompt,'duration_requested_s':duration,'height':height,'width':width,
            'seed':seed,'decoder':'conv','enhance_prompt':False},
            'provider_echo_prompt':used_prompt,'provider_echo_seed':used_seed,
            'provider_duration_text':result[3] if isinstance(result,(tuple,list)) and len(result)>3 else None,
            'latency_s':round(time.monotonic()-start,3),'cost_usd':None,
            'cost_label':'NO_PROVIDER_INVOICE_HF_ZERO_GPU_QUOTA_CONSUMED',
            'generation_mode':'REAL_REMOTE_TEXT_TO_VIDEO_MODEL','source_client':'gradio_client'}
