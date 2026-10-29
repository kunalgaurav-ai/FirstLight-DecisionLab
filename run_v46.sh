#!/bin/bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
# Keep dependencies isolated to this release, not the user's existing research env.
if [ -n "${AIL_PYTHON:-}" ]; then
  PYTHON="$AIL_PYTHON"
else
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    python3 -m venv "$ROOT/.venv"
  fi
  PYTHON="$ROOT/.venv/bin/python"
fi
# Lightweight official provider clients; failed installation is explicit in the dashboard.
if ! "$PYTHON" -c 'import gradio_client, huggingface_hub, PIL' >/dev/null 2>&1; then
  echo 'INSTALLING OFFICIAL GRADIO / HUGGING FACE CLIENTS (NO MODEL DOWNLOAD)...'
  "$PYTHON" -m pip install --disable-pip-version-check 'gradio_client>=1.5,<3' 'huggingface-hub>=1.16,<3' 'Pillow>=10,<13' >"$ROOT/provider_dependencies_v46.log" 2>&1 || \
    echo 'OPTIONAL PROVIDER CLIENT INSTALL FAILED — LOCAL TEXT/AUDIO STILL AVAILABLE. SEE provider_dependencies_v46.log'
fi
RUN="$ROOT/runs/v46_$(date -u +%Y%m%dT%H%M%SZ)_$($PYTHON -c 'import uuid;print(uuid.uuid4().hex[:8])')"
trap '"$PYTHON" -m ail_v46.cli --run "$RUN" package >/dev/null 2>&1 || true' EXIT
printf 'AIL v4.6 PRE-FLIGHT\n'
mkdir -p "$RUN"
if ! "$PYTHON" scripts/verify_v45_release.py >"$RUN/source_integrity.txt" 2>&1 || \
   ! "$PYTHON" scripts/verify_v46_release.py >>"$RUN/source_integrity.txt" 2>&1; then
  cat "$RUN/source_integrity.txt";echo 'SOURCE INTEGRITY FAILURE';exit 1
fi
printf 'SOURCE INTEGRITY PASS\n'
if "$PYTHON" -m unittest discover -s tests -q >"$RUN/regressions.txt" 2>&1; then
   grep -E 'Ran [0-9]+ tests' "$RUN/regressions.txt" | tail -1 || true
else
   tail -50 "$RUN/regressions.txt";echo 'TEST FAILURE — NO EXECUTION';exit 1
fi
if command -v open >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
  if ! curl --connect-timeout 2 --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    open -a Ollama >/dev/null 2>&1 || true
    for i in 1 2 3 4 5; do
      if curl --connect-timeout 2 --max-time 2 -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
fi
# Each version writes into its own run, never overwrites prior results.
"$PYTHON" -m ail_v46.cli --run "$RUN" init
"$PYTHON" -m ail_v46.cli --run "$RUN" experiment
printf 'RUN DIRECTORY: %s\n' "$RUN"
printf 'MODEL/PROVIDER LIMITATIONS: see dashboard readiness; no external generation on startup\n'
"$PYTHON" -m ail_v46.cli --run "$RUN" serve
