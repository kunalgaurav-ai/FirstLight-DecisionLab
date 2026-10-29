"""Matched prospective public-program repair with bounded risk-aware precommit checks.

This is research only, not calibrated safe-policy improvement. Gold tests are never
loaded before every policy has completed. No SWE-bench or paid models.
"""
from __future__ import annotations
import hashlib,json,pathlib,random,time,datetime as dt,csv,statistics
from .contracts import ALL,DEV,HOLDOUT,probes
from .probes import single_case,complexity
from .stats import paired_bootstrap,exact_discordance_p
from firstlight_v55.ollama import generate,installed
from firstlight_v55.sandbox import extract,validate
from firstlight_v55.experiment import prompt_initial,receipts
from firstlight_v55.source import sha
from firstlight_v55.sandbox import run_cases
POLICIES=('COMPETENT_OPTIMIZED','COMPETENT_ALL_CHECKS','FIRSTLIGHT_SELECTIVE_VALUE_CHECK')


def risk_decision(code,name,basic_pass,exposure_units=1,probe_time_upper_s=.15):
    """Heuristic stress-test priority, NOT a failure-probability estimate.

    Value-of-information production gating requires calibration and real downstream
    cost data. Here we simply screen high-risk code under a small probe budget.
    """
    feat=complexity(code,name)
    if not basic_pass:return {'probe':False,'reason':'BASELINE_ALREADY_DETECTED','features':feat}
    if feat['recursive_calls']>=2:
        return {'probe':True,'reason':'BRANCHING_RECURSION_CHECK_COMPLEXITY','features':feat}
    if feat['score']>=4 and exposure_units>=1 and probe_time_upper_s<=.3:
        return {'probe':True,'reason':'HIGH_COMPLEXITY_PRECOMMIT','features':feat}
    return {'probe':False,'reason':'LOW_INFORMATION_OR_BUDGET','features':feat}


def receipt_call(invoke,model,prompt):
    r=invoke(model,prompt)
    if r.get('status')!='OK':return r
    if r.get('input_tokens') is None or r.get('output_tokens') is None:
        # Keep evidence but forbid unsupported economics claims
        r={**r,'usage_incomplete':True}
    return r


def make_feedback(task,check,previous_code):
    if not check:return 'No usable verification feedback.'
    if check['status']=='STATIC_REJECT':
        return ('Static rejection: '+check.get('reason','unknown')+'. Rewrite with explicit ordinary conditionals/loops. '
                'Avoid import statements, lambda expressions, introspection, and indirect function invocation.')
    c=check.get('case')
    if c is None:return 'Bounded precommit execution failed; simplify and ensure termination.'
    return ('Precommitted non-gold counterexample. Inputs: '+repr(c[0])[:300]
           +'. Expected: '+repr(c[1])[:300]+'. Observed: '+check.get('observed','unknown')[:200]
           +'. Status: '+check['status']+'. Correct the specific semantic or nontermination failure.')


def choose_check(task,code,policy):
    suite=probes(task)
    start=time.perf_counter();observations=[]
    basic=single_case(code,task,suite[0],timeout=.9)
    observations.append(basic)
    used_extra=False
    rationale={'probe':False,'reason':'COMPETENT_BASE_CHECK_ONLY','features':complexity(code,task)}
    if basic['status']=='PASS':
        if policy=='COMPETENT_ALL_CHECKS':
            used_extra=True;rationale={'probe':True,'reason':'ALL_EXTRA_CONTRACTS_COMPETENT','features':complexity(code,task)}
        elif policy=='FIRSTLIGHT_SELECTIVE_VALUE_CHECK':
            rationale=risk_decision(code,task,True)
            used_extra=rationale['probe']
        if used_extra:
            for spec in suite[1:]:
                o=single_case(code,task,spec,timeout=.9)
                observations.append(o)
                if o['status']!='PASS':break
    fail=next((x for x in observations if x['status']!='PASS'),None)
    return {'status':'PASS' if fail is None else fail['status'], 'failure':fail,
           'observations':observations,'extras_run':len(observations)-1,'decision':rationale,
           'elapsed_s':time.perf_counter()-start}


