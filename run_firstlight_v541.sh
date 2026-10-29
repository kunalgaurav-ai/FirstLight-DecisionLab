#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"
PY="${FIRSTLIGHT_PYTHON:-}"
if [ -z "$PY" ]; then
    if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"
    else PY="$(command -v python3 || true)"; fi
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    echo 'FIRST_LIGHT_ERROR: Python 3 executable not found' >&2
    exit 7
fi
# The resolution MUST happen outside the inherited test subprocess.
CANONICAL_TEMP="$("$PY" -m firstlight_v541.temp)" || exit 8
export TMPDIR="$CANONICAL_TEMP" TMP="$CANONICAL_TEMP" TEMP="$CANONICAL_TEMP"
export PYTHONUNBUFFERED=1
printf '\nFIRST LIGHT v5.4.1 · MACOS-SAFE FULL BENCHMARK LAUNCHER\n'
printf 'CANONICAL TEST TEMP DIRECTORY: %s\n' "$TMPDIR"
printf 'PRESERVING ALL v5.4 MODEL POLICIES, BENCHMARKS AND PROVENANCE\n'
# An extra independent check protects against inadvertently calling a patched
# inherited test suite. It does not run tests from a different project tree.
"$PY" -m firstlight_v541.verify || exit 9
exec bash "$ROOT/run_firstlight_v54.sh" "$@"
