"""Compare a run snapshot's baseline table against the committed (published) table.

Same logic as F:\\zero trust\\realdata\\compare_paper_table.py, but reads the
"fresh" table from a run-snapshot directory instead of artifacts/outputs, so it
can be run while another arm is still writing to artifacts/outputs.

Usage:
    python -u artifacts/analysis/compare_snapshot_to_published.py <snapshot_dir>
"""

import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
GIT = r"F:\zero trust\tools\MinGit\cmd\git.exe"
WT = Path(r"F:\zero trust\gitwork")

committed_txt = subprocess.run(
    [GIT, "-C", str(WT), "show", "HEAD:artifacts/outputs/tables/baseline_comparison.csv"],
    capture_output=True, text=True, encoding="utf-8", check=True).stdout


def parse(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    df = df.set_index("method")
    out = {}
    for m, row in df.iterrows():
        vals = {}
        for col in ("accuracy", "f_score", "tsr"):
            s = str(row[col]).replace("\u00b1", "+-").replace("卤", "+-")
            parts = s.split("+-")
            vals[col] = (float(parts[0].strip()),
                         float(parts[1].strip()) if len(parts) > 1 else 0.0)
        out[m] = vals
    return out


def main() -> int:
    snap = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    fresh_path = (snap / "tables" / "baseline_comparison.csv") if snap else (
        ROOT / "artifacts" / "outputs" / "tables" / "baseline_comparison.csv")
    print(f"committed : {WT} HEAD:artifacts/outputs/tables/baseline_comparison.csv")
    print(f"fresh     : {fresh_path}")
    if not fresh_path.exists():
        print("MISSING fresh table")
        return 2

    fresh = fresh_path.read_text(encoding="utf-8-sig")
    old = parse(committed_txt)
    new = parse(fresh)

    print(f"\n{'method':<13}{'metric':<11}{'committed':>18}{'re-run':>18}   status")
    print("-" * 78)
    exact = 0
    total = 0
    mismatches = []
    for m in old:
        for col in ("accuracy", "f_score", "tsr"):
            total += 1
            o = old[m][col]
            n = new[m][col]
            same = abs(o[0] - n[0]) < 1e-9 and abs(o[1] - n[1]) < 1e-9
            exact += same
            flag = "exact" if same else f"DIFF mean{o[0]-n[0]:+.1f} sd{o[1]-n[1]:+.1f}"
            if not same:
                mismatches.append((m, col, o, n))
            print(f"{m:<13}{col:<11}{o[0]:>10.1f} +-{o[1]:<5.1f}"
                  f"{n[0]:>10.1f} +-{n[1]:<5.1f}   {flag}")

    print("-" * 78)
    print(f"exact matches: {exact}/{total}")
    if mismatches:
        print("\nmismatches:")
        for m, col, o, n in mismatches:
            print(f"  {m:<13}{col:<11} committed {o[0]:.1f}+-{o[1]:.1f}  "
                  f"re-run {n[0]:.1f}+-{n[1]:.1f}")
        return 1
    print("\nThe published table reproduces cell-for-cell under the fixed code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
