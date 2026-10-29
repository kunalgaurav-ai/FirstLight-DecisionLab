"""First Light v5.4: holdout BFCL screening and matched optimizer-policy comparison.

A local BFCL *diagnostic*, not official BFCL grading, SWE-bench, OSS installation,
independent customer approval or USD inference benchmarking.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import math
import os
import time
from pathlib import Path
from firstlight_v5.core import OFFICIAL_FILES, json_dump, read_items, sample_rows, prepare_prompt, score_diagnostic, sha, tool_specs
from firstlight_v5.runner import fetch_official, ollama_models, attempt
from firstlight_v53.matrix import reuse_verified_dataset, discover_dataset_paths
from .ollama import safe_attempt

CANDIDATES=(
    'qwen2.5:0.5b', 'qwen2.5:1.5b', 'qwen2.5:3b',
    'qwen3:0.6b','qwen3:1.7b','qwen3:4b',
    'llama3.2:1b','llama3.2:3b',
    'gemma3:1b','gemma3:4b','qwen2.5-coder:3b',
)
CHEAP='qwen2.5:0.5b'
POLICIES=('SINGLE_TARGET','GUARDED_TARGET','COMPETENT_CHEAP_FIRST','FIRSTLIGHT_CONSTRAINED')
SOURCE_GROUPS=tuple(OFFICIAL_FILES)


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


def gold_lookup(directory):
    return {g:{r['id']:r for r in read_items(directory/'possible_answer'/f)} for g,f in OFFICIAL_FILES.items()}


def disjoint_cohorts(grouped,screen_n,eval_n):
    if screen_n<=0 or eval_n<=0:raise ValueError('COHORT_LIMIT_INVALID')
    selections=sample_rows(grouped,screen_n+eval_n,seed='FIRSTLIGHT_V54_FROZEN_SEED')
    if len(selections)<screen_n+eval_n:raise ValueError('INSUFFICIENT_PUBLIC_BENCHMARK_ITEMS')
    a=selections[:screen_n];b=selections[screen_n:]
    if len({r['id'] for _,r in a}&{r['id'] for _,r in b}):raise ValueError('COHORT_LEAKAGE')
    return a,b


def score(call,reference):
    if reference is None:return {'status':'REFERENCE_MISSING'}
    prediction=None if not call else (call['name'],call['arguments'])
    return score_diagnostic(prediction,reference)


def attempt_sum(calls):
    return {
        'call_count':len(calls),
        'input_tokens':sum(a.get('input_tokens') or 0 for a in calls),
        'output_tokens':sum(a.get('output_tokens') or 0 for a in calls),
        'reported_tokens':sum((a.get('input_tokens') or 0)+(a.get('output_tokens') or 0) for a in calls),
        'sum_model_wall_s':round(sum(a.get('wall_s') or 0 for a in calls),6),
        'billed_usd':None,
    }


def run_one(row,model,policy,calibration,call_fn=safe_attempt,cheap=CHEAP):
    """Only schema/tool-count and frozen calibration influence decisions; never gold."""
    if policy not in POLICIES:raise ValueError('UNKNOWN_POLICY')
    if policy=='FIRSTLIGHT_CONSTRAINED':
        group=row.get('_group','UNKNOWN')
        selected=bool(calibration.get(model,{}).get(group,{}).get('strong_preflight'))
        first=model if selected else cheap
        reason='CALIBRATED_STRONG_PREFLIGHT' if selected else 'FALLBACK_COMPETENT_CHEAP_FIRST'
    elif policy in ('SINGLE_TARGET','GUARDED_TARGET'):
        first=model;reason='TARGET_FIRST'
    else:
        first=cheap;reason='COMPETENT_CHEAP_FIRST'
    t0=time.perf_counter()
    first_call=call_fn(first,row,strict=True)
    calls=[first_call]
    warning=first_call.get('status')=='OK' and first_call.get('call') is None
    if first_call.get('status')!='OK':
        final=first_call;state='BLOCKED_MODEL';reason='MODEL_CALL_ERROR'
    elif warning and policy!='SINGLE_TARGET':
        replacement=model
        # Guarded and cheap-first use the exact same schema failure criterion.
        second=call_fn(replacement,row,strict=True,corrective=True)
        calls.append(second)
        final=second
        reason+='; SCHEMA_RETRY' if policy=='GUARDED_TARGET' else '; SCHEMA_ESCALATION'
        state='COMPLETE' if second.get('status')=='OK' else 'BLOCKED_MODEL'
    else:
        final=first_call
        state='COMPLETE'
    total=round(time.perf_counter()-t0,6)
    return {'model':model,'policy':policy,'status':state,'decision':reason,
            'first_model':first,'precommit_schema_alarm':warning,
            'first_call_diagnostic':None, # populated AFTER execution, never read by policy
            'result':final.get('call'), 'calls':calls,
            'controller_plus_model_wall_s':total,
            'instrumentation_plus_validation_wall_s':max(0,round(total-sum((x.get('wall_s') or 0) for x in calls),6)),
            **attempt_sum(calls)}


def screen_summary(records,models):
    """All 11 candidate models (when physically available), screening only.

    Screening outputs are model-selection evidence, NOT untouched heldout.
    """
    result={}
    for model in models:
        entries=[r['attempts'][model] for r in records if model in r['attempts']]
        graded=[x for x in entries if x.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
        hits=sum(bool(x['diagnostic']['pass']) for x in graded)
        result[model]={'model':model,'policy':'MODEL_SCREEN_ONLY','attempted':len(entries),
             'expected':len(records),'scored':len(graded),'passed':hits,
             'diagnostic_rate':hits/len(graded) if graded else None,
             'reported_tokens':sum((x.get('input_tokens') or 0)+(x.get('output_tokens') or 0) for x in entries),
             'summed_stage_wall_s':round(sum(x.get('wall_s') or 0 for x in entries),3),
             'finished_all_tasks':len(entries)==len(records) and all(x.get('status')=='OK' for x in entries),
             'cannot_be_reported_as_holdout':True}
    return result


def calibrate(screen,models,min_support=12):
    """Conservative, population-specific retrospective preflight selection.

    A model receives authorization only if its screened group pass rate beats
    the cheap anchor by >=0.20 and there are >=12 paired gold-scored examples.
    This is an engineering screening rule, NOT a calibrated risk estimate.
    """
    out={}
    for model in models:
        out[model]={}
        for group in SOURCE_GROUPS:
            pairs=[]
            for r in screen:
                if r['group']!=group:continue
                a=r['attempts'].get(CHEAP,{}).get('diagnostic',{})
                b=r['attempts'].get(model,{}).get('diagnostic',{})
                if a.get('status')=='SCORED_DIAGNOSTIC' and b.get('status')=='SCORED_DIAGNOSTIC':
                    pairs.append((bool(a['pass']),bool(b['pass'])))
            cheap_hits=sum(x for x,y in pairs);strong_hits=sum(y for x,y in pairs)
            eligible=(model!=CHEAP and len(pairs)>=min_support and 0<cheap_hits<len(pairs) and strong_hits>cheap_hits)
            # Conservative fixed gap on screened cases; must NOT be sold as proven calibrated.
            go=bool(eligible and (strong_hits-cheap_hits)/len(pairs)>=0.2)
            out[model][group]={'screened_pairs':len(pairs),'cheap_passes':cheap_hits,'target_passes':strong_hits,
                'strong_preflight':go,'status':'SCREENED_RULE_GO' if go else 'HOLD_COMPETENT_FALLBACK',
                'confidence':'NOT_STATISTICALLY_CALIBRATED','rule_min_support':min_support,
                'rule_required_pass_gap':0.2}
    return out


def pick_finalists(screen,models,n):
    def order(m):
        xs=[r['attempts'][m] for r in screen if m in r['attempts']]
        scored=[x for x in xs if x['diagnostic'].get('status')=='SCORED_DIAGNOSTIC']
        rate=sum(bool(x['diagnostic']['pass']) for x in scored)/len(scored) if scored else -1
        time_sum=sum(x.get('wall_s',0) for x in xs)
        return (-rate,time_sum,m)
    others=sorted((m for m in models if m!=CHEAP),key=order)
    if CHEAP not in models:raise ValueError('CHEAP_ANCHOR_MISSING')
    return [CHEAP]+others[:max(0,n-1)]


def compute_summary(rows,finalists):
    summ={};every=len(rows)
    for model in finalists:
        for policy in POLICIES:
            key=model+'|'+policy
            parts=[r['arms'][key] for r in rows if key in r['arms']]
            grades=[x['diagnostic'] for x in parts if x.get('diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
            summ[key]={'model':model,'policy':policy,'attempted':len(parts),'denominator_expected':every,
                'passed':sum(bool(g['pass']) for g in grades),'scored':len(grades),
                'diagnostic_rate':sum(bool(g['pass']) for g in grades)/len(grades) if grades else None,
                'reported_tokens':sum(x.get('reported_tokens',0) for x in parts),
                'summed_model_wall_s':round(sum(x.get('sum_model_wall_s',0) for x in parts),3),
                'summed_stage_wall_s':round(sum(x.get('controller_plus_model_wall_s',0) for x in parts),3),
                'inference_calls':sum(x.get('call_count',0) for x in parts),
                'finished_all_tasks':len(parts)==every and all(x['status']=='COMPLETE' for x in parts),
                'usd':None,'independently_approved':None}
    for model in finalists:
        # Basic per-matched-case schema warning performance. Not a long-horizon detector.
        k=model+'|FIRSTLIGHT_CONSTRAINED'
        considered=[r['arms'][k] for r in rows if k in r['arms'] and r['arms'][k].get('first_call_diagnostic',{}).get('status')=='SCORED_DIAGNOSTIC']
        tp=sum(x['precommit_schema_alarm'] and not x['first_call_diagnostic']['pass'] for x in considered)
        fn=sum(not x['precommit_schema_alarm'] and not x['first_call_diagnostic']['pass'] for x in considered)
        fp=sum(x['precommit_schema_alarm'] and x['first_call_diagnostic']['pass'] for x in considered)
        tn=sum(not x['precommit_schema_alarm'] and x['first_call_diagnostic']['pass'] for x in considered)
        summ[k]['precommit_detector']={'kind':'SINGLE_TURN_SCHEMA_WARNING_NOT_LONG_HORIZON','tp':tp,'fn':fn,'fp':fp,'tn':tn,
            'lead_time_stages':0,'actual_avoided_downstream_cost':None,'no_claim_of_causal_savings':True}
    return summ


def paired_comparisons(rows,finalists):
    """Paired heldout task outcomes. Small-N McNemar exact p; never causal cost savings."""
    from math import comb
    results={}
    for model in finalists:
        k1=model+'|COMPETENT_CHEAP_FIRST'
        k2=model+'|FIRSTLIGHT_CONSTRAINED'
        pairs=[(r['arms'][k1],r['arms'][k2]) for r in rows
               if k1 in r.get('arms',{}) and k2 in r.get('arms',{})]
        matched=[(a,b) for a,b in pairs
                 if a['status']=='COMPLETE' and b['status']=='COMPLETE' and
                    a['diagnostic'].get('status')=='SCORED_DIAGNOSTIC' and
                    b['diagnostic'].get('status')=='SCORED_DIAGNOSTIC']
        wins=sum(not a['diagnostic']['pass'] and b['diagnostic']['pass'] for a,b in matched)
        losses=sum(a['diagnostic']['pass'] and not b['diagnostic']['pass'] for a,b in matched)
        n=len(matched);d=wins+losses
        pval=min(1.0,2*sum(comb(d,j) for j in range(min(wins,losses)+1))/2**d) if d else (1.0 if n else None)
        tokens_a=sum(a['reported_tokens'] for a,b in matched);tokens_b=sum(b['reported_tokens'] for a,b in matched)
        wall_a=sum(a['controller_plus_model_wall_s'] for a,b in matched)
        wall_b=sum(b['controller_plus_model_wall_s'] for a,b in matched)
        results[model]={'matched_scored_tasks':n,'intended_tasks':len(rows),
            'firstlight_only_passes':wins,'competent_only_passes':losses,
            'paired_pass_rate_difference':(wins-losses)/n if n else None,
            'exact_two_sided_mcnemar_p':pval,
            'competent_tokens_on_matched':tokens_a,'firstlight_tokens_on_matched':tokens_b,
            'firstlight_token_ratio_relative_to_competent':tokens_b/tokens_a if tokens_a else None,
            'competent_total_stage_seconds':round(wall_a,3),
            'firstlight_total_stage_seconds':round(wall_b,3),
            'firstlight_stage_time_ratio_relative_to_competent':wall_b/wall_a if wall_a else None,
            'economic_usd_advantage':None,'independent_quality_noninferiority':'NOT_EVALUATED',
            'right_to_publish_superiority':False}
    return results


def emit_csv(path,rows):
    with Path(path).open('w',newline='',encoding='utf8') as f:
        writer=csv.writer(f)
        writer.writerow(['task_id','group','model','policy','status','scored','diagnostic_pass','first_model',
                         'schema_alarm','calls','reported_tokens','sum_model_seconds','stage_seconds'])
        for r in rows:
            for k,a in sorted(r['arms'].items()):
                writer.writerow([r['id'],r['group'],a['model'],a['policy'],a['status'],a['diagnostic']['status'],
                    a['diagnostic'].get('pass'),a['first_model'],a['precommit_schema_alarm'],a['call_count'],
                    a['reported_tokens'],a['sum_model_wall_s'],a['controller_plus_model_wall_s']])


def run(argv=None,call_fn=safe_attempt):
    ap=argparse.ArgumentParser(description='First Light v5.4 registered BFCL research runner')
    ap.add_argument('--run',required=True)
    ap.add_argument('--screen-limit',type=int,default=24)
    ap.add_argument('--eval-limit',type=int,default=24)
    ap.add_argument('--finalists',type=int,default=3)
    ap.add_argument('--models',default='auto',help='auto for installed members of 11-candidate manifest, or comma-separated tags')
    ap.add_argument('--dataset',default='',help='existing verified official_data directory')
    a=ap.parse_args(argv)
    if not (4<=a.screen_limit<=100 and 4<=a.eval_limit<=200 and 2<=a.finalists<=5):raise ValueError('BAD_STUDY_LIMITS')
    root=Path(a.run).resolve();root.mkdir(parents=True,exist_ok=True)
    present=ollama_models()
    names=list(CANDIDATES) if a.models=='auto' else list(dict.fromkeys(s.strip() for s in a.models.split(',') if s.strip()))
    if not names or any(n not in CANDIDATES for n in names):raise ValueError('UNREGISTERED_MODEL')
    available=[n for n in names if n in present]
    missing=[n for n in names if n not in present]
    report={'brand':'First Light','version':'5.4.0','started_utc':utc(),'state':'PREFLIGHT',
        'benchmark':'BFCL V4 published single-turn subset; unofficial local evaluator',
        'model_candidates':names,'installed_models':available,'missing_models':missing,
        'screen':[],'eval':[],'screen_summary':{},'selection':{},'calibration':{},'summary':{},'paired':{},'source':None,
        'notes':['SCREEN_AND_EVAL_TASKS_DISJOINT','GOLD_NOT_SUPPLIED_TO_INFERENCE','NOT_SWE_BENCH',
                 'NO_INDEPENDENT_TASK_APPROVAL','NO_INVOICE_USD','LOCAL_DIAGNOSTIC_NOT_OFFICIAL_BFCL',
                 'NO_OSS_PACKAGE_IMPLEMENTATION_PROVEN','EARLY_WARNING_SINGLE_TURN_ONLY'],
        'strong_baseline':'COMPETENT_CHEAP_FIRST_WITH_SCHEMA_ESCALATION',
        'policy_precommit':{'candidate_models':CANDIDATES,'policies':POLICIES,'frozen_sample_seed':'FIRSTLIGHT_V54_FROZEN_SEED',
            'min_screen_calibration_per_group':12,'minimum_strong_improvement':0.2,
            'fallback':'COMPETENT_CHEAP_FIRST_WHEN_UNCALIBRATED'}}
    json_dump(root/'results_v54.json',report)
    try:
        if len(available)<2 or CHEAP not in available:raise RuntimeError('INSUFFICIENT_LOCAL_MODELS_NEED_CHEAP_PLUS_ONE')
        source=root/'official_data'
        sources=[Path(a.dataset)] if a.dataset else list(discover_dataset_paths())
        reused=reuse_verified_dataset(source,sources)
        provenance=fetch_official(source)
        report['source']={'commit':provenance['commit'],'files':provenance['files'],'verified_reused_from':reused}
        grouped={g:read_items(source/f) for g,f in OFFICIAL_FILES.items()}
        gold=gold_lookup(source)
        screen,eval_set=disjoint_cohorts(grouped,a.screen_limit,a.eval_limit)
        report['screen_ids']=[r['id'] for g,r in screen]
        report['eval_ids']=[r['id'] for g,r in eval_set]
        report['state']='SCREENING';json_dump(root/'results_v54.json',report)
        # Registered calibration cohort. No model sees reference answers.
        for ix,(g,row) in enumerate(screen,1):
            rec={'id':row['id'],'group':g,'attempts':{}}
            for model in available:
                res=call_fn(model,row,strict=True)
                di=score(res.get('call'),gold[g].get(row['id'])) if res.get('status')=='OK' else {'status':'BLOCKED_MODEL_CALL'}
                rec['attempts'][model]={'status':res.get('status'),'call':res.get('call'),
                    'input_tokens':res.get('input_tokens'),'output_tokens':res.get('output_tokens'),
                    'wall_s':res.get('wall_s',0),'diagnostic':di,'sha256':res.get('sha256')}
            report['screen'].append(rec)
            report['screen_summary']=screen_summary(report['screen'],available)
            json_dump(root/'results_v54.json',report)
            print(f'FIRST LIGHT SCREEN {ix}/{len(screen)} {row["id"]} models={len(available)}',flush=True)
        final=pick_finalists(report['screen'],available,min(a.finalists,len(available)))
        report['selection']={'finalists':final,'not_selected':[m for m in available if m not in final],
            'rule':'cheap anchor plus highest screen diagnostic rate; faster ties; frozen before holdout'}
        report['calibration']=calibrate(report['screen'],final)
        report['state']='HOLDOUT_EVALUATION';json_dump(root/'results_v54.json',report)
        # Evaluate full cohort even if a particular policy fails. No selective omission.
        for ix,(g,row) in enumerate(eval_set,1):
            entry={'id':row['id'],'group':g,'arms':{}}
            policy_row=dict(row);policy_row['_group']=g
            for mi,model in enumerate(final):
                offset=(ix+mi)%len(POLICIES)
                for policy in POLICIES[offset:]+POLICIES[:offset]:
                    rec=run_one(policy_row,model,policy,report['calibration'],call_fn)
                    rec['diagnostic']=score(rec['result'],gold[g].get(row['id'])) if rec['status']=='COMPLETE' else {'status':'BLOCKED_MODEL_CALL'}
                    first=rec['calls'][0]
                    rec['first_call_diagnostic']=score(first.get('call'),gold[g].get(row['id'])) if first.get('status')=='OK' else {'status':'BLOCKED_MODEL_CALL'}
                    entry['arms'][model+'|'+policy]=rec
            report['eval'].append(entry)
            report['summary']=compute_summary(report['eval'],final)
            report['paired']=paired_comparisons(report['eval'],final)
            json_dump(root/'results_v54.json',report)
            print(f'FIRST LIGHT HOLDOUT {ix}/{len(eval_set)} {row["id"]} model_policy_arms={len(entry["arms"])}',flush=True)
        report['state']='COMPLETE_LOCAL_DIAGNOSTIC' if all(a['finished_all_tasks'] and a['scored']==len(eval_set) for a in report['summary'].values()) else 'PARTIAL_INCOMPLETE'
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as e:
        report['state']='BLOCKED' if not report['eval'] and not report['screen'] else 'PARTIAL_BLOCKED'
        report['blocker']=f'{type(e).__name__}: {str(e)[:500]}'
    report['finished_utc']=utc()
    json_dump(root/'results_v54.json',report)
    from .early import summarize_bfcl
    json_dump(root/'early_warning_v54.json', summarize_bfcl(report))
    emit_csv(root/'holdout_rows_v54.csv',report['eval'])
    print('FIRST LIGHT V5.4 REAL BENCHMARK STATUS:',report['state'],'screen:',len(report['screen']),'holdout:',len(report['eval']),flush=True)
    if 'blocker' in report:print('ACTUAL BLOCKER:',report['blocker'],flush=True)
    return report

if __name__=='__main__':run()
