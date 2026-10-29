# First Light v5.1 — Dependency-correct competitive benchmark launcher

## Root-cause investigation (actual user Mac run 2026-10-25/26)

v5.0's fresh `.venv` installed **zero** Python runtime dependencies. Its inherited
`tests/test_v46_runtime.py` image-provider test uses `from PIL import Image` to
create a controlled image and therefore returned `FAILED_PROVIDER` when Pillow
was absent. The catch-all provider status obscured the `ModuleNotFoundError`.
Reproduced in a fresh Python virtualenv without Pillow.

`DNS_DOWN` appeared in the **regression suite** from the deliberately mocked
`test_offline_blocked_gives_json_not_fake_score`, not from a live GitHub request.
The full BFCL benchmark never started: v5.0 launcher exits on test failure.
The uploaded v5 results ZIP has no tasks and a zero-row CSV.

## Correction

`bash ./run_firstlight_v51.sh` is the **only v5.1 launch command**. It verifies
all inherited sources before running, uses an isolated venv, explicitly verifies
and if necessary installs the Pillow 13.0.0 binary wheel, validates actual PNG
encoding plus FFmpeg/FFprobe availability, and runs all inherited/new tests.
Test fixture output (including controlled DNS_DOWN) is kept in the results log.
Dependency installation failures halt with a clear diagnostic and seal results.

The full regression test runner also has a 165-second maximum and terminates any
lingering child test subprocess group on timeout; it never continues to live benchmarks
after a timeout.

The benchmark now stores public BFCL dataset provenance under the run directory,
so the ZIP includes its exact pinned commit and file hash manifest. No remote
model is downloaded or remote inference billed. Network and local Ollama models
remain genuine external dependencies.

## Evidence boundary

Passing 274 software tests does not establish official BFCL scores, quality,
commercial costs, comparative superiority or a product multiplier. A 24-case
local pilot is diagnostic only and historical v5.0 raw results remain unchanged.

On Mac, after the launcher runs: Ctrl+C closes the website, then locate
`UPLOAD_THIS_FIRST_LIGHT_V5_*.zip` under the release's `runs` directory.
