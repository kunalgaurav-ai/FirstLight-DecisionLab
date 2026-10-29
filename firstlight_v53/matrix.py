"""Matched, multi-model, multiple-policy BFCL-V4 pilot; never describe scores as official grading."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from firstlight_v5.core import (OFFICIAL_FILES, json_dump, read_items, prepare_prompt,
    tool_specs, parse_generation, score_diagnostic, validate_call, sample_rows,sha)
from firstlight_v5.runner import (fetch_official, ollama_models, attempt)

DEFAULT_MODELS=('qwen2.5:0.5b','qwen2.5:1.5b','qwen3:0.6b','llama3.2:1b','gemma3:1b')
STRATEGIES=('SINGLE','GUARDED','FIRSTLIGHT')


def key(model,strategy):
    return strategy+'::'+model


def checked_attempt(model,row,strict,corrective=False):
    return attempt(model,row,strict=strict,corrective=corrective)


def evaluate_strategy(row,model,strategy,cheap='qwen2.5:0.5b',fn=None):
    """Precommitted decisions. Only syntax and tool schema available to policies; no gold or tests."""
    fn=fn or checked_attempt
    if strategy not in STRATEGIES: raise ValueError('UNKNOWN_STRATEGY')
    specs=tool_specs(row)
    risk_features={'tool_count':len(specs),'complexity_threshold':2}
    # Tool count is public task input, never the benchmark answer.
    preflight_to_strong = strategy=='FIRSTLIGHT' and model!=cheap and len(specs)>=2
    first_model = (model if strategy!='FIRSTLIGHT' or preflight_to_strong else cheap)
    actions=[]
    a=fn(first_model,row,strict=(strategy!='SINGLE'))
    actions.append(a)
    fallback=None
    if a.get('status')!='OK':
        return {'status':'BLOCKED_MODEL','decision':'HOLD_MODEL_ERROR','calls':actions,
                'preflight':risk_features,'model':model,'strategy':strategy,'parsed_call':None,
                'tokens':None,'wall_s':sum(x.get('wall_s',0) for x in actions)}
    if a.get('call') is None and strategy!='SINGLE':
        fallback=model
        b=fn(fallback,row,strict=True,corrective=True)
        actions.append(b)
        a=b
    dec=('SCHEMA_ESCALATE' if fallback and strategy=='FIRSTLIGHT' else
         'SCHEMA_RETRY' if fallback else 'PREFLIGHT_ROUTE_STRONG' if preflight_to_strong else
         'CHEAP_FIRST_ACCEPT' if strategy=='FIRSTLIGHT' and first_model==cheap else 'ACCEPT_FIRST')
    valid=all(x.get('status')=='OK' for x in actions)
    in_tokens=sum(x.get('input_tokens') or 0 for x in actions)
    out_tokens=sum(x.get('output_tokens') or 0 for x in actions)
    return {'status':'COMPLETE' if valid else 'BLOCKED_MODEL', 'decision':dec,
            'calls':actions,'preflight':risk_features,'model':model,'strategy':strategy,
            'parsed_call':a.get('call'),'input_tokens':in_tokens,'output_tokens':out_tokens,
            'tokens':in_tokens+out_tokens,'wall_s':sum(x.get('wall_s',0) for x in actions)}


def wilson(k,n):
    if n==0:return None
    z=1.96;p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d;w=z*((p*(1-p)/n+z*z/(4*n*n))**0.5)/d
    return [round(max(0,c-w),4),round(min(1,c+w),4)]


def score_summary(rows,models):
    info={}; total=len(rows)
    for m in models:
        for s in STRATEGIES:
            k=key(m,s)
            arms=[r['arms'][k] for r in rows if k in r.get('arms',{})]
            scored=[a for a in arms if a.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
            complete=sum(a.get('status')=='COMPLETE' for a in arms)
            good=sum(bool(a['diagnostic'].get('pass')) for a in scored)
            info[k]={'model':m,'strategy':s,'attempted':len(arms),'completed':complete,
                     'scored':len(scored),'passes':good,'rate':good/len(scored) if scored else None,
                     'ci95':wilson(good,len(scored)),'reported_tokens':sum(a.get('tokens') or 0 for a in arms),
                     'summed_call_wall_s':round(sum(a.get('wall_s',0) for a in arms),4),
                     'calls':sum(len(a.get('calls',[])) for a in arms),
                     'usd':None,'approved_outcome_count':None}
    # Fully matched / complete cohorts only; never silently exclude a failing arm.
    pairs={}
    for m in models:
        a,b=key(m,'GUARDED'),key(m,'FIRSTLIGHT')
        matched=[(r['arms'][a],r['arms'][b]) for r in rows if a in r.get('arms',{}) and b in r.get('arms',{})]
        aa=[x for x,y in matched if x.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC' and y.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
        bb=[y for x,y in matched if x.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC' and y.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
        wins=sum(not x['diagnostic']['pass'] and y['diagnostic']['pass'] for x,y in zip(aa,bb))
        losses=sum(x['diagnostic']['pass'] and not y['diagnostic']['pass'] for x,y in zip(aa,bb))
        n=len(aa)
        from math import comb
        d=wins+losses
        pval=min(1.0,2*sum(comb(d,j) for j in range(min(wins,losses)+1))/2**d) if d else 1.0 if n else None
        pairs[m]={'scored_pairs':n,'firstlight_only_passes':wins,'guarded_only_passes':losses,
                  'exact_mcnemar_p':pval,'delta_pass_rate':(wins-losses)/n if n else None}
    return {'arms':info,'paired_comparisons':pairs,'total_tasks':total,
            'grade':'LOCAL_DIAGNOSTIC_NOT_OFFICIAL_BFCL',
            'publication_gate':'HOLD_NO_OFFICIAL_BFCL_OR_APPROVED_OUTCOME_INVOICES',
            'tokens_note':'Tokenizer counts are model-dependent; not interchangeable with dollars.',
            'model_wall_note':'Summed Ollama call wall times; not full pipeline elapsed time.'}


def discover_dataset_paths(home=None):
    home=Path(home or Path.home())
    roots=['FirstLight-v52-executions','FirstLight-v51-executions','FirstLight-v5-executions']
    for parent in roots:
        base=home/'Downloads'/parent
        if not base.exists():continue
        for p in sorted(base.glob('source-*/**/runs/*/official_data/SOURCE_PROVENANCE.json'),reverse=True):
            yield p.parent


def reuse_verified_dataset(target, candidates):
    for source in candidates:
        source=Path(source)
        meta=source/'SOURCE_PROVENANCE.json'
        if not meta.is_file():continue
        try:
            d=json.loads(meta.read_text())
            if len(d.get('files',[]))!=4:continue
            if all((source/f['local']).is_file() and sha((source/f['local']).read_bytes())==f['sha256'] for f in d['files']):
                shutil.copytree(source,target,dirs_exist_ok=True)
                return str(source)
        except (OSError,ValueError,KeyError):continue
    return None


def write_csv(path,rows,models):
    with Path(path).open('w',newline='') as f:
        w=csv.writer(f)
        w.writerow(['task_id','group','model','strategy','state','local_diagnostic_pass','schema_decision','calls','reported_tokens','summed_model_wall_s'])
        for r in rows:
            for m in models:
                for s in STRATEGIES:
                    a=r.get('arms',{}).get(key(m,s))
                    if a:
                        w.writerow([r['id'],r['group'],m,s,a['status'],a.get('diagnostic',{}).get('pass'),a['decision'],len(a['calls']),a.get('tokens'),round(a.get('wall_s',0),5)])


def run(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--run',required=True)
    ap.add_argument('--limit',type=int,default=48)
    ap.add_argument('--models',default=','.join(DEFAULT_MODELS))
    ap.add_argument('--cache-from',default='')
    ap.add_argument('--no-download',action='store_true')
    args=ap.parse_args(argv)
    if not 1<=args.limit<=200:raise ValueError('LIMIT_BETWEEN_1_AND_200')
    models=tuple(dict.fromkeys(x.strip() for x in args.models.split(',') if x.strip()))
    if not 2<=len(models)<=8 or any('/' in m or len(m)>80 for m in models):raise ValueError('MODEL_MATRIX_INVALID')
    cheap='qwen2.5:0.5b'
    if cheap not in models:raise ValueError('CHEAP_ANCHOR_REQUIRED')
    root=Path(args.run).resolve();root.mkdir(parents=True,exist_ok=True)
    data=root/'official_data'
    report={'brand':'First Light','version':'5.3.0','state':'PREFLIGHT','benchmark':'BFCL V4 two single-turn subsets',
            'requested_models':models,'models_available':[],'missing_models':[],'source':None,'rows':[],
            'summary':None,'warnings':['UNOFFICIAL_LOCAL_SCORE','NOT_CUSTOMER_TASK_SUCCESS','NO_PROVIDER_DOLLAR_INVOICES',
                    'NO_LEADERBOARD_CLAIM','MODEL_LICENSE_CHECK_REQUIRED_FOR_EXTERNAL_USE'],
            'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'policy_precommit':{'strategies':STRATEGIES,'cheap_anchor':cheap,'strong_preflight_tool_count':2,
                  'schema_repair_max_retries':1,'sample_seed':'firstlight-v5-precommitted','no_gold_in_prompts':True}}
    json_dump(root/'matrix_results.json',report)
    try:
        cached=reuse_verified_dataset(data,[args.cache_from] if args.cache_from else discover_dataset_paths())
        if args.no_download and not (data/'SOURCE_PROVENANCE.json').is_file():raise RuntimeError('MISSING_VERIFIED_OFFLINE_DATASET')
        provenance=fetch_official(data)
        report['source']={'commit':provenance['commit'],'source_files':provenance['files'],
                          'cache_reused_from':cached,'license_publication':'HOLD_VERIFY_DATA_TERMS'}
        available=ollama_models()
        report['models_available']=[m for m in models if m in available]
        report['missing_models']=[m for m in models if m not in available]
        if not report['models_available'] or cheap not in report['models_available']:
            raise RuntimeError('OLLAMA_MODELS_MISSING:'+','.join(report['missing_models']))
        # Strict fair matrix: stop if a named competitor model is absent, don't silently drop it.
        if report['missing_models']:
            raise RuntimeError('MISSING_MATRIX_MODELS:'+','.join(report['missing_models']))
        grouped={g:read_items(data/f) for g,f in OFFICIAL_FILES.items()}
        gold={g:{r['id']:r for r in read_items(data/'possible_answer'/f)} for g,f in OFFICIAL_FILES.items()}
        selected=sample_rows(grouped,args.limit)
        report['sampled_ids']=[r['id'] for _,r in selected]
        report['state']='RUNNING';json_dump(root/'matrix_results.json',report)
        report['rows']=[{'id':row['id'],'group':group,
                          'question_sha256':sha(json.dumps(prepare_prompt(row),sort_keys=True)),
                          'arms':{}} for group,row in selected]
        # Keep one target model active across a block of matched tasks, rather than
        # bouncing between five target models on every task on an 8 GB Mac.
        # Rotate within-task policy ordering to limit systematic hot-cache advantage.
        for mi,m in enumerate(models):
            for idx,(group,row) in enumerate(selected):
                case=report['rows'][idx]
                start_policy=(idx+mi)%len(STRATEGIES)
                policy_order=STRATEGIES[start_policy:]+STRATEGIES[:start_policy]
                ref=gold[group].get(row['id'])
                for s in policy_order:
                    out=evaluate_strategy(row,m,s,cheap)
                    out['diagnostic']=score_diagnostic((out['parsed_call']['name'],out['parsed_call']['arguments']) if out['parsed_call'] else None,ref) if ref else {'status':'REFERENCE_MISSING'}
                    case['arms'][key(m,s)]=out
                report['summary']=score_summary(report['rows'],models)
                json_dump(root/'matrix_results.json',report)
                print(f'FIRST LIGHT MATRIX model={m} CASE {idx+1}/{len(selected)} {row["id"]} diagnostics: '+', '.join(f'{s}={case["arms"][key(m,s)]["diagnostic"].get("pass","NA")}' for s in STRATEGIES),flush=True)
        report['state']='COMPLETE_LOCAL_PILOT' if all(a['status']=='COMPLETE' for r in report['rows'] for a in r['arms'].values()) else 'PARTIAL_MODEL_FAILURE'
    except Exception as e:
        report['state']='BLOCKED' if not report['rows'] else 'PARTIAL_BLOCKED'
        report['blocker']=str(e)[:600]
        json_dump(root/'error_report_v53.json',{'error':report['blocker'],'type':type(e).__name__})
    if report['rows']:report['summary']=score_summary(report['rows'],models)
    report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    json_dump(root/'matrix_results.json',report)
    write_csv(root/'matrix_rows.csv',report['rows'],models)
    print('FIRST LIGHT MULTI-MODEL STATUS:',report['state'],'ROWS:',len(report['rows']),flush=True)
    if report.get('blocker'):print('REAL BLOCKER:',report['blocker'],flush=True)
    return report

if __name__=='__main__':
    run()
