"""Wrapper for v5 benchmark, with explicit package, error, and provenance handling.
Do not alter the archived v5.0 scoring or rename its measured policy fields.
"""
import argparse, json, pathlib, shutil, sys
from firstlight_v5 import runner, package
from firstlight_v5.core import json_dump


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--run',required=True)
    ap.add_argument('--limit',type=int,default=24)
    args=ap.parse_args(argv)
    root=pathlib.Path(args.run).resolve()
    # Dataset is saved INSIDE execution dir (v5.0 accidentally used a
    # code-tree source cache, so v5.0 evidence ZIP omitted source provenance).
    code=runner.main(['--run',str(root),'--limit',str(args.limit)])
    result_path=root/'benchmark_results.json'
    if not result_path.exists():
        json_dump(result_path,{'state':'BLOCKED','blocking_error':'RUNNER_DID_NOT_SAVE_RESULTS','results':[], 'summary':None})
    result=json.loads(result_path.read_text())
    gate=result.get('summary',{}).get('commercial_gate') if isinstance(result.get('summary'),dict) else None
    print('FIRST LIGHT 5.1 BENCHMARK STATUS:',result.get('state','UNKNOWN'),flush=True)
    print('OFFICIAL LEADERBOARD CLAIM: NOT ESTABLISHED',flush=True)
    print('ALL-IN COST AND INDEPENDENT APPROVAL: NOT ESTABLISHED',flush=True)
    if result.get('blocking_error'):
        print('BENCHMARK BLOCKER:',result['blocking_error'],flush=True)
    if gate:print('COMMERCIAL CLAIM GATE:',gate,flush=True)
    package.pack(root)
    return code

if __name__=='__main__':raise SystemExit(main())
