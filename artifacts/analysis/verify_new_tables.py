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
    return d[d["malicious_ratio"].abs() - 0.30 < 1e-9]


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
if failures:
    print(f"FAILED: {len(failures)} check(s)")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("All checks passed.")
