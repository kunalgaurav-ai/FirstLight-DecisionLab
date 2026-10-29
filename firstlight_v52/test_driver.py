"""Run the unchanged inherited regression suite with canonical temporary paths.

macOS exposes /var/folders as a symlink to /private/var/folders. The
v5.1 provenance test compared a temp directory's spelling to a canonical
path created by the production runner. They are the same directory but
Path.is_relative_to() compares path spelling, causing a false test failure.

This module fixes the process environment *before* spawning unittest;
previous source and test files remain byte-for-byte intact.
"""
from __future__ import annotations
import argparse
import os
import pathlib
import tempfile
import sys

from firstlight_v51.test_driver import execute


def canonical_tmp(path: str | os.PathLike[str] | None = None) -> str:
    original = pathlib.Path(path or tempfile.gettempdir())
    resolved = original.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError('TMPDIR_IS_NOT_DIRECTORY')
    return str(resolved)


def canonical_test_environment(path: str | os.PathLike[str] | None = None) -> dict[str, str]:
    normalized = canonical_tmp(path)
    # These names are used by tempfile on different POSIX platforms.
    return {key: normalized for key in ('TMPDIR', 'TMP', 'TEMP')}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('logfile')
    ap.add_argument('--timeout', type=int, default=165)
    args = ap.parse_args(argv)
    env = canonical_test_environment()
    os.environ.update(env)
    print('REGRESSION_TEMP_CANONICAL:', env['TMPDIR'], flush=True)
    return execute(pathlib.Path(args.logfile), args.timeout)


if __name__ == '__main__':
    sys.exit(main())
