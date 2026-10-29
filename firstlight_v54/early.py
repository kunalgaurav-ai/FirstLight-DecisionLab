"""Separate retrospective prefix-only monitor assessment for annotated public/user-authorized traces.

Read-only, no gold passed into detector; NOT a randomized continuation, provider
cost savings, safe error localization on live tools, or a customer success study.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib


def evaluate_trace(trace,threshold=0.8):
    tid=trace.get('trace_id')
    events=trace.get('events')
    if not isinstance(tid,str) or not tid or not isinstance(events,list) or not events:
        raise ValueError('INVALID_TRACE')
    success=trace.get('terminal_success')
    if not isinstance(success,bool):raise ValueError('REQUIRES_TRUE_TERMINAL_SUCCESS_LABEL')
    first_error=trace.get('failure_step')
    if success and first_error is not None:raise ValueError('SUCCESS_WITH_FAILURE_STEP')
    if not success and (not isinstance(first_error,int) or isinstance(first_error,bool) or first_error<1):
        raise ValueError('FAILURE_REQUIRES_ANNOTATED_FAILURE_STEP')
    previous=0;alarm_at=None;read_ms=0.0
    for evt in events:
        step=evt.get('step');value=evt.get('precommit_risk_score')
        if not isinstance(step,int) or isinstance(step,bool) or step<=previous:raise ValueError('BAD_EVENT_STEPS')
        if not isinstance(value,(int,float)) or not 0<=value<=1:raise ValueError('BAD_PREFIX_SCORE')
        if set(evt)&{'final_outcome','failure_step','ground_truth','future_events','terminal_success'}:
            raise ValueError('FUTURE_LABEL_INSIDE_PREFIX_EVENT')
        previous=step
        read_ms+=float(evt.get('detector_wall_ms',0))
        if alarm_at is None and value>=threshold:alarm_at=step
    if first_error is not None and first_error>previous:raise ValueError('FAILURE_STEP_AFTER_TRACE')
    early=(alarm_at is not None and not success and alarm_at<=first_error)
    late=(alarm_at is not None and not success and alarm_at>first_error)
    return {'trace_id':tid,'terminal_success':success,'error_step':first_error,
        'first_alarm_step':alarm_at,'flag_before_or_at_annotated_error':early,
        'alarm_after_annotated_error':late,'lead_steps':first_error-alarm_at if early else None,
        'detector_wall_ms_reported':read_ms,
        'classification':('FALSE_ALARM' if success and alarm_at is not None else
            'SAFE_NO_ALARM' if success else 'EARLY_DETECTION' if early else
            'LATE_ALARM' if late else 'MISSED_ERROR')}


def run_file(input_path,output_path,threshold=0.8):
    source=pathlib.Path(input_path)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    lines=[json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if not lines:raise ValueError('NO_TRAJECTORIES')
    trials=[evaluate_trace(x,threshold) for x in lines]
    if len(set(x['trace_id'] for x in trials))!=len(trials):raise ValueError('DUPLICATE_TRACE_ID')
    counts={k:sum(x['classification']==k for x in trials) for k in ('FALSE_ALARM','SAFE_NO_ALARM','EARLY_DETECTION','LATE_ALARM','MISSED_ERROR')}
    safe=counts['FALSE_ALARM']+counts['SAFE_NO_ALARM']
    failed=counts['EARLY_DETECTION']+counts['LATE_ALARM']+counts['MISSED_ERROR']
    summary={'kind':'RETROSPECTIVE_PUBLIC_OR_USER_ANNOTATED_PREFIX_EVALUATION',
        'not_a_causal_cost_savings_result':True,'not_prospective':True,
        'independent_label_provenance':'USER_SUPPLIED_NOT_VERIFIED','source_sha256':digest,
        'threshold_fixed':threshold,'n_traces':len(trials),'safe_traces':safe,'failed_traces':failed,
        'detection_rate_at_or_before_error':counts['EARLY_DETECTION']/failed if failed else None,
        'false_alarm_rate_per_safe_trajectory':counts['FALSE_ALARM']/safe if safe else None,
        'counts':counts,'trials':trials,'usd_cost_saved':None,
        'inference_tokens_avoided':None,'counterfactual_continuations_executed':0}
    pathlib.Path(output_path).write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return summary


def summarize_bfcl(results):
    """Stage-boundary warnings: schema checks are not semantic error predictors."""
    observed=[]
    for row in results.get('eval',[]):
        for a in row.get('arms',{}).values():
            d=a.get('first_call_diagnostic') or {}
            if d.get('status')!='SCORED_DIAGNOSTIC':continue
            observed.append({'task':row['id'],'policy':a['policy'],
                'schema_warning_before_commit':bool(a['precommit_schema_alarm']),
                'diagnostic_first_call_failure':not bool(d['pass'])})
    figures={}
    for p in sorted(set(x['policy'] for x in observed)):
        xs=[x for x in observed if x['policy']==p]
        mistakes=[x for x in xs if x['diagnostic_first_call_failure']]
        found=sum(x['schema_warning_before_commit'] for x in mistakes)
        figures[p]={'observed_attempts':len(xs),'incorrect_first_attempts':len(mistakes),
            'incorrect_and_schema_flagged':found,'incorrect_but_schema_valid':len(mistakes)-found,
            'sensitivity_to_local_diagnostic_failure':found/len(mistakes) if mistakes else None,
            'stage_lead_time':0,'dollars_avoided':None,'real_downstream_continuation':False}
    return {'kind':'BFCL_PRECOMMIT_SCHEMA_WARNING_VS_LOCAL_DIAGNOSTIC','version':'5.4.0',
        'figures':figures,'interpretation':'A structural validity check before a single tool call; not a sequential agent failure predictor',
        'false_alarm_burden_recoverability_and_cost_savings':'NOT_ESTABLISHED',
        'independent_long_horizon_error_labels':'MISSING'}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--threshold',type=float,default=0.8);a=ap.parse_args()
    print(json.dumps(run_file(a.input,a.output,a.threshold)['counts'],indent=2))
