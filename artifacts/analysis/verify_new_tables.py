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
LEARNED = ["LR-Trust", "MLP-Trust", "S-TIM"]
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
        name = name.replace("Learned, marginal block only", "marg")
        name = name.replace("Learned, shape-aware", "shape")
        name = name.replace("Gap, shape-aware minus rule-based", "gap")
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
    check("gap on--off is +50.0 to +92.0",
          abs((s_lo - r_hi) - 50.0) < 0.05 and abs((s_hi - r_lo) - 92.0) < 0.05,
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
    ("task-success proxy 0.22~pp at p=0.021", "0.22~pp" in tex and "$p=0.021$" in tex),
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
    "0.22~pp",
    "$p=0.021$",
    "$p=0.049$",
    "86.0\\%",
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
    """Rows of the tabular inside the table whose label is `label`."""
    m = re.search(r"\\label\{" + re.escape(label) + r"\}", tex)
    if not m:
        return []
    start = tex.rfind("\\begin{table}", 0, m.start())
    end = tex.find("\\end{table}", m.start())
    block = tex[start:end]
    body = block[block.find("\\begin{tabular}"):]
    body = body[:body.find("\\end{tabular}")]
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


# ---- tab:modality_ladder -------------------------------------------------
LADDER_SPEC = [
    ("S-TIM, 13 dims (marginal)", "spatial_position_13dim", "S-TIM"),
    ("S-TIM, 18 dims (marginal + shape)", "spatial_position_18dim", "S-TIM"),
    ("S-TIM, 23 dims (marginal + shape + neighborhood)",
     "spatial_position_23dim", "S-TIM"),
    ("LR-Trust, 18 dims (per-node)", "spatial_position_23dim", "LR-Trust"),
    ("MLP-Trust, 18 dims (per-node)", "spatial_position_23dim", "MLP-Trust"),
]
LADDER_COLS = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]

rows = table_rows("tab:modality_ladder")
check("tab:modality_ladder is present", bool(rows))
if rows:
    parsed = {r[0]: r[1:] for r in rows}
    for label, run, method in LADDER_SPEC:
        if label not in parsed:
            check(f"modality ladder row present: {label}", False)
            continue
        cells = parsed[label]
        for i, atk in enumerate(LADDER_COLS):
            claimed = cells[i] if i < len(cells) else "--"
            computed = mean_atk(run, method, atk)
            if computed is None:
                check(f"ladder {label} / {atk}", False, "no log")
                continue
            ok = abs(float(claimed) - computed) < 0.06
            check(f"ladder {label} / {atk}", ok,
                  f"tex={claimed} computed={computed:.1f}")

# ---- tab:fusion_mechanism -------------------------------------------------
FUSION_SPEC = [
    ("LR-Trust (linear)", "18 dims, per-node",
     "spatial_position_23dim", "LR-Trust"),
    ("MLP-Trust (single MLP)", "18 dims, per-node",
     "spatial_position_23dim", "MLP-Trust"),
    ("LR-Trust (linear)", "23 dims, same vector",
     "spatial_position_fusion", "LR-Trust"),
    ("MLP-Trust (single MLP)", "23 dims, same vector",
     "spatial_position_fusion", "MLP-Trust"),
    ("S-TIM (multi-head)", "23 dims, same vector",
     "spatial_position_fusion", "S-TIM"),
]

rows = table_rows("tab:fusion_mechanism")
check("tab:fusion_mechanism is present", bool(rows))
if rows:
    parsed = {(r[0], r[1]): r[2:] for r in rows}
    for learner, inp, run, method in FUSION_SPEC:
        key = (learner, inp)
        if key not in parsed:
            check(f"fusion row present: {learner} / {inp}", False)
            continue
        cells = parsed[key]
        pos = mean_atk(run, method, "position-inconsistent")
        const = mean_atk(run, method, "constant")
        base = baseline_row(run, method)
        claimed_pos = cells[0] if len(cells) > 0 else "--"
        claimed_const = cells[1] if len(cells) > 1 else "--"
        if pos is not None:
            check(f"fusion {learner} / {inp} / position-inconsistent",
                  abs(float(claimed_pos) - pos) < 0.06,
                  f"tex={claimed_pos} computed={pos:.1f}")
        if const is not None:
            check(f"fusion {learner} / {inp} / constant",
                  abs(float(claimed_const) - const) < 0.06,
                  f"tex={claimed_const} computed={const:.1f}")
        if base is not None:
            for i, col in enumerate(("accuracy", "f_score", "tsr")):
                claimed = cells[2 + i] if len(cells) > 2 + i else "--"
                check(f"fusion {learner} / {inp} / {col}",
                      abs(float(claimed) - base[col]) < 0.06,
                      f"tex={claimed} computed={base[col]:.1f}")

print()
print("=" * 74)
print("7b. tab:spatial_main")
print("=" * 74)

