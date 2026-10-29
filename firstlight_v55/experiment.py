"""Matched executed QuixBugs repair continuations; no SWE-bench/OSS superiority claim.

Gold tests are available only to the final evaluator AFTER both arms complete.
Initial model proposal is shared, then independent continuations are executed.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,os,pathlib,statistics,time
from . import VERSION
from .source import TASKS,sha,source_checkout
from .ollama import generate,installed
from .sandbox import PROBES,extract,run_cases,validate

POLICIES=('COMPETENT_TEST_REPAIR','FIRSTLIGHT_PRECOMMIT')


def prompt_initial(name,bug):
    return ('You are an expert Python bug fixer. Correct the behavior of the function below. '
            'Respond with ONLY the complete Python function implementation, no markdown, no imports, no external libraries. '
            'You may use Python builtins and ordinary language constructs. Preserve exact function name and signature. '
            'Avoid imports or introspection; ordinary list/dict methods are allowed. The code is executed with limited resources.\n'
            'BUGGY QUixBUGS FUNCTION:\n'+bug[:10000]+'\nCORRECTED FUNCTION:\n')

def prompt_repair(name,bug,candidate,feedback):
    return (f'Repair the Python function {name}. Current proposal failed precommit verification. '
            'Do not change function signature. Output ONLY a complete updated Python function, '
            'no markdown, no imports or unsafe attribute access.\nORIGINAL BUGGY FUNCTION:\n'+bug[:8500]+
            '\nCURRENT PATCH:\n'+candidate[:9000]+'\nVALIDATION FEEDBACK (precommitted probes; not final benchmark cases):\n'
            +feedback[:1100]+'\nFIXED FUNCTION:\n')

def receipts(calls):
    missing=any(x.get('status')!='OK' or not isinstance(x.get('input_tokens'),int) or not isinstance(x.get('output_tokens'),int) for x in calls)
    return {'total_calls':len(calls),'input_tokens':sum(x.get('input_tokens') or 0 for x in calls),
            'output_tokens':sum(x.get('output_tokens') or 0 for x in calls),
            'total_tokens':sum((x.get('input_tokens') or 0)+(x.get('output_tokens') or 0) for x in calls),
            'all_provider_token_receipts_present':not missing,
            'model_call_wall_s':round(sum(x.get('wall_s') or 0 for x in calls),6)}

def precommit(task,code,policy):
    """Competent baseline verifies static AST + one cheap smoke example.

    Extra checks are precommitted from task spec; First Light currently chooses
    extra check using an explicit UNCALIBRATED high-risk rule, not labels/gold.
    """
    tests=list(PROBES[task][:1]); reason='COMPETENT_SMOKE_TEST'
    if policy=='FIRSTLIGHT_PRECOMMIT' and task in {'gcd','levenshtein','is_valid_parenthesization','rpn_eval','find_in_sorted'}:
        tests=PROBES[task][:2];reason='FIXED_RISK_RULE_EXTRA_PRECOMMIT'
    r=run_cases(code,task,tests)
    r['policy_decision']=reason;r['probe_count']=len(tests)
    return r

def continuation(task,bug,initial_call,model,policy,invoke=generate,max_repairs=2):
    if policy not in POLICIES:raise ValueError('INVALID_POLICY')
    history=[initial_call]
    current=extract(initial_call.get('response',''),task)
    steps=[];repair=0
    while True:
        t=time.perf_counter()
        check=precommit(task,current,policy)
        steps.append({'stage':'PRECOMMIT','attempt':repair,'result':check,'code_sha256':sha(current.encode()),
                      'policy_wall_s':round(time.perf_counter()-t,6)})
        if check['status']=='PASS':break
        if repair>=max_repairs or initial_call.get('status')!='OK':break
        repair+=1
        feedback=f"status={check['status']} reason={check.get('reason','')} passed={check['passed']}/{check['total']}."
        # A probing counterexample is separately authored; official final gold
        # is NEVER passed into model or controller.
        if check['status']=='FAIL':feedback+=' Revise behavior for the algorithm specification and try again.'
        call=invoke(model,prompt_repair(task,bug,current,feedback))
        history.append(call)
        current=extract(call.get('response',''),task)
        steps.append({'stage':'MODEL_REPAIR','attempt':repair,'model_status':call.get('status'),
                      'input_tokens':call.get('input_tokens'),'output_tokens':call.get('output_tokens'),
                      'model_wall_s':call.get('wall_s')})
        if call.get('status')!='OK':break
    return {'policy':policy,'final_code':current,'final_code_sha256':sha(current.encode()),'precommit_history':steps,
            'model_history':history,'repair_calls':repair,'precommit_pass':steps[-1]['result']['status']=='PASS',
            'reported_usage':receipts(history),'precommit_wall_s':sum(s.get('policy_wall_s',0) for s in steps),
            'precommit_probe_wall_s':sum(s['result'].get('wall_s',0) for s in steps if s['stage']=='PRECOMMIT'),
            'precommit_warnings':sum(s['result']['status']!='PASS' for s in steps if s['stage']=='PRECOMMIT'),
            'extra_precommit_used':any(s.get('result',{}).get('policy_decision')=='FIXED_RISK_RULE_EXTRA_PRECOMMIT' for s in steps)}

def paired_task(task,problem,model,invoke=generate,max_repairs=2,policy_order=POLICIES):
    # Counterfactual pair begins at the identical initial patch/proposal.
    p=prompt_initial(task,problem['source'])
    proposal=invoke(model,p)
    result={'task':task,'initial_proposal':proposal,'initial_prompt_sha256':sha(p.encode()),
            'same_initial_model_output_for_both_arms':True,'executed_arm_order':list(policy_order),'arms':{}}
    if set(policy_order)!=set(POLICIES) or len(policy_order)!=2:raise ValueError('BAD_POLICY_ORDER')
    for policy in policy_order:
        start=time.perf_counter()
        arm=continuation(task,problem['source'],proposal,model,policy,invoke=invoke,max_repairs=max_repairs)
        arm['continuation_plus_inference_wall_s']=round(time.perf_counter()-start+proposal.get('wall_s',0),6)
        result['arms'][policy]=arm
    # gold only enters scope after both continuations completed
    for policy in POLICIES:
        arm=result['arms'][policy]
        grade=run_cases(arm['final_code'],task,problem['final_gold'],timeout=4)
        arm['independent_final_cases']={'passed':grade['passed'],'total':grade['total'],
              'status':grade['status'],'grade_wall_s':grade['wall_s'],
              'all_pass':grade['status']=='PASS'}
    # Measurement-only gold grading of shared initial proposal occurs AFTER both
    # continuations. This label is not accessible to either policy.
    first=run_cases(extract(proposal.get('response',''),task),task,problem['final_gold'],timeout=4)
    result['retrospective_initial_proposal_grade']={'pass':first['status']=='PASS','passed':first['passed'],
       'total':first['total'],'wall_s_outside_policy':first['wall_s'],'not_an_online_detector_signal':True}
    return result

def summarize(records):
    summary={};alln=len(records)
    for policy in POLICIES:
        arms=[r['arms'][policy] for r in records]
        summary[policy]={'tasks_attempted':alln,'fully_correct':sum(a['independent_final_cases']['all_pass'] for a in arms),
           'total_reported_tokens':sum(a['reported_usage']['total_tokens'] for a in arms),
           'all_token_receipts_present':all(a['reported_usage']['all_provider_token_receipts_present'] for a in arms),
           'total_model_calls':sum(a['reported_usage']['total_calls'] for a in arms),
           'repair_calls':sum(a['repair_calls'] for a in arms),
           'precommit_warnings':sum(a['precommit_warnings'] for a in arms),
           'precommit_probe_wall_s':round(sum(a['precommit_probe_wall_s'] for a in arms),6),
           'total_continuation_wall_s':round(sum(a['continuation_plus_inference_wall_s'] for a in arms),6)}
    base=summary[POLICIES[0]];fl=summary[POLICIES[1]]
    wins=sum(not r['arms'][POLICIES[0]]['independent_final_cases']['all_pass'] and r['arms'][POLICIES[1]]['independent_final_cases']['all_pass'] for r in records)
    losses=sum(r['arms'][POLICIES[0]]['independent_final_cases']['all_pass'] and not r['arms'][POLICIES[1]]['independent_final_cases']['all_pass'] for r in records)
    equal_quality=(wins==losses)
    saved=base['total_reported_tokens']-fl['total_reported_tokens']
    warning_analysis={}
    for policy in POLICIES:
        c={'tp':0,'fp':0,'fn':0,'tn':0}
        for r in records:
            warning=r['arms'][policy]['precommit_history'][0]['result']['status']!='PASS'
            failed=not r['retrospective_initial_proposal_grade']['pass']
            c['tp' if warning and failed else 'fp' if warning else 'fn' if failed else 'tn']+=1
        c['warning_sensitivity_to_final_test_failure']=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None
        c['false_alarm_fraction_when_initial_code_is_correct']=c['fp']/(c['fp']+c['tn']) if c['fp']+c['tn'] else None
        c['lead_time_agent_steps']=0
        c['verified_downstream_stages_saved']=None
        warning_analysis[policy]=c
    return {'arms':summary,'initial_proposal_warning_analysis':warning_analysis,'paired':{'tasks':alln,'fl_only_approved':wins,'baseline_only_approved':losses,
           'net_quality_gain_tasks':wins-losses,'absolute_token_difference_baseline_minus_fl':saved,
           'incremental_token_reduction_fraction':saved/base['total_reported_tokens'] if base['total_reported_tokens'] and all(a['all_token_receipts_present'] for a in summary.values()) else None,
           'equal_approval_count':equal_quality,'quality_gate':'UNESTABLISHED_SMALL_PILOT',
           'proven_long_horizon_downstream_cost_avoidance':False,
           'claimed_usd_saved':None,'best_applicable_oss_comparator_executed':False,
           'unofficial_public_benchmark_local_pilot':True}}

def csv_export(run,records):
    with (run/'task_results.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['task','policy','final_pass','cases_passed','cases_total','model_calls','repair_calls','input_tokens','output_tokens','total_tokens','model_seconds','precommit_probe_seconds','total_seconds','extra_precommit_used'])
        for r in records:
            for k,a in r['arms'].items():
                w.writerow([r['task'],k,a['independent_final_cases']['all_pass'],a['independent_final_cases']['passed'],a['independent_final_cases']['total'],
                 a['reported_usage']['total_calls'],a['repair_calls'],a['reported_usage']['input_tokens'],
                 a['reported_usage']['output_tokens'],a['reported_usage']['total_tokens'],a['reported_usage']['model_call_wall_s'],
                 a['precommit_probe_wall_s'],a['continuation_plus_inference_wall_s'],a['extra_precommit_used']])

def execute(run_dir,model='qwen2.5:1.5b',tasks=TASKS,source_dir=None,invoke=generate,models_fn=installed,source_fn=source_checkout):
    run=pathlib.Path(run_dir);run.mkdir(parents=True,exist_ok=False)
    evidence={'version':VERSION,'evidence_type':'EXECUTED_PUBLIC_QUIXBUGS_PAIRED_CONTINUATIONS_LOCAL_PILOT',
      'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'model':model,
      'requested_tasks':list(tasks),'planned_policies':list(POLICIES),
      'not_swebench':True,'not_official_quixbugs_leaderboard':True,'not_customer_outcomes':True,
      'not_strongest_oss_baseline':True,'not_invoice_cost':True,'no_savings_claim_without_measured_quality':True,
      'firstlight_addition_is_fixed_heuristic_not_calibrated_predictor':True,
      'counterfactual_design':'ONE_SHARED_INITIAL_LLM_PROPOSAL_THEN_EXECUTED_PAIRED_CONTINUATIONS',
      'safety_limit':'AST_FILTER_AND_RESOURCE_BOUNDED_CHILD_NOT_HARDENED_SANDBOX','records':[]}
    try:
        candidates=models_fn()
        if model not in candidates:raise RuntimeError('MODEL_NOT_INSTALLED:'+model)
        data,source_info=source_fn(run,source_dir)
        evidence['source_provenance']=source_info
        for i,name in enumerate(tasks):
            if name not in TASKS or name not in data:raise ValueError('UNKNOWN_TASK:'+name)
            print(f'PUBLIC QUIXBUGS TASK {i+1}/{len(tasks)} {name}: two matched continuations',flush=True)
            order=POLICIES if i%2==0 else tuple(reversed(POLICIES))
            r=paired_task(name,data[name],model,invoke=invoke,policy_order=order)
            evidence['records'].append(r)
            (run/'live_partial_results.json').write_text(json.dumps(evidence,indent=2))
        evidence['status']='COMPLETE_LOCAL_PILOT';evidence['summary']=summarize(evidence['records'])
        csv_export(run,evidence['records'])
    except Exception as e:
        evidence['status']='BLOCKED';evidence['blocker']=type(e).__name__+': '+str(e)[:460]
    (run/'results.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    if (run/'live_partial_results.json').exists():(run/'live_partial_results.json').unlink()
    return evidence

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--model',default='qwen2.5:1.5b');ap.add_argument('--source',default=None);ap.add_argument('--task-limit',type=int,default=6)
    a=ap.parse_args();assert 1<=a.task_limit<=len(TASKS)
    out=execute(a.run,a.model,TASKS[:a.task_limit],a.source)
    print('FIRST LIGHT V5.5 STATUS:',out['status'],'TASKS:',len(out['records']),flush=True)
    if 'blocker' in out:print('ACTUAL BLOCKER:',out['blocker'])
    else:print('PAIRED SUMMARY:',json.dumps(out['summary']['paired'],sort_keys=True),flush=True)
