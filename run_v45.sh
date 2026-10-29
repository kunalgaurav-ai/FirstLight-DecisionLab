#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${AIL_PYTHON:-python3}"
if [ "${AIL_PYTHON:-}" = "" ] && [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then PYTHON="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"; fi
RUN="$ROOT/runs/v45_$(date -u +%Y%m%dT%H%M%SZ)_$($PYTHON -c 'import uuid;print(uuid.uuid4().hex[:8])')"
mkdir -p "$RUN"
seal(){ "$PYTHON" -m ail_v45.cli --run "$RUN" package >/dev/null 2>&1 || true; }
trap seal EXIT
printf 'VERIFYING ALL INHERITED SOURCE MANIFESTS...\n'
if "$PYTHON" scripts/verify_v44_release.py >"$RUN/source_integrity_v45.txt" 2>&1 && \
   "$PYTHON" scripts/verify_v431_release.py >>"$RUN/source_integrity_v45.txt" 2>&1 && \
   "$PYTHON" scripts/verify_v45_release.py >>"$RUN/source_integrity_v45.txt" 2>&1; then
  echo 'SOURCE INTEGRITY PASS'
else
  echo 'SOURCE INTEGRITY FAILED — source files must be audited';cat "$RUN/source_integrity_v45.txt";exit 1
fi
if "$PYTHON" -m unittest discover -s tests -q >"$RUN/tests_v45.txt" 2>&1; then
  grep -E 'Ran [0-9]+ tests' "$RUN/tests_v45.txt" | tail -1 || true
  echo 'REGRESSION TESTS PASS'
else
  echo 'REGRESSION TESTS FAILED — diagnostics retained at:' "$RUN/tests_v45.txt"
  tail -40 "$RUN/tests_v45.txt"
  exit 1
fi
if command -v curl >/dev/null 2>&1 && command -v open >/dev/null 2>&1; then
  if ! curl --connect-timeout 2 --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo 'OLLAMA NOT READY; ATTEMPTING TO START INSTALLED MAC APP (NO MODEL DOWNLOAD)'
    open -a Ollama >/dev/null 2>&1 || true
    for i in 1 2 3 4 5; do
      if curl --connect-timeout 2 --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
fi
printf 'RUNNING REAL QWEN TEXT BRANCHES AND MAC SPEECH CACHE BASELINES...\n'
"$PYTHON" -m ail_v45.cli --run "$RUN" experiment
printf 'RESULTS ZIP AND LOCAL OUTPUT: %s\n' "$RUN"
printf 'VIDEO MODEL CALLS ON THIS LAUNCH: 0 (19 SHOTS REMAIN SEPARATELY GATED)\n'
"$PYTHON" -m ail_v45.cli --run "$RUN" serve
