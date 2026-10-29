"""Conservative economic gate for future production; NOT fitted by pilot data.

The randomized experimental test selector in engine.py is an uncalibrated
mechanism under study. Production action uses this conservative gate ONLY when
supported by independent calibration and real exposure/cost units.
"""
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class RiskEvidence:
    sample_size: int
    suspected_failures: int
    detectable_and_correctable: int
    false_alarms: int
    safe_examples: int
    exposure_cost_per_failure: float
    cost_probe_and_repair: float
    false_alarm_harm: float
    min_samples: int=40


def wilson_interval(successes,n,z=1.96):
    if n<1:return (0.0,1.0)
    p=successes/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    width=z/den*sqrt(p*(1-p)/n+z*z/(4*n*n))
    return max(0.0,center-width), min(1.0,center+width)


def safe_value_gate(e: RiskEvidence):
    """LCB net incremental value, with an explicit abstain path.

    Not a theorem guaranteeing safe improvement. Correlation, selective labels,
    shift and imperfect counterfactual identification invalidate naive bounds.
    The product must demonstrate quality non-inferiority in matched trials.
    """
    if e.sample_size<e.min_samples or e.suspected_failures<15 or e.safe_examples<15:
        return {'action':'FALLBACK_TO_COMPETENT','reason':'INSUFFICIENT_INDEPENDENT_SUPPORT','lower_bound_net_value':None}
    if any(v<0 for v in (e.exposure_cost_per_failure,e.cost_probe_and_repair,e.false_alarm_harm)):
        return {'action':'FALLBACK_TO_COMPETENT','reason':'INVALID_COST_UNITS','lower_bound_net_value':None}
    p_fail_lower=wilson_interval(e.suspected_failures,e.sample_size)[0]
    p_recovery_lower=wilson_interval(e.detectable_and_correctable,e.suspected_failures)[0]
    false_upper=wilson_interval(e.false_alarms,e.safe_examples)[1]
    lcb=(p_fail_lower*p_recovery_lower*e.exposure_cost_per_failure
         -e.cost_probe_and_repair-false_upper*e.false_alarm_harm)
    return {'action':'CHECK' if lcb>0 else 'FALLBACK_TO_COMPETENT',
            'reason':'CONSERVATIVE_ESTIMATED_VALUE' if lcb>0 else 'NONPOSITIVE_CONSERVATIVE_VALUE',
            'lower_bound_net_value':lcb,
            'not_a_formal_policy_safety_guarantee':True}
