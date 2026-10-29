#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ -n "${FIRSTLIGHT_PYTHON:-}" ]; then
  PYTHON="$FIRSTLIGHT_PYTHON"
  ALLOW_PIP=0
else
  if [ ! -x "$ROOT/.venv/bin/python" ]; then python3 -m venv "$ROOT/.venv"; fi
  PYTHON="$ROOT/.venv/bin/python"
  ALLOW_PIP=1
fi
RUN="$ROOT/runs/firstlight_v51_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$RUN"
export FIRSTLIGHT_RUN="$RUN"
seal() { "$PYTHON" -m firstlight_v5.package "$RUN" >/dev/null 2>&1 || true; }
trap seal EXIT
printf '\nFIRST LIGHT v5.1 · DEPENDENCY-CHECKED OFFICIAL BFCL PILOT\n'
# Source integrity before dependency installation or executing the test suite.
if "$PYTHON" scripts/verify_v46_release.py >"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" scripts/verify_firstlight_release.py >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" -m firstlight_v51.assert_release >>"$RUN/source_integrity.txt" 2>&1; then
  echo 'INHERITED + V5.1 SOURCE INTEGRITY PASS'
else
  cat "$RUN/source_integrity.txt"
  echo 'SOURCE VERIFICATION FAILED; no benchmarking'
  exit 10
fi
# PILLOW is required by inherited image integration tests. v5.0 never installed it.
if ! "$PYTHON" -c 'from PIL import Image; import io; p=io.BytesIO(); Image.new("RGB",(2,2),"orange").save(p,"PNG"); assert p.getvalue().startswith(bytes.fromhex("89504e470d0a1a0a"))' >/dev/null 2>&1; then
  echo 'DEPENDENCY: Pillow absent in isolated Python; installing binary wheel 13.0.0.'
  if [ "$ALLOW_PIP" -eq 0 ]; then
    echo 'ERROR: FIRSTLIGHT_PYTHON is externally managed; install Pillow there yourself or unset FIRSTLIGHT_PYTHON.'
    exit 11
  fi
  if ! PIP_DEFAULT_TIMEOUT=15 PIP_RETRIES=1 "$PYTHON" -m pip install --disable-pip-version-check --only-binary=:all: 'Pillow==13.0.0' >"$RUN/dependency_install.txt" 2>&1; then
    cat "$RUN/dependency_install.txt"
    echo 'DEPENDENCY BLOCKED: Could not install Pillow binary wheel. Check pip DNS/connectivity. No tests or benchmark attempted.'
    exit 11
  fi
fi
if "$PYTHON" -m firstlight_v51.preflight >"$RUN/dependency_check.txt" 2>&1; then
  echo 'PLATFORM PREFLIGHT: PASS (Pillow and FFmpeg/FFprobe)'
else
  cat "$RUN/dependency_check.txt"
  echo 'PLATFORM PREFLIGHT FAILED; no benchmark attempted'
  exit 12
fi
# Test output is captured rather than exposing simulated offline-fixture errors as live blockers.
if "$PYTHON" -m firstlight_v51.test_driver "$RUN/regression_tests.txt" --timeout 165; then
  grep -E 'Ran [0-9]+ tests' "$RUN/regression_tests.txt" | tail -1 || true
  echo 'REGRESSION SUITE: PASS (includes controlled DNS_DOWN simulation, not a real DNS check)'
else
  tail -80 "$RUN/regression_tests.txt"
  echo 'REGRESSION SUITE FAILED; no benchmark execution'
  exit 13
fi
if command -v open >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
  if ! curl --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    open -a Ollama >/dev/null 2>&1 || true
    for i in 1 2 3 4 5; do
      if curl --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
fi
TASKS="${FIRSTLIGHT_TASK_LIMIT:-24}"
if ! [[ "$TASKS" =~ ^[0-9]+$ ]] || [ "$TASKS" -lt 1 ] || [ "$TASKS" -gt 500 ]; then
  echo 'INVALID FIRSTLIGHT_TASK_LIMIT: expected integer from 1 to 500'
  exit 14
fi
"$PYTHON" -m firstlight_v51.run --run "$RUN" --limit "$TASKS"
echo "FIRST LIGHT EVIDENCE DIRECTORY: $RUN"
echo 'RESEARCH DASHBOARD: localhost; benchmark inputs are authentic, local diagnostic is not official grade'
"$PYTHON" -m firstlight_v5.site "$RUN"