def continuation(task,bug,initial,model,policy,invoke=generate,max_repairs=2):
    current=extract(initial.get('response',''),task)
    calls=[initial];hist=[];seen={sha(current.encode())};repair_prompts=set();stop_reason=None
    for attempt in range(max_repairs+1):
        checked=choose_check(task,current,policy)
        hist.append({'attempt':attempt,'code_sha256':sha(current.encode()),'check':checked,'online_only':True})
        if checked['status']=='PASS':stop_reason='PRECOMMIT_PASS';break
        if attempt==max_repairs:stop_reason='REPAIR_BUDGET';break
        if not calls[-1].get('status')=='OK':stop_reason='MODEL_UNAVAILABLE';break
        feedback=make_feedback(task,checked['failure'],current)
        # OSS-compentent dedupe and concrete feedback in ALL arms.
        prompt=('Fix the Python implementation of '+task+'. Output ONLY the complete corrected function. '
                'Keep name/signature, no imports/lambdas/introspection. Do not repeat an unchanged patch. '
                'Minimize time complexity while preserving semantics.\n'
                'ORIGINAL BUGGY CODE:\n'+bug[:6000]+'\nCURRENT PATCH:\n'+current[:6000]
                +'\nACTIONABLE PRECOMMIT FEEDBACK:\n'+feedback+'\nCORRECTED FUNCTION:\n')
        if policy=='FIRSTLIGHT_SELECTIVE_VALUE_CHECK' and 'BRANCHING_RECURSION' in checked['decision']['reason']:
            prompt += '\nUse memoization-free bottom-up dynamic programming instead of recomputing overlapping recursive subproblems.'
        ph=sha(prompt.encode())
        if ph in repair_prompts:stop_reason='IDENTICAL_PROMPT_DEDUPE';break
        repair_prompts.add(ph)
        call=receipt_call(invoke,model,prompt)
        calls.append(call)
        revised=extract(call.get('response',''),task)
        digest=sha(revised.encode())
        if digest in seen:
            hist.append({'attempt':attempt+1,'stage':'DEDUPE_REPEAT_OUTPUT','sha256':digest,'online_only':True})
            stop_reason='REPEATED_PATCH_STOP';break
        seen.add(digest);current=revised
        if call.get('status')!='OK':stop_reason='MODEL_UNAVAILABLE';break
    else:stop_reason='MAX_REPAIRS'
    usage=receipts(calls)
    return {'policy':policy,'final_code':current,'final_sha256':sha(current.encode()),
            'usage':usage,'model_calls':len(calls),'model_history':calls,'checks':hist,
            'warnings':sum('check' in x and x['check']['status']!='PASS' for x in hist),
            'extras_run':sum(x.get('check',{}).get('extras_run',0) for x in hist),
            'probe_wall_s':sum(x.get('check',{}).get('elapsed_s',0) for x in hist),
            'stop_reason':stop_reason}


def paired(task,bug,gold_path,model,invoke=generate,seed=27):
    proposal_prompt=prompt_initial(task,bug)
    initial=receipt_call(invoke,model,proposal_prompt)
    order=list(POLICIES);random.Random(seed+int(sha(task.encode())[:6],16)).shuffle(order)
    record={'task':task,'cohort':'DEV' if task in DEV else 'HOLDOUT','initial_sha256':sha(initial.get('response','').encode()),
      'same_initial_proposal':True,'initial_call':initial,'arm_order':order,'arms':{}}
    for policy in order:
        record['arms'][policy]=continuation(task,bug,initial,model,policy,invoke=invoke)
    # GATE: published final gold is read only AFTER all 3 continuations finish.
    published=[]
    for line in gold_path.read_text().splitlines():
        if line.strip():published.append(json.loads(line))
    for policy in POLICIES:
        arm=record['arms'][policy]
        grade=run_cases(arm['final_code'],task,published,timeout=3.0)
        arm['final_grade']={'status':grade['status'],'passed':grade['passed'],'total':grade['total'],
          'accepted':grade['status']=='PASS','wall_s_not_in_policy':grade['wall_s']}
    record['published_gold_only_read_after_all_arms']=True
    return record


