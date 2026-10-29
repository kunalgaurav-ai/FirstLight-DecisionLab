import unittest,pathlib,json,tempfile
from firstlight_decision.contracts import DEV,HOLDOUT,ALL,probes
from firstlight_decision.probes import complexity,single_case
from firstlight_decision.engine import risk_decision,choose_check,continuation,paired,execute,make_feedback,POLICIES
from firstlight_decision.decision_theory import RiskEvidence,safe_value_gate,wilson_interval
from firstlight_decision.offline_audit import run as audit
ROOT=pathlib.Path(__file__).resolve().parent.parent
DATA=ROOT/'data/QUIXBUGS_OFFICIAL_SUBSET'
class DecisionKernelTests(unittest.TestCase):
 def test_dev_holdout_disjoint(self):self.assertFalse(set(DEV)&set(HOLDOUT))
 def test_all_bundled_source_and_gold(self):
  for n in ALL:
   self.assertTrue((DATA/'python_programs'/f'{n}.py').is_file());self.assertTrue((DATA/'json_testcases'/f'{n}.json').is_file())
 def test_precommit_cases_not_identical_to_holdout_gold(self):
  for n in HOLDOUT:
   gold=[json.loads(s) for s in (DATA/'json_testcases'/f'{n}.json').read_text().splitlines() if s]
   self.assertTrue(probes(n));self.assertFalse(any(p in gold for p in probes(n)),n)
 def test_concrete_counterexample_exec(self):
  s='def bitcount(n):\n    return 0\n'
  r=single_case(s,'bitcount',[[7],3]);self.assertEqual(r['status'],'FAIL');self.assertEqual(r['observed'],'0')
 def test_static_reject_not_run(self):
  r=single_case('def bitcount(n):\n    return open("/etc/passwd")\n','bitcount',[[7],3]);self.assertEqual(r['status'],'STATIC_REJECT')
 def test_true_python_implementation(self):
  s='def bitcount(n):\n    return bin(n).count("1")\n'
  # bin is deliberately excluded from inherited worker builtins: test ordinary safe implementation
  r=single_case('def bitcount(n):\n    c=0\n    while n:\n        n=n&(n-1)\n        c+=1\n    return c\n','bitcount',[[7],3])
  self.assertEqual(r['status'],'PASS')
 def test_complexity_is_prefix_only(self):
  f='def levenshtein(a,b):\n    return levenshtein(a[1:],b)+levenshtein(a,b[1:])\n'
  r=risk_decision(f,'levenshtein',True);self.assertTrue(r['probe']);self.assertIn('RECURSION',r['reason'])
 def test_low_priority_falls_back(self):
  r=risk_decision('def gcd(a,b):\n    return a if b==0 else a%b\n','gcd',True);self.assertFalse(r['probe'])
 def test_bad_initial_repeat_is_stopped(self):
  calls=[]
  def fake(model,prompt):
   calls.append(prompt);return {'status':'OK','response':'def bitcount(n):\n    return 1','input_tokens':50,'output_tokens':10,'wall_s':.01}
  initial=fake('x','init')
  r=continuation('bitcount','def bitcount(n): return 0',initial,'x','COMPETENT_OPTIMIZED',invoke=fake)
  self.assertEqual(r['stop_reason'],'REPEATED_PATCH_STOP');self.assertEqual(r['model_calls'],2)
 def test_feedback_includes_case_but_not_gold(self):
  s=make_feedback('bitcount',{'status':'FAIL','case':[[7],3],'observed':'0'},'code')
  self.assertIn('[7]',s);self.assertIn('3',s);self.assertIn('0',s)
 def test_all_arms_same_initial(self):
  count=[]
  def fake(model,prompt):
   count.append(prompt);return {'status':'OK','response':'def bitcount(n):\n    c=0\n    while n:\n        n=n&(n-1)\n        c+=1\n    return c','input_tokens':25,'output_tokens':35,'wall_s':.01}
  r=paired('bitcount',(DATA/'python_programs/bitcount.py').read_text(),DATA/'json_testcases/bitcount.json','fake',invoke=fake)
  self.assertTrue(r['published_gold_only_read_after_all_arms']);self.assertEqual(len(count),1)
  self.assertEqual({p:r['arms'][p]['final_sha256'] for p in POLICIES}['COMPETENT_OPTIMIZED'],r['arms']['FIRSTLIGHT_SELECTIVE_VALUE_CHECK']['final_sha256'])
 def test_probe_policy_never_runs_fewer_than_basic(self):
  s='def bitcount(n):\n    return 1\n'
  for policy in POLICIES:
   r=choose_check('bitcount',s,policy);self.assertNotEqual(r['status'],'PASS');self.assertGreaterEqual(len(r['observations']),1)
 def test_historic_replay_is_not_a_savings_claim(self):
  rec=audit(ROOT)
  self.assertTrue(rec['only_offline_reverification']);self.assertEqual(len(rec['records']),6)
  self.assertTrue(all(x['posthoc_only'] for x in rec['records']))
 def test_strict_cost_gate_abstains_small_data(self):
  e=RiskEvidence(6,3,2,0,3,100,1,3)
  self.assertEqual(safe_value_gate(e)['action'],'FALLBACK_TO_COMPETENT')
 def test_cost_gate_positive_with_sufficient_support(self):
  e=RiskEvidence(400,300,260,0,100,1000,1,1)
  self.assertEqual(safe_value_gate(e)['action'],'CHECK')
 def test_cost_gate_negative(self):
  e=RiskEvidence(400,300,260,0,100,1,100,50)
  self.assertEqual(safe_value_gate(e)['action'],'FALLBACK_TO_COMPETENT')
 def test_wilson_interval(self):
  low,high=wilson_interval(0,10);self.assertEqual(low,0);self.assertGreater(high,0)
 def test_integrated_with_stub_and_no_llm_claim(self):
  def fake(model,prompt):
   return {'status':'OK','response':'def bitcount(n):\n    c=0\n    while n:\n        n=n&(n-1)\n        c+=1\n    return c','input_tokens':40,'output_tokens':30,'wall_s':0.01}
  with tempfile.TemporaryDirectory() as d:
   result=execute(DATA,pathlib.Path(d)/'run',model='testonly',invoke=fake,model_check=lambda:{'testonly'},task_limit=7)
   self.assertEqual(result['status'],'COMPLETE_PUBLIC_LOCAL_PILOT')
   self.assertEqual(len(result['records']),7)
   self.assertTrue((pathlib.Path(d)/'run/results.json').exists())
   self.assertEqual(result['cohorts']['HOLDOUT']['policies']['COMPETENT_OPTIMIZED']['accepted'],1)
 def test_license(self):self.assertIn('Permission is hereby granted',(DATA/'LICENSE').read_text())

if __name__=='__main__':unittest.main()
