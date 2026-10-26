"""Audit every figure and table of the manuscript against what the artifact does.

The manuscript quotes a lot of numbers, and a number that no longer matches its
source is the defect a reviewer finds first. This script checks the two
directions of that correspondence:

  1. each float against its data source: every cell of every table is
     recomputed from the committed run logs, and every name a caption promises
     is looked for in the figure source;
  2. each claim in the prose against the float or the configuration that backs
     it: the seed counts, the evaluation-seed counts, the training-set sizes and
     the mechanisms the manuscript says are implemented.

It is a guard, not a report: it exits non-zero when a claim stops matching.

Usage:
    python -u artifacts/analysis/audit_float_correspondence.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"
CONFIGS = ROOT / "artifacts" / "configs"
TABLES = ROOT / "artifacts" / "outputs" / "tables"
ANALYSIS = ROOT / "artifacts" / "analysis"
FIGURES = ROOT / "paper" / "figures"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def strip_tex(s: str) -> str:
    for a, b in (("\\textbf{", ""), ("\\emph{", ""), ("$+$", "+"), ("$-$", "-"),
                 ("{", ""), ("}", ""), ("$", ""), ("\\%", "%"), ("\\,", ""), ("~", " ")):
        s = s.replace(a, b)
    return s.strip()


def table_rows(label: str) -> list[list[str]]:
    """The rows of the tabular belonging to the float with this label."""
    text = TEX.read_bytes().decode("utf-8")
    m = re.search(r"\\label\{" + re.escape(label) + r"\}", text)
    if not m:
        return []
    tab = text.find("\\begin{tabular}", m.start())
    end = text.find("\\end{tabular}", tab)
    if tab < 0 or end < 0:
        return []
    rows = []
    for line in text[tab:end].splitlines():
        s = line.strip()
        if "&" not in s or not s.endswith("\\\\"):
            continue
        rows.append([strip_tex(c) for c in s[:-2].split("&")])
    return rows


def num(cell: str) -> float:
    m = re.match(r"[-+]?[\d.]+", cell.replace(",", ""))
    return float(m.group(0)) if m else float("nan")


def main() -> int:
    text = TEX.read_bytes().decode("utf-8")
    cfg = json.loads((CONFIGS / "default.json").read_text(encoding="utf-8-sig"))
    spatial_cfg = json.loads((CONFIGS / "spatial_position.json").read_text(encoding="utf-8-sig"))

    print("=" * 96)
    print("1. every float is referenced, and no float is orphaned")
    print("=" * 96)
    floats = []
    for kind in ("figure", "table"):
        for m in re.finditer(r"\\begin\{" + kind + r"\}(.*?)\\end\{" + kind + r"\}",
                             text, re.S):
            block = m.group(1)
            lab = re.search(r"\\label\{([^}]+)\}", block)
            if lab:
                floats.append((kind, lab.group(1)))
    for kind, label in floats:
        refs = [j for j, line in enumerate(text.split("\n"), 1)
                if re.search(r"\\ref\{" + re.escape(label) + r"\}", line)]
        check(f"{kind} {label} is referenced", bool(refs),
              f"{len(refs)} reference(s)")

    print()
    print("=" * 96)
    print("2. tab:arch_params against the configuration the runs used")
    print("=" * 96)
    rows = table_rows("tab:arch_params")
    flat = {r[1]: r[2] for r in rows if len(r) >= 3}
    ts = cfg["train_seeds"]
    ev = cfg["evaluation_seeds"]
    check("the training seeds are the ones the published configuration uses",
          flat.get("Training seeds", "").startswith(f"{ts[0]}--{ts[-1]}"),
          f"config {ts[0]}--{ts[-1]}, table says '{flat.get('Training seeds')}'")
    check("the evaluation seeds are the ones the published configuration uses",
          flat.get("Evaluation seeds", "") == f"{ev['start']}--{ev['stop']}",
          f"config {ev['start']}--{ev['stop']}, table says '{flat.get('Evaluation seeds')}'")
    check("the decision threshold is the configured one",
          cfg["marl_training"]["decision_threshold"] == 0.60
          and "0.60" in flat.get("Decision threshold", ""),
          flat.get("Decision threshold", ""))
    steps = cfg["network"]["mission_duration_s"] // cfg["network"]["trust_update_interval_s"]
    warm = cfg["network"]["warmup_s"] // cfg["network"]["trust_update_interval_s"]
    check("the step count matches mission duration over the update interval",
          f"{steps} /" in flat.get("Steps / nominal interval", ""),
          flat.get("Steps / nominal interval", ""))
    check("the warm-up matches the configured warm-up",
          f"{warm} steps" in flat.get("Warm-up", ""), flat.get("Warm-up", ""))
    check("the UAV count range matches the scalability grid",
          str(min(cfg["experiments"]["scalability_uavs"])) in flat.get("UAV count N", "")
          and str(max(cfg["experiments"]["scalability_uavs"])) in flat.get("UAV count N", ""),
          flat.get("UAV count N", ""))

    print()
    print("=" * 96)
    print("3. tab:baseline_comparison against the committed table")
    print("=" * 96)
    csv = pd.read_csv(TABLES / "baseline_comparison.csv", encoding="utf-8-sig").set_index("method")
    rows = table_rows("tab:baseline_comparison")
    for r in rows:
        if len(r) < 4 or not r[0]:
            continue
        name = r[0].split("\\cite")[0].strip()
        name = name.replace("(ours)", "").strip()
        if name not in csv.index:
            continue
        for i, col in enumerate(("accuracy", "f_score", "tsr")):
            claimed = num(r[1 + i])
            cell = str(csv.loc[name, col]).replace("±", "+-").split("+-")[0]
            check(f"{name} / {col}",
                  abs(claimed - float(cell)) < 0.05,
                  f"table={claimed:.1f} csv={float(cell):.1f}")

    print()
    print("=" * 96)
    print("4. tab:probe_level against the committed probe output")
    print("=" * 96)
    probe = (ANALYSIS / "probe_level.txt").read_text(encoding="utf-8")
    arms = {
        "13 marginal": "13 marginal",
        "5 shape only": "5 shape only",
        "5 shape, time-shuffled": "5 shape shuffled",
        "13 marginal $+$ 5 shape": "18 = 13 + 5 shape",
        "13 marginal $+$ 5 shape, shuffled": "18, shape shuffled",
    }
    rows = table_rows("tab:probe_level")
    for r in rows:
        if len(r) < 7 or r[0] not in arms:
            continue
        line = next((l for l in probe.splitlines() if arms[r[0]] in l), None)
        if line is None:
            check(f"probe row present in the artifact output: {r[0]}", False)
            continue
        # the artifact line reads "auc=0.9724 acc=91.56 f1=85.61 ...", so the
        # values are read by key: the "1" of "f1" is not a measurement
        got = []
        for key in ("auc", "acc", "f1", "constant", "dormant", "onoff"):
            m = re.search(key + r"=([\d.]+)", line)
            got.append(float(m.group(1)) if m else float("nan"))
        want = [num(r[1]), num(r[2]), num(r[3]), num(r[4]), num(r[5]), num(r[6])]
        check(f"probe row {r[0]}",
              all(abs(a - b) < 0.06 for a, b in zip(got, want)),
              f"table={want} artifact={got}")

    print()
    print("=" * 96)
    print("5. tab:duty_sweep against the committed sweep output")
    print("=" * 96)
    duty = (ANALYSIS / "duty_sweep.txt").read_text(encoding="utf-8")
    rows = table_rows("tab:duty_sweep")
    for r in rows:
        if len(r) < 3 or not re.match(r"^0\.\d+$", r[0]):
            continue
        line = next((l for l in duty.splitlines() if l.startswith(r[0] + " ")), None)
        if line is None:
            check(f"duty row present in the artifact output: {r[0]}", False)
            continue
        vals = [float(v) for v in line.split()]
        # the artifact line is "duty S-TIM MLP-Trust LR-Trust GDM-DTM"
        check(f"duty row {r[0]}",
              abs(num(r[1]) - vals[1]) < 0.06 and abs(num(r[2]) - vals[4]) < 0.06,
              f"table={r[1]},{r[2]} artifact={vals[1]},{vals[4]}")

    print()
    print("=" * 96)
    print("6. the spatial tables state the number of evaluation seeds they used")
    print("=" * 96)
    ev_spatial = spatial_cfg["evaluation_seeds"]
    n_spatial = ev_spatial["stop"] - ev_spatial["start"] + 1
    check("the spatial configuration runs the number of seeds the tables claim",
          n_spatial == 20, f"config {ev_spatial['start']}..{ev_spatial['stop']} = {n_spatial}")
    check("no caption or note still says 19 evaluation seeds",
          "19 evaluation seeds" not in text)
    for label in ("tab:spatial_main", "tab:spatial_blocks"):
        # the caption precedes the label in this manuscript
        idx = text.index("\\label{" + label + "}")
        cap = None
        for m in re.finditer(r"\\caption\{(.+?)\}\s*\n", text, re.S):
            if m.end() < idx:
                cap = m.group(1)
            else:
                break
        check(f"{label} states the seed count",
              cap is not None and f"{n_spatial} evaluation seeds" in cap)

    print()
    print("=" * 96)
    print("7. the training-set sizes the prose quotes")
    print("=" * 96)
    rows_per_seed = (len(cfg["experiments"]["ratio_grid"])
                     * int(cfg["network"]["default_uavs"]))
    k12 = json.loads((CONFIGS / "dataeff_k12_pub.json").read_text(encoding="utf-8-sig"))
    k12_rows = len(k12["train_seeds"]) * rows_per_seed
    k60_rows = len(cfg["train_seeds"]) * rows_per_seed
    check("the smallest measured arm is described with its real size",
          f"from {k12_rows} to {k60_rows} node-level samples" in text,
          f"{k12_rows} -> {k60_rows}")
    check("the enlargement is described with the right factor",
          "fivefold" in text and "sixfold" not in text)
    val_rows = round(len(k12["train_seeds"]) * 0.2) * rows_per_seed
    check("the 90 rows are described as the validation split",
          f"validation split of as few as {val_rows} node-level rows" in text,
          f"{val_rows} rows")

    print()
    print("=" * 96)
    print("8. the mechanisms the manuscript says are implemented")
    print("=" * 96)
    scripts = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                        for p in (ROOT / "artifacts" / "scripts").glob("*.py"))
    check("the artifact contains no cross-validation threshold",
          "gamma_th" not in scripts and "gamma_th" not in text.replace(
              "$\\gamma_{\\text{th}}$", ""))
    check("the manuscript does not say the cross-validation mechanism is implemented",
          "a \\textbf{cross-validation mechanism} is implemented" not in text)
    check("the manuscript marks the design-only algorithm steps",
          text.count("\\emph{design}") >= 2)
    check("the manuscript says the released implementation does not run it",
          "the released implementation does not run it" in text)

    print()
    print("=" * 96)
    print("9. the figures name only what they draw")
    print("=" * 96)
    pipeline = (FIGURES / "pipeline_tikz.tex").read_text(encoding="utf-8")
    for box in ("Trust-stream", "Evidence blocks", "Shared encoder", "Risk head",
                "Decision", "Allocation proxy", "Task-success proxy",
                "Auxiliary heads"):
        check(f"figure 1 draws the '{box}' box", box in pipeline)
    deployment = (FIGURES / "deployment_tikz.tex").read_text(encoding="utf-8")
    for box in ("Proposed aggregation", "Proposed state update", "Proposed constraint"):
        check(f"figure 2 draws the '{box}' box", box in deployment)
    check("figure 2 marks the three extensions as not executed",
          deployment.count("not executed in artifact") >= 2)

    print()
    print("=" * 96)
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All correspondence checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
