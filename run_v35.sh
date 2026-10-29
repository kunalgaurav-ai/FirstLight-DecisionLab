#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${AIL_V35_PYTHON:-}" ]; then PYTHON="$AIL_V35_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then PYTHON="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else PYTHON="$(command -v python3 || true)"; fi
if [ -z "$PYTHON" ]; then echo 'Python 3 is missing' >&2; exit 2; fi
"$PYTHON" -c 'import sys;assert sys.version_info >= (3,10),"Python 3.10+ required"'
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" scripts/launch_v35.py
