"""Byte-compile every script in artifacts/scripts so a syntax error is caught
before a background arm launches its next stage.

    python -u artifacts/analysis/compile_check.py
"""

import compileall
import pathlib
import sys

ROOT = pathlib.Path(r"F:\zero trust\zero-trust\artifacts\scripts")


def main() -> int:
    ok = compileall.compile_dir(str(ROOT), quiet=1, force=True, workers=1)
    print(f"compile_dir({ROOT}) -> {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
