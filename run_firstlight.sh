#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ "${FIRSTLIGHT_PYTHON:-}" != "" ]; then PYTHON="$FIRSTLIGHT_PYTHON"; else
 if [ ! -x "$ROOT/.venv/bin/python" ]; then python3 -m venv "$ROOT/.venv"; fi
 PYTHON="$ROOT/.venv/bin/python"
fi
RUN="$ROOT/runs/firstlight_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$RUN"
EXIT_STATUS=0
on_exit(){ "$PYTHON" -m firstlight_v5.package "$RUN" >/dev/null 2>&1 || true; }
trap on_exit EXIT
printf '\nFIRST LIGHT v5 · REPRODUCIBLE COMPETITIVE BENCHMARK\n'
printf 'BRAND: First Light / archived Agent Intelligence Lab source preserved\n'
# inherited source verification and full regression suite, including new integration tests
if "$PYTHON" scripts/verify_v46_release.py >"$RUN/source_integrity.txt" 2>&1 && \
   "$PYTHON" scripts/verify_firstlight_release.py >>"$RUN/source_integrity.txt" 2>&1; then
 echo 'INHERITED SOURCE INTEGRITY: PASS'
else
 cat "$RUN/source_integrity.txt"
 echo 'SOURCE INTEGRITY FAILED; no benchmark execution'
 exit 1
fi
if "$PYTHON" -m unittest discover -s tests -q >"$RUN/regression_tests.txt" 2>&1; then
 grep -E 'Ran [0-9]+ tests' "$RUN/regression_tests.txt" | tail -1 || true
 echo 'REGRESSION SUITE: PASS'
else
 tail -60 "$RUN/regression_tests.txt"
 echo 'REGRESSION SUITE FAILED; no benchmark execution'
 exit 1
fi
# Mac convenience; never install models or any paid services automatically
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
"$PYTHON" -m firstlight_v5.runner --run "$RUN" --source-dir "$ROOT/data/firstlight/official_bfcl" --limit "$TASKS" || true
"$PYTHON" -m firstlight_v5.package "$RUN"
echo "RUN FOLDER: $RUN"
echo 'RESEARCH DASHBOARD: starting localhost; no remote inference charges'
"$PYTHON" -m firstlight_v5.site "$RUN"
