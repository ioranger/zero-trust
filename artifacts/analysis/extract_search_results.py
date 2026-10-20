"""Extract the title / link / snippet triples from a chunked JSONL search artifact.

The search tool externalises its output into chunked JSONL files whose chunk
"text" fields concatenate into the original JSON. This reassembles it and
prints the result list compactly.

    python -u artifacts/analysis/extract_search_results.py <artifact.jsonl> [...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def reassemble(path: Path) -> str:
    chunks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "chunk":
            chunks.append((obj.get("index", 0), obj.get("text", "")))
    chunks.sort(key=lambda c: c[0])
    return "".join(t for _, t in chunks)


def main() -> int:
    for arg in sys.argv[1:]:
        p = Path(arg)
        raw = reassemble(p)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"--- {p.name}: not JSON after reassembly "
                  f"({len(raw)} chars), showing head ---")
            print(raw[:1500])
            continue
        results = data.get("results") or []
        print(f"--- {p.name}: {len(results)} results ---")
        for i, r in enumerate(results, 1):
            title = (r.get("title") or "").strip()
            link = (r.get("link") or "").strip()
            source = (r.get("source") or "").strip()
            print(f"[{i}] {title}")
            print(f"    {source}  {link}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
