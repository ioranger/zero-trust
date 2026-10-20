"""Find the page on which a phrase appears in the built PDF.

Pure-stdlib: the PDF content streams are Flate-compressed, so they are
inflated and searched for the text-showing operators.

    python -u artifacts/analysis/pdf_find_page.py "Modality ladder" <pdf>
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path


def page_streams(data: bytes) -> list[bytes]:
    out = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            out.append(zlib.decompress(raw))
        except zlib.error:
            out.append(raw)
    return out


def main() -> int:
    phrase = sys.argv[1].encode("latin-1", "replace")
    pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        r"F:\zero trust\zero-trust\paper\template.pdf")
    data = pdf.read_bytes()

    # Map object number -> stream bytes so pages can be attributed.
    objects = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, flags=re.S):
        num = int(m.group(1))
        body = m.group(2)
        sm = re.search(rb"stream\r?\n", body)
        if not sm:
            continue
        end = body.find(b"endstream", sm.end())
        if end < 0:
            continue
        raw = body[sm.end():end]
        try:
            objects[num] = zlib.decompress(raw)
        except zlib.error:
            objects[num] = raw

    pages = re.findall(rb"/Type\s*/Page[^s].*?/Contents\s+(\d+)\s+0\s+R", data, flags=re.S)
    if not pages:
        pages = re.findall(rb"/Contents\s+\[?\s*(\d+)\s+0\s+R", data)

    print(f"pages found: {len(pages)}")
    for i, pnum in enumerate(pages, 1):
        body = objects.get(int(pnum), b"")
        # Text in a content stream appears inside ( ) show operators.
        text = b" ".join(re.findall(rb"\((?:\\.|[^\\()])*\)", body))
        text = text.replace(b"(", b"").replace(b")", b"")
        if phrase in text:
            print(f"  HIT page {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
