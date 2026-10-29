#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${AIL_V36_PYTHON:-}" ]; then P="$AIL_V36_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then P="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else P="$(command -v python3 || true)"; fi
if [ -z "$P" ]; then echo 'Python 3 is missing' >&2;exit 2;fi
"$P" -c 'import sys;assert sys.version_info >= (3,10),"Python 3.10+ required"'
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$P" scripts/launch_v36.py "$@"
