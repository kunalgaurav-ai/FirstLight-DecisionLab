#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# No downloads, no model calls, no docker, no pip installs. Dedicated run directory.
if [ -n "${AIL_V33_PYTHON:-}" ]; then
  PYTHON="$AIL_V33_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then
  PYTHON="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else
  PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3 is required" >&2; exit 2
fi
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ is required"'
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" scripts/launch_v33.py
