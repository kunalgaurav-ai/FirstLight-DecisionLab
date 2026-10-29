"""Chronological, explicitly labeled empirical calibration, with strict abstention.

Scope: observational prediction of a single actionable defect at precommit.
It is NOT off-policy evaluation or evidence that intervening saves money.
No simulated/constructed tasks are accepted as calibration observations.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import time
from pathlib import Path

FEATURES = {
    'text': ('source_risk', 'tool_error_rate', 'retry_rate', 'progress_stall'),
    'tool': ('tool_error_rate', 'retry_rate', 'progress_stall', 'budget_pressure'),
    'image': ('visual_mismatch_score', 'provenance_risk', 'retry_rate', 'budget_pressure'),
    'video': ('render_warning_rate', 'visual_mismatch_score', 'retry_rate', 'budget_pressure'),
    'audio': ('clipping_fraction', 'spectral_anomaly', 'retry_rate', 'budget_pressure'),
    'mixed': ('upstream_dependency_risk', 'retry_rate', 'progress_stall', 'budget_pressure'),
}
REQUIRED = ('episode_id','checkpoint_utc','label_utc','modality','stage_kind','failure_type',
            'executor_version','checkpoint_bucket','policy_id','independent_adjudicator',
            'label', 'intervened_before_label', 'features')
BASE_MIN = dict(train=80, calibration=40, test=40, positive_train=10, positive_calibration=5, positive_test=5)


def iso_datetime(s):
    if not isinstance(s,str) or not s.endswith(('Z','+00:00')):
        raise ValueError('UTC timestamp required')
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None or d.utcoffset().total_seconds()!=0:
        raise ValueError('UTC timestamp required')
    return d


def _sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<18),b''):
            h.update(b)
    return h.hexdigest()


def _validate_provenance(prov):
    if not isinstance(prov,dict):
        raise ValueError('missing provenance document')
    if prov.get('data_kind') not in {'OBSERVED_REAL_AGENT_TRAJECTORIES','OBSERVED_REAL_WORKFLOW_STAGES'}:
        raise ValueError('data_kind must describe observed real agents or workflow stages')
    for flag in ['rights_authorized','consent_or_permitted_use','independent_adjudication']:
        if prov.get(flag) is not True:
            raise ValueError('data provenance gate: '+flag)
    if not isinstance(prov.get('dataset_id'),str) or len(prov['dataset_id'])<4:
        raise ValueError('dataset_id missing')
    if not isinstance(prov.get('source_description'),str) or len(prov['source_description'])<10:
        raise ValueError('source_description missing')


def read_dataset(dataset_path:Path, provenance_path:Path):
    """Reject entire invalid import; no partial silent record drops."""
    provenance=json.loads(provenance_path.read_text(encoding='utf-8'))
    _validate_provenance(provenance)
    obs=[]; seen=set(); episodes={}
    with dataset_path.open('r',encoding='utf-8') as f:
        for lineno,line in enumerate(f,1):
            if not line.strip():
                continue
            try:
                r=json.loads(line)
                if not isinstance(r,dict):raise ValueError('record not object')
                if not all(k in r for k in REQUIRED):
                    raise ValueError('missing '+str([k for k in REQUIRED if k not in r]))
                if r['modality'] not in FEATURES:raise ValueError('unknown modality')
                for key in ['episode_id','stage_kind','failure_type','executor_version','checkpoint_bucket','policy_id','independent_adjudicator']:
                    if not isinstance(r[key],str) or not r[key].strip():raise ValueError('invalid '+key)
                if r['independent_adjudicator'] in ('self','model_self_rating','unknown'):
                    raise ValueError('not independently adjudicated')
                if r['policy_id']!='INCUMBENT_NO_OPTIONAL_INTERVENTION':
                    raise ValueError('observed record is not an untreated incumbent trajectory')
                if r['intervened_before_label'] is not False:
                    raise ValueError('censored/treated observations cannot be labeled as incumbent outcomes')
                if type(r['label']) is not int or r['label'] not in (0,1):
                    raise ValueError('binary independent label must be 0/1')
                t=iso_datetime(r['checkpoint_utc']); lt=iso_datetime(r['label_utc'])
                if lt<=t:raise ValueError('label must be observed after checkpoint')
                fs=r['features']
                if not isinstance(fs,dict):raise ValueError('features object missing')
                allowed=FEATURES[r['modality']]
                if set(fs)!=set(allowed):raise ValueError('feature schema mismatch for '+r['modality'])
                if any(type(fs[key]) not in (int,float) or not math.isfinite(fs[key]) or not 0<=fs[key]<=1 for key in allowed):
                    raise ValueError('normalized precommit feature outside [0,1]')
                if r.get('evidence_class','OBSERVED')!='OBSERVED':
                    raise ValueError('unobserved/synthetic data not eligible')
                if r.get('future_fields_used',False):raise ValueError('future leakage flag present')
                key=(r['episode_id'],r['modality'],r['stage_kind'],r['failure_type'],r['executor_version'],r['checkpoint_bucket'])
                if key in seen:raise ValueError('duplicate checkpoint per episode and group')
                seen.add(key)
                prev=episodes.get(r['episode_id'])
                # Episode identity is a global split unit, never split one job across partitions.
                if prev is None or t<prev:episodes[r['episode_id']]=t
                r=dict(r);r['_t']=t;r['_lt']=lt
                obs.append(r)
            except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
                raise ValueError(f'line {lineno}: {exc}') from exc
    if not obs:raise ValueError('empty observed dataset')
    return provenance, obs, episodes, {'dataset_sha256':_sha(dataset_path),'provenance_sha256':_sha(provenance_path)}


def sigmoid(x):
    return 1/(1+math.exp(-max(-35,min(35,x))))


def fit_logistic(X,y,epochs=450, ridge=0.6):
    p=len(X[0]); w=[0.]*p
    mu=min(.99,max(.01,(sum(y)+.5)/(len(y)+1)))
    b=math.log(mu/(1-mu))
    # A conservative low-dimensional convex logistic predictor (stdlib CPU only).
    for j in range(epochs):
        db=0.;dw=[0.]*p
        for x,v in zip(X,y):
            d=sigmoid(b+sum(a*z for a,z in zip(w,x)))-v
            db+=d
            for k in range(p):dw[k]+=d*x[k]
        lr=0.6/(1+0.005*j)
        b-=lr*db/len(y)
        for k in range(p):w[k]-=lr*(dw[k]/len(y)+ridge*w[k]/len(y))
    return w,b


def offset_calibration(logits,labels):
    """Calibration-in-the-large on distinct chronological calibration partition."""
    if len(logits)!=len(labels) or not logits:raise ValueError('no calibration split')
    p=(sum(labels)+.5)/(len(labels)+1)
    lo=-15.;hi=15.
    for _ in range(60):
        mid=(lo+hi)/2
        if sum(sigmoid(x+mid) for x in logits)/len(logits)<p:lo=mid
        else:hi=mid
    return (lo+hi)/2


def brier(ps,ys):return sum((p-y)**2 for p,y in zip(ps,ys))/len(ys)
def logloss(ps,ys):
    return -sum(y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p)) for y,p in zip(ys,ps))/len(ys)
def ece(ps,ys):
    acc=0.
    for i in range(5):
        js=[j for j,p in enumerate(ps) if (i/5<=p< (i+1)/5 if i<4 else i/5<=p<=1)]
        if js:acc+=len(js)/len(ys)*abs(sum(ps[j] for j in js)/len(js)-sum(ys[j] for j in js)/len(js))
    return acc


def paired_brier_difference_bootstrap(ps, baseline, ys, episode_ids, repetitions=400):
    """Cluster/bootstrap by independent episode, NEVER treat prefixes as iid."""
    groups={}
    for idx,eid in enumerate(episode_ids):groups.setdefault(eid,[]).append(idx)
    ids=sorted(groups);rng=random.Random(3401);diffs=[]
    for _ in range(repetitions):
        drawn=[rng.choice(ids) for _ in ids]
        indices=[j for eid in drawn for j in groups[eid]]
        d=sum(((ps[j]-ys[j])**2-(baseline[j]-ys[j])**2) for j in indices)/len(indices)
        diffs.append(d)
    diffs.sort()
    return [round(diffs[int(repetitions*.025)],6),round(diffs[int(repetitions*.975)-1],6)]

def wilson(pos,n):
    if not n:return None
    z=1.96;p=pos/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d
    err=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0,mid-err),5),round(min(1,mid+err),5)]


def _vals(r):return [float(r['features'][f]) for f in FEATURES[r['modality']]]


def _metric(ps,ys):
    return {"brier":round(brier(ps,ys),6),"log_loss":round(logloss(ps,ys),6),
            "ece_5bin":round(ece(ps,ys),6),"event_rate":round(sum(ys)/len(ys),6)}


def study(dataset_path:Path|None=None, provenance_path:Path|None=None):
    start_time=time.perf_counter()
    base={"version":"3.4.0-calibration-lab","evidence_kind":"OBSERVATIONAL_PREDICTION_ONLY",
          "policy_eligible":False,"causal_intervention_value":"NOT_IDENTIFIED",
          "cost_per_approved_outcome":None,"quality_noninferiority":"NOT_TESTED",
          "hmm_gate":"HOLD_NO_VALIDATED_SEQUENTIAL_STATE_DATA",
          "design":{"splits":"GLOBAL_EPISODE_CHRONOLOGICAL_60_20_20", "test_seen_in_training":False,
                    "feature_registry":{k:list(v) for k,v in FEATURES.items()},"min_per_group":BASE_MIN}}
    if dataset_path is None or provenance_path is None or not dataset_path.is_file() or not provenance_path.is_file():
        return {**base,"status":"HOLD_NO_AUTHORIZED_OBSERVED_DATASET", "groups":[],
                "reason":"No eligible observed precommit trajectories and independent post-checkpoint defect labels. No statistical calibration executed."}
    try:
        provenance, rows, eps, hashes=read_dataset(dataset_path,provenance_path)
    except (ValueError,OSError,UnicodeDecodeError,json.JSONDecodeError) as exc:
        return {**base,"status":"REJECT_DATASET", "groups":[],"reason":str(exc),
                "dataset_filename":dataset_path.name,"provenance_filename":provenance_path.name}
    unique_ids=sorted(eps, key=lambda key:(eps[key],key))
    n=len(unique_ids)
    if n<3:
        return {**base,"status":"HOLD_TOO_FEW_EPISODES", "total_episodes":n,"groups":[],**hashes}
    first=int(n*.6);second=int(n*.8)
    assignments={key:('train' if i<first else 'calibration' if i<second else 'test') for i,key in enumerate(unique_ids)}
    # Enforce data availability at temporal boundary. Label reported after cutoff cannot train pre-cutoff model.
    cut_train=eps[unique_ids[first]] if first<n else datetime.max.replace(tzinfo=timezone.utc)
    cut_cal=eps[unique_ids[second]] if second<n else datetime.max.replace(tzinfo=timezone.utc)
    groups=defaultdict(lambda:defaultdict(list))
    for r in rows:
        group='|'.join(r[k] for k in ('modality','stage_kind','failure_type','executor_version','checkpoint_bucket'))
        split=assignments[r['episode_id']]
        # Quarantine unavailable labels, don't backfill from future later-labeled episodes.
        if (split=='train' and r['_lt']>cut_train) or (split=='calibration' and r['_lt']>cut_cal):
            groups[group]['quarantined'].append(r);continue
        groups[group][split].append(r)
    outputs=[]
    for key,by in sorted(groups.items()):
        tr=by['train'];ca=by['calibration'];te=by['test']
        sizes={k:len(by[k]) for k in ('train','calibration','test')}
        pos={k:sum(int(r['label']) for r in by[k]) for k in ('train','calibration','test')}
        problems=[]
        for split in ('train','calibration','test'):
            if sizes[split]<BASE_MIN[split]:problems.append('INSUFFICIENT_'+split.upper())
            if pos[split]<BASE_MIN['positive_'+split]:problems.append('TOO_FEW_FAILURES_'+split.upper())
            if sizes[split]-pos[split]<BASE_MIN['positive_'+split]:problems.append('TOO_FEW_NONFAILURES_'+split.upper())
        item={"group":key,"counts":sizes,"failures":pos,"quarantined_post_cutoff_labels":len(by['quarantined']),
              "calibration_method":"RIDGE_LOGISTIC_PLUS_INTERCEPT_ONLY_CHRONOLOGICAL_CALIBRATION",
              "promotion_gate":"SHADOW_ONLY_NEEDS_PROSPECTIVE_ACTION_OUTCOMES"}
        if problems:
            item.update(status='HOLD_INSUFFICIENT_SUPPORT', reasons=problems)
        else:
            features=FEATURES[tr[0]['modality']]
            X=[_vals(r) for r in tr];y=[r['label'] for r in tr]
            w,b=fit_logistic(X,y)
            Z=[b+sum(a*z for a,z in zip(w,_vals(r))) for r in ca]
            shift=offset_calibration(Z,[r['label'] for r in ca])
            test_prob=[sigmoid(b+shift+sum(a*z for a,z in zip(w,_vals(r)))) for r in te]
            prevalence=(sum(y)+.5)/(len(y)+1)
            base_probs=[prevalence]*len(te)
            ys=[r['label'] for r in te]
            metric=_metric(test_prob,ys);baseline=_metric(base_probs,ys)
            # Prediction proof and policy proof are different gates. No model autopromotion.
            item.update(status='PREDICTION_STUDY_COMPLETE_SHADOW_ONLY', features=list(features),
                        observed_test_event_rate_wilson95=wilson(sum(ys),len(ys)),
                        predictive_model=metric, incumbent_prevalence_baseline=baseline,
                        model_brier_minus_baseline=round(metric['brier']-baseline['brier'],6),
                        paired_episode_bootstrap_brier_difference_95=paired_brier_difference_bootstrap(test_prob,base_probs,ys,[r['episode_id'] for r in te]),
                        prediction_outperforms_constant_on_test=metric['brier']<baseline['brier'],
                        calibration_intercept=round(shift,6),
                        model_coefficient_vector=[round(v,6) for v in w],
                        prospective_action_effect='UNIDENTIFIED')
        outputs.append(item)
    return {**base,"status":"SHADOW_REPORT_ONLY" if outputs else 'HOLD_NO_ELIGIBLE_GROUPS',
            "dataset_id":provenance['dataset_id'],"source_description":provenance['source_description'],
            "total_observations":len(rows),"total_episodes":n,"group_count":len(outputs),
            "groups":outputs,"splits_episode_counts":{k:sum(s==k for s in assignments.values()) for k in ('train','calibration','test')},
            "calibration_wall_seconds":round(time.perf_counter()-start_time,6),**hashes}
