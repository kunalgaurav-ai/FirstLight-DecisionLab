"""Exercise macOS-style /var alias even on Linux: correct path, not skipped test."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from firstlight_v541.temp import canonical_tmp, test_env
from firstlight_v541.verify import verify


class V541MacTempRecovery(unittest.TestCase):
    def test_release_sha_verifier(self):
        self.assertGreaterEqual(verify(), 2)

    def test_alias_resolved_for_all_temp_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            canonical=root/'physical'
            canonical.mkdir()
            alias=root/'logical'
            alias.symlink_to(canonical, target_is_directory=True)
            env=test_env({'TMPDIR':str(alias),'TEMP':str(alias),'TMP':str(alias)})
            self.assertEqual(env['TMPDIR'], str(canonical.resolve()))
            self.assertEqual(env['TMP'], env['TMPDIR'])
            self.assertEqual(env['TEMP'], env['TMPDIR'])
            self.assertEqual(canonical_tmp({'TMPDIR':str(alias)}), str(canonical.resolve()))

    def test_provenance_regression_survives_symlinked_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            physical=root/'physical'
            physical.mkdir()
            alias=root/'logical'
            alias.symlink_to(physical, target_is_directory=True)
            env=test_env({**os.environ, 'TMPDIR':str(alias), 'TMP':str(alias), 'TEMP':str(alias)})
            # Run the exact inherited test unchanged in a fresh interpreter.
            command=[sys.executable,'-m','unittest','discover','-s','tests',
                     '-p','test_firstlight_v51.py','-q']
            output=subprocess.run(command,env=env,text=True,capture_output=True,timeout=45)
            self.assertEqual(output.returncode,0,output.stdout+'\n'+output.stderr)
            self.assertIn('Ran 5 tests',output.stderr)
            self.assertIn('OK',output.stderr)

    def test_bad_temp_path_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            bad=Path(folder)/'does-not-exist'
            with self.assertRaises((FileNotFoundError,OSError,ValueError)):
                canonical_tmp({'TMPDIR':str(bad)})


if __name__=='__main__':unittest.main()
