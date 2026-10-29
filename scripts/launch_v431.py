#!/usr/bin/env python3
"""Recover the original v4.3 genuine MP4; never auto-invoke a provider."""
from __future__ import annotations
import argparse, sys, uuid, json, os, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v431.console import discover,EvidenceConsole,serve

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--original-run',type=Path)
    p.add_argument('--max-new-calls',type=int,default=3)
    p.add_argument('--no-browser',action='store_true')
    p.add_argument('--no-dashboard',action='store_true')
    args=p.parse_args()
    if args.max_new_calls<0 or args.max_new_calls>10:p.error('max-new-calls must be 0..10')
    downloads=Path.home()/'Downloads'/'AIL-v43-executions'
    candidates=discover(downloads)
    original=args.original_run.resolve() if args.original_run else (candidates[0] if candidates else None)
    if original is None or not (original/'generative_receipts_v43.json').is_file():
        print('FAIL_CLOSED: cannot find an original complete v4.3 Mac run with its physical video.',flush=True)
        print('Use --original-run /ABSOLUTE/PATH/TO/runs/v43_<id>; no model request has been made.',flush=True)
        return 2
    prompt_path=ROOT/'data'/'frozen_prompt_first_v01.json'
    run=ROOT/'runs'/('v431_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
    session=EvidenceConsole(original,run,prompt_path,args.max_new_calls)
    print('SOURCE V4.3 RUN:',original,flush=True)
    print('VIDEO INVENTORY:',[(x['task_id'],x['status']) for x in session.tasks_overview()],flush=True)
    print('RECOVERED VERIFIED FILES:',sum(x['status']=='VIDEO_AVAILABLE' for x in session.tasks_overview()),flush=True)
    print('STARTUP PROVIDER CALLS: 0 (guaranteed by constructor; only explicit UI action can generate)',flush=True)
    print('EVIDENCE ZIP:',session.upload,flush=True)
    if args.no_dashboard:return 0
    server,url=serve(session,ROOT/'ail_v431'/'app.js',open_browser=not args.no_browser)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:
        session.persist();server.server_close()
        print('SEALED EVIDENCE ZIP:',session.upload,flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
