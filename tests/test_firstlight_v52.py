"""Regression coverage for the actual macOS /var -> /private/var path failure."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from firstlight_v52.test_driver import canonical_test_environment, canonical_tmp
from firstlight_v51 import run
from firstlight_v52 import run as v52_run
from firstlight_v5 import runner
from firstlight_v52.verify import check as check_release

BASE = Path(__file__).resolve().parent.parent


class MacOSPathAndProvenanceTests(unittest.TestCase):
    def test_v52_integrity_manifest(self):
        self.assertGreaterEqual(check_release(), 4)

    def test_symlinked_tmpdir_is_canonicalized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            physical = root / 'physical'
            physical.mkdir()
            alias = root / 'alias'
            alias.symlink_to(physical, target_is_directory=True)
            self.assertNotEqual(str(alias), str(alias.resolve()))
            self.assertEqual(canonical_tmp(alias), str(physical.resolve()))
            env = canonical_test_environment(alias)
            self.assertEqual(env['TMPDIR'], str(physical.resolve()))
            self.assertEqual(env['TMP'], env['TMPDIR'])
            self.assertEqual(env['TEMP'], env['TMPDIR'])

    def test_prior_v51_provenance_case_passes_with_symlink_tmp_env(self):
        """Run the unchanged failed test under the corrected child environment."""
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / 'real'
            real.mkdir()
            alias = Path(td) / 'alias'
            alias.symlink_to(real, target_is_directory=True)
            env = dict(os.environ)
            env.update(canonical_test_environment(alias))
            # The failure used to occur only on platforms with symlinked TMPDIR.
            cmd = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                   '-p', 'test_firstlight_v51.py', '-q']
            proc = subprocess.run(cmd, cwd=BASE, env=env, capture_output=True,
                                  text=True, timeout=25)
            self.assertEqual(proc.returncode, 0, (proc.stdout+proc.stderr)[-4000:])

    def test_provenance_survives_failure_when_original_run_path_is_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            physical = root / 'physical'
            physical.mkdir()
            alias = root / 'alias'
            alias.symlink_to(physical, target_is_directory=True)
            # A blocked download may already have saved partial provenance.
            def staged_download(path):
                dest = Path(path)
                self.assertEqual(dest.resolve(), (physical/'session'/'official_data').resolve())
                dest.mkdir(parents=True, exist_ok=True)
                (dest/'SOURCE_PROVENANCE.json').write_text(
                    '{"kind":"SIMULATED_TEST_PROVENANCE_NOT_OFFICIAL"}\n')
                raise RuntimeError('SIMULATED_STOP_NO_REMOTE_CALL')
            with mock.patch.object(runner,'fetch_official',side_effect=staged_download):
                run.main(['--run', str(alias/'session'), '--limit', '1'])
            with zipfile.ZipFile(next((physical/'session').glob(
                    'UPLOAD_THIS_FIRST_LIGHT_V5_*.zip'))) as archive:
                self.assertIn('official_data/SOURCE_PROVENANCE.json',archive.namelist())
                self.assertIn('SIMULATED_TEST_PROVENANCE', archive.read(
                    'official_data/SOURCE_PROVENANCE.json').decode())
            report=json.loads((physical/'session'/'benchmark_results.json').read_text())
            self.assertEqual(report['state'],'BLOCKED')
            self.assertEqual(report['results'],[])

    def test_v52_wrapper_records_block_without_fabricated_scores(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner,'fetch_official',side_effect=RuntimeError('STOP_REAL_NETWORK')):
                v52_run.main(['--run',td,'--limit','1'])
            out=json.loads((Path(td)/'benchmark_results.json').read_text())
            self.assertEqual(out['state'],'BLOCKED')
            self.assertEqual(out['results'],[])
            self.assertIsNone(out['summary'])

    def test_missing_provenance_does_not_appear_in_evidence_zip(self):
        """No fictitious BFCL provenance when the actual request never completed."""
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner,'fetch_official',side_effect=RuntimeError('NETWORK_STOP')):
                run.main(['--run',td,'--limit','1'])
            with zipfile.ZipFile(next(Path(td).glob('UPLOAD_THIS_FIRST_LIGHT_V5_*.zip'))) as z:
                self.assertNotIn('official_data/SOURCE_PROVENANCE.json',z.namelist())
            result=json.loads((Path(td)/'benchmark_results.json').read_text())
            self.assertEqual(result['state'],'BLOCKED')
            self.assertIsNone(result['summary'])

if __name__ == '__main__': unittest.main()
