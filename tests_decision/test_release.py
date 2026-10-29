import json,hashlib,pathlib,unittest
from firstlight_decision.verify_release import verify,ROOT
from firstlight_decision.offline_audit import run as offline
class ReleaseTests(unittest.TestCase):
 def test_additive_sha256(self):self.assertGreaterEqual(verify(),35)
 def test_historic_provenance(self):
  p=ROOT/'data/DEV_INITIAL_ACTUAL_MAC_RESPONSES.json';self.assertTrue(p.is_file())
  j=json.loads(p.read_text());self.assertEqual(j['data_kind'],'USER_ACTUAL_MAC_FIRST_PROPOSALS_REPLAY_ONLY_NOT_PROSPECTIVE')
 def test_historical_one_additional_development_warning(self):
  r=offline(ROOT)
  gained=[x for x in r['records'] if x['experimental_extra_warning'] and not x['original_baseline_warning']]
  self.assertEqual([x['task'] for x in gained],['levenshtein'])
 def test_no_bash_empty_array_expansion(self):
  s=(ROOT/'run_firstlight_decision.sh').read_text()
  self.assertNotIn('SRC_ARGS[@]',s);self.assertIn('set -Eeuo pipefail',s)
 def test_dataset_mit_commit(self):
  j=json.loads((ROOT/'data/QUIXBUGS_OFFICIAL_SUBSET/PROVENANCE.json').read_text())
  self.assertEqual(j['commit'],'4257f44b0ff1181dedaedee6a447e133219fcebf')
if __name__=='__main__':unittest.main()
