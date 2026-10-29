"""Strict v3.7 recovery of official SWE-bench grades and original development splits.

Never deduce failure from agent exit_status, absent grades or tool errors.
No current intervention/cost outcome is estimated by these observations.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,statistics
from ail_v36.trajectories import paths,observations,features,sha,MARKS,MIN
from ail_v34.calibration import fit_logistic,offset_calibration,sigmoid,brier,ece,logloss,paired_brier_difference_bootstrap

RESOLVED={'official_resolved','official_grader_resolved','official_exact_resolved'}
NONRESOLVED={'official_nonresolved_complement','official_unresolved','official_grader_unresolved','official_exact_unresolved'}
SPLITS={'train':'train','training':'train','development_train':'train','cal':'calibration',
        'calibration':'calibration','development_calibration':'calibration',
        'validation':'validation','val':'validation','development_validation':'validation',
        'test':'previously_inspected_test','heldout':'previously_inspected_test',
        'held_out':'previously_inspected_test','original_test':'previously_inspected_test'}

def _type_label(x):
    if x is None:return 'null'
    if isinstance(x,bool):return 'bool'
    if isinstance(x,dict):return 'object'
    if isinstance(x,list):return 'array'
    if isinstance(x,int):return 'integer'
    if isinstance(x,float):return 'number'
    return 'string'

def _canonical_submission(row):
    v=row.get('entry')
    if isinstance(v,dict):v=v.get('submission') or v.get('submission_id') or v.get('name')
    return row.get('submission') or row.get('source_submission') or row.get('submission_id') or v

def _parse_target(x):
    if type(x)==bool:return bool(x)
    if type(x)==int and x in (0,1):return bool(x)
    if isinstance(x,dict):
        for k in ('resolved','official_resolved','swebench_resolved'):
            if type(x.get(k)) in (bool,int) and x[k] in (0,1):return bool(x[k])
    return None

def historical_issue_split(instance_id):
    '''Reproduce the documented AIL v0.7 issue-level SHA256 split exactly.'''
    bucket=int(hashlib.sha256(instance_id.encode('utf-8')).hexdigest()[:12],16)%100
    return ('train' if bucket<55 else 'calibration' if bucket<70 else
            'validation' if bucket<85 else 'previously_inspected_test')

def _single_grade(row,submission):
    if not isinstance(row,dict):return None,'not_object',None
    iid=row.get('instance_id')
    entry=_canonical_submission(row)
    if not isinstance(iid,str) or not iid:return None,'missing_id',None
    if not isinstance(entry,str) or entry!=submission:return None,'entry_not_exact_submission',None
    flags=row.get('quality_flags')
    if isinstance(flags,dict) and any(flags.get(k) is False for k in (
            'exact_entry_match','exact_submission_match','graded_identity_match','official_grade_match')):
        return None,'quality_flags_disqualify',None
    src=row.get('outcome_source')
    if not isinstance(src,str):return None,'missing_official_outcome_source',None
    if src in RESOLVED: result=True
    elif src in NONRESOLVED: result=False
    else:return None,'unrecognized_official_outcome_source',None
    target=_parse_target(row.get('target'))
    # target may have an entirely different semantic/shape; only demand agreement
    # if it is explicitly binary. Do not interpret bare target as grader evidence.
    if target is not None and target!=result:
        return None,'contradictory_target_and_official_source',None
    group=row.get('task_group')
    norm=SPLITS.get(group.strip().lower()) if isinstance(group,str) else None
    computed=historical_issue_split(iid)
    # `task_group` may mean repository/family rather than split; preserve the
    # documented *original hash rule*, not a guessed meaning of this field.
    if norm is not None and norm!=computed:
        return None,'contradictory_explicit_split_and_historical_hash',None
    return {'instance_id':iid,'grade':result,'split':computed,'source':src},None,group

def _iter_rows(path,max_rows=20000):
    if path.suffix=='.jsonl':
        with path.open(encoding='utf-8') as f:
            for n,line in enumerate(f,1):
                if n>max_rows:raise ValueError('grade record safety limit exceeded')
                if line.strip():yield json.loads(line)
    else:
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,dict):data=data.get('records',data.get('results'))
        if not isinstance(data,list) or len(data)>max_rows:raise ValueError('Unsupported grade structure')
        yield from data

def read_original_labels(path:Path,submission:str):
    if not path.is_file():return {},{'status':'MISSING_LABEL_SOURCE'}
    keys={};rejected=Counter();schemas=Counter();sources=Counter();groups=Counter()
    for row in _iter_rows(path):
        if isinstance(row,dict):
            schemas.update({f'{k}:{_type_label(v)}' for k,v in row.items()})
            if isinstance(row.get('outcome_source'),str):sources[row['outcome_source']]+=1
            if isinstance(row.get('task_group'),str):groups[row['task_group']]+=1
        outcome,reason,_=_single_grade(row,submission)
        if reason:rejected[reason]+=1;continue
        key=(submission,outcome['instance_id'])
        if key in keys:
            if keys[key]!=outcome:raise ValueError('Contradictory duplicate independently graded case')
            rejected['exact_duplicate']+=1;continue
        keys[key]=outcome
    return keys,{'status':'OFFICIAL_LABEL_PROVENANCE_CHECKED','records':len(keys),
                 'outcome_source_counts':dict(sources),'original_group_counts':dict(groups),
                 'rejected':dict(rejected),'schema_type_counts':dict(sorted(schemas.items())),
                 'label_sha256':sha(path),'reason':'Only exact submission, recognized official result source and preserved original split accepted'}

def join(directory:Path,grades:Path,submission:str):
    labels,info=read_original_labels(grades,submission)
    all_files=paths(directory); rejection=Counter();records=[]
    for p in all_files:
        try:
            row=json.loads(p.read_text(encoding='utf-8'))
            if not isinstance(row,dict) or not isinstance(row.get('messages'),list):
                rejection['no_messages_array']+=1;continue
            iid=row.get('instance_id') or p.name.removesuffix('.traj.json')
            sub=row.get('source_submission') or row.get('submission_id') or submission
            k=(sub,iid)
            if k not in labels:rejection['no_verified_graded_match']+=1;continue
            o=observations(row['messages'])
            if not o:rejection['no_extractable_tool_observations']+=1;continue
            records.append({'episode_id':iid,'submission':sub,'success':labels[k]['grade'],
                            'split':labels[k]['split'],'observations':o,'trace_sha256':sha(p)})
        except (OSError,ValueError,TypeError,UnicodeDecodeError,json.JSONDecodeError):
            rejection['corrupted_trajectory']+=1
    seen=set()
    for r in records:
        k=(r['submission'],r['episode_id'])
        if k in seen:raise ValueError('Duplicate observed episode')
        seen.add(k)
    records.sort(key=lambda r:(r['split'],r['episode_id']))
    return records,{'discovered_trajectory_files':len(all_files),'joined_episodes':len(records),
      'label_source':info,'join_rejection_counts':dict(rejection),'modality':'text_tool',
      'no_raw_data_exported':True,'trajectory_dir_sha256':hashlib.sha256(str(directory).encode()).hexdigest(),
      'grade_source_file_sha256':sha(grades)}

def _metrics(ps,ys):
    return {'brier':round(brier(ps,ys),6),'log_loss':round(logloss(ps,ys),6),
            'ece_5_bin':round(ece(ps,ys),6),'failure_rate':round(sum(ys)/len(ys),6)}

def evaluate(episodes,provenance):
    splits={n:[r for r in episodes if r['split']==n] for n in
            ('train','calibration','validation','previously_inspected_test')}
    report={'version':'v3.7','status':'HOLD','data_provenance':provenance,
      'cohort_counts':{k:len(v) for k,v in splits.items()},
      'evidence_kind':'HISTORICAL_OBSERVED_MINISWEAGENT_PREDICTION',
      'statistical_split':'PRESERVED_ORIGINAL_ISSUE_GROUPS_NOT_REPARTITIONED',
      'original_test':'PREVIOUSLY_INSPECTED_NOT_USED_FOR_MODEL_EVALUATION',
      'validation':'ALREADY_EXPLORED_IN_PAST_AIL_VERSIONS; NO VIRGIN_HOLDOUT',
      'causal_policy_savings':'UNIDENTIFIED', 'commercial_savings':'NOT_EVALUATED',
      'deployment_eligible':False,'independent_customer_approval':'NOT_OBSERVED',
      'models_fitted':0,'landmarks':[]}
    if len(episodes)<100 or any(len(splits[k])<MIN[{'validation':'test'}.get(k,k)] for k in ('train','calibration','validation')):
        report['status']='HOLD_INSUFFICIENT_ORIGINAL_SPLIT_SUPPORT';return report
    for mark in MARKS:
        sub={s:[r for r in v if len(r['observations'])>=mark] for s,v in splits.items() if s!='previously_inspected_test'}
        n={s:len(v) for s,v in sub.items()};bad={s:sum(not r['success'] for r in v) for s,v in sub.items()}
        q={'mark':mark,'n':n,'failures':bad,'status':'HOLD','prediction_target':'ORIGINAL_AGENT_FINAL_FAILURE'}
        if any(n[k]<MIN[{'validation':'test'}.get(k,k)] or bad[k]<MIN['failure_'+{'validation':'test'}.get(k,k)] or n[k]-bad[k]<MIN['failure_'+{'validation':'test'}.get(k,k)] for k in sub):
            q['status']='HOLD_INSUFFICIENT_POSITIVE_NEGATIVE_LABEL_SUPPORT';report['landmarks'].append(q);continue
        tr,ca,te=(sub[k] for k in ('train','calibration','validation'))
        X=[features(x['observations'],mark) for x in tr];ys=[int(not r['success']) for r in tr]
        w,b=fit_logistic(X,ys)
        z=[b+sum(u*v for u,v in zip(w,features(r['observations'],mark))) for r in ca]
        sh=offset_calibration(z,[int(not r['success']) for r in ca])
        p=[sigmoid(b+sh+sum(u*v for u,v in zip(w,features(r['observations'],mark)))) for r in te]
        yt=[int(not r['success']) for r in te]
        # calibrated single-feature baseline and constant prevalence model
        x1=[[v[0]] for v in X];w1,b1=fit_logistic(x1,ys)
        z1=[b1+w1[0]*features(r['observations'],mark)[0] for r in ca]
        sh1=offset_calibration(z1,[int(not r['success']) for r in ca])
        p1=[sigmoid(b1+sh1+w1[0]*features(r['observations'],mark)[0]) for r in te]
        pc=[(sum(ys)+.5)/(len(ys)+1)]*len(te)
        ci1=paired_brier_difference_bootstrap(p,pc,yt,[r['episode_id'] for r in te],400)
        ci2=paired_brier_difference_bootstrap(p,p1,yt,[r['episode_id'] for r in te],400)
        q.update(status='EXPLORATORY_HISTORICAL_VALIDATION_ONLY',model=_metrics(p,yt),
          constant=_metrics(pc,yt),simple=_metrics(p1,yt),
          paired_brier_delta_vs_constant_CI95=ci1,paired_brier_delta_vs_simple_CI95=ci2,
          outperforms_simple_on_exploratory_validation=(ci2[1]<0),
          training_cost_not_metered='FITTING_RESOURCES_NOT_DOLLARS',
          action_decisions='NOT_EXECUTED')
        report['models_fitted']+=2
        report['landmarks'].append(q)
    report['status']=('EXPLORATORY_HISTORICAL_PREDICTION_EVALUATED_NO_CAUSAL_SAVINGS' if report['models_fitted'] else 'HOLD_INSUFFICIENT_LANDMARK_SUPPORT')
    return report
