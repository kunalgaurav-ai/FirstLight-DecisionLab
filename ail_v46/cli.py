from __future__ import annotations
import argparse,pathlib,traceback,sys
from . import runtime as rt
from .server import serve
from ail_v45.engine import new_report

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--plan',default='data/workflow_suite_v44.json')
    p.add_argument('action',choices=['init','experiment','serve','package','diagnose']);a=p.parse_args();run=pathlib.Path(a.run)
    if a.action=='init':
        rt.start(run,a.plan)
        recovered=rt.recover_prior_v43_clips(run)
        print('INITIALIZED',run,'PREVIOUS VERIFIED 5-SECOND CLIPS RECOVERED:',len(recovered))
    elif a.action=='experiment':
        try:
            comp=run/'v45_comparison';comp.mkdir(exist_ok=True)
            r=new_report(comp,'data/decision_suite_v45.json','qwen2.5:1.5b')
            print('COMPARISON EXECUTED:',len(r['text_trials']),'texts; audio:',r['audio_trials']['status'])
        except Exception as e:
            (run/'comparison_failure.txt').write_text(rt.safe_error(e)+'\n')
            print('COMPETITOR STUDY HELD:',rt.safe_error(e))
        print('EVIDENCE ZIP:',rt.close_reports(run))
    elif a.action=='serve':
        rt.recover_interrupted(run)
        serve(run,a.plan)
    elif a.action=='package':print(rt.close_reports(run))
    else:print(rt.readiness())
if __name__=='__main__':main()
