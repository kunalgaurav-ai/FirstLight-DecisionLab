"""Authorized optional LTX v2 asynchronous video API: explicit billable action only.

No paid calls are made by the v4.4 launcher. API key via LTXV_API_KEY
(environment), never written to artifacts or logs. Inferred rates are NOT invoices.
"""
import json, os, time, urllib.request, urllib.error
from urllib.parse import urlsplit
from pathlib import Path

BASE='https://api.ltx.io/v2/text-to-video'
MODELS=('ltx-2-5-fast','ltx-2-5-pro')
class ProviderError(RuntimeError):pass

def _safe(ex,key):
    s=str(ex).replace(key,'[REDACTED]') if key else str(ex)
    return (type(ex).__name__+':'+s)[:230]

def _json_request(url,headers,body=None,timeout=60,opener=None):
    opener=opener or urllib.request.urlopen
    rq=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers,method='POST' if body is not None else 'GET')
    with opener(rq,timeout=timeout) as res:return json.loads(res.read(3_000_000))

def generate(prompt,dest,model,ack_billable=False,price_usd_per_sec=None,poll_interval=5,deadline_seconds=540,opener=None,on_status=None):
    if not ack_billable:raise ProviderError('BILLED_API_CALL_REQUIRES_ACK_BILLABLE')
    if model not in MODELS:raise ProviderError('MODEL_NOT_ALLOWED')
    if type(price_usd_per_sec) not in (int,float) or price_usd_per_sec<=0:raise ProviderError('USER_CONFIRMED_PRICE_REQUIRED_NOT_PROVIDER_INVOICE')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>5000:raise ProviderError('INVALID_PROMPT')
    key=os.environ.get('LTXV_API_KEY')
    if not key:raise ProviderError('MISSING_LTXV_API_KEY_IN_LOCAL_ENVIRONMENT')
    if poll_interval<5:raise ProviderError('POLL_INTERVAL_MUST_BE_AT_LEAST_5S')
    if deadline_seconds<10 or deadline_seconds>3600:raise ProviderError('INVALID_DEADLINE')
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
    # 720x1280 portrait, 24fps, 8s supported by official LTX 2.5 support matrix.
    payload={'model':model,'prompt':prompt,'duration':8,'resolution':'720x1280','fps':24,'generate_audio':False}
    try:
        created=_json_request(BASE,headers,payload,opener=opener)
        job=created.get('id')
        if not isinstance(job,str) or not job or len(job)>120 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.' for c in job):
            raise ProviderError('NO_VALID_JOB_ID')
        started=time.monotonic();status=None
        if on_status:on_status({'event':'SUBMITTED','job_id':job,'model':model,'requested_s':8,'cost_estimate_usd':8*price_usd_per_sec,'basis':'USER_CONFIRMED_RATE_NOT_PROVIDER_INVOICE'})
        while time.monotonic()-started<deadline_seconds:
            time.sleep(poll_interval)
            status=_json_request(BASE+'/'+job,headers,opener=opener)
            if status.get('status')=='failed':raise ProviderError('REMOTE_JOB_FAILED_'+str(status.get('error','unknown'))[:100])
            if status.get('status')=='completed':break
            if status.get('status') not in ('pending','processing','queued'):raise ProviderError('UNEXPECTED_JOB_STATUS')
        if not status or status.get('status')!='completed':raise ProviderError('REMOTE_JOB_PENDING_MANUAL_POLL_JOB_ID_'+job)
        url=status.get('result',{}).get('video_url')
        if not isinstance(url,str) or urlsplit(url).scheme!='https' or not urlsplit(url).netloc:raise ProviderError('NO_AUTHORIZED_HTTPS_VIDEO_URL')
        # Do not send the API bearer token to a separate signed storage download URL.
        opener=opener or urllib.request.urlopen
        req=urllib.request.Request(url,headers={'User-Agent':'AIL-v4.4-client'},method='GET')
        p=Path(dest);p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix('.partial')
        with opener(req,timeout=120) as res,open(tmp,'wb') as f:
            n=0
            while True:
                b=res.read(65536)
                if not b:break
                n+=len(b)
                if n>200_000_000:raise ProviderError('VIDEO_DOWNLOAD_SIZE_LIMIT')
                f.write(b)
        if n<4096:raise ProviderError('DOWNLOADED_VIDEO_TOO_SMALL')
        tmp.replace(p)
        return {'generation_mode':'REAL_REMOTE_TEXT_TO_VIDEO_MODEL','provider':'LTXV_V2_OFFICIAL_BILLED_API','model':model,
                'provider_job_id':job,'request':payload,'wall_s':time.monotonic()-started,'file_bytes':n,
                'inferred_cost_usd':8*price_usd_per_sec,'cost_evidence':'USER_DECLARED_RATE_MULTIPLIED_BY_REQUESTED_SECONDS_NOT_PROVIDER_INVOICE',
                'actual_invoice_usd':None}
    except (ProviderError,urllib.error.HTTPError,urllib.error.URLError,ValueError,TypeError) as e:
        if isinstance(e,ProviderError):raise
        raise ProviderError('LTX_V2_API_ERROR_'+_safe(e,key)) from e
