"""CLI: execute all three matched arms on public QuixBugs; no paid APIs."""
import argparse,pathlib,json
from .engine import execute,DEV,HOLDOUT,ALL
from .offline_audit import run as replay


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--model',default='qwen2.5:1.5b');ap.add_argument('--task-limit',type=int,default=14)
    o=ap.parse_args()
    if not 1<=o.task_limit<=len(ALL):raise SystemExit('TASK_LIMIT_INVALID_1_TO_14')
    p=pathlib.Path(o.output)
    d=execute(pathlib.Path(o.root)/'data/QUIXBUGS_OFFICIAL_SUBSET',p,o.model,task_limit=o.task_limit)
    (p/'historic_development_replay.json').write_text(json.dumps(replay(o.root),indent=2)+'\n')
    print('FIRST LIGHT DECISION STUDY:',d['status'],'TASKS:',len(d['records']),flush=True)
    if d['status']=='BLOCKED':print('ACTUAL BLOCKER:',d['blocker'],flush=True)
    if 'cohorts' in d:
        print('HELD-OUT PAIRED EVIDENCE:',json.dumps(d['cohorts']['HOLDOUT']['fl_vs_competent'],sort_keys=True),flush=True)

if __name__=='__main__':main()
