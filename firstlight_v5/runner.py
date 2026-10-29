"""Actual BFCL V4 source download, inference, frozen paired comparison and evidence packaging."""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from .core import OFFICIAL_FILES, ENDPOINT, json_dump, read_items, prepare_prompt, tool_specs, parse_generation, score_diagnostic, validate_call, sample_rows, summarize, sha

MODELS=('qwen2.5:1.5b','qwen2.5:0.5b')
USER_AGENT='FirstLight-Benchmark/5.0 research reproducibility'

def download(url, max_bytes=3_500_000):
    if not url.startswith('https://'): raise ValueError('HTTPS_REQUIRED')
    request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=25) as f:
        raw=f.read(max_bytes+1)
    if len(raw)>max_bytes: raise ValueError('DATASET_EXCEEDS_CAP')
    return raw


def fetch_official(root):
    """Content addressed and pinned to an observed Git SHA. No unpinned moving main use."""
    path=Path(root);path.mkdir(parents=True,exist_ok=True)
    existing=path/'SOURCE_PROVENANCE.json'
    if existing.is_file():
        p=json.loads(existing.read_text())
        for item in p['files']:
            fp=path/item['local']
            if not fp.is_file() or sha(fp.read_bytes())!=item['sha256']: raise ValueError('OFFICIAL_DATASET_SHA_MISMATCH')
        return p
    commit=json.loads(download('https://api.github.com/repos/ShishirPatil/gorilla/commits/main',1_000_000))['sha']
    if not re.fullmatch('[a-f0-9]{40}',commit): raise ValueError('INVALID_REPO_COMMIT')
    urlbase=f'{ENDPOINT}{commit}/berkeley-function-call-leaderboard/bfcl_eval/data/'
    entries=[]
    # Ensure all downloads succeed before marking the source ready.
    for g,fn in OFFICIAL_FILES.items():
        for prefix in ('', 'possible_answer/'):
            rel=prefix+fn
            blob=download(urlbase+rel)
            if len(blob)<100: raise ValueError('DATASET_RESPONSE_TOO_SHORT')
            read_data=blob.decode('utf8')
            try:
                if not read_data.lstrip().startswith(('{','[')): raise ValueError('UNEXPECTED_BENCHMARK_FORMAT')
                [json.loads(line) for line in read_data.splitlines() if line.strip()] if not read_data.lstrip().startswith('[') else json.loads(read_data)
            except (ValueError,json.JSONDecodeError):
                # A top-level mapping is also valid.
                json.loads(read_data)
            output=path/rel
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(blob)
            entries.append({'local':rel,'url':urlbase+rel,'bytes':len(blob),'sha256':sha(blob)})
    meta={'source':'OFFICIAL_BFCL_V4_GITHUB','repository':'https://github.com/ShishirPatil/gorilla',
          'commit':commit,'downloaded_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
          'license_for_public_promotion':'UNVERIFIED_HOLD','files':entries}
    json_dump(existing,meta)
    return meta


def ollama_models(url='http://127.0.0.1:11434'):
    try:
        with urllib.request.urlopen(url+'/api/tags',timeout=4) as f: data=json.load(f)
        return {x.get('name') for x in data.get('models',[])}
    except (urllib.error.URLError,TimeoutError,ValueError,ConnectionError): return set()


