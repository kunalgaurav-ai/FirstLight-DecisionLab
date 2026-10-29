"""Audits actual historical first-patch outputs; NOT executed saved continuations."""
import pathlib,json
from .engine import choose_check
from .contracts import DEV
from firstlight_v55.sandbox import extract

def run(root):
    data=json.loads((pathlib.Path(root)/'data/DEV_INITIAL_ACTUAL_MAC_RESPONSES.json').read_text())
    out=[]
    for name in DEV:
        record=data['items'][name]
        code=extract(record['response'],name)
        a=choose_check(name,code,'COMPETENT_OPTIMIZED')
        b=choose_check(name,code,'FIRSTLIGHT_SELECTIVE_VALUE_CHECK')
        out.append({'task':name,'gold_failure_known_only_retrospectively':not record['retrospective_gold_pass'],
                    'original_baseline_warning':a['status']!='PASS',
                    'experimental_extra_warning':b['status']!='PASS',
                    'extra_checks':b['extras_run'],
                    'posthoc_only':True,'not_an_executed_repair_or_savings_result':True})
    return {'source':'actual_v5.5.1_mac_initial_model_responses','only_offline_reverification':True,'records':out}

if __name__=='__main__':
 import sys
 print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '.'),indent=2))
