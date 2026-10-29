#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
export PYTHONUNBUFFERED=1
PY="${FIRSTLIGHT_PYTHON:-}"
if [ -z "$PY" ]; then
  REUSE="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
  if [ -x "$REUSE" ] && "$REUSE" -c 'from PIL import Image' >/dev/null 2>&1;then PY="$REUSE"
  elif [ -x "$ROOT/.venv/bin/python" ];then PY="$ROOT/.venv/bin/python"
  else python3 -m venv "$ROOT/.venv";PY="$ROOT/.venv/bin/python";fi
fi
export TMPDIR="$("$PY" -m firstlight_v541.temp)"
export TMP="$TMPDIR" TEMP="$TMPDIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$ROOT/runs/decision_lab_${STAMP}_$$"
mkdir -p "$ROOT/runs"
if [ -e "$RUN" ];then echo 'FAIL_CLOSED_RUN_PATH_EXISTS';exit 5;fi
mkdir -p "$RUN"
echo 'FIRST LIGHT · ECONOMIC DECISION KERNEL · THREE EXECUTED MATCHED POLICIES'
echo 'No new model weights; no paid APIs; official SWE-bench/OSS superiority NOT claimed.'
echo "CANONICAL MAC TEMP: $TMPDIR"
"$PY" -m firstlight_v551.verify || { echo 'FAILED_INHERITED_SOURCE_INTEGRITY';exit 6; }
"$PY" -m firstlight_decision.verify_release || { echo 'FAILED_NEW_SOURCE_INTEGRITY';exit 6; }
if ! "$PY" -c 'from PIL import Image' >/dev/null 2>&1;then
  if [ "$PY" != "$ROOT/.venv/bin/python" ];then
    echo 'PIL_MISSING_IN_REUSED_PYTHON: set FIRSTLIGHT_PYTHON to compatible env';exit 7
  fi
  "$PY" -m pip install --disable-pip-version-check --only-binary=:all: 'Pillow==13.0.0' || exit 7
fi
if "$PY" -m firstlight_v54.test_runner "$RUN/inherited_regression_tests.txt" --timeout 190 --min-tests 328;then
  echo 'INHERITED REGRESSION GATE PASS'
else
  tail -50 "$RUN/inherited_regression_tests.txt"; echo 'FAIL_CLOSED_REGRESSION';exit 8
fi
if "$PY" -m unittest discover -s tests_decision -q >"$RUN/decision_regression_tests.txt" 2>&1;then
  echo 'DECISION KERNEL REGRESSION GATE PASS'
else
  tail -60 "$RUN/decision_regression_tests.txt";echo 'FAIL_CLOSED_DECISION_TESTS';exit 8
fi
if [ "$(uname -s)" = 'Darwin' ] && command -v curl >/dev/null 2>&1;then
  if ! curl -f -sS -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1;then
    open -a Ollama >/dev/null 2>&1 || true
    for i in 1 2 3 4 5;do
      if curl -f -sS -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1;then break;fi
      sleep 2
    done
  fi
fi
MODEL="${FIRSTLIGHT_MODEL:-qwen2.5:1.5b}"
LIMIT="${FIRSTLIGHT_TASK_LIMIT:-14}"
case "$LIMIT" in ''|*[!0-9]*)echo 'BAD_TASK_LIMIT';exit 9;;esac
if [ "$LIMIT" -lt 1 ] || [ "$LIMIT" -gt 14 ];then echo 'TASK_LIMIT_OUTSIDE_1_TO_14';exit 9;fi
"$PY" -m firstlight_decision.run --root "$ROOT" --output "$RUN/experiment" --model "$MODEL" --task-limit "$LIMIT"
cp "$RUN/inherited_regression_tests.txt" "$RUN/experiment/inherited_regression_tests.txt"
cp "$RUN/decision_regression_tests.txt" "$RUN/experiment/decision_regression_tests.txt"
"$PY" -m firstlight_decision.pack "$RUN/experiment"
echo "LOCAL RESEARCH RESULTS: $RUN/experiment"
echo 'CAUSAL LONG-HORIZON SAVINGS / OFFICIAL EVAL / INVOICES: NOT ESTABLISHED'
"$PY" -m firstlight_decision.web "$RUN/experiment"
