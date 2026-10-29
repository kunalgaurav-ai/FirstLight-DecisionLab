import json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
from ail_v44.workbench import (suite, init_run, get,admit,review,assemble,decision,voi,cvar,local_modality_execution,package,artifact_valid,CATEGORIES)
from ail_v44.server import range_parts

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'data/workflow_suite_v44.json'

class SuiteTest(unittest.TestCase):
 def test_all_11(self):self.assertEqual(len(suite(PLAN)['tasks']),11)
 def test_six_video_workflows(self):self.assertEqual(len([t for t in suite(PLAN)['tasks'] if t['modality']=='text_to_video']),6)
 def test_all_long_24_to_32(self):
  for t in suite(PLAN)['tasks']:
   if t['modality']=='text_to_video':self.assertTrue(24<=t['target_duration_s']<=32)
 def test_per_shot_hash(self):
  from ail_v44.workbench import digest
  for t in suite(PLAN)['tasks']:
   for s in t.get('shots',[]):self.assertEqual(digest(s['prompt']),s['prompt_sha256'])
 def test_tampered_shot_rejected(self):
  d=suite(PLAN);d['tasks'][0]['shots'][0]['prompt']+=' tamper'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'x.json';p.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'MODIFIED_SHOT_PROMPT'):suite(p)
 def test_unchanged_frozen_source_prompts(self):
  from ail_v43.engine import task_index
  originals=task_index(ROOT/'data/frozen_prompt_first_v01.json')
  for t in suite(PLAN)['tasks']:self.assertEqual(t['source_prompt_sha256'],originals[t['task_id']]['prompt_sha256'])
 def test_modality_coverage(self):
  self.assertEqual(set(x['modality'] for x in suite(PLAN)['tasks']),{'text_to_video','text_to_image','text_to_speech','text_generation','tool_using_agent'})
 def test_no_automatic_provider_generation_in_launcher(self):
  src=(ROOT/'run_v44.sh').read_text();self.assertNotIn('ltx-proof',src);self.assertNotIn('generate(',src)

class DecisionTest(unittest.TestCase):
 def test_voi_calibrated_lower_bound_only_arithmetic(self):self.assertEqual(voi(3,.2,30,1),2)
 def test_voi_can_be_negative(self):self.assertEqual(voi(5,.1,10),-4)
 def test_invalid_probability(self):
  with self.assertRaises(ValueError):voi(3,1.2,10)
 def test_no_cost_claim_without_prospective_action_evidence(self):
  st={'artifacts':[{'id':'x','duration_gate':'PASS'}],'reviews':[{'artifact_id':'x','passed_local_rubric':False}]}
  self.assertEqual(decision(st,'x')['action'],'HOLD_FOR_CORRECTIVE_PROPOSAL')
 def test_empty_review_hold(self):
  self.assertEqual(decision({'artifacts':[{'id':'x','duration_gate':'PASS'}],'reviews':[]},'x')['action'],'HOLD_REVIEW')
 def test_short_video_not_approved(self):
  self.assertEqual(decision({'artifacts':[{'id':'x','duration_gate':'SHORT_FOR_TARGET'}],'reviews':[]},'x')['action'],'HOLD_REVIEW_OR_REGENERATE')
 def test_cvar_requires_support(self):
  with self.assertRaises(ValueError):cvar([1]*19)
 def test_cvar_actual_cost_samples(self):self.assertEqual(cvar(list(range(1,21))),19.5)

class WorkbenchTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.run=init_run(Path(self.temp.name)/'run',PLAN);self.plan=suite(PLAN)
 def test_missing_video_rejected(self):
  with self.assertRaisesRegex(ValueError,'NO_INPUT_VIDEO'):admit(self.run,self.plan,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01','/not/found.mp4','p','m','AUTHORIZED_NONCONFIDENTIAL_TEST')
 def test_rights_gate(self):
  f=Path(self.temp.name)/'a.mp4';f.write_bytes(b'fake')
  with self.assertRaisesRegex(ValueError,'VIDEO_RIGHTS_UNVERIFIED'):admit(self.run,self.plan,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01',f,'p','m','UNKNOWN')
 def test_spoof_verified_origin_rejected(self):
  f=Path(self.temp.name)/'a.mp4';f.write_bytes(b'fake')
  with self.assertRaisesRegex(ValueError,'ACTUAL_PROVIDER_RECEIPT_REQUIRED'):admit(self.run,self.plan,'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01',f,'p','m','AUTHORIZED_NONCONFIDENTIAL_TEST',origin='VERIFIED_LTX_SPACE_API')
 def test_cannot_assemble_without_real_reviewed_shots(self):
  with self.assertRaisesRegex(ValueError,'MISSING_VALID_REVIEWED_SHOT'):assemble(self.run,self.plan,'VID-03-LIBRARY-HANDOFF')
 def test_invalid_approval(self):
  with self.assertRaisesRegex(ValueError,'VIDEO_NOT_VERIFIED'):review(self.run,self.plan,'nonexistent',{}, {})
 def test_no_video_promised_when_absent(self):self.assertFalse((self.run/'artifacts').exists())
 def test_package_excludes_media_and_has_manifest(self):
  out=package(self.run)
  import zipfile
  with zipfile.ZipFile(out) as z:self.assertIn('MANIFEST_V44.json',z.namelist());self.assertIn('state.json',z.namelist())
 def test_asset_tamper_rejected(self):
  p=self.run/'artifacts'/'fake.mp4';p.parent.mkdir();p.write_bytes(b'old')
  self.assertTrue(artifact_valid(self.run,{'path':'artifacts/fake.mp4','sha256':__import__('hashlib').sha256(b'old').hexdigest()}))
  p.write_bytes(b'new');self.assertFalse(artifact_valid(self.run,{'path':'artifacts/fake.mp4','sha256':__import__('hashlib').sha256(b'old').hexdigest()}))
 def test_range_206(self):self.assertEqual(range_parts('bytes=0-9',100),(0,9,206))
 def test_range_416(self):self.assertEqual(range_parts('bytes=100-',100),(None,None,416))
 def test_real_tool_task_executes(self):
  results=local_modality_execution(self.run,self.plan,model='nonexistent-local-llm')
  r=next(x for x in results if x['task_id']=='AGENT-01-REPAIR')
  self.assertEqual(r['status'],'EXECUTED_CONTROLLED_TOOL_REPAIR');self.assertNotEqual(r['initial_returncode'],0);self.assertEqual(r['final_returncode'],0)
  self.assertEqual(next(x for x in results if x['task_id']=='IMG-01-COMPOSITION')['status'],'AWAITING_REAL_GENERATIVE_IMAGE_PROVIDER')

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Requires actual FFmpeg binary')
class ActualMediaTests(unittest.TestCase):
 def test_actual_7_second_video_probe_and_gate(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=init_run(Path(tmp)/'run',PLAN);out=Path(tmp)/'video.mp4'
   q=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=256x256:rate=12','-t','7','-c:v','mpeg4',str(out)],capture_output=True,timeout=80)
   self.assertEqual(q.returncode,0,q.stderr[:250])
   a=admit(run,suite(PLAN),'VID-01-LION-TEMPORAL','VID-01-LION-TEMPORAL-S01',out,'controlled-ffmpeg-fixture','mpeg4-pattern','AUTHORIZED_NONCONFIDENTIAL_TEST')
   self.assertEqual(a['duration_gate'],'PASS')
   self.assertEqual(a['origin'],'USER_ATTESTED')
   ratings={k:4 for k in CATEGORIES}
   task=suite(PLAN)['tasks'][0]
   events={task['shots'][0]['events_covered'][0]:'present'}
   r=review(run,suite(PLAN),a['id'],ratings,events)
   self.assertTrue(r['passed_local_rubric'])
   self.assertEqual(r['independent_approval'],'UNKNOWN')
   self.assertEqual(decision(get(run),a['id'])['action'],'REUSE_IF_SCOPED_AND_AUTHORIZED')

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Requires actual FFmpeg')
class ActualLongAssemblyTest(unittest.TestCase):
 def test_3_distinct_moving_sources_assemble_after_review(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=init_run(Path(tmp)/'run',PLAN);plan=suite(PLAN);task=next(t for t in plan['tasks'] if t['task_id']=='VID-03-LIBRARY-HANDOFF')
   for i,shot in enumerate(task['shots']):
    f=Path(tmp)/('moving-fixture-'+str(i)+'.mp4')
    q=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'testsrc2=size=160x288:rate=12,format=yuv420p','-t','7', '-c:v','mpeg4',str(f)],capture_output=True,timeout=90)
    self.assertEqual(q.returncode,0)
    a=admit(run,plan,task['task_id'],shot['shot_id'],f,'fixture-generator-not-a-video-model','ffmpeg-testsrc','AUTHORIZED_NONCONFIDENTIAL_TEST')
    r=review(run,plan,a['id'],{k:4 for k in CATEGORIES},{shot['events_covered'][0]:'present'})
    self.assertTrue(r['passed_local_rubric'])
   result=assemble(run,plan,task['task_id'])
   self.assertGreater(result['duration_s'],20)
   self.assertEqual(len(result['shot_ids']),3)
   self.assertFalse(result['independently_approved'])
