"""Canonicalize test-run temp directories before *any* unittest process starts.

On macOS, /var is a symlink to /private/var. Some inherited provenance
assertions compare noncanonical TemporaryDirectory names with a production
execution directory resolved using Path.resolve(). Both paths identify the
same directory but Path.is_relative_to is lexical and rejects the alias.

No test, benchmark scorer, model policy, saved result or inherited source is
modified here. Fail closed if temp path cannot be verified and written to.
"""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import sys


def canonical_tmp(environ=None):
    env = dict(os.environ if environ is None else environ)
    candidate = next((env.get(key) for key in ('TMPDIR', 'TMP', 'TEMP') if env.get(key)), None)
    if not candidate:
        candidate = tempfile.gettempdir()
    raw = Path(candidate).expanduser()
    if not raw.is_absolute():
        raise ValueError('TEMP_PATH_MUST_BE_ABSOLUTE')
    canonical = raw.resolve(strict=True)
    if not canonical.is_dir():
        raise ValueError('TEMP_PATH_NOT_DIRECTORY')
    # Check that actual tempfile operations work here without leaving files.
    with tempfile.TemporaryFile(dir=canonical) as handle:
        handle.write(b'firstlight-temp-preflight')
    return str(canonical)


def test_env(environ=None):
    result = dict(os.environ if environ is None else environ)
    resolved = canonical_tmp(result)
    result.update({'TMPDIR': resolved, 'TMP': resolved, 'TEMP': resolved})
    return result


if __name__ == '__main__':
    try:
        print(canonical_tmp(), flush=True)
    except (OSError, ValueError) as exc:
        print('TEMP_CANONICAL_PREFLIGHT_FAILED: '+str(exc), file=sys.stderr)
        raise SystemExit(8)
