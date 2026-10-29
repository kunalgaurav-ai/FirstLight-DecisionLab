"""Fail-closed paired quality-constrained economic decisions, not synthetic claims."""
from __future__ import annotations
import math
from statistics import mean

def bound_action(episodes,unit='usd',delta=.05,loss_ceiling=None,minimum=30,tail_tolerance=None):
    """Bound paired baseline minus AIL cost on prospective independently approved episodes.

    Hoeffding lower bound uses precommitted absolute paired cost ceiling. Units
    must be verified all-in, identical, and include instrumentation. Assumes
    independent paired episodes. Returns HOLD unless all quality checks pass.
    """
    held=lambda reason:{'decision':'HOLD','reason':reason,'incremental_savings_proven':False}
    if unit!='usd':return held('REQUIRE_ALL_IN_USD_NOT_TOKENS_OR_ILLUSTRATIVE_TARIFF')
    if not isinstance(episodes,list) or len(episodes)<minimum:return held('MINIMUM_INDEPENDENT_PAIRED_EPISODES_NOT_MET')
    if type(loss_ceiling) not in (float,int) or loss_ceiling<=0:return held('PRECOMMITTED_COST_DIFFERENCE_CEILING_MISSING')
    if not 0<delta<.5:return held('INVALID_CONFIDENCE')
    if tail_tolerance is None or type(tail_tolerance) not in (int,float) or tail_tolerance<0:return held('TAIL_RISK_BUDGET_UNKNOWN')
    seen=set();gains=[];tail=[]
    for e in episodes:
        if not isinstance(e,dict) or e.get('pair_id') in seen or not e.get('pair_id'):return held('DUPLICATE_OR_MISSING_PAIR_ID')
        seen.add(e['pair_id'])
        if e.get('provenance')!='ACTUAL_EXECUTION_INDEPENDENTLY_GRADED':return held('NOT_INDEPENDENTLY_APPROVED_OR_NOT_ACTUAL')
        if e.get('split')!='PROSPECTIVE_HELD_OUT':return held('NOT_PROSPECTIVE_HELD_OUT')
        if type(e.get('baseline_accepted')) is not bool or type(e.get('ail_accepted')) is not bool:return held('MISSING_ACCEPTANCE')
        if not e['ail_accepted'] and e['baseline_accepted']:return held('QUALITY_NONINFERIORITY_VIOLATED')
        if not e['baseline_accepted'] or not e['ail_accepted']:return held('APPROVED_OUTCOME_DENOMINATOR_NOT_COMPARABLE')
        b=e.get('baseline_all_in_usd');a=e.get('ail_all_in_usd')
        if type(a) not in (float,int) or type(b) not in (float,int) or not math.isfinite(a) or not math.isfinite(b) or min(a,b)<0:
            return held('ACTUAL_COST_NOT_VERIFIABLE')
        d=b-a
        if abs(d)>loss_ceiling:return held('COST_SUPPORT_EXCEEDS_PRECOMMITTED_BOUND')
        gains.append(d);tail.append(max(0,a-b))
    n=len(gains)
    lower=mean(gains)-loss_ceiling*math.sqrt(2*math.log(2/delta)/n)
    worst_k=max(1,math.ceil(n*.1));cvar=sum(sorted(tail,reverse=True)[:worst_k])/worst_k
    if lower<=0:return {'decision':'HOLD','reason':'LOWER_CONFIDENCE_BOUND_NOT_POSITIVE','mean_paired_savings_usd':mean(gains),
                         'conservative_lower_bound_usd':lower,'negative_delta_cvar_90_usd':cvar,'n':n,'incremental_savings_proven':False}
    if cvar>tail_tolerance:return held('TAIL_CVAR_EXCEEDS_RISK_BUDGET')
    return {'decision':'QUALIFIED_FOR_FURTHER_VALIDATION_NOT_AUTODEPLOY','mean_paired_savings_usd':mean(gains),
            'conservative_lower_bound_usd':lower,'negative_delta_cvar_90_usd':cvar,'n':n,'incremental_savings_proven':True,
            'warning':'Only under documented independent matched-sample and cost-bound assumptions; not proof of general superiority'}

def workflow_action(shot,review=None,cache=None,rights=None):
    """Only defensible automatic control actions; never infer unmeasured repair success."""
    if rights!='AUTHORIZED_NONCONFIDENTIAL_TEST':return {'action':'HOLD','reason':'RIGHTS_UNVERIFIED'}
    if cache is not None and cache.get('sha256')==shot.get('sha256') and cache.get('permissions_match') is True and cache.get('version_match') is True and cache.get('quality_accepted') is True:
        return {'action':'REUSE_VERIFIED_CACHE','reason':'EXACT_VERSIONED_PERMISSION_SCOPED_IDENTITY'}
    if not shot.get('available'):return {'action':'GENERATE_OR_IMPORT','reason':'ACTUAL_MEDIA_REQUIRED_NO_SAVINGS_ASSUMED'}
    if review is None:return {'action':'REVIEW_BEFORE_EXPENSIVE_DESCENDANTS','reason':'NO_GRADED_OUTPUT'}
    if review.get('passed_local_rubric'):
        return {'action':'STOP_REGENERATION','reason':'SELF_REVIEW_PASS_BUT_INDEPENDENT_APPROVAL_UNKNOWN'}
    return {'action':'HUMAN_DECISION_REQUIRED','reason':'TARGETED_REPAIR_OR_REGENERATE_EFFECT_NOT_CALIBRATED'}
