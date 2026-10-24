"""Check that every bold cell marks a column the proposed model actually
leads.

After the bold cells were moved onto the proposed model's own rows, the
emphasis must still be true: a bold cell may not sit in a column where
another row of the same table is higher, because that is the case the
reader would notice first.

Usage:
    python -u artifacts/analysis/check_bold_semantics.py
"""

from __future__ import annotations

import re
from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# table label -> the row that holds the proposed model's own configuration
OURS = {
    "tab:baseline_comparison": "S-TIM (ours)",
    "tab:method_class": "Proposed model, 18 dimensions",
    "tab:probe_level": "13 marginal $+$ 5 shape",
    "tab:duty_sweep": None,          # columns are methods, not rows
    "tab:spatial_main": "S-TIM (ours)",
    "tab:spatial_robust": None,      # rows are configurations of one method
    "tab:spatial_blocks": "S-TIM, 23 dims (all three blocks)",
    "tab:arch_controls": "Published",
}


def strip_tex(s: str) -> str:
    s = s.replace("\\textbf{", "").replace("\\emph{", "")
    s = s.replace("$+$", "+").replace("$-$", "-")
    s = s.replace("{", "").replace("}", "").replace("$", "")
    s = s.replace("\\%", "%").replace("\\,", "").replace("~", " ")
    s = s.replace("\\dots", "")
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    return s.strip()


def numbers(s: str):
    return [float(x) for x in re.findall(r"-?\d+\.\d+", s)]


def main() -> int:
    lines = TEX.read_text(encoding="utf-8").splitlines()
    problems = 0
    for s, line in enumerate(lines):
        if "\\begin{table}" not in line:
            continue
        j = s
        while j < len(lines) and "\\end{table}" not in lines[j]:
            j += 1
        block = lines[s:j + 1]
        m = re.search(r"\\label\{(tab:[^}]+)\}", "\n".join(block))
        label = m.group(1) if m else ""
        rows = []
        for l in block:
            t = l.strip()
            if "&" in t and t.endswith("\\" * 2):
                body = t[:-2]
                raw = body.split("&")
                cells = [strip_tex(c) for c in raw]
                bold = ["\\textbf" in c for c in raw]
                rows.append((t, cells, bold))
        ours = OURS.get(label)
        if ours is None:
            print(f"{label}: (rows are not methods; bolding checked by hand)")
            continue
        our_cells = next((c for _t, c, _b in rows
                          if c[0].startswith(ours)), None)
        if our_cells is None:
            print(f"{label}: proposed-model row {ours!r} not found")
            problems += 1
            continue
        print(f"{label}:")
        for t, cells, bold in rows:
            for idx, cell in enumerate(cells):
                if not bold[idx]:
                    continue
                col_vals = []
                for _t2, c2, _b2 in rows:
                    if idx < len(c2):
                        v = numbers(c2[idx])
                        if v:
                            col_vals.append((v[0], c2[0]))
                if not col_vals:
                    continue
                top = max(col_vals)
                our_v = numbers(our_cells[idx]) if idx < len(our_cells) else []
                our_v = our_v[0] if our_v else None
                if our_v is None:
                    print(f"    col {idx} {cell!r}: not a plain number")
                    continue
                if top[1].startswith(ours) and abs(top[0] - our_v) < 1e-6:
                    print(f"    col {idx} {cell!r}: OK, the proposed model leads")
                else:
                    print(f"    col {idx} {cell!r}: NOT the column best "
                          f"({top[1]} = {top[0]}, ours = {our_v})")
                    problems += 1
        print()
    print(f"problems: {problems}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
