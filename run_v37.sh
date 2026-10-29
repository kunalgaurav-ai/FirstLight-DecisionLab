#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${AIL_V37_PYTHON:-}" ]; then PY="$AIL_V37_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then PY="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then echo 'Python 3.10+ required' >&2;exit 2;fi
"$PY" -c 'import sys;assert sys.version_info >= (3,10),"Python 3.10+ required"'
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PY" scripts/launch_v37.py "$@"
