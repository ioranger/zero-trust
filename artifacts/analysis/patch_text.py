"""Apply exact-text replacements to a file.

Replacements are given in a JSON list of {find, replace} pairs, matched as
exact substrings. The script refuses to write if any `find` is absent or
ambiguous, so a typo cannot silently corrupt the manuscript.

    python -u artifacts/analysis/patch_text.py <file> <patches.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    target = Path(sys.argv[1])
    patches = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    text = target.read_text(encoding="utf-8")

    for i, p in enumerate(patches, 1):
        find = p["find"]
        repl = p["replace"]
        n = text.count(find)
        if n != 1:
            print(f"!! patch {i}: expected exactly 1 match, found {n}")
            print(f"   find starts: {find[:90]!r}")
            return 2
        text = text.replace(find, repl)
        print(f"ok patch {i}: replaced {len(find)} chars with {len(repl)}")

    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {target} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
