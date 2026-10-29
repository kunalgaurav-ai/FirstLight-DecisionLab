import json,tempfile,unittest
from pathlib import Path
from ail_v37.observed import read_original_labels,join,evaluate,_single_grade,historical_issue_split

S='20260901_mini-v2.4.2_gemini-3-5-flash'

def record(i,s='official_resolved',group=None,**kw):
    if group is None:group=historical_issue_split(f'issue{i}')
    return dict(entry=S,instance_id=f'issue{i}',target=(s=='official_resolved'),
                outcome_source=s,task_group=group,quality_flags={},**kw)

class GradeRecoveryTests(unittest.TestCase):
    def test_original_labels_recognized_with_independent_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'labels.jsonl'
            f.write_text('\n'.join(json.dumps(x) for x in [record(1),record(2,'official_nonresolved_complement')])+'\n')
            data,info=read_original_labels(f,S)
            self.assertEqual(info['records'],2)
            self.assertTrue(data[(S,'issue1')]['grade'])
            self.assertFalse(data[(S,'issue2')]['grade'])
            self.assertEqual(data[(S,'issue2')]['split'],historical_issue_split('issue2'))
    def test_unattested_target_does_not_become_a_grade(self):
        self.assertEqual(_single_grade({'entry':S,'instance_id':'x','target':True,'task_group':'train'},S)[1],'missing_official_outcome_source')
    def test_submitted_is_not_a_grade(self):
        row=record(1);row.pop('outcome_source');row['exit_status']='Submitted'
        self.assertIsNone(_single_grade(row,S)[0])
    def test_official_nonresolved_complement_is_explicitly_supported(self):
        self.assertFalse(_single_grade(record(1,'official_nonresolved_complement'),S)[0]['grade'])
    def test_other_submissions_must_not_join(self):
        q=record(1);q['entry']='unrelated_entry'
        self.assertEqual(_single_grade(q,S)[1],'entry_not_exact_submission')
    def test_conflicting_binary_target_refused(self):
        q=record(1);q['target']=False
        self.assertEqual(_single_grade(q,S)[1],'contradictory_target_and_official_source')
    def test_old_inspected_test_is_never_fresh_holdout(self):
        self.assertEqual(_single_grade(record(1),S)[0]['split'],historical_issue_split('issue1'))
    def test_unknown_task_group_does_not_overwrite_documented_hash_split(self):
        self.assertEqual(_single_grade(record(1,group='astropy_repo'),S)[0]['split'],historical_issue_split('issue1'))
    def test_mismatched_explicit_split_is_quarantined(self):
        wrong='test' if historical_issue_split('issue1')!='previously_inspected_test' else 'train'
        self.assertEqual(_single_grade(record(1,group=wrong),S)[1],'contradictory_explicit_split_and_historical_hash')
    def test_quality_flag_false_fails_closed(self):
        q=record(1);q['quality_flags']={'exact_entry_match':False}
        self.assertEqual(_single_grade(q,S)[1],'quality_flags_disqualify')
    def test_contradictory_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'g.jsonl'
            f.write_text(json.dumps(record(1))+'\n'+json.dumps(record(1,'official_nonresolved_complement'))+'\n')
            with self.assertRaises(ValueError):read_original_labels(f,S)
    def test_join_uses_original_input_and_keeps_private_content_local(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d);t=q/'traces';t.mkdir()
            (q/'g.jsonl').write_text(json.dumps(record(1))+'\n')
            messages=[{'role':'assistant','extra':{'actions':[{'command':'secret command'}]}},
                      {'role':'user','extra':{'returncode':0},'content':'<returncode>0</returncode> secret result'}]
            (t/'issue1.traj.json').write_text(json.dumps({'instance_id':'issue1','messages':messages}))
            data,info=join(t,q/'g.jsonl',S)
            self.assertEqual(len(data),1)
            self.assertEqual(data[0]['split'],historical_issue_split('issue1'))
            self.assertNotIn('secret',json.dumps(info))
    def test_insufficient_cohorts_hold_no_training(self):
        result=evaluate([],{})
        self.assertEqual(result['models_fitted'],0)
        self.assertFalse(result['deployment_eligible'])
    def test_calibrated_study_uses_original_groups_not_time_split(self):
        episodes=[]
        for g,n in [('train',110),('calibration',45),('validation',45),('previously_inspected_test',20)]:
            for i in range(n):
                fail=i%4==0
                obs=[{'bad':int(fail and j%5==0),'repeat':int(j%6==0),
                      'error_text':int(fail and j%3==0),'test_cmd':int(j%4==0),
                      'output_chars':120+j} for j in range(26)]
                episodes.append({'episode_id':f'{g}-{i}','split':g,'success':not fail,'observations':obs})
        r=evaluate(episodes,{'status':'UNIT_TEST_ONLY_SYNTHETIC_INPUT'})
        self.assertEqual(r['cohort_counts']['train'],110)
        self.assertEqual(r['cohort_counts']['previously_inspected_test'],20)
        self.assertGreater(r['models_fitted'],0)
        self.assertEqual(r['landmarks'][0]['status'],'EXPLORATORY_HISTORICAL_VALIDATION_ONLY')
        self.assertFalse(r['deployment_eligible'])
