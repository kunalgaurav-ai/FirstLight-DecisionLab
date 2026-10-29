import argparse
from pathlib import Path
from .engine import new_report,package
from .server import serve

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--plan',default='data/decision_suite_v45.json');p.add_argument('--video-plan',default='data/workflow_suite_v44.json');p.add_argument('--model',default='qwen2.5:1.5b')
 p.add_argument('action',choices=['experiment','package','serve']);a=p.parse_args()
 if a.action=='experiment':
  report=new_report(a.run,a.plan,a.model);z=package(a.run)
  print('ACTUAL TEXT BRANCH CASES:',len(report['text_trials']))
  print('AUDIO EXECUTION STATUS:',report['audio_trials']['status'])
  print('RESULT ZIP:',z)
 elif a.action=='package':print('RESULT ZIP:',package(a.run))
 else:serve(a.run,a.plan,a.video_plan)
if __name__=='__main__':main()