def call_ollama(model, msgs, options=None, base='http://127.0.0.1:11434'):
    # User context is only included in the explicit benchmark prompt.
    payload={'model':model,'messages':msgs,'stream':False,
             'options':{'temperature':0,'num_predict':192,'num_ctx':4096,'seed':13,**(options or {})}}
    start=time.perf_counter()
    req=urllib.request.Request(base+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as f: res=json.load(f)
        elapsed=time.perf_counter()-start
        raw=res.get('message',{}).get('content','')
        if not isinstance(raw,str) or not raw.strip(): raise ValueError('EMPTY_OLLAMA_COMPLETION')
        return {'status':'OK','raw':raw,'model':res.get('model',model),
                'input_tokens':res.get('prompt_eval_count'), 'output_tokens':res.get('eval_count'),
                'provider_wall_ns':res.get('total_duration'), 'wall_s':elapsed,'sha256':sha(raw),
                'template_model':model}
    except (urllib.error.URLError,TimeoutError,ValueError) as e:
        return {'status':'BLOCKED_MODEL_CALL','error':str(e)[:400], 'template_model':model,
                'wall_s':time.perf_counter()-start,'input_tokens':None,'output_tokens':None}


def prompt_messages(row, strict=False, corrective=False):
    p=prepare_prompt(row)
    schema=json.dumps(p['tools'],sort_keys=True,ensure_ascii=False)
    base='You are a function-calling agent. Select the correct function and exact arguments from the provided tools. Do not execute tools. Output exactly one JSON object: {"name":"tool_name","arguments":{"key":"value"}}. No prose.'
    if strict: base+=' Arguments must respect the JSON schema, types and required fields. Only use tools provided. If unsure, still do your best; no added commentary.'
    if corrective: base+=' Prior output failed parsing or schema validation. Re-read the allowed tool specification and produce syntactically valid exact JSON.'
    system={'role':'system','content':base+'\nAllowed tool specifications: '+schema}
    return [system]+p['messages']


def attempt(model, row, *, strict, corrective=False):
    res=call_ollama(model,prompt_messages(row,strict=strict,corrective=corrective))
    res['parse_status']='NOT_ATTEMPTED'
    res['call']=None
    if res['status']=='OK':
        try:
            call=parse_generation(res['raw'])
            valid,reason=validate_call(call,tool_specs(row))
            res['parse_status']=reason
            if valid:
                res['call']={'name':call[0],'arguments':call[1]}
        except (ValueError,SyntaxError,TypeError) as e: res['parse_status']='INVALID_RESPONSE:'+str(e)[:100]
    return res


def branch(row,primary,secondary,adaptive):
    calls=[]
    a=attempt(primary,row,strict=True)
    calls.append(a)
    if a['status'] != 'OK': return {'status':'BLOCKED','calls':calls, 'decision':'HOLD_MODEL_UNAVAILABLE'}
    if a['call'] is None:
        b=attempt(secondary,row,strict=True,corrective=True)
        calls.append(b)
        if b['status']=='OK' and b['call'] is not None: a=b
        else: a=b
        decision='ESCALATE_AFTER_SCHEMA_FAILURE' if adaptive else 'COMPETENT_SINGLE_RETRY'
    else:
        decision='ACCEPT_SCHEMA_VALID'
    obj={'status':'COMPLETED' if a['status']=='OK' else 'BLOCKED',
         'decision':decision,'calls':calls,'call':a.get('call'),
         'input_tokens':sum(c['input_tokens'] or 0 for c in calls),
         'output_tokens':sum(c['output_tokens'] or 0 for c in calls),
         'wall_s':sum(c['wall_s'] for c in calls),
         'schema_status':a.get('parse_status')}
    return obj


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--run',required=True)
    ap.add_argument('--limit',type=int,default=24)
    ap.add_argument('--source-dir',default='')
    ap.add_argument('--skip-download',action='store_true')
    args=ap.parse_args(argv)
    root=Path(args.run).resolve(); root.mkdir(parents=True,exist_ok=True)
    path=Path(args.source_dir).resolve() if args.source_dir else root/'official_data'
    status={'version':'First Light v5.0','benchmark':'BFCL V4 simple_python + multiple','state':'PREFLIGHT',
            'dataset':None,'results':[],'summary':None,
            'warnings':['UNOFFICIAL_LOCAL_DIAGNOSTIC_NOT_BFCL_LEADERBOARD','LOCAL_OLLAMA_COST_NOT_API_INVOICE',
                        'NO_INDEPENDENT_CUSTOMER_APPROVAL','COMMERCIAL_CLAIM_HOLD']}
    json_dump(root/'benchmark_results.json',status)
    try:
        if args.skip_download and not (path/'SOURCE_PROVENANCE.json').exists(): raise ValueError('NO_PINNED_DATASET_OFFLINE')
        prov=fetch_official(path)
        status['dataset']={'commit':prov['commit'],'file_hashes':prov['files'],'license_public_claim':prov['license_for_public_promotion']}
        rows={group:read_items(path/fn) for group,fn in OFFICIAL_FILES.items()}
        gold={}
        for group,fn in OFFICIAL_FILES.items():
            ref=read_items(path/'possible_answer'/fn)
            gold[group]={r['id']:r for r in ref if isinstance(r,dict) and 'id' in r}
        selection=sample_rows(rows,args.limit)
        status['sampled_task_ids']=[r['id'] for _,r in selection]
        status['sample_seed']='firstlight-v5-precommitted'
        status['dataset_size_by_group']={g:len(v) for g,v in rows.items()}
        available=ollama_models()
        status['available_models']=sorted(available)
        if MODELS[0] not in available:
            raise RuntimeError('OLLAMA_STRONG_MODEL_NOT_INSTALLED_OR_NOT_RUNNING:'+MODELS[0])
        if MODELS[1] not in available:
            raise RuntimeError('OLLAMA_CHEAP_MODEL_NOT_INSTALLED_OR_NOT_RUNNING:'+MODELS[1])
        status['state']='RUNNING'
        json_dump(root/'benchmark_results.json',status)
        for i,(group,row) in enumerate(selection):
            # Frozen ordering; gold is read ONLY after both arms finish.
            case={'id':row['id'],'group':group,'question_sha256':sha(json.dumps(prepare_prompt(row),sort_keys=True)),
                  'arms':{}}
            case['arms']['COMPETENT_LLM_GUARDED']=branch(row,MODELS[0],MODELS[0],False)
            case['arms']['FIRSTLIGHT_ADAPTIVE']=branch(row,MODELS[1],MODELS[0],True)
            reference=gold[group].get(row['id'])
            for arm in case['arms'].values():
                prediction=arm.get('call')
                if reference is None:
                    arm['diagnostic']={'status':'NOT_SCORABLE_LOCAL','reason':'REFERENCE_MISSING'}
                else:
                    arm['diagnostic']=score_diagnostic((prediction['name'],prediction['arguments']) if prediction else None,reference)
            status['results'].append(case)
            status['summary']=summarize(status['results'])
            json_dump(root/'benchmark_results.json',status)
            print(f"CASE {i+1}/{len(selection)} {row['id']} local diagnostic {[(p, a['diagnostic'].get('pass','NA')) for p,a in case['arms'].items()]}",flush=True)
        status['state']='PARTIAL_RUN_BLOCKED' if any(arm.get('status')!='COMPLETED' for rec in status['results'] for arm in rec.get('arms',{}).values()) else 'COMPLETE_PILOT'
    except Exception as e:
        status['state']='BLOCKED' if not status['results'] else 'PARTIAL_RUN_BLOCKED'
        status['blocking_error']=str(e)[:700]
        json_dump(root/'error_report.json',{'kind':type(e).__name__,'error':str(e)[:700]})
    if status['results']: status['summary']=summarize(status['results'])
    json_dump(root/'benchmark_results.json',status)
    print('FIRST LIGHT STATE:',status['state'], 'TASKS:',len(status['results']),flush=True)
    if status.get('blocking_error'): print('BLOCKER:',status['blocking_error'],flush=True)
    return 0

if __name__=='__main__': sys.exit(main())
