#!/usr/bin/env python3
"""One Mac launcher, test-first, actual LTX remote attempt, reports and live review console."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys, uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ail_v43.engine import now, save_json, file_sha, write_zip, task_index
from ail_v43.server import Session, serve

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prompt-id',default='VID-03-LIBRARY-HANDOFF')
    ap.add_argument('--max-generations',type=int,default=4)
    ap.add_argument('--no-auto-generate',action='store_true')
    ap.add_argument('--no-dashboard',action='store_true')
    args=ap.parse_args()
    if not 1<=args.max_generations<=10:ap.error('--max-generations must be 1..10')
    prompts=ROOT/'data'/'frozen_prompt_first_v01.json';tasks=task_index(prompts)
    if args.prompt_id not in tasks or tasks[args.prompt_id]['modality']!='text_to_video':ap.error('choose a video prompt')
    run=ROOT/'runs'/('v43_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);run.mkdir(parents=True,exist_ok=False)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,
                          capture_output=True,text=True,timeout=240)
    (run/'tests_v43.txt').write_text('EXIT '+str(result.returncode)+'\n'+result.stdout+result.stderr)
    print('REGRESSION TESTS:', 'PASS' if not result.returncode else 'FAIL',flush=True)
    software={'run_id':run.name,'utc':now(),'python':sys.version,'system':platform.platform(),
       'inherited_source_preserved':'v4.2 repository copied unmodified into v4.3 additive release',
       'unit_tests_exit':result.returncode,'frozen_prompt_sha256':file_sha(prompts),
       'video_backend':'OFFICIAL_LIGHTricks_LTX2.5_HF_GRADIO_ZERO_GPU',
       'real_model_tested_in_this_builder_environment':False,'media_generation_model_installed_locally':False,
       'provider_billable_charges':'UNKNOWN_QUOTA_DOES_NOT_EQUAL_USD',
       'external_OSS_superiority':'NOT_TESTED','independent_approval':'UNKNOWN',
       'prompt_rights':'PUBLIC_CONSTRUCTED_NON_CUSTOMER'}
    ffprobe=subprocess.run(['ffprobe','-version'],capture_output=True,text=True,timeout=10) if shutil_which('ffprobe') else None
    software['ffprobe']={'ready':bool(ffprobe and ffprobe.returncode==0),
                         'path':shutil_which('ffprobe')}
    software['ffmpeg']={'ready':bool(shutil_which('ffmpeg')),'path':shutil_which('ffmpeg')}
    try:import gradio_client;software['gradio_client']={'ready':True,'version':getattr(gradio_client,'__version__','unknown')}
    except ImportError:software['gradio_client']={'ready':False,'reason':'NOT_INSTALLED'}
    save_json(run/'source_audit_v43.json',software)
    save_json(run/'frozen_prompt_protocol_v43.json',{'protocol_id':'AIL_PROMPT_FIRST_GENERATIVE_BENCH_V0.1_2026-10-25',
            'prompt_file_sha256':file_sha(prompts),'selected_id':args.prompt_id,'selected_prompt_sha256':tasks[args.prompt_id]['prompt_sha256'],
            'max_generation_calls':args.max_generations,'supports_true_model_generation_only':True,
            'generative_visual_review':'HUMAN_ANNOTATION_REQUIRED','provider_price':'NOT_OBSERVED',
            'baseline':'COMPETENT_ORIGINAL_PROMPT_WITH_CRITIC_GUIDED_RETRY',
            'ail':'CONDITIONAL_STRUCTURED_REPAIR_OR_MULTISHOT_WHEN_REVIEW_SUPPORTS_IT',
            'not_applicable_baselines':['photo-montage editing','static-pan-zoom video'],
            'no_paid_api_keys_represented_as_active':True})
    if result.returncode:
        print('TEST FAILURE DETAILS:', (result.stdout+result.stderr)[-3500:],flush=True)
        save_json(run/'generative_receipts_v43.json',{'status':'BLOCKED_SOFTWARE_REGRESSION','model_calls':0})
        print('RESULTS ZIP:',write_zip(run),flush=True);return 2
    session=Session(run,prompts,args.prompt_id,args.max_generations)
    if not software['ffprobe']['ready'] or not software['ffmpeg']['ready']:
        session.status='BLOCKED_MISSING_FFMPEG';session._log('Install or locate ffmpeg AND ffprobe; no fake generation');session.persist()
        auto=False
    elif not software['gradio_client']['ready']:
        session.status='BLOCKED_MISSING_GRADIO_CLIENT';session._log('No API library installed; run pip install gradio_client in the project venv');session.persist()
        auto=False
    else:auto=not args.no_auto_generate
    print('REAL T2V TARGET:',args.prompt_id,' official provider: Lightricks/LTX-2.5',flush=True)
    print('DOWNLOAD/RESULTS LOCATION:',session.upload,flush=True)
    if args.no_dashboard:
        if auto:
            try:session.start(args.prompt_id,'B1_FIRST')
            except ValueError as e:session._log('Generation blocked: '+str(e))
            import time
            while any(x['status'] in ('QUEUED','RUNNING') for x in session.records):time.sleep(.3)
        session.persist();print('SEALED RESULTS ZIP:',session.upload,flush=True);return 0
    serve(session,auto_generate=auto)
    return 0

def shutil_which(name):
    import shutil
    return shutil.which(name)

if __name__=='__main__':raise SystemExit(main())
