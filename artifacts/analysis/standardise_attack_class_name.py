"""Standardise the intermittent attack class name.

The class is written `on--off` (an en dash) in most of the manuscript and
`on-off` in five places. The bibliography is left alone, because the titles
of the cited papers spell it with a hyphen.

    python -u artifacts/analysis/standardise_attack_class_name.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"


def main() -> int:
    raw = TEX.read_text(encoding="utf-8")
    body, sep, bib = raw.partition("\\begin{thebibliography}")
    if not sep:
        print("!! the bibliography marker was not found")
        return 2

    n = body.count("on-off")
    body = body.replace("on-off", "on--off")

    TEX.write_text(body + sep + bib, encoding="utf-8")
    print(f"  rewrote {n} occurrence(s) of the class name in the body")
    print("  bibliography left untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
