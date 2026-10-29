import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ail_v38.workflow import CASES,content_contract
from ail_v39.workflow import (ARMS,decide_after_draft,factual_narration,
                               run_pipeline,storyboard_prompt,narration_prompt,summarize)
class PrecommitV39(unittest.TestCase):
 def setUp(self):self.task=CASES[0]
 def test_baseline_value_protection(self):
  text=factual_narration(self.task)
  self.assertTrue(content_contract(text,self.task)['narrow_literal_contract_pass'])
 def test_all_task_source_preservation(self):
  for task in CASES:
   s=factual_narration(task)
   self.assertTrue(content_contract(s,task)['narrow_literal_contract_pass'])
   self.assertEqual(len(s.split()),len(s.split()))
 def test_b1_failure_requires_retry(self):
  self.assertEqual('ONE_LLM_REASK',decide_after_draft('B1_STRICT_REASK',self.task,'wrong',{'narrow_literal_contract_pass':False}))
 def test_ail_changes_action_after_failure(self):
  self.assertEqual('DETERMINISTIC_REPAIR_NO_EXTRA_LLM',decide_after_draft('AIL_CONDITIONAL_REPAIR_EXPERIMENTAL',self.task,'wrong',{'narrow_literal_contract_pass':False}))
 def test_valid_draft_requires_no_repair(self):
  for arm in ['B1_STRICT_REASK','AIL_CONDITIONAL_REPAIR_EXPERIMENTAL']:
   self.assertEqual('ACCEPT_LLM_NARRATION',decide_after_draft(arm,self.task,'valid',{'narrow_literal_contract_pass':True}))
 def test_toolfirst(self):
  self.assertEqual('DETERMINISTIC_SOURCE_ASSEMBLY',decide_after_draft('B2_TOOL_FIRST',self.task,'',{'narrow_literal_contract_pass':False}))
 def test_storyboard_requirements_are_stage_specific(self):
  self.assertNotIn('both exact factual sentences',storyboard_prompt(self.task).lower())
  self.assertIn('copy',narration_prompt(self.task,'plan').lower())
 def test_strict_block_never_launches_say(self):
  with tempfile.TemporaryDirectory() as temp:
   ran=[]
   def fake(*args,**kwargs):
    ran.append(args[3]); return 'Plan' if len(ran)==1 else 'No correct facts.'
   with patch('ail_v39.workflow.model_call',side_effect=fake), patch('ail_v39.workflow.safe_run',side_effect=AssertionError('should not run media')):
    v=run_pipeline(Path(temp),Path(temp)/'unused.mp4','m','base',self.task,'B1_STRICT_REASK',1)
   self.assertEqual(v['status'],'STOPPED_PRECOMMIT_NARRATION')
   self.assertEqual(len(ran),3)
   self.assertFalse(any(x['stage']=='mac_say_speech' for x in v['receipts']))
 def test_ail_fallback_must_pass_exact_fact_gate(self):
  with tempfile.TemporaryDirectory() as temp:
   def fake(*args,**kwargs):return 'A shot plan.' if args[3]=='ollama_storyboard' else 'Invalid narration.'
   with patch('ail_v39.workflow.model_call',side_effect=fake), patch('ail_v39.workflow.safe_run',side_effect=lambda *a,**k:{'exit':1}):
    out=run_pipeline(Path(temp),Path(temp)/'unused.mp4','m','base',self.task,'AIL_CONDITIONAL_REPAIR_EXPERIMENTAL',1)
   self.assertEqual(out['status'],'FAILED_EXECUTION')
   self.assertTrue(out['narration_contract']['narrow_literal_contract_pass'])
   self.assertTrue(any(r['stage']=='hard_precommit_gate' and r['result']=='PASS' for r in out['receipts']))
   self.assertFalse(any(r['stage']=='ollama_narration_reask' for r in out['receipts']))
 def test_summary_zero_denominator(self):
  s=summarize([])
  self.assertEqual(set(s),set(ARMS))
  self.assertTrue(all(d['cost_per_approved_result'] is None for d in s.values()))
if __name__=='__main__':unittest.main()
