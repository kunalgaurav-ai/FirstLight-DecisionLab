#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -x "$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python" ]]; then
  PY="$HOME/Downloads/agent-intelligence-lab-rigorous/.venv/bin/python"
else
  PY="$(command -v python3)"
fi
"$PY" scripts/verify_v39_release.py
"$PY" scripts/verify_v41_release.py
"$PY" scripts/launch_v41.py "$@"
