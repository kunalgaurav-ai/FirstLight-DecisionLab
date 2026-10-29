"""Evidence-graded DAG opportunity upper bounds and robust decision screening.

NOT a fitted causal model; NOT verified commercial opportunity. Scenario bound
only under explicitly stated action, cost, salvage and incumbent assumptions.
No optional production action is authorized by this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any


def _unit(v: Any, name: str) -> float:
    if type(v) not in (int, float) or not isfinite(v) or not 0 <= v <= 1:
        raise ValueError(f'{name} must be a finite probability in [0,1]')
    return float(v)


def _cost(v: Any, name: str) -> float:
    if type(v) not in (int, float) or not isfinite(v) or v < 0:
        raise ValueError(f'{name} must be a finite, nonnegative quantity')
    return float(v)


def _interval(v: Any, name: str, *, probability: bool) -> tuple[float,float]:
    if not isinstance(v, list) or len(v) != 2:
        raise ValueError(f'{name} requires [lower, upper] bounds')
    f = _unit if probability else _cost
    a,b = f(v[0], name),f(v[1], name)
    if a>b: raise ValueError(f'{name} lower exceeds upper')
    return a,b


def validate(workflow: dict) -> dict:
    if not isinstance(workflow, dict) or not isinstance(workflow.get('nodes'),list) or not workflow['nodes']:
        raise ValueError('nonempty nodes list required')
    if workflow.get('unit') not in {'metered_compute_seconds','physical_operations','billed_usd','illustrative_cost_units'}:
        raise ValueError('explicit comparable cost unit required')
    if workflow.get('evidence_class') not in {'CONSTRUCTED_TEST_ONLY', 'OBSERVED_STAGE_RECEIPTS'}:
        raise ValueError('evidence_class required')
    nodes={}
    for n in workflow['nodes']:
        if not isinstance(n,dict):raise ValueError('bad node')
        name=n.get('id')
        if not isinstance(name,str) or not name or name in nodes:raise ValueError('duplicate/empty node id')
        ps=n.get('parents')
        if not isinstance(ps,list) or len(set(ps))!=len(ps) or not all(isinstance(p,str) for p in ps):
            raise ValueError('invalid dependency list')
        for key in ('planned_after_checkpoint','already_avoided_by_incumbent','allowed_to_skip_if_defective'):
            if type(n.get(key)) is not bool:raise ValueError('missing explicit '+key)
        cost=_interval(n.get('marginal_cost'),name+'.marginal_cost',probability=False)
        salvage=_interval(n.get('salvage_fraction'),name+'.salvage_fraction',probability=True)
        nodes[name]={**n,'marginal_cost':cost,'salvage_fraction':salvage}
    for k,n in nodes.items():
        if not set(n['parents']) <= set(nodes):raise ValueError('parent node does not exist')
    state={}
    def visit(x):
        if state.get(x)==1:raise ValueError('dependency cycle')
        if state.get(x)==2:return
        state[x]=1
        for p in nodes[x]['parents']:visit(p)
        state[x]=2
    for k in nodes:visit(k)
    return nodes


def descendants(nodes:dict, origins:list[str]) -> set[str]:
    if not origins or any(x not in nodes for x in origins):raise ValueError('unknown/empty affected ancestor')
    frontier=set(origins)
    while True:
        added={k for k,n in nodes.items() if set(n['parents']) & frontier}
        new=frontier|added
        if len(new)==len(frontier):return frontier
        frontier=new


def assess_workflow(workflow:dict) -> dict:
    """Compute an explicit bound on downstream *marginal* work at risk.

    This is NOT a bound on customer savings in the absence of real causal effects.
    The reported theoretical upper is relative to an eligible action set whose
    effect can completely eliminate the at-risk work without other side effects.
    """
    nodes=validate(workflow)
    out=[]
    for c in workflow.get('checkpoints',[]):
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id']:
            raise ValueError('checkpoint id missing')
        reach=descendants(nodes,c.get('affected_ancestors'))
        eligible=sorted(k for k in reach if nodes[k]['planned_after_checkpoint'] and
                        not nodes[k]['already_avoided_by_incumbent'] and
                        nodes[k]['allowed_to_skip_if_defective'])
        unavoidable=sorted(k for k in reach if k not in eligible)
        costlo=sum(nodes[k]['marginal_cost'][0]*(1-nodes[k]['salvage_fraction'][1]) for k in eligible)
        costhi=sum(nodes[k]['marginal_cost'][1]*(1-nodes[k]['salvage_fraction'][0]) for k in eligible)
        # The lower bound is an ACCOUNTING lower bound on this explicit set only.
        # It does not imply a real-world lower bound on potential intervention gains.
        out.append({'checkpoint':c['id'],'affected_reachable_nodes':sorted(reach),
                    'eligible_unique_nodes':eligible,'excluded_nodes':unavoidable,
                    'total_eligible_nodes':len(eligible),
                    'avoidable_downstream_work_interval':[round(costlo,6),round(costhi,6)],
                    'bound_interpretation':'CONDITIONAL_THEORETICAL_OPPORTUNITY_NOT_CAUSAL_OR_VERIFIED_SAVINGS',
                    'comparison_baseline':'INCUMBENT_ALREADY_HAS_EARLY_CHECKS_CACHE_AND_SELECTIVE_REPAIR'})
    if len({x['checkpoint'] for x in out})!=len(out):raise ValueError('duplicate checkpoint')
    return {'evidence_class':workflow['evidence_class'],'cost_unit':workflow['unit'],
            'incremental_customer_value':'UNESTIMABLE_WITHOUT_ACTION_OUTCOMES_AND_APPROVAL',
            'checkpoints':out}


def screen_action(action:dict, opportunity:dict, *, approved_risk_bounds:bool=False) -> dict:
    """Interval arithmetic, never falsely called a guaranteed confidence bound.

    All bounds are inputs and are NOT calibrated by this function. Requirement:
    probability of defect, causal effectiveness, check cost, disruption and quality
    effects must come from supported independent data or be marked scenario.
    """
    if not isinstance(action,dict):raise ValueError('action object required')
    p=_interval(action.get('defect_probability'), 'defect_probability',probability=True)
    e=_interval(action.get('causal_prevention_effect'), 'causal_prevention_effect',probability=True)
    check=_interval(action.get('full_check_and_repair_cost'),'full_check_and_repair_cost',probability=False)
    disrupt=_interval(action.get('false_alarm_disruption_cost'),'false_alarm_disruption_cost',probability=False)
    quality=_interval(action.get('quality_loss_cost_proxy'),'quality_loss_cost_proxy',probability=False)
    opp=_interval(opportunity['avoidable_downstream_work_interval'],'work_interval',probability=False)
    if action.get('quality_gate') not in ('APPROVED_INDEPENDENTLY','UNESTABLISHED'):
        raise ValueError('quality gate missing')
    lower=p[0]*e[0]*opp[0]-check[1]-disrupt[1]-quality[1]
    upper=p[1]*e[1]*opp[1]-check[0]  # deliberately optimistic ceiling, omits optional harms
    # Strictly shadow only, even with a positive lower arithmetic result.
    eligible=(bool(approved_risk_bounds) and action['quality_gate']=='APPROVED_INDEPENDENTLY'
              and lower>0 and opp[1]>0)
    return {'action_id':action.get('id','unspecified'),'scenario_net_value_interval':[round(lower,6),round(upper,6)],
            'shadow_screen_result': 'CANDIDATE_FOR_PROSPECTIVE_RANDOMIZED_EVALUATION' if eligible else 'HOLD_NO_SUPPORTED_POSITIVE_ACTION_VALUE',
            'production_action_authorized':False, 'interval_evidence_status': 'PROVIDED_NOT_VERIFIED_BY_THIS_TOOL',
            'note':'Interval products require causal and calibration assumptions. No auto-promotion; quality constraints are hard gates.'}
