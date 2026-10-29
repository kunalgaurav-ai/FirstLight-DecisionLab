#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${AIL_V38_PYTHON:-}" ]; then PY="$AIL_V38_PYTHON"
elif [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then PY="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then echo 'ERROR: Python 3.10+ unavailable' >&2;exit 2;fi
"$PY" -c 'import sys; assert sys.version_info >= (3,10),"Python 3.10+ required"'
"$PY" scripts/verify_v38_release.py
# If the locally installed Ollama desktop app is present but its loopback API
# is not active, open the app. No model pull or external API request is made.
if [ "$(uname -s)" = "Darwin" ] && command -v curl >/dev/null 2>&1; then
  if ! curl --silent --max-time 2 --fail http://127.0.0.1:11434/api/tags >/dev/null; then
    if open -Ra Ollama >/dev/null 2>&1; then
      echo 'Starting already-installed local Ollama desktop runtime...'
      open -a Ollama
      for n in 1 2 3 4 5 6 7 8 9 10; do
        if curl --silent --max-time 2 --fail http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
        sleep 1
      done
    fi
  fi
fi
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PY" scripts/launch_v38.py "$@"