def summarize(records):
    arms={}
    for policy in POLICIES:
        group=[r['arms'][policy] for r in records]
        arms[policy]={'tasks':len(group),'accepted':sum(a['final_grade']['accepted'] for a in group),
          'tokens':sum(a['usage']['total_tokens'] for a in group),
          'calls':sum(a['model_calls'] for a in group),'probe_seconds':sum(a['probe_wall_s'] for a in group),
          'inference_seconds':sum(a['usage']['model_call_wall_s'] for a in group),
          'extra_checks':sum(a['extras_run'] for a in group),
          'complete_receipts':all(a['usage']['all_provider_token_receipts_present'] for a in group)}
    for item in arms.values():
        item['reported_tokens_per_accepted']=(item['tokens']/item['accepted'] if item['accepted'] and item['complete_receipts'] else None)
        item['measured_inference_plus_probe_s_per_accepted']=((item['inference_seconds']+item['probe_seconds'])/item['accepted'] if item['accepted'] else None)
    base=arms[POLICIES[0]];fl=arms[POLICIES[-1]]
    wins=sum(r['arms'][POLICIES[-1]]['final_grade']['accepted'] and not r['arms'][POLICIES[0]]['final_grade']['accepted'] for r in records)
    losses=sum(r['arms'][POLICIES[0]]['final_grade']['accepted'] and not r['arms'][POLICIES[-1]]['final_grade']['accepted'] for r in records)
    binary_diffs=[int(r['arms'][POLICIES[-1]]['final_grade']['accepted'])-int(r['arms'][POLICIES[0]]['final_grade']['accepted']) for r in records]
    token_diffs=[r['arms'][POLICIES[0]]['usage']['total_tokens']-r['arms'][POLICIES[-1]]['usage']['total_tokens'] for r in records]
    uncertainty={'quality_delta_per_task':paired_bootstrap(binary_diffs),
      'baseline_minus_fl_tokens_per_task':paired_bootstrap(token_diffs),
      'two_sided_exact_discordance_p':exact_discordance_p(wins,losses),
      'noninferiority_not_established':True}
    return {'policies':arms,'paired_uncertainty':uncertainty,'fl_vs_competent':{'fl_only_success':wins,'competent_only_success':losses,
      'paired_quality_delta':wins-losses,'token_difference':base['tokens']-fl['tokens'],
      'token_reduction':(base['tokens']-fl['tokens'])/base['tokens'] if base['tokens'] and base['complete_receipts'] and fl['complete_receipts'] else None,
      'better_at_equal_paired_quality':wins==0 and losses==0 and fl['tokens']<base['tokens'],
      'competitive_superiority_established':False,'official_benchmark_score_established':False,
      'long_horizon_downstream_dollar_savings_established':False},
      'minimum_statistics_gate':'HOLD_WITHOUT_MULTISEED_SIGNIFICANCE_AND_EXTERNAL_STRONG_OSS'}


def execute(root,output,model='qwen2.5:1.5b',invoke=generate,model_check=installed,task_limit=0):
    root=pathlib.Path(root);output=pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=False)
    names=list(ALL) if not task_limit else list(ALL)[:task_limit]
    report={'study':'FIRST_LIGHT_DECISION_KERNEL','model':model,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'status':'STARTED','data_origin':'QuixBugs MIT source from user-provided executed benchmark ZIP',
      'dev_tasks':list(DEV),'holdout_tasks':list(HOLDOUT),
      'claimed_swebench':False,'claimed_dollars':False,'claimed_best_oss':False,
      'controller_is_calibrated':False,'code_execution_is_hardened':False,'records':[]}
    try:
        models=model_check()
        if model not in models:raise RuntimeError('LOCAL_MODEL_NOT_INSTALLED:'+model)
        for i,task in enumerate(names):
            src=root/'python_programs'/f'{task}.py';gold=root/'json_testcases'/f'{task}.json'
            if not src.is_file() or not gold.is_file():raise ValueError('DATASET_TASK_NOT_FOUND:'+task)
            print(f'DECISION STUDY {i+1}/{len(names)} {task} ({"DEV" if task in DEV else "HOLDOUT"})',flush=True)
            rec=paired(task,src.read_text(),gold,model,invoke=invoke)
            report['records'].append(rec)
            (output/'partial_live.json').write_text(json.dumps(report,indent=2))
        report['status']='COMPLETE_PUBLIC_LOCAL_PILOT'
        report['cohorts']={k:summarize([r for r in report['records'] if r['cohort']==k]) for k in ('DEV','HOLDOUT')}
    except Exception as e:
        report['status']='BLOCKED';report['blocker']=type(e).__name__+':'+str(e)[:280]
    (output/'results.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (output/'partial_live.json').unlink(missing_ok=True)
    with (output/'per_task.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['task','cohort','policy','accepted','tokens','calls','probe_seconds','extra_checks','stop_reason'])
        for r in report['records']:
            for policy,a in r['arms'].items():w.writerow([r['task'],r['cohort'],policy,a['final_grade']['accepted'],a['usage']['total_tokens'],a['model_calls'],round(a['probe_wall_s'],5),a['extras_run'],a['stop_reason']])
    return report
