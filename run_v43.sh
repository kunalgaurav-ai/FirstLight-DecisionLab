#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]; then
  BASE="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else
  BASE="$(command -v python3)"
fi
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  "$BASE" -m venv "$ROOT/.venv"
fi
PY="$ROOT/.venv/bin/python"
if ! "$PY" -c 'import gradio_client' 2>/dev/null; then
  echo "Installing Gradio client inside this release's isolated .venv; no paid API or model download."
  if ! "$PY" -m pip install --disable-pip-version-check 'gradio_client>=1.5,<3'; then
    echo 'Gradio client installation unavailable. Launcher will report missing-dependency evidence.'
  fi
fi
"$PY" scripts/verify_v39_release.py
"$PY" scripts/verify_v41_release.py
"$PY" scripts/verify_v42_release.py
"$PY" scripts/verify_v43_release.py
"$PY" scripts/launch_v43.py "$@"
