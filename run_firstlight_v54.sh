#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
INSTALL=0
for arg in "$@"; do
 case "$arg" in
   --install-models) INSTALL=1 ;;
   *) echo "Unknown argument: $arg. Allowed: --install-models";exit 2 ;;
 esac
done
if [ -n "${FIRSTLIGHT_PYTHON:-}" ]; then
 PY="$FIRSTLIGHT_PYTHON";ALLOW_PIP=0
else
 if [ ! -x "$ROOT/.venv/bin/python" ]; then python3 -m venv "$ROOT/.venv";fi
 PY="$ROOT/.venv/bin/python";ALLOW_PIP=1
fi
RUN="$ROOT/runs/firstlight_v54_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$RUN"
finalize() { "$PY" -m firstlight_v54.pack "$RUN" >/dev/null 2>&1 || true; }
trap finalize EXIT
printf '\nFIRST LIGHT v5.4 · MATCHED QUALITY-ECONOMICS RESEARCH\n'
if "$PY" scripts/verify_v46_release.py >"$RUN/source_integrity.txt" 2>&1 \
 && "$PY" scripts/verify_firstlight_release.py >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PY" -m firstlight_v51.assert_release >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PY" -m firstlight_v52.verify >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PY" -m firstlight_v53.verify >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PY" -m firstlight_v54.verify >>"$RUN/source_integrity.txt" 2>&1; then
 echo 'SOURCE INTEGRITY: PASS (ALL PREVIOUS VERSIONS PRESERVED)'
else
 cat "$RUN/source_integrity.txt";echo 'INTEGRITY FAIL - NO EXPERIMENT';exit 10
fi
if ! "$PY" -c 'from PIL import Image;from io import BytesIO;b=BytesIO();Image.new("RGB",(2,2)).save(b,"PNG");assert b.getvalue().startswith(bytes.fromhex("89504e470d0a1a0a"))' 2>/dev/null; then
 if [ "$ALLOW_PIP" -eq 0 ];then echo 'PILLOW_MISSING_IN_PROVIDED_PYTHON';exit 11;fi
 echo 'Installing Pillow required by inherited image regressions (no paid model provider)'
 if ! PIP_DEFAULT_TIMEOUT=15 PIP_RETRIES=1 "$PY" -m pip install --disable-pip-version-check --only-binary=:all: 'Pillow==13.0.0' >"$RUN/dependency_install.txt" 2>&1;then
  cat "$RUN/dependency_install.txt";echo 'PILLOW_INSTALL_BLOCKED';exit 11
 fi
fi
if ! "$PY" -m firstlight_v51.preflight >"$RUN/preflight.txt" 2>&1;then cat "$RUN/preflight.txt";exit 12;fi
if "$PY" -m firstlight_v54.test_runner "$RUN/regression_tests.txt" --timeout 180 --min-tests 310;then
 grep -E 'Ran [0-9]+ tests' "$RUN/regression_tests.txt" | tail -1 || true
 echo 'REGRESSIONS PASS; TEST OUTPUT QUARANTINED FROM LIVE EVIDENCE'
else
 tail -55 "$RUN/regression_tests.txt";echo 'TEST FAILURE; NO BENCHMARK RUN';exit 13
fi
# Mac Ollama may already run without the CLI on PATH.
if [ "$(uname -s)" = "Darwin" ] && command -v open >/dev/null 2>&1 && command -v curl >/dev/null 2>&1;then
 if ! curl --max-time 2 -fsS 'http://127.0.0.1:11434/api/tags' >/dev/null 2>&1;then
  open -a Ollama >/dev/null 2>&1 || true
  for i in 1 2 3 4 5;do
   if curl --max-time 2 -fsS 'http://127.0.0.1:11434/api/tags' >/dev/null 2>&1;then break;fi
   sleep 2
  done
 fi
fi
if [ "$INSTALL" -eq 1 ];then
 echo 'EXPLICIT 11-MODEL INSTALLATION OPT-IN: individual model licenses apply'
 if ! "$PY" -m firstlight_v54.models --install-missing >"$RUN/models.txt" 2>&1;then
  cat "$RUN/models.txt";echo 'MODEL_PULL_FAILED; BENCHMARK WILL USE INSTALLED MODELS ONLY';
 fi
else
 "$PY" -m firstlight_v54.models >"$RUN/models.txt" 2>&1 || true
fi
cat "$RUN/models.txt"
SCREEN="${FIRSTLIGHT_SCREEN_LIMIT:-24}"
EVAL="${FIRSTLIGHT_EVAL_LIMIT:-24}"
FINALISTS="${FIRSTLIGHT_FINALISTS:-3}"
MODEL_SET="${FIRSTLIGHT_MODELS:-auto}"
if ! [[ "$SCREEN" =~ ^[0-9]+$ && "$EVAL" =~ ^[0-9]+$ && "$FINALISTS" =~ ^[0-9]+$ ]];then echo 'TASK COUNTS MUST BE INTEGERS';exit 14;fi
printf 'EXECUTING BFCL SCREEN + DISJOINT HOLDOUT · %s screen / %s evaluation · %s finalists max\n' "$SCREEN" "$EVAL" "$FINALISTS"
"$PY" -m firstlight_v54.experiment --run "$RUN" --screen-limit "$SCREEN" --eval-limit "$EVAL" --finalists "$FINALISTS" --models "$MODEL_SET"
if [ -n "${FIRSTLIGHT_ANNOTATED_TRACES_JSONL:-}" ];then
 echo 'EVALUATING USER-SUPPLIED ANNOTATED PREFIX TRACES (RETROSPECTIVE ONLY)'
 "$PY" -m firstlight_v54.early --input "$FIRSTLIGHT_ANNOTATED_TRACES_JSONL" --output "$RUN/trace_prefix_results_v54.json" || echo 'TRAJECTORY_DATA_REJECTED; NOT COUNTED'
fi
"$PY" -m firstlight_v54.pack "$RUN"
echo "RESULTS DIRECTORY: $RUN"
echo 'COMPETITIVE CLAIM GATE: HOLD WITHOUT OFFICIAL GRADING, ACCEPTED OUTCOME AND REAL COST DATA'
"$PY" -m firstlight_v54.research "$RUN"
