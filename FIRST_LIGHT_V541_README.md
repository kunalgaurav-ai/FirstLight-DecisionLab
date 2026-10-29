# First Light v5.4.1: macOS regression-launch recovery

## Observed problem
User's real v5.4 Mac run passed inherited source verification but failed
`test_runner_uses_execution_dir_for_provenance` before starting BFCL inference.
The inherited v5.1 test lexically compared `TemporaryDirectory` paths that
macOS may express under `/var/folders` to the production runner's resolved
`/private/var/folders` directory. This false failure had also been seen in
v5.1, fixed in v5.2, and accidentally reintroduced by the v5.4 test launcher.

## Correction
`run_firstlight_v541.sh` canonicalizes TMPDIR/TMP/TEMP *before* the existing
v5.4 script launches Python or creates test fixtures. Source models, dataset
selection, scoring, policies, historical results, preexisting tests and evidence
packers are unchanged and retain their checksums. The new regression test
reproduces the actual symlink-alias failure against the inherited test code.

## Launch
From the extracted project directory, run:
`FIRSTLIGHT_SCREEN_LIMIT=24 FIRSTLIGHT_EVAL_LIMIT=24 FIRSTLIGHT_FINALISTS=3 bash ./run_firstlight_v541.sh`

Add `--install-models` **only** if authorizing downloads of missing model weights.
No paid providers are called by this benchmark. Requires Internet access for
BFCL source if a verified local cache cannot be reused, and Ollama for execution.
Only completed, source-verified local diagnostic results are plotted; official
BFCL grades, independent customer acceptance and billed dollars are not
established. Tests are always isolated from benchmark outcomes.

The former `DNS_DOWN`, `NETWORK_STOP` and `SIMULATED_STOP` messages printed
inside the regression suite were controlled test fixtures. They must never be
interpreted as a diagnosis of the actual user's Internet connection.
