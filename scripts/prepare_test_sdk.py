"""Prepare the GenVM runtime archive that direct mode tests load.

Direct mode (gltest 0.29.2) tries to download a release asset named
``genvm-universal.tar.xz`` from the pinned GenVM release. That asset name no longer
exists, so a clean machine cannot run the tests. genvm-linter 0.11.0 downloads the
same archive under its versioned name, so this script links or copies the already
resolved archive into the directory direct mode looks at.

Nothing installed is modified and no contract source is touched.

Usage:
    python scripts/prepare_test_sdk.py
    python scripts/prepare_test_sdk.py --version v0.3.0-rc7
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_VERSION = "v0.3.0-rc7"


def archive_name(version: str) -> str:
    return f"genvm-universal-{version}.tar.xz"


def find_linter() -> Path | None:
    """Locate genvm-lint even when the virtual environment is not activated."""
    suffix = ".exe" if os.name == "nt" else ""
    beside_python = Path(sys.executable).parent / f"genvm-lint{suffix}"
    if beside_python.is_file():
        return beside_python
    found = shutil.which("genvm-lint")
    return Path(found) if found else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION, help="GenVM release tag")
    args = parser.parse_args()

    name = archive_name(args.version)
    home = Path.home()
    source = home / ".cache" / "genvm-linter" / name
    target = home / ".cache" / "gltest-direct" / name

    if target.is_file() or target.is_symlink():
        print(f"already prepared: {target}")
        return 0

    if not source.is_file():
        tool = find_linter()
        if tool is None:
            print(
                "genvm-lint was not found. Activate the virtual environment or run "
                "`python -m pip install -r requirements-dev.txt` first.",
                file=sys.stderr,
            )
            return 1
        print(f"fetching {args.version} through {tool.name or tool}")
        try:
            subprocess.run([str(tool), "download", "-v", args.version], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"could not download the GenVM archive: {exc}", file=sys.stderr)
            return 1

    if not source.is_file():
        print(f"expected archive is missing: {source}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)

    # A symlink avoids keeping a second copy of the archive. It is skipped on Windows,
    # where symlink creation needs elevated privileges.
    if os.name != "nt":
        try:
            target.symlink_to(source)
            print(f"linked: {target} -> {source}")
            return 0
        except OSError:
            pass

    shutil.copy2(source, target)
    print(f"copied: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
