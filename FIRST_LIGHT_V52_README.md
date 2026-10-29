# First Light v5.2 — macOS BFCL launch recovery

**Status**: Executable BFCL V4 small pilot. NOT an official BFCL leaderboard score; no customer-dollar or independent quality superiority claims.

## What actually failed on macOS v5.1

The inherited v5.1 test `test_runner_uses_execution_dir_for_provenance` uses `TemporaryDirectory()` and compares `Path.is_relative_to()` against that non-resolved temporary path. The production runner calls `.resolve()` before accessing the same directory. On macOS the default temp folder may be spelled `/var/folders/...` while its resolved equivalent is `/private/var/folders/...`. Both are the same directory. The test assertion incorrectly fails, so the simulated fixture never writes `SOURCE_PROVENANCE.json`, which subsequently causes its ZIP assertion to fail. There was no public BFCL download attempt: regression tests stopped the launcher.

## Correction

The v5.2 test driver canonicalizes `TMPDIR`, `TMP` and `TEMP` **before launching the inherited regression suite**; inherited code and historical manifests are not modified. A real symlink-temporary-directory subprocess test replays the v5.1 test suite under canonical temp paths. Provenance must still exist before the ZIP can contain it. Missing real provenance is never fabricated.

## Single Mac launcher

Download ZIP and unzip into a new folder under `~/Downloads`:

```bash
setopt interactivecomments
cd "$HOME/Downloads" || exit 1
ZIP="$HOME/Downloads/first-light-v5.2-macos-benchmark-recovery.zip"
TARGET="$HOME/Downloads/FirstLight-v52-executions/source-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$TARGET"
unzip -q "$ZIP" -d "$TARGET" || exit 1
cd "$TARGET/first-light-v5.2-macos-benchmark-recovery" || exit 1
bash ./run_firstlight_v52.sh
```

The launcher creates a separate `.venv`, verifies inherited + new checksums, ensures Pillow and FFmpeg work, runs full regression tests, then attempts GitHub BFCL V4 data download and real Ollama inference with precommitted policies. It always writes a data report ZIP in `runs/`, and opens the localhost research dashboard even if the *actual* dataset/model stage is blocked.

There are **no paid model API calls**. It requires HTTPS to GitHub and the Ollama models `qwen2.5:0.5b` and `qwen2.5:1.5b` already present on your Mac. Do not share credentials in chat.

## After the run

Stop the dashboard with Control+C, then use:

```bash
ROOT="$HOME/Downloads/FirstLight-v52-executions"
RESULT_ZIP="$(find "$ROOT" -type f -name 'UPLOAD_THIS_FIRST_LIGHT_V5_*.zip' -print | sort | tail -n 1)"
if [ -n "$RESULT_ZIP" ] && [ -f "$RESULT_ZIP" ]; then
  echo "$RESULT_ZIP"
  open -R "$RESULT_ZIP"
fi
```

The ZIP's `benchmark_results.json` contains actual task count, state, diagnostic arm results (when successfully run), and exact blocked reason (if not). `official_data/SOURCE_PROVENANCE.json` appears only when a valid download yielded provenance. All files inside are checksummed. User input and public benchmark licenses remain subject to their terms; the local diagnostic is not BFCL's official evaluator.

The v5.2 wrapper preserves the v5 BFCL scoring and result schema but labels runtime status as v5.2.
