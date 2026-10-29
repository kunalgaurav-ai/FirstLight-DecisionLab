"""Mac Bash empty-array regression and v5.5.1 additive source integrity."""
import pathlib,unittest,subprocess,shutil
from firstlight_v551.verify import verify
ROOT=pathlib.Path(__file__).resolve().parents[1]

class V551RecoveryTests(unittest.TestCase):
    def test_v551_manifest_inherits_v55_without_modification(self):
        r=verify()
        self.assertEqual(r['v551_files_verified'],6)
        self.assertEqual(r['inherited']['v55_items'],15)
    def test_shell_syntax_and_empty_array_failure_removed(self):
        runner=ROOT/'run_firstlight_v551.sh'
        text=runner.read_text()
        self.assertNotIn('SRC_ARGS[@]',text)
        self.assertNotIn('SRC_ARGS=()',text)
        self.assertIn('if [ -n "${FIRSTLIGHT_QUIXBUGS_DIR:-}" ]; then',text)
        self.assertEqual(subprocess.run(['bash','-n',str(runner)],capture_output=True).returncode,0)
    def test_both_source_argument_branches_are_protected(self):
        text=(ROOT/'run_firstlight_v551.sh').read_text()
        lines=[x.strip() for x in text.splitlines() if '"$PY" -m firstlight_v55.experiment' in x]
        self.assertEqual(len(lines),2)
        self.assertTrue(all('--run "$RUN/experiment" --model "$MODEL" --task-limit "$TASK_LIMIT"' in x for x in lines))
        self.assertTrue(any(x.endswith('--source "$FIRSTLIGHT_QUIXBUGS_DIR"') for x in lines))
        self.assertTrue(any(x.endswith('"$TASK_LIMIT"') for x in lines))
    def test_known_mac_bash_3_nounset_empty_array_hazard_recorded(self):
        # Mac Bash 3.2 treats a declared, empty array under set -u as unset.
        # The fixed launcher uses scalar arguments, without array expansion.
        script=(ROOT/'run_firstlight_v551.sh').read_text()
        self.assertTrue(script.startswith('#!/usr/bin/env bash\nset -Eeuo pipefail'))
        self.assertNotIn('${SRC_ARGS',script)
