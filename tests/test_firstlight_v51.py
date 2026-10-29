import json,io,pathlib,tempfile,subprocess,unittest,urllib.error
from unittest import mock
from firstlight_v51 import preflight,run,test_driver
from firstlight_v5 import runner
from firstlight_v51.assert_release import check

class FirstLightV51Tests(unittest.TestCase):
 def test_manifest_verified(self):
  self.assertGreaterEqual(check(),5)
 def test_test_runner_timeout_rejects_unsafe_configuration(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):test_driver.execute(pathlib.Path(td)/"test.log",5)
 def test_dependency_preflight_really_uses_pillow(self):
  self.assertTrue(preflight.dependency_status()['pillow_installed'])
 def test_benchmark_failure_has_no_fake_data_or_scores(self):
  with tempfile.TemporaryDirectory() as td:
   with mock.patch.object(runner,'fetch_official',side_effect=urllib.error.URLError('controlled DNS_DOWN')):
    run.main(['--run',td,'--limit','2'])
   d=json.loads((pathlib.Path(td)/'benchmark_results.json').read_text())
   self.assertEqual(d['results'],[]);self.assertIsNone(d['summary'])
 def test_runner_uses_execution_dir_for_provenance(self):
  with tempfile.TemporaryDirectory() as td:
   def fake_fetch(path):
    p=pathlib.Path(path)
    self.assertTrue(p.is_relative_to(pathlib.Path(td)/'official_data'))
    p.mkdir(parents=True,exist_ok=True)
    (p/'SOURCE_PROVENANCE.json').write_text('not a real benchmark fixture')
    raise RuntimeError('CONTROLLED_NETWORK_STOP')
   with mock.patch.object(runner,'fetch_official',side_effect=fake_fetch):
    run.main(['--run',td,'--limit','1'])
   d=json.loads((pathlib.Path(td)/'benchmark_results.json').read_text())
   self.assertEqual(d['state'],'BLOCKED')
   import zipfile
   z=next(pathlib.Path(td).glob('UPLOAD_THIS_FIRST_LIGHT_V5_*.zip'))
   with zipfile.ZipFile(z) as fp:
    self.assertIn('official_data/SOURCE_PROVENANCE.json',fp.namelist())

if __name__=='__main__':unittest.main()
