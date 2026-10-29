import tempfile,unittest,json
from pathlib import Path
from ail_v36.trajectories import parse_label,observations,features,read_grades,load_episodes,study
from ail_v36.fallback import fixture_parity

class ObservedTests(unittest.TestCase):
    def test_only_official_grade(self):
        self.assertIsNone(parse_label({'exit_status':'Submitted'}))
        self.assertTrue(parse_label({'resolved':True}))
        self.assertFalse(parse_label({'evaluation':{'resolved':False}}))
    def test_reject_no_grade(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d);f=q/'grades.jsonl';f.write_text('{"instance_id":"task1","exit_status":"Submitted"}\n')
            x,stat=read_grades(f,'fixed_submission');self.assertEqual(x,{})
    def test_observation_only_tool_outputs(self):
        msgs=[{'role':'assistant','extra':{'actions':[{'command':'pytest -q'}]}},
              {'role':'user','content':'<returncode>1</returncode>\nERROR', 'extra':{'returncode':1}},
              {'role':'assistant','content':'After the observation!','extra':{}},
              {'role':'user','content':'<returncode>0</returncode>\nPASS', 'extra':{'returncode':0}}]
        ob=observations(msgs);self.assertEqual(len(ob),2)
        self.assertEqual(ob[0]['bad'],1)
        self.assertAlmostEqual(features(ob,1)[0],1.)
    def test_no_real_labels_no_training(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d);(q/'empty.jsonl').write_text('')
            obs,summary=load_episodes(q,q/'empty.jsonl','test')
            self.assertEqual(study(obs,summary)['status'],'HOLD_INSUFFICIENT_JOINED_OBSERVED_TRAJECTORIES')
    def test_fail_closed_conflicting_grades(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'grades.jsonl'
            p.write_text('{"instance_id":"x","submission":"s","resolved":true}\n{"instance_id":"x","submission":"s","resolved":false}\n')
            with self.assertRaises(ValueError):read_grades(p,'s')
    def test_actual_training_pipeline_requires_minimum_support(self):
        episodes=[]
        for i in range(180):
            # Unit-test fabrication ONLY. Never included as eligible runtime data.
            fail=(i%4==0)
            observations=[{'bad':int(fail and j%3==0),'repeat':int(j%8==0),
                           'error_text':int(fail),'test_cmd':int(j%4==0),
                           'output_chars':100+j} for j in range(32)]
            episodes.append({'submission':'unit-test','episode_id':f'case{i}',
                            'success':not fail,'timestamp':1700000000+i*180,
                            'observations':observations})
        result=study(episodes,{'status':'CONSTRUCTED_TEST_RECORDS'})
        self.assertEqual(result['joined_episodes'],180)
        self.assertEqual(result['splits'],{'train':108,'calibration':36,'test':36})
        self.assertEqual(result['landmarks'][0]['status'],
                         'HISTORICAL_PREDICTION_EVALUATED_SHADOW_ONLY')
        self.assertFalse(result['deployment_eligible'])

    def test_incumbent_parity_corrects_28_versus_25(self):
        with tempfile.TemporaryDirectory() as d:
            r=fixture_parity(Path(d)/'run')
            self.assertEqual(r['incumbent_operations'],25)
            self.assertEqual(r['ail_safe_fallback_operations'],25)
            self.assertTrue(r['baseline_parity'])
            self.assertEqual(r['historical_v33_ail_operations'],28)
