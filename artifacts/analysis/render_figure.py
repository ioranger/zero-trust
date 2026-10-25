"""Rasterise a standalone TikZ figure into the PNG that the manuscript includes.

The MDPI class does not load TikZ, so the figures are shipped as rasterised
PNGs. This script compiles the standalone wrapper with the portable MiKTeX
pdflatex and converts the resulting PDF with PyMuPDF. The raster width is
pinned to the width of the PNG that is being replaced, so a re-render does not
change the size of the figure on the page.

Usage:
    python -u artifacts/analysis/render_figure.py deployment
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import fitz

FIGDIR = Path(r"F:\zero trust\zero-trust\paper\figures")
PDFLATEX = Path(r"F:\zero trust\tools\miktex\texmfs\install\miktex\bin\x64\pdflatex.exe")


def render(name: str) -> int:
    tex = FIGDIR / f"{name}_standalone.tex"
    pdf = FIGDIR / f"{name}_standalone.pdf"
    png = FIGDIR / f"{name}.png"
    if not tex.exists():
        print(f"[FAIL] missing {tex}")
        return 1

    # the width of the PNG that is being replaced, so the layout on the page
    # does not move
    target_width = fitz.Pixmap(str(png)).width if png.exists() else 0

    proc = subprocess.run(
        [str(PDFLATEX), "-interaction=nonstopmode", "-file-line-error", tex.name],
        cwd=str(FIGDIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not pdf.exists():
        print("[FAIL] pdflatex failed")
        print(proc.stdout[-2000:])
        return 1

    doc = fitz.open(str(pdf))
    page = doc[0]
    zoom = target_width / page.rect.width if target_width else 2.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(str(png))
    print(f"[OK] {png.name}: {pix.width}x{pix.height} (zoom {zoom:.3f}, target width {target_width})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(render(sys.argv[1]))
