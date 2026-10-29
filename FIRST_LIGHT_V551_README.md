# First Light v5.5.1 — Mac launcher hotfix (2026-10-26)

## Root cause and scope

The real Mac execution of v5.5 passed 329 tests but stopped at `line 56: SRC_ARGS[@]: unbound variable`. The v5.5 launcher expanded a declared empty Bash array while `set -u` was active; macOS ships Bash 3.2, where this triggers an abort. No QuixBugs live task ran and no evidence ZIP was produced.

v5.5.1 adds a **new** launcher that explicitly branches on whether `FIRSTLIGHT_QUIXBUGS_DIR` is set. It never expands an empty Bash array. It leaves the v5.5 launch script, benchmark model calls, task order, quality checks, source fetcher, packager, dashboard and every inherited file unchanged. All changes are tracked in `FIRST_LIGHT_V551_SOURCE_SHA256.json`.

## Mac one-launch

`FIRSTLIGHT_TASK_LIMIT=6 FIRSTLIGHT_MODEL=qwen2.5:1.5b bash ./run_firstlight_v551.sh`

The launcher first verifies all manifests and runs inherited regression tests. It then executes actual paired public QuixBugs tasks, packages results and opens a localhost research dashboard. If the public repository or local model cannot be accessed, it records a BLOCKED report rather than synthesizing performance scores.

A completed local pilot is **not** official SWE-bench grading, a benchmark of customer workflows, an OSS superiority result, or evidence of commercial USD savings.

## Inputs and safety

- Requires local `qwen2.5:1.5b` installed in Ollama. No model downloads or paid APIs.
- Requires `git` and network access to `https://github.com/jkoppel/QuixBugs.git`, unless `FIRSTLIGHT_QUIXBUGS_DIR` identifies a local checkout with verified MIT license and required files.
- The generated-function executor is a resource-limited AST-filtered subprocess **not** a hardened security sandbox. Use only trusted public benchmark tasks.
- All raw v5.4.1 measured evidence and inherited source remain unchanged.
- The v5.5 engine emits `UPLOAD_THIS_FIRSTLIGHT_V55_*.zip` names; v5.5.1 is the launcher release, not a new scoring engine.
