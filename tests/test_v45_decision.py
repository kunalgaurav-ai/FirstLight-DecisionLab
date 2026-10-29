import json,tempfile,unittest
from pathlib import Path
from urllib import request,error
from threading import Thread
from ail_v45.engine import (load_plan,validate_text,targeted_repair,text_trial,audio_trials,new_report,package,file_sha)
from ail_v45.server import create_server,get_available

PLAN='data/decision_suite_v45.json'
def fake_call(output):
 def f(prompt,model):return {'output':output,'model':'mock-only','model_digest':'test-not-real','prompt_eval_count':13,'eval_count':17,'wall_s':.03,'provider_ns':{}}
 return f
class DecisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.plan=load_plan(PLAN)
 def test_all_four_canonical_texts_pass(self):
  for t in self.plan['texts']:self.assertTrue(validate_text(t,t['canonical'])['objective_pass'])
 def test_truncated_original_is_repaired_not_declared_approved(self):
  t=self.plan['texts'][0];out,a=targeted_repair(t,'Visit us soon.')
  self.assertTrue(validate_text(t,out)['objective_pass']);self.assertIn(a,('CANONICAL_FALLBACK','TARGETED_FACT_INSERTION','TARGETED_FACT_AND_PADDING'))
 def test_unrepaired_initial_can_fall_back_to_safe_canonical(self):
  t=self.plan['texts'][1];out,a=targeted_repair(t,'word '*120)
  self.assertEqual(a,'CANONICAL_FALLBACK');self.assertEqual(out,t['canonical'])
 def test_valid_output_no_extra_modification(self):
  t=self.plan['texts'][1];o,a=targeted_repair(t,t['canonical'])
  self.assertEqual(o,t['canonical']);self.assertEqual(a,'NO_REPAIR')
 def test_retry_branch_physically_calls_model_twice_and_preserves_shared_prefix(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[];t=self.plan['texts'][0]
   def model(prompt,model):
    calls.append(prompt)
    return fake_call('Bad short answer' if len(calls)==1 else t['canonical'])(prompt,model)
   r=text_trial(t,tmp,'mock-only',model)
   self.assertEqual(len(calls),2);self.assertEqual(r['arms']['B1_COMPETENT_LLM_RETRY']['llm_call_count'],2)
   self.assertEqual(r['arms']['AIL_CONDITIONAL_REPAIR']['llm_call_count'],1)
   self.assertEqual(r['arms']['B2_COMPETENT_TOOL_FIRST']['llm_call_count'],0)
   self.assertTrue(all(v['validation']['objective_pass'] for v in r['arms'].values()))
   self.assertEqual(r['predecision_objective']['objective_pass'],False)
 def test_valid_initial_never_triggers_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=self.plan['texts'][0];calls=[]
   def model(prompt,model):calls.append(1);return fake_call(t['canonical'])(prompt,model)
   r=text_trial(t,tmp,'mock-only',model)
   self.assertEqual(len(calls),1)
   self.assertEqual(r['arms']['B1_COMPETENT_LLM_RETRY']['action'],'ACCEPT_INITIAL')
 def test_no_ollama_is_a_hold_not_a_fake_benchmark(self):
  with tempfile.TemporaryDirectory() as tmp:
   def missing(prompt,model):raise ConnectionError('No Ollama')
   r=text_trial(self.plan['texts'][0],tmp,'mock-only',missing)
   self.assertEqual(r['status'],'HOLD_NO_REAL_LLM_INPUT')
   self.assertNotIn('AIL_CONDITIONAL_REPAIR',r['arms'])
 def test_changed_prompt_hash_fails_closed(self):
  import copy
  with tempfile.TemporaryDirectory() as tmp:
   p=copy.deepcopy(self.plan);p['texts'][0]['prompt']+=' unsafe'
   f=Path(tmp)/'bad.json';f.write_text(json.dumps(p))
   with self.assertRaises(ValueError):load_plan(f)
 def test_voice_text_excludes_delivery_instruction(self):
  for t in self.plan['audios']:
   self.assertNotIn(t['delivery_instructions'],t['spoken_text'])
 def test_audio_cache_baseline_has_same_benefit_as_ail(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def synth(text,out):
    calls.append(text);Path(out).write_bytes(b'FORM'+b'1'*200);return 0.02,4.2
   r=audio_trials(self.plan,tmp,synth)
   self.assertEqual(r['arms']['B1_COMPETENT_NO_CACHE']['actual_tts_calls'],3)
   self.assertEqual(r['arms']['B2_COMPETENT_EXACT_CACHE']['actual_tts_calls'],2)
   self.assertEqual(r['arms']['AIL_EXACT_CACHE']['actual_tts_calls'],2)
   self.assertEqual(len(calls),7)
   self.assertTrue(r['arms']['AIL_EXACT_CACHE']['records'][2]['cache_hit'])
 def test_launcher_precreated_log_directory_is_permitted_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';run.mkdir();(run/'tests_v45.txt').write_text('passed')
   new_report(run,PLAN,call_fn=fake_call(self.plan['texts'][0]['canonical']))
   self.assertTrue((run/'results_v45.json').exists())
   with self.assertRaises(ValueError):new_report(run,PLAN,call_fn=fake_call('x'))
 def test_no_provider_dollars_in_results(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=self.plan['texts'][0]
   r=new_report(Path(tmp)/'run',PLAN,call_fn=fake_call(t['canonical']))
   self.assertIsNone(r['provider_cost_usd']);self.assertIsNone(r['independently_approved_outcomes'])
   self.assertEqual(r['strong_oss_competitive_superiority'],'NOT_ESTABLISHED')
 def test_report_zip_hashes(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';new_report(run,PLAN,call_fn=fake_call(self.plan['texts'][0]['canonical']))
   z=package(run)
   import zipfile,hashlib
   with zipfile.ZipFile(z) as f:
    manifest=json.loads(f.read('MANIFEST_V45.json'))
    for a in manifest['files']:self.assertEqual(hashlib.sha256(f.read(a['path'])).hexdigest(),a['sha256'])
    self.assertTrue(all('artifacts/' not in n for n in f.namelist()))
 def test_media_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';r=new_report(run,PLAN,call_fn=fake_call(self.plan['texts'][0]['canonical']))
   name=r['audio_trials']['arms'] if r['audio_trials'].get('arms') else None
   rec=r['text_trials'][0]['arms']['B2_COMPETENT_TOOL_FIRST'];p=Path(rec['output_path']);self.assertTrue(get_available(run,'text',r['text_trials'][0]['task_id'],'B2_COMPETENT_TOOL_FIRST'))
   p.write_text('tampered');self.assertIsNone(get_available(run,'text',r['text_trials'][0]['task_id'],'B2_COMPETENT_TOOL_FIRST'))
 def test_http_receipts_and_self_review_persistence(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'run';new_report(run,PLAN,call_fn=fake_call(self.plan['texts'][0]['canonical']))
   srv=create_server(run,PLAN,'data/workflow_suite_v44.json');worker=Thread(target=srv.serve_forever,daemon=True);worker.start()
   try:
    base=f'http://127.0.0.1:{srv.server_port}'
    with request.urlopen(base+'/api/report') as u:d=json.load(u)
    self.assertEqual(len(d['video_campaigns']),6);self.assertEqual(len(d['report']['text_trials']),4)
    with request.urlopen(base+'/app.js') as u:self.assertIn('function makeReview',u.read().decode())
    p=json.dumps({'kind':'TEXT','task_id':'TEXT-01-FACTS','arm':'B2_COMPETENT_TOOL_FIRST','decision':'USABLE'}).encode()
    with request.urlopen(request.Request(base+'/api/review',data=p,headers={'Content-Type':'application/json'})) as u:self.assertEqual(u.status,200)
    with request.urlopen(base+'/api/report') as u:self.assertEqual(len(json.load(u)['reviews']),1)
    with self.assertRaises(error.HTTPError):request.urlopen(request.Request(base+'/api/review',data=p,headers={'Content-Type':'application/json'}))
    with request.urlopen(base+'/artifact/text/TEXT-01-FACTS/B2_COMPETENT_TOOL_FIRST') as u:self.assertIn('museum',u.read().decode().lower())
    with self.assertRaises(error.HTTPError):request.urlopen(base+'/artifact/text/TEXT-01-FACTS/not-a-policy')
   finally:srv.shutdown();srv.server_close();worker.join(timeout=2)

if __name__=='__main__':unittest.main()
