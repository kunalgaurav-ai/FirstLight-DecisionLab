import json,os,pathlib,subprocess,tempfile,threading,unittest,urllib.request
from unittest.mock import patch
from ail_v46 import runtime as rt
from ail_v46.controller import bound_action,workflow_action
from ail_v46.server import create_server
from ail_v44.workbench import suite, get, review

ROOT=pathlib.Path(__file__).resolve().parents[1]
PLAN=suite(ROOT/'data/workflow_suite_v44.json')

class RealPathTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.run=pathlib.Path(self.temp.name)/'v46_trial';rt.start(self.run,ROOT/'data/workflow_suite_v44.json')
 def video(self):
  p=self.run/'movie.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=384x640:rate=15','-t','1.5','-pix_fmt','yuv420p','-c:v','libx264',str(p)],check=True,capture_output=True,timeout=45)
  return p
 def test_frozen_plans_have_nineteen_and_no_phantom_video(self):
  self.assertEqual(sum(len(t.get('shots',[])) for t in PLAN['tasks']),19)
  self.assertFalse(get(self.run/'workflow')['artifacts']);self.assertFalse(rt.jobs(self.run))
 def test_ollama_real_contract_mocked_provider_not_efficacy(self):
  def fn(p,m):return {'output':'Actual provider test output','prompt_eval_count':9,'eval_count':4,'wall_s':.03,'model':m}
  j=rt.execute_local(self.run,'text','Write a note about the forest',call_fn=fn)
  self.assertEqual(j['status'],'SUCCESS_VERIFIED');self.assertEqual(j['receipt']['prompt_eval_count'],9)
  self.assertTrue((self.run/j['path']).is_file())
 def test_local_bad_response_is_not_success(self):
  j=rt.execute_local(self.run,'text','write a note',call_fn=lambda p,m:{'output':'test'})
  self.assertEqual(j['status'],'FAILED_PROVIDER')
 def test_video_fails_closed_on_wrong_length_and_rights(self):
  def fake(prompt,destination,**kw):
   self.video().replace(destination)
   return {'generation_mode':'REAL_REMOTE_TEXT_TO_VIDEO_MODEL','provider':'HF_SPACES_ZEROGPU','model':'LTX test', 'cost_usd':None}
  r=rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_5s_probe',True,free_backend=fake)
  self.assertEqual(r['status'],'SUCCESS_VERIFIED');self.assertEqual(r['duration_gate'],'SHORT_FOR_TARGET')
  a=get(self.run/'workflow')['artifacts'][0]
  self.assertEqual(a['origin'],'VERIFIED_LTX_SPACE_API')
  with self.assertRaises(ValueError):review(self.run/'workflow',PLAN,a['id'],{}, {})
 def test_quota_failure_persists_and_is_not_retried(self):
  def fail(*a,**kw):raise RuntimeError('ZeroGPU quota exceeded')
  r=rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_5s_probe',True,free_backend=fail)
  self.assertEqual(r['status'],'BLOCKED_DEPENDENCY');self.assertIn('quota',r['reason'])
  self.assertEqual(len(rt.jobs(self.run)),1)
 def test_billed_must_be_local_authorized_explicit_and_price_valid(self):
  with self.assertRaises(ValueError):rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_v2_8s',False)
  with self.assertRaises(ValueError):rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_v2_8s',True,rate=None)
 def test_interruption_never_resubmits(self):
  j=rt.create_job(self.run,'video','VID-01','S01','ltx_v2_8s');rt.modify(self.run,j['id'],status='PROVIDER_SUBMITTED',provider_job_id='abc')
  rt.recover_interrupted(self.run)
  self.assertEqual(rt.jobs(self.run)[0]['status'],'INTERRUPTED');self.assertEqual(rt.jobs(self.run)[0]['provider_job_id'],'abc')
 def test_report_zip_has_evidence_and_no_media(self):
  p=rt.close_reports(self.run)
  import zipfile
  with zipfile.ZipFile(p) as z:
   self.assertIn('jobs.json',z.namelist());self.assertIn('MANIFEST_V46.json',z.namelist())
   self.assertFalse(any(x.endswith('.mp4') for x in z.namelist()))
 def test_http_session_and_actual_video_playback_byte_range(self):
  r=rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_5s_probe',True,
                      free_backend=lambda p,d,**kw:(__import__('shutil').copyfile(self.video(),d) and {'generation_mode':'REAL_REMOTE_TEXT_TO_VIDEO_MODEL','provider':'HF_SPACES_ZEROGPU','model':'LTX-test'}))
  srv=create_server(self.run,ROOT/'data/workflow_suite_v44.json');thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start();self.addCleanup(srv.server_close);self.addCleanup(srv.shutdown)
  host=f'http://127.0.0.1:{srv.server_port}'
  with urllib.request.urlopen(host+'/api/state') as resp:state=json.load(resp)
  self.assertEqual(len(state['state']['artifacts']),1)
  vid=state['state']['artifacts'][0]['id'];rq=urllib.request.Request(host+'/media/video/'+vid,headers={'Range':'bytes=0-99'})
  with urllib.request.urlopen(rq) as resp:self.assertEqual(resp.status,206);self.assertEqual(len(resp.read()),100)
  # Wrong session token fails; browser must not silently record actions.
  rq=urllib.request.Request(host+'/api/local',data=b'{"kind":"text","prompt":"hello"}',headers={'Content-Type':'application/json','X-AIL-Session':'bad'})
  with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(rq)
  self.assertEqual(cm.exception.code,403)
  # SHA mismatch blocks streaming immediately.
  a=get(self.run/'workflow')['artifacts'][0];(self.run/'workflow'/a['path']).write_bytes(b'bad')
  with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(host+'/media/video/'+vid)
  self.assertEqual(cm.exception.code,404)
 def test_cache_stop_holds_without_review(self):
  self.assertEqual(workflow_action({'available':True},None,rights='AUTHORIZED_NONCONFIDENTIAL_TEST')['action'],'REVIEW_BEFORE_EXPENSIVE_DESCENDANTS')
 def test_economic_weak_evidence_never_passes(self):
  self.assertEqual(bound_action([])['decision'],'HOLD')
  self.assertEqual(bound_action([{'pair_id':'a'}]*35,loss_ceiling=5,tail_tolerance=1)['decision'],'HOLD')
 def test_economic_valid_but_no_strong_edge_holds(self):
  rows=[{'pair_id':str(i),'provenance':'ACTUAL_EXECUTION_INDEPENDENTLY_GRADED','split':'PROSPECTIVE_HELD_OUT','baseline_accepted':True,'ail_accepted':True,'baseline_all_in_usd':2.0,'ail_all_in_usd':2.0} for i in range(60)]
  self.assertEqual(bound_action(rows,loss_ceiling=2,tail_tolerance=1)['decision'],'HOLD')
 def test_economic_quality_worse_fails_closed(self):
  rows=[{'pair_id':str(i),'provenance':'ACTUAL_EXECUTION_INDEPENDENTLY_GRADED','split':'PROSPECTIVE_HELD_OUT','baseline_accepted':True,'ail_accepted':i>0,'baseline_all_in_usd':2.0,'ail_all_in_usd':1.0} for i in range(40)]
  self.assertEqual(bound_action(rows,loss_ceiling=5,tail_tolerance=1)['reason'],'QUALITY_NONINFERIORITY_VIOLATED')

