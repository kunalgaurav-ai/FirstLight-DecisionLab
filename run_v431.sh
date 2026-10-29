#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY_BIN="${AIL_PYTHON:-python3}"
if [ "$PY_BIN" = python3 ]; then
  FOUND="$(find "$HOME/Downloads/AIL-v43-executions" -path '*/agent-intelligence-lab-v4.3-prompt-first-generative/.venv/bin/python' -print -quit 2>/dev/null || true)"
  if [ -n "$FOUND" ]; then PY_BIN="$FOUND"; fi
fi
"$PY_BIN" scripts/verify_v43_release.py
"$PY_BIN" scripts/verify_v431_release.py
"$PY_BIN" -m unittest discover -s tests -v
"$PY_BIN" scripts/launch_v431.py "$@"
