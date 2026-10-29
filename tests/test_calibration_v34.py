"""All internally generated observations are TEST FIXTURES, never market evidence."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from ail_v34.calibration import read_dataset,study,FEATURES,fit_logistic,sigmoid,offset_calibration


def mock_rows(n=240):
    start=dt.datetime(2026,2,1,tzinfo=dt.timezone.utc)
    rows=[]
    for k in range(n):
        t=start+dt.timedelta(days=k)
        y=int((k%4)==0)
        fs={key:float(y)*.8+.08 for key in FEATURES['text']}
        rows.append({'episode_id':'fixture'+str(k),'checkpoint_utc':t.isoformat(),
                     'label_utc':(t+dt.timedelta(hours=2)).isoformat(),
                     'modality':'text','stage_kind':'research','failure_type':'unsupported_claim',
                     'executor_version':'test-v1','checkpoint_bucket':'precommit',
                     'policy_id':'INCUMBENT_NO_OPTIONAL_INTERVENTION',
                     'independent_adjudicator':'fixture_assertion',
                     'label':y,'intervened_before_label':False,'features':fs,
                     'evidence_class':'OBSERVED'})
    return rows


def write_data(root,rows,provenance=None):
    d=root/'obs.jsonl';p=root/'provenance.json'
    d.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    p.write_text(json.dumps(provenance or {'data_kind':'OBSERVED_REAL_AGENT_TRAJECTORIES',
      'rights_authorized':True,'consent_or_permitted_use':True,'independent_adjudication':True,
      'dataset_id':'unit_fixture_only', 'source_description':'Unit test constructed records, NOT genuine agent data'}))
    return d,p

class CalibrationTests(unittest.TestCase):
    def test_no_dataset_is_hold(self):
        r=study()
        self.assertEqual(r['status'],'HOLD_NO_AUTHORIZED_OBSERVED_DATASET')
        self.assertFalse(r['policy_eligible'])
    def test_typical_synthetic_unit_test_traverses_algorithm_but_no_real_claim(self):
        with tempfile.TemporaryDirectory() as t:
            d,p=write_data(Path(t),mock_rows())
            r=study(d,p)
            self.assertEqual(r['status'],'SHADOW_REPORT_ONLY')
            self.assertEqual(r['groups'][0]['status'],'PREDICTION_STUDY_COMPLETE_SHADOW_ONLY')
            self.assertEqual(r['groups'][0]['counts'],{'train':144,'calibration':48,'test':48})
            self.assertFalse(r['policy_eligible'])
            self.assertIsNone(r['cost_per_approved_outcome'])
    def test_separate_modalities_never_falsely_pool(self):
        with tempfile.TemporaryDirectory() as t:
            rows=mock_rows()
            for i,r in enumerate(rows[:]):
                if i%3==0:
                    q=dict(r);q['modality']='audio';q['features']={k:.1 for k in FEATURES['audio']};rows[i]=q
            d,p=write_data(Path(t),rows)
            r=study(d,p)
            self.assertEqual(len(r['groups']),2)
            self.assertTrue(all(v['status']=='HOLD_INSUFFICIENT_SUPPORT' for v in r['groups']))
    def test_no_full_life_label_at_checkpoint(self):
        with tempfile.TemporaryDirectory() as t:
            rows=mock_rows(3);rows[0]['label_utc']=rows[0]['checkpoint_utc']
            d,p=write_data(Path(t),rows)
            self.assertEqual(study(d,p)['status'],'REJECT_DATASET')
    def test_censored_outcomes_not_eligible(self):
        with tempfile.TemporaryDirectory() as t:
            rows=mock_rows(3);rows[0]['intervened_before_label']=True
            d,p=write_data(Path(t),rows)
            self.assertIn('censored',study(d,p)['reason'])
    def test_fixture_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d,p=write_data(Path(t),mock_rows(3),{'data_kind':'CONSTRUCTED_FIXTURES','rights_authorized':True,'consent_or_permitted_use':True,'independent_adjudication':True,'dataset_id':'constructed','source_description':'a'*15})
            self.assertEqual(study(d,p)['status'],'REJECT_DATASET')
    def test_missing_permission_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d,p=write_data(Path(t),mock_rows(3),{'data_kind':'OBSERVED_REAL_AGENT_TRAJECTORIES','rights_authorized':False,'consent_or_permitted_use':True,'independent_adjudication':True,'dataset_id':'observed','source_description':'a'*15})
            self.assertEqual(study(d,p)['status'],'REJECT_DATASET')
    def test_bad_future_feature_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            rows=mock_rows(3);rows[0]['future_fields_used']=True
            d,p=write_data(Path(t),rows)
            self.assertEqual(study(d,p)['status'],'REJECT_DATASET')
    def test_duplicate_episode_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            rows=mock_rows(3);rows.append(dict(rows[0]));d,p=write_data(Path(t),rows)
            self.assertIn('duplicate',study(d,p)['reason'])
    def test_label_abstains_if_empty_group(self):
        with tempfile.TemporaryDirectory() as t:
            d,p=write_data(Path(t),mock_rows(20))
            r=study(d,p);self.assertEqual(r['groups'][0]['status'],'HOLD_INSUFFICIENT_SUPPORT')
    def test_logistic_nonconstant(self):
        X=[[float(i%2)] for i in range(100)]
        y=[i%2 for i in range(100)]
        w,b=fit_logistic(X,y)
        self.assertGreater(sigmoid(w[0]+b),sigmoid(b))
        self.assertTrue(-15<=offset_calibration([b]*20,[0,1]*10)<=15)

if __name__=='__main__':unittest.main()

class DeploymentGuardTests(unittest.TestCase):
    def test_no_calibration_spoof_to_active_control(self):
        from ail_v34.policy import decide_v34
        from ail_v33.core import OptionalCheckEstimate,DecisionInput
        ev=OptionalCheckEstimate(.8,.9,.9,.01,100,1,1,1,'CALIBRATED_EXTERNAL')
        req=DecisionInput('task','tenant','ALLOW','VALID',False,'CONTINUE_WITH_SAFETY_CHECK','research',ev,12)
        outcome=decide_v34(req)
        self.assertEqual(outcome['decision'],'CONTINUE_WITH_SAFETY_CHECK')
        self.assertFalse(outcome['evaluator_invoked'])
        self.assertIn('NOT_VERIFIED',outcome['reason'])
    def test_rights_gate_takes_precedence(self):
        from ail_v34.policy import decide_v34
        from ail_v33.core import OptionalCheckEstimate,DecisionInput
        ev=OptionalCheckEstimate(.8,.9,.9,.01,100,1,1,1,'CALIBRATED_EXTERNAL')
        req=DecisionInput('task','tenant','DENY','VALID',False,'CONTINUE_WITH_SAFETY_CHECK','research',ev,12)
        self.assertEqual(decide_v34(req)['decision'],'BLOCK')
