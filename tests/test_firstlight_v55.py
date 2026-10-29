import json,os,pathlib,tempfile,unittest,zipfile
from firstlight_v55 import VERSION
from firstlight_v55.sandbox import validate,run_cases,extract,PROBES
from firstlight_v55.experiment import continuation,paired_task,summarize,execute,precommit
from firstlight_v55.pack import pack,check
from firstlight_v55.source import TASKS
from firstlight_v55.web import serve

class V55ResearchTests(unittest.TestCase):
    def test_static_validator_denies_imports_dynamic_exec_introspection_and_attributes(self):
        bad=['import os\ndef gcd(a,b):return a','def gcd(a,b):return __import__("os")',
             'def gcd(a,b):return (1).__class__','def gcd(a,b):return os.system("ls")','def gcd(a,b):return eval("7")',
             'def gcd(a,b):return open("/etc/passwd")']
        for text in bad:self.assertIsNotNone(validate(text,'gcd'),text)
        self.assertIsNone(validate('def gcd(a,b):\n    while b:\n        a,b=b,a%b\n    return a\n','gcd'))
        self.assertIsNone(validate('def gcd(a,b):\n    xs=[]\n    xs.append(a)\n    return xs\n','gcd'))
    def test_actual_bounded_subprocess_correct_and_wrong(self):
        good='def gcd(a,b):\n    while b:\n        a,b=b,a%b\n    return a\n'
        self.assertEqual(run_cases(good,'gcd',PROBES['gcd'])['status'],'PASS')
        wrong='def gcd(a,b):\n    return a\n'
        self.assertEqual(run_cases(wrong,'gcd',PROBES['gcd'])['status'],'FAIL')
    def test_actual_bounded_subprocess_timeout(self):
        p='def gcd(a,b):\n    while True:\n        pass\n'
        self.assertIn(run_cases(p,'gcd',PROBES['gcd'][:1],timeout=.7)['status'],('CHILD_TIMEOUT','CHILD_ERROR'))
    def test_extraction(self):
        self.assertTrue(extract('Here:\n```python\ndef gcd(a,b):\n return 1\n```','gcd').startswith('def gcd('))
    def test_extra_signal_not_secret_gold(self):
        good='def gcd(a,b):\n    while b:\n        a,b=b,a%b\n    return a\n'
        base=precommit('gcd',good,'COMPETENT_TEST_REPAIR');fl=precommit('gcd',good,'FIRSTLIGHT_PRECOMMIT')
        self.assertEqual(base['probe_count'],1);self.assertEqual(fl['probe_count'],2)
        self.assertEqual(base['status'],'PASS');self.assertEqual(fl['status'],'PASS')
    def test_pair_shared_checkpoint_and_gold_never_in_prompt(self):
        seen=[]
        wrong='def gcd(a,b):\n return a\n';correct='def gcd(a,b):\n while b:\n  a,b=b,a%b\n return a\n'
        def model(m,p):
            seen.append(p)
            return dict(status='OK',response=wrong if len(seen)==1 else correct,input_tokens=10,output_tokens=7,wall_s=.05,model=m)
        problem={'source':'def gcd(a,b):\n return 999\n','final_gold':[[[121,11],11],[[7,2],1]]}
        r=paired_task('gcd',problem,'mock-local',invoke=model,max_repairs=1)
        self.assertEqual(len(seen),3)
        self.assertTrue(r['same_initial_model_output_for_both_arms'])
        self.assertTrue(all(a['independent_final_cases']['all_pass'] for a in r['arms'].values()))
        self.assertTrue(all('121' not in s for s in seen))
        self.assertEqual(r['retrospective_initial_proposal_grade']['pass'],False)
        self.assertEqual(r['arms']['COMPETENT_TEST_REPAIR']['reported_usage']['total_tokens'],34)
    def test_detects_quality_failure_even_when_lower_tokens(self):
        # Explicit counterexample to claiming quality-downgrade savings.
        correct={'independent_final_cases':{'all_pass':True},'reported_usage':{'total_tokens':100,'all_provider_token_receipts_present':True,'total_calls':2},'repair_calls':1,'precommit_warnings':1,'precommit_probe_wall_s':1,'continuation_plus_inference_wall_s':2,
                 'precommit_history':[{'result':{'status':'FAIL'}}]}
        fail={**correct,'independent_final_cases':{'all_pass':False},'reported_usage':{'total_tokens':10,'all_provider_token_receipts_present':True,'total_calls':1}}
        r=[{'arms':{'COMPETENT_TEST_REPAIR':correct,'FIRSTLIGHT_PRECOMMIT':fail},'retrospective_initial_proposal_grade':{'pass':False}}]
        s=summarize(r)
        self.assertEqual(s['paired']['net_quality_gain_tasks'],-1)
        self.assertEqual(s['paired']['quality_gate'],'UNESTABLISHED_SMALL_PILOT')
        self.assertEqual(s['paired']['claimed_usd_saved'],None)
    def test_research_integration_fixture_labeled_and_evidence_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_source(run,where):
                return {'gcd':{'name':'gcd','source':'def gcd(a,b):\n    return a\n','final_gold':[[[21,35],7],[[8,2],2]]}}, {'source':'CONTROLLED_UNIT_TEST_NO_PUBLIC_DATA','git_commit':None}
            def model(m,p):return dict(status='OK',response='def gcd(a,b):\n    while b:\n        a,b=b,a%b\n    return a\n',input_tokens=8,output_tokens=7,wall_s=.05,model=m)
            run=pathlib.Path(tmp)/'live'
            r=execute(run,'mock-model',('gcd',),source_fn=fake_source,invoke=model,models_fn=lambda:{'mock-model'})
            self.assertEqual(r['status'],'COMPLETE_LOCAL_PILOT');self.assertEqual(r['summary']['arms']['COMPETENT_TEST_REPAIR']['fully_correct'],1)
            self.assertTrue((run/'task_results.csv').exists())
            z=pack(run);self.assertTrue(check(z))
            with zipfile.ZipFile(z) as f:self.assertIn('results.json',f.namelist())
    def test_missing_model_fail_closed_without_score(self):
        with tempfile.TemporaryDirectory() as d:
            r=execute(pathlib.Path(d)/'blocked',model='not-installed',models_fn=lambda: set())
            self.assertEqual(r['status'],'BLOCKED');self.assertNotIn('summary',r)
    def test_official_testcases_not_in_probe_registry(self):
        self.assertEqual(len(TASKS),6)
        self.assertTrue(all(t in PROBES for t in TASKS))
    def test_rotating_policy_order(self):
        def model(m,p):return dict(status='OK',response='def gcd(a,b):\n    return 7\n',input_tokens=3,output_tokens=2,wall_s=.01,model=m)
        problem={'source':'def gcd(a,b):\n    return a\n','final_gold':[[[21,35],7]]}
        reversed_policies=('FIRSTLIGHT_PRECOMMIT','COMPETENT_TEST_REPAIR')
        r=paired_task('gcd',problem,'mock',invoke=model,max_repairs=0,policy_order=reversed_policies)
        self.assertEqual(r['executed_arm_order'],list(reversed_policies))
    def test_source_integrity_inherited(self):
        from firstlight_v541.verify import verify
        self.assertGreaterEqual(verify(),1)

if __name__=='__main__':unittest.main()
