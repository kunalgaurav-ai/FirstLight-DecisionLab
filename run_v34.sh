#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${AIL_V34_PYTHON:-}" ]; then
  PYTHON="$AIL_V34_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then
  PYTHON="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else
  PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ]; then echo "Python 3 missing" >&2; exit 2; fi
"$PYTHON" -c 'import sys;assert sys.version_info>=(3,10),"Python 3.10+ is required"'
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" scripts/launch_v34.py
