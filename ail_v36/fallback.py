"""Regression fix: when benefit isn't supported, preserve competent safety check.

This adapter deliberately gives the incumbent credit and does not claim AIL's
custom decision outperforms it. Used in LOCAL constructed benchmark only.
"""
from pathlib import Path
from ail_v33.benchmark import SCENARIOS, execute_scenario


def fixture_parity(root:Path):
    root.mkdir(parents=True,exist_ok=False)
    records=[]
    for task in SCENARIOS:
        incumbent=execute_scenario('B1_COMPETENT_EARLY_CHECK',task,root)
        # No action-conditioned evidence: explicitly preserve incumbent behavior.
        ail=execute_scenario('B1_COMPETENT_EARLY_CHECK',task,root/'fallback_copy')
        records.append({'task':task['id'], 'baseline_operations':incumbent['stage_ops'],
                        'fallback_operations':ail['stage_ops'],
                        'identical_status':ail['status']==incumbent['status'],
                        'identical_output_sha256':ail.get('package_sha256')==incumbent.get('package_sha256'),
                        'quality_reference':'TECHNICAL_FIXTURE_ONLY',
                        'reason':'NO_SUPPORTED_INCREMENTAL_ACTION_VALUE_RETAIN_SAFE_INCUMBENT'})
    before=sum(x['baseline_operations'] for x in records)
    after=sum(x['fallback_operations'] for x in records)
    return {'version':'v3.6','evidence_kind':'CONSTRUCTED_REGRESSION_NOT_CUSTOMER_VALUE',
            'incumbent_operations':before,'ail_safe_fallback_operations':after,
            'baseline_parity':after==before and all(x['identical_status'] and x['identical_output_sha256'] for x in records),
            'historical_v33_ail_operations':28,'historical_v33_competent_operations':25,
            'comment':'Fallback fixes avoidable v3.3 rule regression, does not beat incumbent',
            'records':records}
