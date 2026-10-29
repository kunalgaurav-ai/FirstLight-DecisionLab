#!/usr/bin/env python3
"""One Mac launcher: integrity, tests, real Ollama, CC0 visual gate, speech+video, review."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,random,subprocess,sys,time,uuid,zipfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ail_v38.workflow import CASES,probe,snapshot_system,sha,utc
from ail_v42.visuals import load_catalog,prepare_assets,task_assets
from ail_v40.workflow import ARMS,execute,aggregate
VERSION="v4.2.0"
from scripts.dashboard_v42 import dashboard
from scripts.launch_v39 import grade_schema_probe

def save(path,d):path.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def archive(run):
    dest=run/('UPLOAD_THIS_v42_'+run.name.removeprefix('v42_')+'.zip')
    tmp=dest.with_suffix('.tmp')
    names=('tests_v42.txt','source_audit_v42.json','historical_grade_schema_v42.json','download_visual_provenance_v42.json','benchmark_v42.json','frozen_protocol_v42.json','blind_review_index_v42.json','manifest_v42.json','reviews.jsonl')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in names:
            if (run/f).is_file():z.write(run/f,f)
    tmp.replace(dest)
    return dest

def frozen_hash(o):return hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description='AIL visual-grounded genuine local video benchmark')
    ap.add_argument('--model',default='qwen2.5:1.5b')
    ap.add_argument('--ollama',default='http://127.0.0.1:11434')
    ap.add_argument('--task-limit',type=int,default=4)
    ap.add_argument('--asset-root',default=str(ROOT/'data'/'downloaded_cc0_v42'))
    ap.add_argument('--no-fetch',action='store_true',help='Only use previously downloaded verified images')
    ap.add_argument('--no-dashboard',action='store_true')
    ap.add_argument('--quick',action='store_true',help='Only first one task, real execution if available')
    args=ap.parse_args()
    limit=1 if args.quick else args.task_limit
    if not 1<=limit<=len(CASES):ap.error('task-limit 1..4')
    run=ROOT/'runs'/('v42_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);run.mkdir(parents=True,exist_ok=False)
    stamp=utc();start=time.perf_counter()
    t=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True,timeout=240)
    (run/'tests_v42.txt').write_text('EXIT '+str(t.returncode)+'\n'+t.stdout+t.stderr)
    print('REGRESSION TESTS:', 'PASS' if t.returncode==0 else 'FAIL',flush=True)
    if t.returncode:
        print('TEST FAILURE DETAILS (last 3500 characters):',flush=True)
        print((t.stdout+t.stderr)[-3500:],flush=True)

    ready_system=snapshot_system();ready_model=probe(args.ollama,args.model)
    ffmpeg_filters=''
    if ready_system.get('ffmpeg'):
        try:
            filt=subprocess.run(['ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=15)
            if filt.returncode==0:ffmpeg_filters=filt.stdout
        except (OSError,subprocess.TimeoutExpired):pass
    filter_check={'core_overlay_available':any(line.split()[1:2]==['overlay'] for line in ffmpeg_filters.splitlines() if line.split()),
                  'core_zoompan_available':any(line.split()[1:2]==['zoompan'] for line in ffmpeg_filters.splitlines() if line.split()),
                  'optional_drawtext_required':False}
    print('FFMPEG FILTER COMPATIBILITY:',filter_check,flush=True)
    catalog=load_catalog(ROOT/'data'/'curated_visual_assets_v40.json')
    allowed_dep=bool(ready_system['ffmpeg'] and ready_system['ffprobe'] and ready_system['say_exists'] and ready_model['ready'] and platform.system()=='Darwin' and t.returncode==0 and filter_check['core_overlay_available'] and filter_check['core_zoompan_available'])
    visuals=prepare_assets(catalog,args.asset_root,fetch=not args.no_fetch) if allowed_dep else []
    if allowed_dep:
        for v in visuals:
            print('ASSET:',v['asset_id'],v['status'],v['fetch'].get('reason',''),v['inspection'].get('reason',''),flush=True)

    save(run/'download_visual_provenance_v42.json',{'collection':'CC0_CURATED_STILLS','records':visuals,'rights_status':'REVIEW_SOURCE_PAGES_BEFORE_EXTERNAL_RELEASE','independent_visual_confirmation':'NOT_PERFORMED','thumbnail_cdn_policy':'STRICT_WIKIMEDIA_HOSTS_INCLUDES_THUMB'})
    save(run/'source_audit_v42.json',{'run_id':run.name,'platform':ready_system,'model':ready_model,'ffmpeg_filter_check':filter_check,'unit_tests_pass':t.returncode==0,'dependency_gate':allowed_dep,'real_workflow_if_asset_ready':bool(allowed_dep),'client_input':'CONSTRUCTED_NOT_DRIFTWOOD','media_kind':'REAL_MOVING_SLIDESHOW_FROM_APPROVED_CC0_STILLS_WITH_SPEECH','not':'GENERATIVE_IMAGE_OR_VIDEO'})
    save(run/'historical_grade_schema_v42.json',grade_schema_probe())
    tasks=list(CASES[:limit]);protocol={'version':VERSION,'created_utc':stamp,'tasks':tasks,'arms':ARMS,'reused_prior_case_prompts':True,'not_fresh_external_holdout':True,'seed':20261025,'output_approval':'INDEPENDENT_REVIEW_UNKNOWN','image_curation':'DOCUMENTED_HUMAN_TOPIC_TAGS_NOT_COMPUTER_VISION','asset_source_sha256':[x.get('inspection',{}).get('sha256') for x in visuals]}
    save(run/'frozen_protocol_v42.json',protocol)
    rows=[]
    if allowed_dep:
        for j,task in enumerate(tasks):
            chosen=task_assets(visuals,task['id'])
            if not chosen:
                for arm in ARMS:
                    rows.append({'task_id':task['id'],'arm':arm,'status':'BLOCKED_PRECOMMIT_VISUAL','reason':'MISSING_VERIFIED_TOPIC_MATCHING_ASSETS','wall_s':0,'receipts':[]})
                print('VISUAL ASSET GATE BLOCK:',task['id'],flush=True)
                continue
            order=list(ARMS);random.Random(20261025+j).shuffle(order)
            for arm in order:
                print('EXECUTING:',task['id'],arm,flush=True)
                rec=execute(run,task,arm,chosen,args.model,args.ollama,8100+j)
                rows.append(rec)
                print('FINISHED:',task['id'],arm,rec['status'],rec['wall_s'],'seconds',flush=True)
    status=('BLOCKED_REGRESSION_TEST_FAILURE' if t.returncode else
      ('BLOCKED_DEPENDENCIES' if not allowed_dep else
      ('BLOCKED_VISUAL_ASSET_ADMISSION' if rows and all(r['status']=='BLOCKED_PRECOMMIT_VISUAL' for r in rows) else
      'ACTUAL_LOCAL_MEDIA_EXECUTION_COMPLETE_OR_PARTIALLY_BLOCKED')))

    report={'version':VERSION,'run_id':run.name,'status':status,'timestamp_utc':utc(), 'attempts':len(rows),'trials':rows,'aggregate':aggregate(rows),'wall_s':round(time.perf_counter()-start,3),'asset_acquisition_wall_s':round(sum(x['fetch'].get('elapsed_s',0) for x in visuals),3),'asset_acquisition_bytes':sum(x['inspection'].get('bytes',0) for x in visuals if x['fetch'].get('downloaded')), 'total_real_ollama_calls':sum(sum(bool(e.get('actual_ollama_inference')) for e in r.get('receipts',[])) for r in rows),'source_visual_relevance':'BROAD_HUMAN_CURATED_TOPIC_TAG_ONLY','independent_approval':'UNKNOWN','dollars_saved':'NOT_MEASURED','baseline':'COMPETENT_TOOL_FIRST','edge_claim':'NOT_ESTABLISHED','customer_production_data':False,'commercialization':'NO_UNVERIFIED_CLIENT_MEDIA_OR_ENTITLEMENTS'}
    save(run/'benchmark_v42.json',report)
    completed=[x for x in rows if x['status']=='COMPLETE_TECHNICALLY']
    rng=random.Random(20261025);rng.shuffle(completed)
    cards=[{'review_id':'VIS-'+str(i+1).zfill(3)+'-'+uuid.uuid4().hex[:4], 'task_id':x['task_id'], 'video_path':x.get('video_path'), 'frame_paths':x.get('frame_paths',[]), 'facts':list(next(t['facts'] for t in tasks if t['id']==x['task_id'])), 'hidden_arm':x['arm']} for i,x in enumerate(completed)]
    # reviewer gets ID/video, no arm; private index is included only in sealed audit package.
    save(run/'blind_review_index_v42.json',cards)
    names=('tests_v42.txt','source_audit_v42.json','historical_grade_schema_v42.json','download_visual_provenance_v42.json','benchmark_v42.json','frozen_protocol_v42.json','blind_review_index_v42.json')
    def seal():
        hashes={n:sha(run/n) for n in names}
        if (run/'reviews.jsonl').exists():hashes['reviews.jsonl']=sha(run/'reviews.jsonl')
        m={'version':VERSION,'created_utc':utc(),'reports_sha256':hashes,'software_tests_passed':t.returncode==0,'dataset_source':'CONSTRUCTED_FICTIONAL_BRIEFS','stage_receipts_source':'ACTUAL_SUBPROCESS_AND_OLLAMA_ONLY_IF_EXECUTED','v32_original_source_integrated':False,'video_generation_model_used':False,'negative_regressions_preserved':True,'approval':'USER_REVIEWS_NOT_INDEPENDENCE_VERIFIED'}
        save(run/'manifest_v42.json',m)
        return archive(run)
    upload=seal()
    print('RESULTS ZIP:',upload,flush=True)
    print('ACTUAL MEDIA DIRECTORY:',run/'media',flush=True)
    if t.returncode:
        print('DASHBOARD NOT OPENED: tests failed; see the logged diagnostics and results ZIP.',flush=True)
        return 2
    if not args.no_dashboard:
        dashboard(run,report,cards)

        upload=seal()
        print('SEALED ZIP:',upload,flush=True)
        if sys.platform=='darwin':subprocess.Popen(['open','-R',str(upload)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return 0
if __name__=='__main__':sys.exit(main())
