import copy
import unittest
from ail_v35.examples import fixture, unsupported_action
from ail_v35.opportunity import assess_workflow,screen_action,validate

class OpportunityTests(unittest.TestCase):
    def setUp(self):self.w=fixture()
    def test_shared_descendant_counted_once(self):
        a=assess_workflow(self.w)['checkpoints'][1]
        self.assertEqual(a['eligible_unique_nodes'],['mux','visuals','voice'])
        self.assertEqual(a['avoidable_downstream_work_interval'],[15,15])
    def test_ordinary_incumbent_advantage_not_claimed(self):
        z=assess_workflow(self.w)['checkpoints'][0]
        self.assertEqual(z['avoidable_downstream_work_interval'],[17,17])
        self.assertNotIn('distribution',z['eligible_unique_nodes'])
    def test_incumbent_checks_eliminate_all_remaining_opportunity(self):
        for n in self.w['nodes']:
            n['already_avoided_by_incumbent']=True
        z=assess_workflow(self.w)['checkpoints'][0]
        self.assertEqual(z['avoidable_downstream_work_interval'],[0,0])
    def test_unknown_causal_bound_holds(self):
        o=assess_workflow(self.w)['checkpoints'][0]
        result=screen_action(unsupported_action(),o)
        self.assertEqual(result['shadow_screen_result'],'HOLD_NO_SUPPORTED_POSITIVE_ACTION_VALUE')
        self.assertFalse(result['production_action_authorized'])
    def test_supposedly_good_scenario_still_never_autodeploys(self):
        o=assess_workflow(self.w)['checkpoints'][0]
        a=unsupported_action()
        a.update(defect_probability=[.9,.95],causal_prevention_effect=[.9,1],
                 full_check_and_repair_cost=[1,1],false_alarm_disruption_cost=[0,0],
                 quality_loss_cost_proxy=[0,0],quality_gate='APPROVED_INDEPENDENTLY')
        result=screen_action(a,o,approved_risk_bounds=True)
        self.assertEqual(result['shadow_screen_result'],'CANDIDATE_FOR_PROSPECTIVE_RANDOMIZED_EVALUATION')
        self.assertFalse(result['production_action_authorized'])
    def test_zero_ops_not_approved(self):
        for n in self.w['nodes']:n['already_avoided_by_incumbent']=True
        z=assess_workflow(self.w)['checkpoints'][0]
        a=unsupported_action();a['quality_gate']='APPROVED_INDEPENDENTLY'
        self.assertEqual(screen_action(a,z,approved_risk_bounds=True)['shadow_screen_result'],'HOLD_NO_SUPPORTED_POSITIVE_ACTION_VALUE')
    def test_cycle_rejected(self):
        self.w['nodes'][0]['parents']=['voice']
        with self.assertRaises(ValueError):validate(self.w)
    def test_missing_parent_rejected(self):
        self.w['nodes'][2]['parents']=['ghost']
        with self.assertRaises(ValueError):validate(self.w)
    def test_duplicate_nodes_rejected(self):
        self.w['nodes'].append(copy.deepcopy(self.w['nodes'][1]))
        with self.assertRaises(ValueError):validate(self.w)
    def test_bad_probability_rejected(self):
        a=unsupported_action();a['defect_probability']=[-1,.5]
        with self.assertRaises(ValueError):screen_action(a,assess_workflow(self.w)['checkpoints'][0])
    def test_bool_cost_rejected(self):
        self.w['nodes'][0]['marginal_cost']=[True,1]
        with self.assertRaises(ValueError):validate(self.w)
    def test_inverted_intervals_rejected(self):
        self.w['nodes'][0]['salvage_fraction']=[.9,.1]
        with self.assertRaises(ValueError):validate(self.w)
    def test_cost_unit_must_be_homogeneous(self):
        self.w['unit']='random_mixed_units'
        with self.assertRaises(ValueError):assess_workflow(self.w)
    def test_corrupt_evidence_class_rejected(self):
        self.w['evidence_class']='REAL_CUSTOMER_INVOICE'
        with self.assertRaises(ValueError):assess_workflow(self.w)
    def test_duplicate_checkpoint_rejected(self):
        self.w['checkpoints'].append(copy.deepcopy(self.w['checkpoints'][0]))
        with self.assertRaises(ValueError):assess_workflow(self.w)
    def test_multiphase_salvage_bound(self):
        self.w['nodes'][2]['salvage_fraction']=[.25,.5]
        z=assess_workflow(self.w)['checkpoints'][1]
        self.assertEqual(z['avoidable_downstream_work_interval'],[13,14])
    def test_other_unauthorized_stage_not_auto_added(self):
        n=self.w['nodes'][3]
        n['allowed_to_skip_if_defective']=False
        a=assess_workflow(self.w)['checkpoints'][1]
        self.assertEqual(a['avoidable_downstream_work_interval'],[6,6])
    def test_no_hidden_model_training(self):
        r=screen_action(unsupported_action(),assess_workflow(self.w)['checkpoints'][0])
        self.assertEqual(r['interval_evidence_status'],'PROVIDED_NOT_VERIFIED_BY_THIS_TOOL')

if __name__=='__main__':unittest.main()