SPATIAL_MAIN_SPEC = [
    ("MFA", "MFA"), ("FUBA", "FUBA"), ("GALTrust", "GALTrust"),
    ("GDM-DTM", "GDM-DTM"), ("AHP-Entropy", "AHP-Entropy"),
    ("LR-Trust", "LR-Trust"), ("MLP-Trust", "MLP-Trust"),
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

print()
print("=" * 74)
print("7c. tab:dataeff")
print("=" * 74)

DATAEFF_SPEC = [
    (12, "modality head supervised (w=0.30)", "dataeff_k12_mod"),
    (12, "all auxiliary losses off", "dataeff_k12_risk"),
    (12, "published configuration", "dataeff_k12_pub"),
    (24, "modality head supervised (w=0.30)", "dataeff_k24_mod"),
    (24, "all auxiliary losses off", "dataeff_k24_risk"),
    (24, "published configuration", "dataeff_k24_pub"),
    (60, "modality head supervised (w=0.30)", "heads_mod_only"),
    (60, "all auxiliary losses off", "heads_risk_only"),
    (60, "published configuration", "paper_18dim_check"),
]

rows = table_rows("tab:dataeff")
check("tab:dataeff is present", bool(rows))
if rows:
    parsed = {(r[0], r[1]): r[2:] for r in rows}
    for k, label, arm in DATAEFF_SPEC:
        key = (str(k), label)
        if key not in parsed:
            check(f"dataeff row present: {k} seeds / {label}", False)
            continue
        cells = parsed[key]
        base = baseline_row(arm, "S-TIM")
        ctrl = baseline_row(arm, "MLP-Trust")
        if base is None or ctrl is None:
            check(f"dataeff {k} / {label} / logs", False)
            continue
        for i, (col, src) in enumerate((("accuracy", base), ("f_score", base),
                                        ("accuracy", ctrl))):
            claimed = cells[i] if len(cells) > i else "--"
            check(f"dataeff {k} seeds / {label} / {'S-TIM' if i < 2 else 'MLP'} {col}",
                  abs(float(claimed) - src[col]) < 0.06,
                  f"tex={claimed} computed={src[col]:.1f}")
        pol = RUNS / arm / "logs" / "marl_policy.json"
        if pol.exists() and len(cells) > 5:
            p = json.loads(pol.read_text(encoding="utf-8"))
            computed = p["modality_supervision"]["validation_accuracy"]
            check(f"dataeff {k} seeds / {label} / modality head",
                  abs(float(cells[5]) - computed) < 0.001,
                  f"tex={cells[5]} computed={computed:.3f}")

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
        ctrl = baseline_row(arm, "MLP-Trust")
        if base is None or ctrl is None:
            check(f"robustness {label} / logs", False)
            continue
        want = [base["accuracy"], base["f_score"], ctrl["accuracy"],
                ctrl["f_score"]]
        for i, (col, value) in enumerate(zip(
                ("S-TIM accuracy", "S-TIM f_score", "MLP accuracy",
                 "MLP f_score"), want)):
            claimed = cells[2 + i] if len(cells) > 2 + i else "--"
            check(f"robustness {label} / {col}",
                  abs(float(claimed) - value) < 0.06,
                  f"tex={claimed} computed={value:.1f}")
        rule_best = max(baseline_row(arm, m)["accuracy"] for m in RULE_METHODS)
        claimed = cells[6] if len(cells) > 6 else "--"
        check(f"robustness {label} / best rule accuracy",
              abs(float(claimed) - rule_best) < 0.06,
              f"tex={claimed} computed={rule_best:.1f}")

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
    ("6.2", "LR-Trust on the forger"),
    ("4.2", "MLP-Trust on the forger"),
    ("$+81.5$~pp", "the paired spatial gain"),
    ("81.5", "the paired spatial gain, plain form"),
    ("1.99", "the largest neighborhood effect size"),
    ("0.04", "the largest behavioural effect size"),
    ("84.5", "MLP-Trust on the forger with the same vector"),
    ("60.8", "LR-Trust on the forger with the same vector"),
    ("$-6.3$~pp", "the linear head's interference cost"),
    ("8.7~pp", "the shape block's cost on constant attackers"),
    ("3.6~pp", "the net cost on constant attackers"),
    ("2.2~pp", "the net cost on dormant attackers"),
    ("46.7\\%", "the rule baselines' best F1 in the spatial scenario"),
    ("46.2\\%", "the trivial classifier's F1"),
    ("93.8", "S-TIM accuracy in the spatial scenario"),
    ("89.4", "S-TIM F-score in the spatial scenario"),
    ("88.9", "S-TIM TSR in the spatial scenario"),
    ("$+7.7$~pp", "the paired accuracy gain over the learned control"),
    ("$+16.7$~pp", "the paired F-score gain over the learned control"),
    ("$+6.7$~pp", "the paired TSR gain over the learned control"),
    ("$+12.3$~pp", "the paired accuracy gain over LR-Trust"),
    ("$+26.2$~pp", "the paired F-score gain over LR-Trust"),
    ("$+54.0$~pp", "the accuracy gain over the strongest rule adapter"),
    ("0.967", "the modality head accuracy at 12 training seeds"),
    ("0.964", "the modality head accuracy at 24 training seeds"),
    ("$+0.1$~pp", "the largest data-efficiency difference"),
    ("90 node-level training rows", "the size of the smallest training set"),
    ("$+4.5$~pp", "the smallest accuracy advantage in the robustness sweep"),
    ("$+11.9$~pp", "the largest accuracy advantage in the robustness sweep"),
    ("$+8.8$~pp", "the smallest F-score advantage in the robustness sweep"),
    ("$+28.6$~pp", "the largest F-score advantage in the robustness sweep"),
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
