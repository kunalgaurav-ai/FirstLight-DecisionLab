"""First Light v5.4 rigorous capability/measurement contracts (constructed test fixtures)."""
import json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from firstlight_v54 import experiment as e, early, pack, research


def mock_call(model,row,strict,corrective=False):
    # Structural, controlled tests; not scored real model calls.
    if row.get('make_invalid') and model==e.CHEAP and not corrective:
        return {'status':'OK','call':None,'wall_s':.03,'input_tokens':30,'output_tokens':5}
    return {'status':'OK','call':{'name':'ok','arguments':{'n':1}},'wall_s':.02,
            'input_tokens':20,'output_tokens':5}

class V54Tests(unittest.TestCase):
    def test_registry_has_11_named_models(self):
        self.assertEqual(len(e.CANDIDATES),11)
        self.assertEqual(len(set(e.CANDIDATES)),11)

    def test_disjoint_frozen_source_cohorts(self):
        grouped={g:[{'id':f'{g}_{i}','question':[[{'role':'user','content':'hello'}]],
                     'function':[{'name':'ok','parameters':{'properties':{'n':{'type':'integer'}},'required':['n']}}]} for i in range(20)] for g in e.SOURCE_GROUPS}
        screen,test=e.disjoint_cohorts(grouped,8,12)
        self.assertEqual(len(screen),8)
        self.assertFalse({x['id'] for g,x in screen}&{x['id'] for g,x in test})
        a,b=e.disjoint_cohorts(grouped,8,12)
        self.assertEqual([x['id'] for _,x in a],[x['id'] for _,x in screen])

    def test_cheap_baseline_frozen_cost_policy(self):
        row={'id':'A','function':[{'name':'ok','parameters':{'properties':{},'required':[]}}]}
        out=e.run_one(row,'qwen2.5:1.5b','COMPETENT_CHEAP_FIRST',{},mock_call)
        self.assertEqual(out['first_model'],e.CHEAP)
        self.assertEqual(out['call_count'],1)
        self.assertEqual(out['reported_tokens'],25)

    def test_uncalibrated_firstlight_falls_back_to_competent(self):
        row={'id':'A','_group':e.SOURCE_GROUPS[0],'function':[{'name':'ok','parameters':{}}]}
        x=e.run_one(row,'qwen2.5:1.5b','FIRSTLIGHT_CONSTRAINED',{},mock_call)
        self.assertEqual(x['first_model'],e.CHEAP)
        self.assertIn('FALLBACK_COMPETENT',x['decision'])

    def test_screening_chart_includes_all_scored_models_not_just_finalists(self):
        screen=[{'attempts':{m:{'status':'OK','diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':True},
                   'input_tokens':30,'output_tokens':5,'wall_s':1.0} for m in e.CANDIDATES}}]
        report=e.screen_summary(screen,e.CANDIDATES)
        self.assertEqual(len(report),11)
        doc=research.page({'state':'SCREENING','model_candidates':list(e.CANDIDATES),
            'installed_models':list(e.CANDIDATES),'screen_summary':report,'summary':{},
            'eval':[],'screen':screen},{'figures':{}})
        self.assertIn('Screening scoreboard',doc)
        self.assertIn('qwen2.5-coder:3b',doc)
        self.assertIn('MODEL_SCREEN_ONLY',str(report))

    def test_calibration_only_frozen_screen_support(self):
        g=e.SOURCE_GROUPS[0];model='qwen2.5:1.5b'
        records=[]
        for i in range(12):
            records.append({'group':g,'attempts':{
                e.CHEAP:{'diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':i<5}},
                model:{'diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':i<10}}}})
        cal=e.calibrate(records,[e.CHEAP,model])
        self.assertTrue(cal[model][g]['strong_preflight'])
        self.assertFalse(cal[model][e.SOURCE_GROUPS[1]]['strong_preflight'])
        row={'id':'A','_group':g,'function':[]}
        out=e.run_one(row,model,'FIRSTLIGHT_CONSTRAINED',cal,mock_call)
        self.assertEqual(out['first_model'],model)

    def test_failure_action_matches_competent_recovery(self):
        row={'id':'A','_group':e.SOURCE_GROUPS[0],'make_invalid':True,'function':[]}
        a=e.run_one(row,'qwen2.5:1.5b','COMPETENT_CHEAP_FIRST',{},mock_call)
        b=e.run_one(row,'qwen2.5:1.5b','FIRSTLIGHT_CONSTRAINED',{},mock_call)
        self.assertEqual(a['call_count'],2)
        self.assertEqual(b['call_count'],2)
        self.assertTrue(a['precommit_schema_alarm'])
        self.assertEqual(b['first_model'],e.CHEAP)

    def test_model_call_blocked_no_success_claim(self):
        def failed(*a,**kw):return {'status':'BLOCKED_MODEL_CALL','call':None,'error':'not running','wall_s':.01}
        a=e.run_one({'function':[]},e.CHEAP,'FIRSTLIGHT_CONSTRAINED',{},failed)
        self.assertEqual(a['status'],'BLOCKED_MODEL')
        self.assertFalse(a['precommit_schema_alarm'])
        self.assertEqual(a['call_count'],1)

    def test_early_warning_prefix_gold_leak_refused(self):
        valid={'trace_id':'a','terminal_success':False,'failure_step':3,
                'events':[{'step':1,'precommit_risk_score':.85},{'step':2,'precommit_risk_score':.4},{'step':3,'precommit_risk_score':.6}]}
        result=early.evaluate_trace(valid)
        self.assertEqual(result['classification'],'EARLY_DETECTION')
        self.assertEqual(result['lead_steps'],2)
        valid['events'][0]['ground_truth']='leak'
        with self.assertRaises(ValueError):early.evaluate_trace(valid)

    def test_early_warning_denominator_and_no_cost_assumption(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'traces.jsonl';dst=Path(d)/'out.json'
            a={'trace_id':'f','terminal_success':False,'failure_step':2,'events':[{'step':1,'precommit_risk_score':.8},{'step':2,'precommit_risk_score':.1}]}
            b={'trace_id':'s','terminal_success':True,'failure_step':None,'events':[{'step':1,'precommit_risk_score':.9}]}
            src.write_text(json.dumps(a)+'\n'+json.dumps(b)+'\n')
            report=early.run_file(src,dst)
            self.assertEqual(report['false_alarm_rate_per_safe_trajectory'],1.)
            self.assertEqual(report['detection_rate_at_or_before_error'],1.)
            self.assertIsNone(report['usd_cost_saved'])
            self.assertEqual(report['counterfactual_continuations_executed'],0)

    def test_precommit_bfcl_counts_schema_valid_wrong(self):
        data={'eval':[{'id':'case','arms':{'A':{
            'policy':'FIRSTLIGHT_CONSTRAINED','precommit_schema_alarm':False,
            'first_call_diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':False}}}}]}
        obj=early.summarize_bfcl(data)
        self.assertEqual(obj['figures']['FIRSTLIGHT_CONSTRAINED']['incorrect_but_schema_valid'],1)
        self.assertIsNone(obj['figures']['FIRSTLIGHT_CONSTRAINED']['dollars_avoided'])

    def test_package_self_verifies_raw_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'results_v54.json').write_text('{}')
            (root/'holdout_rows_v54.csv').write_text('id\n')
            archive=pack.package(root)
            with zipfile.ZipFile(archive) as z:
                manifest=json.loads(z.read('EVIDENCE_MANIFEST.json'))
                import hashlib
                self.assertEqual(hashlib.sha256(z.read('holdout_rows_v54.csv')).hexdigest(),
                                 manifest['sha256_by_file']['holdout_rows_v54.csv'])

    def test_dashboard_omits_fake_points(self):
        doc=research.page({'state':'BLOCKED','model_candidates':list(e.CANDIDATES),
            'installed_models':[],'summary':{},'eval':[],'screen':[]},{'figures':{}})
        self.assertIn('No completed matched holdout yet',doc)
        self.assertIn('NOT ESTABLISHED',doc)
        self.assertIn('11',doc)

    def test_full_experiment_with_controlled_model_and_public_schema_fixture(self):
        # This exercises pipeline ownership, disjoint cohort, JSON/CSV and grade joins;
        # MODEL OUTPUTS ARE FIXTURES, not evidence of a live Ollama or BFCL run.
        from unittest.mock import patch
        grouped={g:[{'id':f'{g}_{i}',
                     'question':[[{'role':'user','content':'Test function call'}]],
                     'function':[{'name':'ok','parameters':{'properties':{'n':{'type':'integer'}},'required':['n']}}]}
                    for i in range(12)] for g in e.SOURCE_GROUPS}
        gold={g:{f'{g}_{i}':{'ground_truth':[{'ok':{'n':[1]}}]} for i in range(12)} for g in e.SOURCE_GROUPS}
        def fake_read(path):
            group=next(g for g,f in e.OFFICIAL_FILES.items() if f in str(path))
            return grouped[group]
        with tempfile.TemporaryDirectory() as d, \
            patch.object(e,'ollama_models',return_value={e.CHEAP,'qwen2.5:1.5b'}), \
            patch.object(e,'reuse_verified_dataset',return_value=None), \
            patch.object(e,'fetch_official',return_value={'commit':'a'*40,'files':[]}), \
            patch.object(e,'read_items',side_effect=fake_read), \
            patch.object(e,'gold_lookup',return_value=gold):
            r=e.run(['--run',d,'--screen-limit','4','--eval-limit','4','--finalists','2'],call_fn=mock_call)
            self.assertEqual(r['state'],'COMPLETE_LOCAL_DIAGNOSTIC')
            self.assertEqual(len(r['screen']),4)
            self.assertEqual(len(r['eval']),4)
            self.assertEqual(len(r['summary']),8)
            self.assertEqual(len(r['screen_summary']),2)
            self.assertFalse(set(r['screen_ids'])&set(r['eval_ids']))
            self.assertTrue(Path(d,'early_warning_v54.json').is_file())
            self.assertTrue(Path(d,'holdout_rows_v54.csv').is_file())
            self.assertTrue(all(v['finished_all_tasks'] for v in r['summary'].values()))

    def test_regression_runner_requires_terminal_success(self):
        from firstlight_v54.test_runner import completed_test_count
        self.assertEqual(completed_test_count(b'logs\nRan 313 tests in 34.1s\n\nOK\n'),313)
        self.assertIsNone(completed_test_count(b'logs\nRan 313 tests in 34.1s\n\nFAILED (failures=1)\n'))
        self.assertIsNone(completed_test_count(b'REGRESSION SIMULATED OUTPUT\nOK\n'))

    def test_paired_statistics_do_not_confuse_quality_and_resources(self):
        model='qwen2.5:1.5b'
        def arm(policy,pas,tok):return {'policy':policy,'status':'COMPLETE',
            'diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':pas},
            'reported_tokens':tok,'controller_plus_model_wall_s':1.0}
        rows=[{'arms':{model+'|COMPETENT_CHEAP_FIRST':arm('COMPETENT_CHEAP_FIRST',True,100),
                        model+'|FIRSTLIGHT_CONSTRAINED':arm('FIRSTLIGHT_CONSTRAINED',False,20)}},
              {'arms':{model+'|COMPETENT_CHEAP_FIRST':arm('COMPETENT_CHEAP_FIRST',False,100),
                        model+'|FIRSTLIGHT_CONSTRAINED':arm('FIRSTLIGHT_CONSTRAINED',True,20)}}]
        result=e.paired_comparisons(rows,[model])[model]
        self.assertEqual(result['paired_pass_rate_difference'],0)
        self.assertEqual(result['exact_two_sided_mcnemar_p'],1)
        self.assertAlmostEqual(result['firstlight_token_ratio_relative_to_competent'],.2)
        self.assertFalse(result['right_to_publish_superiority'])

    def test_summary_incomplete_denominator_and_counts(self):
        d={'policy':'COMPETENT_CHEAP_FIRST','model':e.CHEAP,'status':'COMPLETE',
            'diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':True},
            'reported_tokens':15,'sum_model_wall_s':.12,'controller_plus_model_wall_s':.13,'call_count':1,
            'first_call_diagnostic':{'status':'SCORED_DIAGNOSTIC','pass':True},'precommit_schema_alarm':False}
        res=e.compute_summary([{'id':'x','arms':{e.CHEAP+'|COMPETENT_CHEAP_FIRST':d}}],[e.CHEAP])
        self.assertTrue(res[e.CHEAP+'|COMPETENT_CHEAP_FIRST']['finished_all_tasks'])
        self.assertEqual(res[e.CHEAP+'|COMPETENT_CHEAP_FIRST']['reported_tokens'],15)

if __name__=='__main__':unittest.main()
