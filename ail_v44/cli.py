"""Single-machine command CLI; all external assets require conscious admission."""
import argparse, json
from pathlib import Path
from .workbench import suite,admit,review,assemble,package,init_run,local_modality_execution,admit_image,put,get
from .server import serve

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--suite',default='data/workflow_suite_v44.json')
 sub=p.add_subparsers(dest='command',required=True)
 sub.add_parser('init');sub.add_parser('local');sub.add_parser('serve');sub.add_parser('package')
 a=sub.add_parser('import-video');a.add_argument('--task',required=True);a.add_argument('--shot',required=True);a.add_argument('--file',required=True);a.add_argument('--provider',required=True);a.add_argument('--model',required=True);a.add_argument('--rights',required=True)
 a=sub.add_parser('import-image');a.add_argument('--task',required=True);a.add_argument('--file',required=True);a.add_argument('--provider',required=True);a.add_argument('--model',required=True);a.add_argument('--rights',required=True)
 a=sub.add_parser('review');a.add_argument('--artifact',required=True);a.add_argument('--json',required=True)
 a=sub.add_parser('assemble');a.add_argument('--task',required=True)
 a=sub.add_parser('ltx-paid');a.add_argument('--task',required=True);a.add_argument('--shot',required=True);a.add_argument('--model',default='ltx-2-5-fast');a.add_argument('--confirmed-price-usd-per-second',type=float,required=True);a.add_argument('--ack-billed-call',action='store_true')
 a=sub.add_parser('ltx-proof');a.add_argument('--task',required=True);a.add_argument('--shot',required=True);a.add_argument('--ack-quota',action='store_true');a.add_argument('--ack-short-clip',action='store_true')
 args=p.parse_args();plan=suite(args.suite);run=Path(args.run)
 if args.command=='init':init_run(run,args.suite);return
 if args.command=='local':local_modality_execution(run,plan);package(run);return
 if args.command=='import-video':
  r=admit(run,plan,args.task,args.shot,args.file,args.provider,args.model,args.rights);package(run)
  print('IMPORTED USER-ATTESTED CLIP:',r['id'],'DURATION:',r['media']['duration_s'],'GATE:',r['duration_gate'])
 elif args.command=='import-image':
  print('IMAGE IMPORT RECEIPT:',admit_image(run,plan,args.task,args.file,args.provider,args.model,args.rights));package(run)
 elif args.command=='review':
  r=json.loads(Path(args.json).read_text());print(review(run,plan,args.artifact,r['ratings'],r['events'],r.get('reviewer_kind','SELF_REVIEW')));package(run)
 elif args.command=='assemble':print(assemble(run,plan,args.task));package(run)
 elif args.command=='package':print(package(run))
 elif args.command=='serve':serve(run,args.suite)
 elif args.command=='ltx-paid':
  if not args.ack_billed_call:raise SystemExit('Use --ack-billed-call to explicitly authorize a real billed provider request.')
  from ail_v44.provider_ltx import generate
  from ail_v44.workbench import write_json,utc
  task=next((t for t in plan['tasks'] if t['task_id']==args.task),None)
  if task is None:raise ValueError('UNKNOWN_TASK')
  shot=next((s for s in task.get('shots',[]) if s['shot_id']==args.shot),None)
  if shot is None:raise ValueError('UNKNOWN_SHOT')
  progress=run/'pending_ltx_job_v44.json'
  def on_status(data):write_json(progress,{'utc':utc(),**data})
  out=run/'provider_downloads'/args.task/args.shot/'output_v2.mp4'
  receipt=generate(shot['prompt'],out,args.model,ack_billable=True,price_usd_per_sec=args.confirmed_price_usd_per_second,on_status=on_status)
  r=admit(run,plan,args.task,args.shot,out,'LTX official v2 API',receipt['model'],'AUTHORIZED_NONCONFIDENTIAL_TEST',origin='VERIFIED_PROVIDER_API',backend_receipt=receipt)
  package(run);print('PROVIDER JOB:',receipt['provider_job_id'],'ACTUAL CLIP:',r['id'],'GATE:',r['duration_gate'],'INVOICE STILL UNKNOWN')
 elif args.command=='ltx-proof':
  if not(args.ack_quota and args.ack_short_clip):raise SystemExit('EXPLICIT --ack-quota AND --ack-short-clip REQUIRED: HF Space clips are max 5 seconds and CANNOT pass 8-second shot acceptance.')
  t=next((t for t in plan['tasks'] if t['task_id']==args.task),None)
  if not t:raise ValueError('UNKNOWN_TASK')
  shot=next((s for s in t.get('shots',[]) if s['shot_id']==args.shot),None)
  if not shot:raise ValueError('UNKNOWN_SHOT')
  from ail_v43.backend import generate
  out=run/'provider_downloads'/str(args.task)/str(args.shot)/'generated.mp4'
  receipt=generate(shot['prompt'],out,seed=42,duration=5)
  r=admit(run,plan,args.task,args.shot,out,'HuggingFace official LTX Space',receipt['model'],'AUTHORIZED_NONCONFIDENTIAL_TEST',origin='VERIFIED_LTX_SPACE_API',backend_receipt=receipt)
  package(run);print('SHORT CAPABILITY PROBE:',r['id'],r['duration_gate'])
if __name__=='__main__':main()
