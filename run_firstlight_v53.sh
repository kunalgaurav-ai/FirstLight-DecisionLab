#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --install-models) INSTALL=1 ;;
    *) echo "Unknown launcher argument: $arg"; echo 'Usage: bash ./run_firstlight_v53.sh [--install-models]'; exit 2 ;;
  esac
done
if [ -n "${FIRSTLIGHT_PYTHON:-}" ]; then PYTHON="$FIRSTLIGHT_PYTHON"; ALLOW_PIP=0
else
  if [ ! -x "$ROOT/.venv/bin/python" ]; then python3 -m venv "$ROOT/.venv"; fi
  PYTHON="$ROOT/.venv/bin/python"; ALLOW_PIP=1
fi
RUN="$ROOT/runs/firstlight_v53_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$RUN"
finalize() { "$PYTHON" -m firstlight_v53.pack "$RUN" >/dev/null 2>&1 || true; }
trap finalize EXIT
printf '\nFIRST LIGHT v5.3 · MULTI-MODEL COMPETITIVE MATRIX\n'
if "$PYTHON" scripts/verify_v46_release.py >"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" scripts/verify_firstlight_release.py >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" -m firstlight_v51.assert_release >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" -m firstlight_v52.verify >>"$RUN/source_integrity.txt" 2>&1 \
 && "$PYTHON" -m firstlight_v53.verify >>"$RUN/source_integrity.txt" 2>&1; then
 echo 'ALL INHERITED SOURCE MANIFESTS + v5.3: PASS'
else
 cat "$RUN/source_integrity.txt"; echo 'SOURCE INTEGRITY FAILURE; no live execution';exit 10
fi
if ! "$PYTHON" -c 'from PIL import Image; import io; p=io.BytesIO();Image.new("RGB",(2,2),"orange").save(p,"PNG");assert p.getvalue().startswith(bytes.fromhex("89504e470d0a1a0a"))' >/dev/null 2>&1; then
  if [ "$ALLOW_PIP" -eq 0 ]; then echo 'PILLOW_MISSING_EXTERNAL_ENV';exit 11;fi
  echo 'Installing Pillow for inherited image regression tests...'
  if ! PIP_DEFAULT_TIMEOUT=15 PIP_RETRIES=1 "$PYTHON" -m pip install --disable-pip-version-check --only-binary=:all: 'Pillow==13.0.0' >"$RUN/dependency_install.txt" 2>&1; then
    cat "$RUN/dependency_install.txt";echo 'PILLOW_INSTALL_BLOCKED';exit 11
  fi
fi
if ! "$PYTHON" -m firstlight_v51.preflight >"$RUN/dependency_check.txt" 2>&1; then
 cat "$RUN/dependency_check.txt";exit 12
fi
if "$PYTHON" -m firstlight_v52.test_driver "$RUN/regression_tests.txt" --timeout 180; then
 grep -E 'Ran [0-9]+ tests' "$RUN/regression_tests.txt" | tail -1 || true
 echo 'REGRESSION SUITE PASS — test fixture output is quarantined in regression_tests.txt'
else
 tail -70 "$RUN/regression_tests.txt";echo 'TESTS_FAILED_LIVE_EXPERIMENT_NOT_RUN';exit 13
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
MODELS="${FIRSTLIGHT_MODELS:-qwen2.5:0.5b,qwen2.5:1.5b,qwen3:0.6b,llama3.2:1b,gemma3:1b}"
TASKS="${FIRSTLIGHT_TASK_LIMIT:-48}"
if ! [[ "$TASKS" =~ ^[0-9]+$ ]] || [ "$TASKS" -lt 1 ] || [ "$TASKS" -gt 200 ]; then
 echo 'FIRSTLIGHT_TASK_LIMIT must be integer 1..200';exit 14
fi
PULL_ARG=''
if [ "$INSTALL" -eq 1 ]; then PULL_ARG='--install-missing';fi
echo 'MODEL PREFLIGHT (only installed models run unless --install-models explicitly supplied)'
"$PYTHON" -m firstlight_v53.setup_models --models "$MODELS" ${PULL_ARG:+$PULL_ARG} >"$RUN/model_setup.txt" 2>&1 || true
cat "$RUN/model_setup.txt"
echo 'EXECUTING REAL BFCL TASKS — published gold answers NOT included in model prompts'
"$PYTHON" -m firstlight_v53.matrix --run "$RUN" --limit "$TASKS" --models "$MODELS"
"$PYTHON" -m firstlight_v53.pack "$RUN"
echo "RESULT DIRECTORY: $RUN"
echo 'RESEARCH PAGE: Named model × policy points only where actual measurements exist'
"$PYTHON" -m firstlight_v53.research "$RUN"
