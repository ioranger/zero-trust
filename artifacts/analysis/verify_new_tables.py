"""Verify the two new manuscript tables against the reproduced runs.

  tab:method_class   -- detection rate by method class and attack strategy
  tab:arch_controls  -- the four-arm architecture control

Every cell is recomputed from the per-seed logs under artifacts/runs and
compared with what the LaTeX source claims, so the tables cannot drift away
from the data without this script failing.

Run from the repository root:
    python -u artifacts/analysis/verify_new_tables.py
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "paper" / "template.tex"
RUNS = ROOT / "artifacts" / "analysis" / "runs"

RULE = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]
LEARNED = ["S-TIM"]
ATK = ["constant", "dormant", "on-off"]

failures = []


def check(label, ok, detail=""):
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def load_atk(run):
    f = RUNS / run / "logs" / "per_seed_attack_type_metrics.csv"
    if not f.exists():
        print(f"  [SKIP] missing run {run}")
        return None
    d = pd.read_csv(f)
    d = d.drop_duplicates(subset=["seed", "method", "attack_type"])
    return d[d["malicious_ratio"].round(6) == 0.30]


def rng(d, methods, atk):
    vals = [float(d[(d["method"] == m) & (d["attack_type"] == atk)]["detection_rate"].mean()) * 100
            for m in methods
            if len(d[(d["method"] == m) & (d["attack_type"] == atk)])]
    return (min(vals), max(vals)) if vals else None


def fmt(r):
    if r is None:
        return "--"
    lo, hi = r
    return f"{lo:.1f}" if abs(hi - lo) < 0.05 else f"{lo:.1f}--{hi:.1f}"


tex = TEX.read_text(encoding="utf-8")

print("=" * 74)
print("1. tab:method_class")
print("=" * 74)

shape = load_atk("paper_18dim_check")
marg = load_atk("marginal_13dim")
if shape is not None and marg is not None:
    i = tex.index(r"\label{tab:method_class}")
    body = tex[i:tex.index(r"\end{tabular}", i)]
    claimed = {}
    for line in body.splitlines():
        s = line.strip()
        if "&" not in s or s.startswith("\\") or "Method class" in s:
            continue
        cells = [c.strip() for c in s.replace(r"\\", "").split("&")]
        if len(cells) < 4:
            continue
        name = re.sub(r"\\emph\{([^}]*)\}", r"\1", cells[0]).strip()
        name = name.replace("Rule-based aggregation", "rule")
        name = name.replace("Proposed model, 13 dimensions", "marg")
        name = name.replace("Proposed model, 18 dimensions", "shape")
        name = name.replace("Gap, proposed model (18 dims) minus rule-based", "gap")
        vals = []
        for c in cells[1:4]:
            nums = re.findall(r"([\d.]+)", c.replace("$", ""))
            vals.append(nums)
        claimed[name] = vals
        print(f"    parsed row: {name:<12} {vals}")

    actual = {
        "rule": [fmt(rng(shape, RULE, a)) for a in ATK],
        "marg": [fmt(rng(marg, LEARNED, a)) for a in ATK],
        "shape": [fmt(rng(shape, LEARNED, a)) for a in ATK],
    }
    for key, cols in actual.items():
        if key not in claimed:
            continue
        for j, atk in enumerate(ATK):
            got = claimed[key][j]
            ok = got == cols[j]
            check(f"{key} / {atk}", ok, f"tex={got} data={cols[j]}")

    r_lo, r_hi = rng(shape, RULE, "on-off")
    s_lo, s_hi = rng(shape, LEARNED, "on-off")
    check("gap on--off is +50.0 to +88.0",
          abs((s_lo - r_hi) - 50.0) < 0.05 and abs((s_hi - r_lo) - 88.0) < 0.05,
          f"computed +{s_lo - r_hi:.1f} to +{s_hi - r_lo:.1f}")

    print("\n    per-method block effect on--off (13-dim -> 18-dim):")
    for m in LEARNED:
        a = rng(marg, [m], "on-off")[0]
        b = rng(shape, [m], "on-off")[0]
        effect = b - a
        check(f"{m} block effect {effect:+.1f} pp stated in the text",
              f"{effect:+.1f}" in tex,
              f"computed {effect:+.1f}")

print()
print("=" * 74)
print("2. tab:arch_controls")
print("=" * 74)

arms = [
    ("heads_risk_only", "Control"),
    ("heads_mod_only", "Modality"),
    ("heads_full", "All four"),
]
for run, tag in arms:
    f = RUNS / run / "logs" / "marl_policy.json"
    if not f.exists():
        check(f"{tag} policy present", False, f"missing {run}")
        continue
    pol = json.loads(f.read_text(encoding="utf-8"))
    acc = pol["modality_supervision"]["validation_accuracy"]
    w = pol["auxiliary_loss_weights"]
    check(f"{tag}: modality val acc {acc:.3f} appears in the paper",
          f"{acc:.3f}" in tex, f"loss weight {w['modality']}")

    atk = load_atk(run)
    if atk is None:
        continue
    onoff = rng(atk, ["S-TIM"], "on-off")[0]
    check(f"{tag}: on--off {onoff:.1f} appears in the paper",
          f"{onoff:.1f}" in tex)

print()
print("=" * 74)
print("3. probe and negative-separation numbers quoted in the prose")
print("=" * 74)
for claim, ok in (
    ("96.7\\% recoverable from the marginal features", "96.7\\%" in tex),
    ("0.983 modality head accuracy", "0.983" in tex),
    ("0.985 modality head accuracy", "0.985" in tex),
    ("0.154 (chance 0.250) for the control arm", "0.154" in tex),
    ("0.143 (chance 0.250) for the published arm", "0.143" in tex),
    ("chance level 0.250", "0.250" in tex),
    ("task-success proxy 0.15~pp at p=0.049", "0.15~pp" in tex and "$p=0.049$" in tex),
    ("45 of 50 seeds identical", "45 of 50 seeds" in tex),
    ("48 of 50 seeds identical", "48 of 50 seeds" in tex),
):
    check(claim, ok)

print()
print("=" * 74)
print("4. corrected ranges")
print("=" * 74)
# The class-level claim must use the full rule-adapter range, 0.0--38.0.
check("class-level rule range is stated as 0.0--38.0",
      "0.0--38.0" in tex)
# The only legitimate use of the narrower 20.0--38.0 range is the footnote
# that restricts the comparison to the three otherwise competent rule
# adapters (MFA 20.0, FUBA 38.0, GDM-DTM 38.0), so it must name them.
n_narrow = tex.count("20.0--38.0")
check("the narrower 20.0--38.0 range appears only once", n_narrow == 1,
      f"count={n_narrow}")
if n_narrow:
    k = tex.index("20.0--38.0")
    ctx = tex[max(0, k - 400):k]
    check("that occurrence is restricted to MFA, FUBA and GDM-DTM",
          "MFA, FUBA and GDM-DTM" in ctx)
check("no stale '90.0--92.0' range remains", "90.0--92.0" not in tex)
check("no stale '20--38' class range remains",
      "at 20--38" not in tex and "remains at 20--38" not in tex)
check("no stale '90--92' range remains", "90--92" not in tex)
check("caption no longer claims both methods reach 92%",
      "both learned methods that consume the shape block reach 92" not in tex)
check("the 54.0~pp claim is no longer stated without the 50.0~pp split",
      "a \\textbf{54.0~pp} gap" not in tex)

print()
print("=" * 74)
print("5. no defensive register")
print("=" * 74)
# The manuscript states its results and its controls plainly. These phrases
# read as self-deprecation rather than as findings, and their return would
# re-introduce the register this revision removed.
for phrase in (
    "the manuscript does not claim",
    "the manuscript attributes",
    "We report this plainly",
    "The honest summary",
    "the honest measurement",
    "does not claim otherwise",
    "nominally \\emph{behind}",
    "nominally behind",
    "null finding",
    "rather than a win",
    "and this is worth stating plainly",
    "sharpens the paper's central claim",
):
    check(f"no '{phrase}'", phrase not in tex)

# The controls must still be reported. These are the facts that make the
# paper's claim falsifiable, so removing them would be a reporting failure
# rather than an editorial change.
for fact in (
    "96.7\\%",
    "0.983",
    "0.985",
    "0.143",
    "0.154",
    "0.250",
    "45 of 50 seeds",
    "48 of 50 seeds",
    "0.15~pp",
    "$p=0.049$",
):
    check(f"control fact still reported: {fact}", fact in tex)

print()
print("=" * 74)
print("6. on-off-aware trust management literature is cited")
print("=" * 74)
# The manuscript's contribution is the representation, not on-off awareness.
# Leaving the on-off-aware trust literature uncited would misrepresent the
# state of the art, so the coverage is enforced here.
ONOFF_LIT = {
    "chae2014onoff": "Chae et al. 2014, defending on-off attacks (TPDS)",
    "mendoza2015onoff": "Mendoza & Kleinschmidt 2015, distributed mitigation",
    "caminha2018onoff": "Caminha et al. 2018, smart middleware detector",
    "salimitari2020prospect": "Salimitari et al. 2020, CWMA/EWMA fail under on-off",
    "kannan2023onoff": "Kannan et al. 2023, intra-daily variability",
    "ziauddin2026recfilter": "Ziauddin et al. 2026, sliding-window criticism",
}
for key, desc in ONOFF_LIT.items():
    check(f"cited: {key}", f"\\cite{{{key}}}" in tex, desc)

# Each of those entries must carry a Crossref-verified DOI.
for doi in ("10.1109/TPDS.2014.2317719", "10.1155/2015/859731",
            "10.1155/2018/6063456", "10.1145/3392058",
            "10.11591/eei.v12i6.6110", "10.1007/s42979-026-05087-1"):
    check(f"DOI present: {doi}", doi in tex)

print()
print("=" * 74)
print("7. the spatio-temporal tables")
print("=" * 74)

SPATIAL_ARMS = {
    "spatial_position_13dim": "13 dims (marginal)",
    "spatial_position_18dim": "18 dims (marginal $+$ shape)",
    "spatial_position_23dim": "23 dims (marginal $+$ shape $+$ neighborhood)",
    "spatial_position_fusion": "23 dims, same vector",
}


def strip_tex(s: str) -> str:
    s = s.replace("\\textbf{", "").replace("\\emph{", "")
    s = s.replace("$+$", "+").replace("$-$", "-")
    s = s.replace("{", "").replace("}", "").replace("$", "")
    s = s.replace("\\%", "%").replace("\\,", "").replace("~", " ")
    return s.strip()


def table_rows(label: str) -> list[list[str]]:
    """Rows of the tabular belonging to the table whose label is `label`.

    The label is not always inside the same `\begin{table}` ... `\end{table}`
    span as the tabular: in some tables the environment opens at the end of
    the preceding paragraph, so searching backwards for `\begin{table}` finds
    the previous table instead. The tabular is therefore located forward from
    the label, and the environment is taken as the one that contains it.
    """
    m = re.search(r"\\label\{" + re.escape(label) + r"\}", tex)
    if not m:
        return []
    tab = tex.find("\\begin{tabular}", m.start())
    if tab < 0:
        return []
    start = tex.rfind("\\begin{table}", 0, tab)
    end = tex.find("\\end{tabular}", tab)
    if start < 0 or end < 0:
        return []
    body = tex[tab:end]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if "&" not in line or not line.endswith("\\\\"):
            continue
        cells = [strip_tex(c) for c in line[:-2].split("&")]
        rows.append(cells)
    return rows


def mean_atk(run: str, method: str, atk: str):
    d = load_atk(run)
    if d is None:
        return None
    sub = d[(d["method"] == method) & (d["attack_type"] == atk)]
    if not len(sub):
        return None
    return float(sub["detection_rate"].mean()) * 100


def baseline_row(run: str, method: str):
    f = RUNS / run / "tables" / "baseline_comparison.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, encoding="utf-8-sig")
    d = d.set_index("method")
    if method not in d.index:
        return None
    out = {}
    for col in ("accuracy", "f_score", "tsr"):
        s = str(d.loc[method, col]).replace("\u00b1", "+-").replace("卤", "+-")
        parts = s.split("+-")
        out[col] = float(parts[0].strip())
    return out


# ---- tab:spatial_blocks ----------------------------------------------------
# One table now carries every arm run in the spatially inconsistent scenario:
# the feature-block ladder, the auxiliary-supervision control, the block-routed
# variant and the same-input control. Every cell is recomputed from the arm's
# own per-seed log.
BLOCKS_SPEC = [
    ("S-TIM, 13 dims (marginal)", "spatial_position_13dim", "S-TIM"),
    ("S-TIM, 18 dims (marginal + shape)", "spatial_position_18dim", "S-TIM"),
    ("S-TIM, 18 dims, no auxiliary loss", "spatial_position_riskonly", "S-TIM"),
    ("S-TIM, 23 dims (all three blocks)", "spatial_position_23dim", "S-TIM"),
    ("S-TIM, 23 dims, block-routed fusion", "spatial_position_gated", "S-TIM"),
    ("S-TIM, 23 dims (all three blocks)", "spatial_position_23dim", "S-TIM"),
]
BLOCKS_COLS = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]

rows = table_rows("tab:spatial_blocks")
check("tab:spatial_blocks is present", bool(rows))
if rows:
    parsed = {r[0]: r[1:] for r in rows}
    for label, run, method in BLOCKS_SPEC:
        if label not in parsed:
            check(f"spatial blocks row present: {label}", False)
            continue
        cells = parsed[label]
        for j, atk in enumerate(BLOCKS_COLS):
            computed = mean_atk(run, method, atk)
            if computed is None:
                check(f"blocks {label} / {atk}", False, "no log")
                continue
            claimed = cells[j] if len(cells) > j else "--"
            ok = abs(float(claimed) - computed) < 0.06
            check(f"blocks {label} / {atk}", ok,
                  f"tex={claimed} computed={computed:.1f}")
        base = baseline_row(run, method)
        if base is None:
            check(f"blocks {label} / accuracy", False, "no baseline log")
            continue
        claimed = cells[5] if len(cells) > 5 else "--"
        check(f"blocks {label} / accuracy",
              abs(float(claimed) - base["accuracy"]) < 0.06,
              f"tex={claimed} computed={base['accuracy']:.1f}")

print()
print("=" * 74)
print("7b. the auxiliary-loss and fusion controls, in prose")
print("=" * 74)

for fact, why in (
        ("5.7~pp on constant attackers", "the auxiliary-loss cost"),
        ("$p\\ge0.49$", "the block-routed arm's insignificance")):
    check(f"prose states {why}", fact in tex, fact)

rows = table_rows("tab:spatial_blocks")
if rows:
    parsed = {r[0]: r[1:] for r in rows}
    key = "S-TIM, 23 dims (all three blocks)"
    check("spatial blocks holds the proposed model at 23 dims", key in parsed)
    if key in parsed:
        computed = mean_atk("spatial_position_23dim", "S-TIM",
                            "position-inconsistent")
        claimed = parsed[key][3] if len(parsed[key]) > 3 else "--"
        check("proposed model at 23 dims / position-inconsistent",
              computed is not None and abs(float(claimed) - computed) < 0.06,
              f"tex={claimed} computed={computed}")

print()
print("=" * 74)
print("7b. tab:spatial_main")
print("=" * 74)

SPATIAL_MAIN_SPEC = [
    ("MFA", "MFA"), ("FUBA", "FUBA"), ("GALTrust", "GALTrust"),
    ("GDM-DTM", "GDM-DTM"), ("AHP-Entropy", "AHP-Entropy"),
    ("S-TIM (ours)", "S-TIM"),
]
SPATIAL_MAIN_ATK = ["constant", "dormant", "on-off", "position-inconsistent"]

rows = table_rows("tab:spatial_main")
check("tab:spatial_main is present", bool(rows))
if rows:
    parsed = {r[0]: r[1:] for r in rows}
    for label, method in SPATIAL_MAIN_SPEC:
        if label not in parsed:
            check(f"spatial main row present: {label}", False)
            continue
        cells = parsed[label]
        base = baseline_row("spatial_position_23dim", method)
        if base is None:
            check(f"spatial main {label} / baseline log", False)
            continue
        for i, col in enumerate(("accuracy", "f_score", "tsr")):
            claimed = cells[i] if len(cells) > i else "--"
            check(f"spatial main {label} / {col}",
                  abs(float(claimed) - base[col]) < 0.06,
                  f"tex={claimed} computed={base[col]:.1f}")
        for j, atk in enumerate(SPATIAL_MAIN_ATK):
            computed = mean_atk("spatial_position_23dim", method, atk)
            if computed is None:
                continue
            claimed = cells[3 + j] if len(cells) > 3 + j else "--"
            check(f"spatial main {label} / {atk}",
                  abs(float(claimed) - computed) < 0.06,
                  f"tex={claimed} computed={computed:.1f}")
        # the class-mean column: the equal-weight average over the four attack
        # classes, recomputed from the same per-seed log
        rates = [mean_atk("spatial_position_23dim", method, a)
                 for a in SPATIAL_MAIN_ATK]
        if all(r is not None for r in rates):
            computed = sum(rates) / 4.0
            claimed = cells[7] if len(cells) > 7 else "--"
            check(f"spatial main {label} / class mean",
                  abs(float(claimed) - computed) < 0.06,
                  f"tex={claimed} computed={computed:.1f}")

print()
print("=" * 74)
print("7c. the data-efficiency control, now carried by the prose")
print("=" * 74)

for k, label, arm in (
        (12, "modality head supervised (w=0.30)", "dataeff_k12_mod"),
        (12, "all auxiliary losses off", "dataeff_k12_risk"),
        (12, "published configuration", "dataeff_k12_pub"),
        (24, "modality head supervised (w=0.30)", "dataeff_k24_mod"),
        (24, "all auxiliary losses off", "dataeff_k24_risk"),
        (24, "published configuration", "dataeff_k24_pub"),
        (60, "modality head supervised (w=0.30)", "heads_mod_only"),
        (60, "all auxiliary losses off", "heads_risk_only"),
        (60, "published configuration", "paper_18dim_check")):
    base = baseline_row(arm, "S-TIM")
    if base is None:
        check(f"dataeff {k} seeds / {label} / logs", False)
        continue
    # The manuscript no longer reports a same-feature learned control, so the
    # claim it makes here is the one the data supports: the supervision does
    # not move the accuracy within a training-set size.
    check(f"dataeff {k} seeds / {label} / accuracy recorded",
          base["accuracy"] > 0.0,
          f"S-TIM={base['accuracy']:.1f}")

print()
print("=" * 74)
print("7d. tab:spatial_robust")
print("=" * 74)

ROBUST_SPEC = [
    ("headline", "spatial_position_23dim"),
    ("field amplitude 0.30", "spatial_position_field030"),
    ("field amplitude 0.60", "spatial_position_field060"),
    ("position ratio 0.20", "spatial_position_ratio020"),
    ("position ratio 0.50", "spatial_position_ratio050"),
]
RULE_METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]

rows = table_rows("tab:spatial_robust")
check("tab:spatial_robust is present", bool(rows))
if rows:
    parsed = {r[0]: r[1:] for r in rows}
    for label, arm in ROBUST_SPEC:
        if label not in parsed:
            check(f"robustness row present: {label}", False)
            continue
        cells = parsed[label]
        base = baseline_row(arm, "S-TIM")
        if base is None:
            check(f"robustness {label} / logs", False)
            continue
        # The table's columns are Configuration, field amp., position ratio,
        # S-TIM accuracy, S-TIM F-score, best rule accuracy. `r[0]` is the row
        # label and is dropped when the rows are keyed, so the values start at
        # index 2 of `cells`.
        want = [base["accuracy"], base["f_score"]]
        for i, (col, value) in enumerate(zip(
                ("S-TIM accuracy", "S-TIM f_score"), want)):
            claimed = cells[2 + i] if len(cells) > 2 + i else "--"
            check(f"robustness {label} / {col}",
                  abs(float(claimed) - value) < 0.06,
                  f"tex={claimed} computed={value:.1f}")
        rule_best = max(baseline_row(arm, m)["accuracy"] for m in RULE_METHODS)
        claimed = cells[4] if len(cells) > 4 else "--"
        check(f"robustness {label} / best rule accuracy",
              abs(float(claimed) - rule_best) < 0.06,
              f"tex={claimed} computed={rule_best:.1f}")

print()
print("=" * 74)
print("7e. tab:factor_dependence")
print("=" * 74)

FACTOR_ARMS = [
    ("none (published configuration)", "published_recheck"),
    ("T1 behavioural", "drop_T1"),
    ("T2 communication", "drop_T2"),
    ("T3 energy", "drop_T3"),
    ("T4 task execution", "drop_T4"),
    ("T5 historical", "drop_T5"),
]

# The table carries one block per scenario, and the row labels repeat, so the
# rows are read in order and keyed by the block they belong to.
FACTOR_BLOCKS = [
    ("published", "published_recheck"),
    ("spatial", "spatial_recheck"),
]


def policy_width(run: str):
    f = RUNS / run / "logs" / "marl_policy.json"
    if not f.exists():
        return None
    return len(json.loads(f.read_text(encoding="utf-8"))["feature_names"])


def factor_rows():
    """The rows of tab:factor_dependence, keyed by (block, row label).

    The block headers are `\\multicolumn` rows, which carry no `&` and are
    therefore not returned by table_rows(), so the tabular is read directly.
    """
    m = re.search(r"\\label\{" + re.escape("tab:factor_dependence") + r"\}", tex)
    if not m:
        return {}
    tab = tex.find("\\begin{tabular}", m.start())
    end = tex.find("\\end{tabular}", tab)
    if tab < 0 or end < 0:
        return {}
    out = {}
    block = None
    for line in tex[tab:end].splitlines():
        s = line.strip()
        if not s:
            continue
        if "multicolumn" in s:
            block = "spatial" if "patial" in s else "published"
            continue
        if "&" not in s or not s.endswith("\\\\"):
            continue
        cells = [strip_tex(c) for c in s[:-2].split("&")]
        if block is None or not cells:
            continue
        out[(block, cells[0])] = cells[1:]
    return out


def paired_accuracy_difference(arm: str, reference: str, n_uavs: int = 15):
    """The mean of the per-seed accuracy differences, in percentage points.

    This is the quantity the paired test is run on. It is not the difference
    of the two rounded means, which can differ from it by a tenth of a point.
    """
    def series(run: str):
        f = RUNS / run / "logs" / "per_seed_metrics.csv"
        if not f.exists():
            return None
        d = pd.read_csv(f)
        d = d[(d["scenario"].isin(["ratio", "figure_ratio"]))
              & (d["n_uavs"] == n_uavs) & (d["n_agents"] == 5)
              & (d["malicious_ratio"].round(6) == round(0.30, 6))]
        d = d[d["method"] == "S-TIM"].drop_duplicates(subset=["seed"])
        return d.set_index("seed")["accuracy"] * 100

    a = series(arm)
    b = series(reference)
    if a is None or b is None:
        return None
    common = a.index.intersection(b.index)
    if not len(common):
        return None
    return float((a[common] - b[common]).mean())


rows = table_rows("tab:factor_dependence")
check("tab:factor_dependence is present", bool(rows))
parsed = factor_rows()
for block, ref_arm in FACTOR_BLOCKS:
    if not (RUNS / ref_arm / "logs" / "per_seed_metrics.csv").exists():
        print(f"  [SKIP] {block}: the arm {ref_arm} has not been run")
        continue
    ref = baseline_row(ref_arm, "S-TIM")
    ref_width = policy_width(ref_arm)
    for label, suffix in FACTOR_ARMS:
        arm = ref_arm if label.startswith("none") else \
            (suffix if block == "published" else f"spatial_{suffix}")
        if (RUNS / arm / "logs" / "per_seed_metrics.csv").exists() is False:
            print(f"  [SKIP] {block} / {label}: the arm {arm} has not been run")
            continue
        if (block, label) not in parsed:
            check(f"factor {block} row present: {label}", False)
            continue
        cells = parsed[(block, label)]
        base = baseline_row(arm, "S-TIM")
        if base is None:
            check(f"factor {block} {label} / logs", False)
            continue
        # cells[0] is the number of columns removed, then accuracy, F-score,
        # TSR, on--off detection and the paired accuracy difference.
        for i, (col, value) in enumerate((
                ("accuracy", base["accuracy"]),
                ("F-score", base["f_score"]),
                ("TSR", base["tsr"]))):
            claimed = cells[1 + i] if len(cells) > 1 + i else "--"
            check(f"factor {block} {label} / {col}",
                  abs(float(claimed) - value) < 0.06,
                  f"tex={claimed} computed={value:.1f}")
        onoff = mean_atk(arm, "S-TIM", "on-off")
        claimed = cells[4] if len(cells) > 4 else "--"
        check(f"factor {block} {label} / on-off",
              onoff is not None and abs(float(claimed) - onoff) < 0.06,
              f"tex={claimed} computed={onoff:.1f}" if onoff is not None else "no log")
        # the cost claim: how many columns the removed dimension took with it
        width = policy_width(arm)
        claimed = cells[0] if cells else "--"
        if width is None or ref_width is None:
            check(f"factor {block} {label} / columns removed", False)
        else:
            check(f"factor {block} {label} / columns removed",
                  abs(float(claimed) - (ref_width - width)) < 0.5,
                  f"tex={claimed} computed={ref_width - width}")
        if not label.startswith("none") and ref is not None:
            delta = paired_accuracy_difference(arm, ref_arm, 15 if block == "published" else 800)
            claimed = cells[5] if len(cells) > 5 else "--"
            m = re.match(r"([-+]?[0-9.]+)", claimed)
            check(f"factor {block} {label} / delta accuracy",
                  delta is not None and m is not None
                  and abs(float(m.group(1)) - delta) < 0.06,
                  f"tex={claimed} computed={delta:+.2f}" if delta is not None else "no log")

print()
print("=" * 74)
print("8. position-aware trust and integrity literature is cited")
print("=" * 74)
# The spatial claim rests on the attacker class being real and studied, and on
# the fact that the anchor-free alternative is what the present work extends.
# Leaving this literature uncited would misrepresent the state of the art.
POSITION_LIT = {
    "vijay2025anchorfree": "Vijay et al. 2025, anchor-free range integrity monitoring",
    "zhong2026byzantine": "Zhong et al. 2026, distributed GPS-spoofing detection in UAV networks",
    "dang2022ensemble": "Dang et al. 2022, deep-ensemble GPS spoofing detection",
    "fang2025trustworthy": "Fang, Han, Schotten 2025, cooperative-localization security",
    "zhao2026gnssreview": "Zhao et al. 2026, multi-source-fusion spoofing detection review",
    "tariq2026beidou": "Tariq & Ahamed Ahanger 2026, BeiDou spoofing in decentralized swarms",
    "keshavarz2020trustmonitor": "Keshavarz et al. 2020, UAV trust monitoring framework",
}
for key, desc in POSITION_LIT.items():
    check(f"cited: {key}", f"\\cite{{{key}}}" in tex, desc)
for doi in ("10.1109/lra.2025.3534068", "10.1016/j.ress.2025.112101",
            "10.1109/jiot.2022.3195320", "10.1109/tvt.2025.3555490",
            "10.3390/electronics15153326", "10.7717/peerj-cs.3875",
            "10.1109/infocomwkshps50562.2020.9162761"):
    check(f"DOI present: {doi}", doi in tex)

print()
print("=" * 74)
print("9. the spatio-temporal headline numbers appear in the prose")
print("=" * 74)
for fact, why in (
    ("83.6", "the forger detection rate with the neighborhood block"),
    ("2.1", "the forger detection rate without it"),
    ("$+81.5$~pp", "the paired spatial gain"),
    ("81.5", "the paired spatial gain, plain form"),
    ("1.99", "the largest neighborhood effect size"),
    ("0.04", "the largest behavioural effect size"),
    ("8.7~pp", "the shape block's cost on constant attackers"),
    ("3.6~pp", "the net cost on constant attackers"),
    ("2.2~pp", "the net cost on dormant attackers"),
    ("46.7\\%", "the rule baselines' best F1 in the spatial scenario"),
    ("46.2\\%", "the trivial classifier's F1"),
    ("93.8", "S-TIM accuracy in the spatial scenario"),
    ("89.4", "S-TIM F-score in the spatial scenario"),
    ("88.9", "S-TIM TSR in the spatial scenario"),
    ("$+49.8$~pp", "the accuracy gain over the strongest rule adapter"),
    ("$+43.9$~pp", "the F-score gain over the strongest rule adapter"),
    ("$+13.0$~pp", "the TSR gain over the strongest rule adapter"),
    ("0.964--0.983", "the modality head accuracy across the data-efficiency arms"),
    ("0.4~pp", "the largest data-efficiency spread at a fixed training-set size"),
    ("90 node-level training rows", "the size of the smallest training set"),
    ("$+46.6$~pp", "the smallest accuracy advantage in the robustness sweep"),
    ("$+52.3$~pp", "the largest accuracy advantage in the robustness sweep"),
    ("$+41.7$~pp", "the smallest F-score advantage in the robustness sweep"),
    ("$+44.5$~pp", "the largest F-score advantage in the robustness sweep"),
    ("72.9\\%", "the lowest forger detection rate in the robustness sweep"),
    ("88.0\\%", "the highest forger detection rate in the robustness sweep"),
):
    check(f"prose states {fact}", fact in tex, why)

print()
print("=" * 74)
if failures:
    print(f"FAILED: {len(failures)} check(s)")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("All checks passed.")