if __name__=='__main__':unittest.main()

class V46ProviderContractTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.run=pathlib.Path(self.temp.name)/'v46_contract';rt.start(self.run,ROOT/'data/workflow_suite_v44.json')
 def test_paid_api_real_media_contract_with_stub_not_billing_claim(self):
  def fake(prompt,dest,model,ack_billable=False,price_usd_per_sec=None,on_status=None):
   self.assertTrue(ack_billable);self.assertTrue(price_usd_per_sec>0)
   on_status({'job_id':'provider-test-id','cost_estimate_usd':8*price_usd_per_sec})
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=384x640:rate=15','-t','8.1','-pix_fmt','yuv420p','-c:v','libx264',str(dest)],check=True,capture_output=True,timeout=45)
   return {'generation_mode':'REAL_REMOTE_TEXT_TO_VIDEO_MODEL','provider':'LTXV_V2_OFFICIAL_BILLED_API','provider_job_id':'provider-test-id','model':model,'inferred_cost_usd':8*price_usd_per_sec,'actual_invoice_usd':None}
  rec=rt.generate_video(self.run,PLAN,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','ltx_v2_8s',True,rate=.2,paid_backend=fake)
  self.assertEqual(rec['status'],'SUCCESS_VERIFIED');self.assertEqual(rec['duration_gate'],'PASS')
  self.assertEqual(rec['provider_cost_usd'],None)
  self.assertEqual(rec['provider_job_id'],'provider-test-id')
  self.assertEqual(len(get(self.run/'workflow')['artifacts']),1)
 def test_existing_dir_from_shell_logs_safe_new_init(self):
  target=pathlib.Path(self.temp.name)/'precreated';target.mkdir();(target/'tests.txt').write_text('passed')
  rt.start(target,ROOT/'data/workflow_suite_v44.json')
  self.assertTrue((target/'tests.txt').exists())
  with self.assertRaises(ValueError):rt.start(target,ROOT/'data/workflow_suite_v44.json')
 def test_image_fail_closed_and_provenance_with_mock_image_not_customer_data(self):
  class Fake:
   def __init__(self,api_key):pass
   def text_to_image(self,prompt,model):
    from PIL import Image
    return Image.new('RGB',(256,256),'orange')
  with patch.dict(os.environ,{'AIL_ALLOW_BILLED_IMAGE':'1','HF_TOKEN':'TEST_NO_NETWORK'}):
   rec=rt.generate_image(self.run,PLAN,'IMG-01-COMPOSITION',True,client_factory=Fake)
  self.assertEqual(rec['status'],'SUCCESS_VERIFIED')
  img=get(self.run/'workflow')['images'][0]
  self.assertEqual(img['origin'],'EXECUTED_HF_INFERENCE_CLIENT_LOCAL_RECEIPT_NOT_PROVIDER_INVOICE')
  self.assertEqual(img['approval'],'UNKNOWN_NO_INDEPENDENT_REVIEW')
 def test_missing_auth_image_rejected_before_job(self):
  with patch.dict(os.environ,{'HF_TOKEN':'','AIL_ALLOW_BILLED_IMAGE':''}):
   with self.assertRaises(ValueError):rt.generate_image(self.run,PLAN,'IMG-01-COMPOSITION',True)
  self.assertFalse(rt.jobs(self.run))

class V46WebActionTests(unittest.TestCase):
 def test_authorized_http_prompt_submitted_not_inert_widget(self):
  import time
  with tempfile.TemporaryDirectory() as td:
   run=pathlib.Path(td)/'run';rt.start(run,ROOT/'data/workflow_suite_v44.json')
   srv=create_server(run,ROOT/'data/workflow_suite_v44.json')
   threading.Thread(target=srv.serve_forever,daemon=True).start()
   try:
    base=f'http://127.0.0.1:{srv.server_port}'
    with urllib.request.urlopen(base+'/api/state') as res:tok=json.load(res)['token']
    def model(prompt,model):return {'output':'An observed generated output','model':model,'prompt_eval_count':20,'eval_count':6,'wall_s':.02}
    # The endpoint invokes the real runtime, with only model transport faked in this controlled test.
    with patch('ail_v46.runtime._ollama',side_effect=model):
     data=json.dumps({'kind':'text','prompt':'Please explain this actual museum note in detail'}).encode()
     rq=urllib.request.Request(base+'/api/local',data=data,headers={'Content-Type':'application/json','X-AIL-Session':tok},method='POST')
     with urllib.request.urlopen(rq) as res:self.assertEqual(res.status,202)
     for _ in range(100):
      if rt.jobs(run) and rt.jobs(run)[-1]['status'] in ('SUCCESS_VERIFIED','FAILED_PROVIDER'):break
      time.sleep(.03)
    self.assertEqual(rt.jobs(run)[-1]['status'],'SUCCESS_VERIFIED')
    jid=rt.jobs(run)[-1]['id']
    with urllib.request.urlopen(base+'/media/local/'+jid) as res:self.assertIn('observed generated output',res.read().decode())
   finally:srv.shutdown();srv.server_close()

class HistoricalSafeRecoveryTests(unittest.TestCase):
 def test_original_video_recovered_by_exact_receipt_not_reassigned_to_shot(self):
  import hashlib
  with tempfile.TemporaryDirectory() as td:
   downloads=pathlib.Path(td)/'Downloads';prior=downloads/'AIL-v431-executions'/'source-test'/'agent-intelligence-lab-v4.3.1-evidence-ready'/'runs'/'v431_test'
   mp4=prior/'media'/'clip-123456789abc'/'generated_0.mp4';mp4.parent.mkdir(parents=True)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=384x640:rate=15','-t','1.5','-c:v','libx264',str(mp4)],check=True,capture_output=True,timeout=35)
   sha=rt.file_sha(mp4)
   report={'records':[{'clip_id':'clip-123456789abc','status':'COMPLETE_VERIFIED','error':None,'final_media':'media/clip-123456789abc/generated_0.mp4','probe':{'sha256':sha},'model':'LTX real historical record','prompt_sent':'Original full five-second prompt'}]}
   (prior/'GENERATIVE_EVIDENCE_V431.json').write_text(json.dumps(report))
   run=pathlib.Path(td)/'current';rt.start(run,ROOT/'data/workflow_suite_v44.json')
   recovered=rt.recover_prior_v43_clips(run,downloads_root=downloads)
   self.assertEqual(len(recovered),1)
   self.assertFalse(recovered[0]['included_in_19_shot_benchmark'])
   self.assertEqual(rt.file_sha(run/recovered[0]['path']),sha)
   self.assertEqual(get(run/'workflow')['artifacts'],[])
   # A modified historical file may not be admitted as evidence.
   (run/recovered[0]['path']).write_bytes(b'corrupted')
   srv=create_server(run,ROOT/'data/workflow_suite_v44.json');threading.Thread(target=srv.serve_forever,daemon=True).start()
   try:
    with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(f'http://127.0.0.1:{srv.server_port}/media/legacy/clip-123456789abc')
    self.assertEqual(cm.exception.code,404)
   finally:srv.shutdown();srv.server_close()
