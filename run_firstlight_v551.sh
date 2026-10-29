#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
export PYTHONUNBUFFERED=1
PY="${FIRSTLIGHT_PYTHON:-}"
if [ -z "$PY" ];then
  # Prefer the existing working research venv to avoid duplicating packages on an 8GB Mac.
  REUSE="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
  if [ -x "$REUSE" ] && "$REUSE" -c 'from PIL import Image' >/dev/null 2>&1;then PY="$REUSE"
  elif [ -x "$ROOT/.venv/bin/python" ];then PY="$ROOT/.venv/bin/python"
  else
    command -v python3 >/dev/null || { echo 'PYTHON3_NOT_FOUND';exit 3; }
    python3 -m venv "$ROOT/.venv"
    PY="$ROOT/.venv/bin/python"
  fi
fi
CANONICAL_TEMP="$("$PY" -m firstlight_v541.temp)" || exit 4
export TMPDIR="$CANONICAL_TEMP" TMP="$CANONICAL_TEMP" TEMP="$CANONICAL_TEMP"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$ROOT/runs/firstlight_v551_${STAMP}_$$"
mkdir -p "$ROOT/runs"
if [ -e "$RUN" ];then echo 'RUN_PATH_ALREADY_EXISTS';exit 5;fi
printf '\nFIRST LIGHT v5.5.1 · PAIRED EXECUTED QUIXBUGS REPAIR RESEARCH\n'
printf 'CANONICAL TEMP: %s\n' "$TMPDIR"
printf 'Existing local Qwen only. No model download; no paid API.\n'
"$PY" -m firstlight_v551.verify || { echo 'SOURCE_INTEGRITY_FAILED';exit 6; }
if ! "$PY" -c 'from PIL import Image' >/dev/null 2>&1;then
  echo 'Inherited regressions require Pillow; installing one pinned wheel to private environment.'
  if [[ "$PY" != "$ROOT/.venv/bin/python" ]];then
    echo 'PIL_MISSING_IN_EXTERNAL_PYTHON: use a Python with PIL installed or unset FIRSTLIGHT_PYTHON';exit 7
  fi
  "$PY" -m pip install --only-binary=:all: --disable-pip-version-check 'Pillow==13.0.0' || exit 7
fi
mkdir -p "$RUN"
if "$PY" -m firstlight_v54.test_runner "$RUN/regression_tests.txt" --timeout 190 --min-tests 328;then
  echo 'FULL REGRESSION SUITE PASS (328+ tests; simulated fixture logs kept separate)'
else
  tail -40 "$RUN/regression_tests.txt";echo 'REGRESSION_FAILURE; NO PUBLIC EXECUTION';exit 8
fi
if [ "$(uname -s)" = 'Darwin' ] && command -v curl >/dev/null 2>&1 && command -v open >/dev/null 2>&1;then
  if ! curl -sS -m 3 -f http://127.0.0.1:11434/api/tags >/dev/null 2>&1;then
    open -a Ollama >/dev/null 2>&1 || true
    for i in 1 2 3 4 5;do
      if curl -sS -m 3 -f http://127.0.0.1:11434/api/tags >/dev/null 2>&1;then break;fi
      sleep 2
    done
  fi
fi
TASK_LIMIT="${FIRSTLIGHT_TASK_LIMIT:-6}"
if ! [[ "$TASK_LIMIT" =~ ^[1-6]$ ]];then echo 'TASK_LIMIT_MUST_BE_1_TO_6';exit 9;fi
MODEL="${FIRSTLIGHT_MODEL:-qwen2.5:1.5b}"
# Compatible with the system Bash 3.2 included on macOS: never expand an empty
# Bash array under set -u. The source path is always separately quoted.
# This is the same v5.5 experiment; only optional source argument wiring changes.
if [ -n "${FIRSTLIGHT_QUIXBUGS_DIR:-}" ]; then
  "$PY" -m firstlight_v55.experiment --run "$RUN/experiment" --model "$MODEL" --task-limit "$TASK_LIMIT" --source "$FIRSTLIGHT_QUIXBUGS_DIR"
else
  "$PY" -m firstlight_v55.experiment --run "$RUN/experiment" --model "$MODEL" --task-limit "$TASK_LIMIT"
fi
cp "$RUN/regression_tests.txt" "$RUN/experiment/regression_tests.txt"
"$PY" -m firstlight_v55.pack "$RUN/experiment" || { echo 'EVIDENCE_PACKAGING_FAILED';exit 10; }
# Keep test receipts, source-integrity and launch metadata outside model results.
"$PY" - "$RUN" "$ROOT" "$MODEL" "$TASK_LIMIT" <<'PY'
import hashlib,json,pathlib,sys,datetime
run,root,model,n=(pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),sys.argv[3],sys.argv[4])
record={'release':'5.5.1','engine_release':'5.5.0','model_requested':model,'tasks_requested':int(n),
'run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_release_sha256':hashlib.sha256((root/'FIRST_LIGHT_V551_SOURCE_SHA256.json').read_bytes()).hexdigest(),
'regression_log_sha256':hashlib.sha256((run/'regression_tests.txt').read_bytes()).hexdigest()}
(run/'LAUNCH_RECEIPT.json').write_text(json.dumps(record,indent=2)+'\n')
PY
STATUS="$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$RUN/experiment/results.json")"
echo "ACTUAL EXPERIMENT STATUS: $STATUS"
ZIP=$(find "$RUN/experiment" -maxdepth 1 -name 'UPLOAD_THIS_FIRSTLIGHT_V55_*.zip' -type f -print | head -1)
if [ -n "$ZIP" ];then echo "UPLOAD THIS FIRST LIGHT RESULTS ZIP: $ZIP";fi
echo "REGRESSION / LAUNCH LOGS: $RUN"
echo 'OFFICIAL SWE-BENCH, APPROVED CUSTOMER OUTCOMES, USD SAVINGS, STRONG OSS SUPERIORITY: NOT ESTABLISHED'
"$PY" -m firstlight_v55.web "$RUN/experiment"
