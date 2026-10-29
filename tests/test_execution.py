import json
import tempfile
import unittest
from pathlib import Path
from ail_v33.benchmark import SCENARIOS, ARMS, execute_scenario, run_all, make_voice, validate_voice
from ail_v33.dashboard import HTML


class ExecutionTests(unittest.TestCase):
    def test_real_wave_generated_and_validated(self):
        self.assertTrue(validate_voice(make_voice('x',False)))
        self.assertFalse(validate_voice(make_voice('x',True)))
    def test_denied_rights_never_execute(self):
        with tempfile.TemporaryDirectory() as d:
            for arm in ARMS:
                row=execute_scenario(arm,SCENARIOS[6],Path(d))
                self.assertEqual(row['stage_ops'],0)
                self.assertEqual(row['status'],'BLOCKED_UNAUTHORIZED')
    def test_unknown_rights_never_execute(self):
        with tempfile.TemporaryDirectory() as d:
            for arm in ARMS:
                row=execute_scenario(arm,SCENARIOS[5],Path(d))
                self.assertEqual(row['stage_ops'],0)
    def test_upstream_high_early_controller_avoids_rework(self):
        with tempfile.TemporaryDirectory() as d:
            a=execute_scenario('AIL_V33_FIXTURE_POLICY',SCENARIOS[2],Path(d))
            self.assertEqual(a['early_check_calls'],1)
            self.assertEqual(a['upstream_repairs'],1)
            self.assertEqual(a['stage_counts']['script'],1)
    def test_low_prior_defect_detected_late_and_repaired(self):
        with tempfile.TemporaryDirectory() as d:
            a=execute_scenario('AIL_V33_FIXTURE_POLICY',SCENARIOS[3],Path(d))
            self.assertEqual(a['late_check_calls'],1)
            self.assertEqual(a['stage_counts']['script'],2)
            self.assertTrue(a['technical_valid'])
    def test_only_voice_repaired_for_audio_defect(self):
        with tempfile.TemporaryDirectory() as d:
            a=execute_scenario('AIL_V33_FIXTURE_POLICY',SCENARIOS[4],Path(d))
            self.assertEqual(a['stage_counts']['script'],1)
            self.assertEqual(a['stage_counts']['art'],1)
            self.assertEqual(a['stage_counts']['voice'],2)
            self.assertEqual(a['audio_repairs'],1)
    def test_real_files_match_hashes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            a=execute_scenario(ARMS[0],SCENARIOS[2],Path(d))
            for rec in a['events']:
                p=Path(d)/ARMS[0]/SCENARIOS[2]['id']/rec['relative_artifact']
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),rec['sha256'])
    def test_no_overwrite_on_repair(self):
        with tempfile.TemporaryDirectory() as d:
            a=execute_scenario(ARMS[0],SCENARIOS[2],Path(d))
            scripts=[e['relative_artifact'] for e in a['events'] if e['operation']=='script']
            self.assertEqual(scripts,['script_1.txt','script_2.txt'])
    def test_full_benchmark_with_competent_baseline_and_parity(self):
        with tempfile.TemporaryDirectory() as d:
            r=run_all(Path(d)/'one_run')
            self.assertTrue(r['parity_exact_package_sha_across_arms'])
            self.assertEqual(len(r['task_rows']),len(SCENARIOS)*len(ARMS))
            self.assertIn('B1_COMPETENT_EARLY_CHECK',r['per_arm'])
            self.assertEqual(r['commercial_gate'],'HOLD_NO_CUSTOMER_APPROVAL_COSTS_OR_ACTUAL_OSS_COMPARATOR')
            self.assertFalse(r['hmm_challenger']['trained'])
            for a in r['per_arm'].values():
                self.assertIsNone(a['cost_per_approved_outcome'])
                self.assertEqual(a['blocked_rights'],2)
                self.assertEqual(a['technically_passed'],6)
    def test_dashboard_communicates_limits(self):
        self.assertIn('constructed',HTML.lower())
        self.assertIn('No customer spend', HTML)
        self.assertIn("/api/report",HTML)

if __name__=='__main__':unittest.main()
