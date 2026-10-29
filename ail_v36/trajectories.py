"""Observed mini-SWE-agent landmark study; never estimates causal savings.

Only original local trajectories and separately matched official graded outcome
records are eligible. Terminal `Submitted` is NOT an independent success label.
No trajectory actions are executed; JSON data is read only.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, math, random, re, statistics
from ail_v34.calibration import fit_logistic, offset_calibration, sigmoid, brier, ece, logloss, paired_brier_difference_bootstrap

MARKS=(4,8,12,16,24)
MIN={'train':60,'calibration':20,'test':20,'failure_train':8,'failure_calibration':3,'failure_test':3}
ERROR_RE=re.compile(r'\b(error|traceback|failed|exception|not found|denied)\b',re.I)
TEST_RE=re.compile(r'\b(pytest|unittest|cargo test|go test|npm test)\b',re.I)
RETURN_RE=re.compile(r'<returncode>\s*(-?\d+)\s*</returncode>',re.I)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(262144),b''):h.update(b)
    return h.hexdigest()

def paths(root:Path,limit=600):
    if not root.is_dir():return []
    candidates=sorted(root.rglob('*.traj.json'))
    if len(candidates)>limit:raise ValueError('Too many trajectory files; narrow input to one graded cohort')
    return candidates

def parse_binary(x):
    if type(x)==bool:return x
    if type(x)==int and x in (0,1):return bool(x)
    return None

def parse_label(obj):
    """Only exact, explicitly graded result fields, never terminal exit_status."""
    if not isinstance(obj,dict):return None
    containers=[obj]
    for k in ('grade','result','evaluation','outcome'):
        if isinstance(obj.get(k),dict):containers.append(obj[k])
    for c in containers:
        for k in ('resolved','is_resolved','grader_resolved','official_resolved','swebench_resolved','swebench_success','success','is_success'):
            if k in c:
                v=parse_binary(c[k])
                if v is not None:return v
    return None

def read_grades(path:Path,source_submission:str|None=None):
    """Separate grade manifest. Must join by (submission, instance_id)."""
    if not path.is_file():return {}, {'status':'MISSING_OFFICIAL_GRADES'}
    if path.suffix=='.jsonl':
        data=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    else:
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,dict):
            if 'results' in data:data=data['results']
            elif 'records' in data:data=data['records']
            else:data=[{**v,'instance_id':k} for k,v in data.items() if isinstance(v,dict)]
    if not isinstance(data,list):raise ValueError('Grades must be JSON list, JSONL or object of records')
    res={};rejected=Counter()
    for row in data:
        if not isinstance(row,dict):rejected['non_object']+=1;continue
        iid=row.get('instance_id') or row.get('task_id') or row.get('id')
        sub=row.get('submission') or row.get('submission_id') or row.get('source_submission') or source_submission
        grade=parse_label(row)
        if grade is None or not isinstance(iid,str) or not isinstance(sub,str):
            rejected['missing_explicit_grade_or_identity']+=1;continue
        key=(sub,iid)
        if key in res and res[key]!=grade:raise ValueError('Conflicting independently graded outcome for '+repr(key))
        res[key]=grade
    return res, {'status':'GRADES_INDEXED','records':len(res),'rejected':dict(rejected),'sha256':sha(path),'source':str(path)}

def _timestamp(messages):
    stamps=[]
    for m in messages:
        if m.get('role')=='assistant' and isinstance(m.get('extra'),dict):
            t=m['extra'].get('timestamp')
            if type(t) in (float,int) and 946684800<t<2000000000:stamps.append(float(t))
    return min(stamps) if stamps else None

def observations(msgs):
    """Build tool-return observations seen BEFORE the next assistant call."""
    ans=[];last_command=None
    for m in msgs:
        if not isinstance(m,dict):continue
        role=m.get('role');extra=m.get('extra')
        if not isinstance(extra,dict):extra={}
        if role=='assistant':
            ac=extra.get('actions')
            if isinstance(ac,list) and ac and isinstance(ac[0],dict):
                last_command=str(ac[0].get('command') or '')[:256]
            continue
        if role not in ('user','tool'):continue
        has_ret='returncode' in extra
        body=m.get('content') if isinstance(m.get('content'),str) else ''
        tag=RETURN_RE.search(body)
        if not has_ret and not tag:continue
        code=extra.get('returncode') if has_ret else int(tag.group(1))
        if type(code) is not int:continue
        ans.append({'bad':int(code!=0),'error_text':int(bool(ERROR_RE.search(body))),
                    'test_cmd':int(bool(TEST_RE.search(last_command or ''))),
                    'repeat':int(bool(last_command and len(ans) and last_command==ans[-1].get('cmd'))),
                    'output_chars':len(body),'cmd':last_command or ''})
    return ans

def features(obs,mark):
    a=obs[:mark]; n=len(a);last=a[-4:]
    return [sum(x['bad'] for x in a)/n,
            sum(x['bad'] for x in last)/len(last),
            sum(x['repeat'] for x in a)/n,
            sum(x['error_text'] for x in a)/n,
            sum(x['test_cmd'] for x in a)/n,
            min(1.,math.log1p(sum(x['output_chars'] for x in a))/15)]

def load_episodes(directory,grades_path,submission,limit=600):
    grade_map,grade_info=read_grades(grades_path,submission)
    discovered=paths(directory,limit)
    records=[];reject=Counter()
    for path in discovered:
        try:
            obj=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(obj,dict) or not isinstance(obj.get('messages'),list):reject['malformed_trajectory']+=1;continue
            iid=obj.get('instance_id') or path.name.removesuffix('.traj.json')
            sub=obj.get('source_submission') or obj.get('submission_id') or submission
            if not sub or (sub,iid) not in grade_map:reject['no_exact_official_grade_join']+=1;continue
            obs=observations(obj['messages'])
            ts=_timestamp(obj['messages'])
            if len(obs)<min(MARKS):reject['too_few_tool_observations']+=1;continue
            if ts is None:reject['missing_start_timestamp']+=1;continue
            records.append({'episode_id':iid,'submission':sub,'success':grade_map[(sub,iid)],'observations':obs,'timestamp':ts,'sha256':sha(path)})
        except (OSError,UnicodeDecodeError,ValueError,TypeError,json.JSONDecodeError):reject['unreadable_or_corrupt']+=1
    if len({(r['submission'],r['episode_id']) for r in records})!=len(records):raise ValueError('Duplicate joined episodes')
    records.sort(key=lambda r:(r['timestamp'],r['episode_id']))
    return records,{'discovered_trajectory_files':len(discovered),'exact_graded_join_count':len(records),
                    'rejected':dict(reject),'official_grade_manifest':grade_info,
                    'traces_directory':str(directory),'submission':submission}

def _metrics(ps,ys):
    return {'brier':round(brier(ps,ys),6),'logloss':round(logloss(ps,ys),6),
            'ece_5bin':round(ece(ps,ys),6),'failure_rate':round(sum(ys)/len(ys),6)}

def study(episodes,origin):
    base={'version':'v3.6.0','evidence_kind':'OBSERVED_HISTORICAL_AGENT_TRAJECTORY_PREDICTION',
          'data_provenance':origin,'deployment_eligible':False,
          'causal_savings':'NOT_IDENTIFIED_HISTORICAL_TRAJECTORIES',
          'independent_customer_approval':'NOT_MEASURED','modality':'tool',
          'labels':'INDEPENDENT_OFFICIAL_SWEBENCH_FINAL_GRADE','landmarks':[],
          'split_method':'CHRONOLOGICAL_EPISODE_START_TIMESTAMP_60_20_20'}
    N=len(episodes)
    if N<100:return {**base,'status':'HOLD_INSUFFICIENT_JOINED_OBSERVED_TRAJECTORIES','joined_episodes':N}
    t=max(1,int(.6*N));c=max(t+1,int(.8*N))
    part={'train':episodes[:t],'calibration':episodes[t:c],'test':episodes[c:]}
    overlap=set((r['submission'],r['episode_id']) for r in part['train']) & set((r['submission'],r['episode_id']) for r in part['test'])
    if overlap:raise AssertionError('episode train/test leakage')
    base['joined_episodes']=N;base['splits']={k:len(v) for k,v in part.items()}
    base['timeline']={k:{'first_utc':datetime.fromtimestamp(v[0]['timestamp'],timezone.utc).isoformat(),
                         'last_utc':datetime.fromtimestamp(v[-1]['timestamp'],timezone.utc).isoformat()} for k,v in part.items()}
    for mark in MARKS:
        records={k:[r for r in v if len(r['observations'])>=mark] for k,v in part.items()}
        sizes={k:len(v) for k,v in records.items()}
        failed={k:sum(not x['success'] for x in v) for k,v in records.items()}
        entry={'landmark_tool_observation':mark,'counts':sizes,'failed':failed,'cohort':'AGENTS_REACHING_THIS_LANDMARK',
               'causal_intervention_value':'NOT_ESTIMATED'}
        insufficient=[k for k in sizes if sizes[k]<MIN[k] or failed[k]<MIN['failure_'+k] or (sizes[k]-failed[k])<MIN['failure_'+k]]
        if insufficient:
            entry.update(status='HOLD_INSUFFICIENT_LABEL_VARIATION',problem_splits=insufficient)
        else:
            tr,ca,te=[records[k] for k in ('train','calibration','test')]
            X=[features(x['observations'],mark) for x in tr];y=[int(not x['success']) for x in tr]
            w,b=fit_logistic(X,y)
            z=[b+sum(a*f for a,f in zip(w,features(r['observations'],mark))) for r in ca]
            shift=offset_calibration(z,[int(not r['success']) for r in ca])
            ps=[sigmoid(b+shift+sum(a*f for a,f in zip(w,features(r['observations'],mark)))) for r in te]
            ys=[int(not r['success']) for r in te]
            prevalence=(sum(y)+.5)/(len(y)+1)
            bp=[prevalence]*len(te)
            # Stronger simple baseline: calibrate a one-feature rule on training then calibration.
            ix=0; lrX=[[x[ix]] for x in X]; wr,br=fit_logistic(lrX,y)
            zr=[br+wr[0]*features(r['observations'],mark)[ix] for r in ca]
            dr=offset_calibration(zr,[int(not r['success']) for r in ca])
            rp=[sigmoid(br+dr+wr[0]*features(r['observations'],mark)[ix]) for r in te]
            ci=paired_brier_difference_bootstrap(ps,bp,ys,[r['episode_id'] for r in te],400)
            cir=paired_brier_difference_bootstrap(ps,rp,ys,[r['episode_id'] for r in te],400)
            entry.update(status='HISTORICAL_PREDICTION_EVALUATED_SHADOW_ONLY',
                         model=_metrics(ps,ys),simple_recent_error_baseline=_metrics(rp,ys),
                         constant_baseline=_metrics(bp,ys),
                         model_minus_constant_brier_95ci=ci,model_minus_simple_rule_brier_95ci=cir,
                         predictive_increment_over_constant_supported=ci[1]<0,
                         predictive_increment_over_simple_rule_supported=cir[1]<0,
                         outcome_variation={'test_success':len(te)-sum(ys),'test_failure':sum(ys)},
                         calibration_offset=round(shift,6))
        base['landmarks'].append(entry)
    base['status']='HISTORICAL_PREDICTION_EVALUATED_NO_CAUSAL_SAVINGS' if any(x['status'].startswith('HISTORICAL') for x in base['landmarks']) else 'HOLD_INSUFFICIENT_LANDMARK_SUPPORT'
    return base
