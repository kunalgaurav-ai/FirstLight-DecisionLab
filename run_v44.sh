#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${AIL_PYTHON:-python3}"
if [ "${AIL_PYTHON:-}" = "" ] && [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then PYTHON="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"; fi
RUN="$ROOT/runs/v44_$(date -u +%Y%m%dT%H%M%SZ)_$($PYTHON -c 'import uuid;print(uuid.uuid4().hex[:8])')"
"$PYTHON" -m ail_v44.cli --run "$RUN" init
"$PYTHON" scripts/verify_v43_release.py >"$RUN/source_integrity_v44.txt" 2>&1
"$PYTHON" scripts/verify_v431_release.py >>"$RUN/source_integrity_v44.txt" 2>&1
"$PYTHON" scripts/verify_v44_release.py >>"$RUN/source_integrity_v44.txt" 2>&1
printf 'SOURCE INTEGRITY VERIFIED\n'
if "$PYTHON" -m unittest discover -s tests -q >"$RUN/tests_v44.txt" 2>&1; then
  printf 'REGRESSION TESTS PASS: '; grep -E 'Ran [0-9]+ tests' "$RUN/tests_v44.txt" | tail -1 || true
else
  printf 'REGRESSION TESTS FAIL — DIAGNOSTIC ZIP CREATED\n'
  "$PYTHON" -m ail_v44.cli --run "$RUN" package
  tail -50 "$RUN/tests_v44.txt"
  exit 1
fi
printf 'EXECUTING REAL LOCAL TEXT / MACOS AUDIO / CONTROLLED TOOL STAGES...\n'
"$PYTHON" -m ail_v44.cli --run "$RUN" local
printf 'EXPECTED VIDEO PROMPTS: 6 campaigns, 19 shots, 24–32 seconds per story\n'
printf 'NO REMOTE MODEL CALLS AUTOMATICALLY; NO PHOTO-SLIDESHOW SUBSTITUTES\n'
printf 'RUN DIRECTORY: %s\n' "$RUN"
printf 'UPLOAD ZIP: %s\n' "$(find "$RUN" -maxdepth 1 -name 'UPLOAD_THIS_v44_*.zip' -print -quit)"
function finish(){ "$PYTHON" -m ail_v44.cli --run "$RUN" package >/dev/null; printf '\nSEALED REPORT ZIP: %s\n' "$(find "$RUN" -maxdepth 1 -name 'UPLOAD_THIS_v44_*.zip' -print -quit)"; }
trap finish EXIT
"$PYTHON" -m ail_v44.cli --run "$RUN" serve
