"""Cross-check every headline number in the manuscript against the CSVs
that produced it.

The point is not typesetting. It is to catch the failure mode where a number
survives in prose after the artifact has been regenerated underneath it, and
to find any place where the text claims more than the table supports.
"""
import pathlib
import re

ROOT = pathlib.Path(r"F:\zero trust\zero-trust")
TEX = ROOT / "paper" / "template.tex"
TABLES = ROOT / "artifacts" / "outputs" / "tables"

tex = TEX.read_text(encoding="utf-8")


def load(name):
    rows = []
    lines = (TABLES / name).read_text(encoding="utf-8").splitlines()
    hdr = [h.strip() for h in lines[0].split(",")]
    for line in lines[1:]:
        if not line.strip():
            continue
        rows.append(dict(zip(hdr, [c.strip() for c in line.split(",")])))
    return rows


def nums(s):
    """Pull (mean, std) out of a cell like '84.8 +- 8.0'."""
    s = (s or "").strip()
    found = re.findall(r"\d+\.\d+", s)
    if not found:
        return None, None
    a = float(found[0])
    b = float(found[1]) if len(found) > 1 else None
    return a, b


base = {r["method"]: r for r in load("baseline_comparison.csv")}
brk = {r["method"]: r for r in load("attack_type_breakdown.csv")}

print("=" * 78)
print("1. baseline_comparison.csv -> manuscript Table 2")
print("=" * 78)
# These tables wrap the tabular in \resizebox, so \begin{tabular} sits AFTER
# \label. Every table in this document follows caption -> label -> tabular.
label_at = tex.index("\\label{tab:baseline_comparison}")
tab_start = tex.index("\\begin{tabular}", label_at)
tab_end = tex.index("\\end{tabular}", tab_start)
block = tex[tab_start:tab_end]
n_tab2 = 0
for line in block.splitlines():
    if "&" not in line or "Method &" in line:
        continue
    cells = [c.strip() for c in line.rstrip("\\ ").split("&")]
    name = re.sub(r"\\cite\{[^}]+\}", "", cells[0]).strip()
    name = re.sub(r"\s*\(ours\)$", "", name)
    name = re.sub(r"\$[^$]*\$", "", name).strip()
    if name not in base:
        continue
    found = [float(x) for x in re.findall(r"([\d.]+)\\?%", " ".join(cells))]
    csv = base[name]
    want = [nums(csv[c])[0] for c in ("accuracy", "f_score", "tsr")]
    sd = [nums(csv[c])[1] for c in ("accuracy", "f_score", "tsr")]
    # LaTeX rows interleave mean/std per column: [m1,s1,m2,s2,m3,s3]
    ok = (len(found) == 6
          and all(abs(found[2 * i] - want[i]) < 0.05 for i in range(3))
          and all(abs(found[2 * i + 1] - sd[i]) < 0.05 for i in range(3)))
    n_tab2 += 1
    print(f"  {name:<11} tex={found}  csv={[want, sd]}")
    print(f"  {'':<11} {'OK' if ok else '*** MISMATCH ***'}")
print(f"  rows cross-checked: {n_tab2}")

print()
print("=" * 78)
print("2. attack_type_breakdown.csv -> manuscript tab:attack_breakdown")
print("=" * 78)
onoff = {k: v["on-off_detection"] for k, v in brk.items()}
for k, v in onoff.items():
    a, b = nums(v)
    print(f"  {k:<11} on-off = {a} +- {b}")
print()
stim_onoff = nums(brk["S-TIM"]["on-off_detection"])[0]
gdm_onoff = nums(brk["GDM-DTM"]["on-off_detection"])[0]
print(f"  headline gap S-TIM vs GDM-DTM on-off: {stim_onoff - gdm_onoff:.1f} pp")
for claim, val in (("92.0% S-TIM on-off", stim_onoff),
                   ("38.0% GDM-DTM on-off", gdm_onoff)):
    s = f"{val:.1f}"
    print(f"  prose states {claim:<26} -> in tex: {s in tex}")

print()
print("=" * 78)
print("3. numbers appearing in prose but not backed by any table")
print("=" * 78)
known = set()
for tbl in (base, brk):
    for r in tbl.values():
        for c in r.values():
            a, b = nums(c)
            if a is not None:
                known.add(a)
            if b is not None:
                known.add(b)
# add computed gaps used in the text
known |= {10.6, 14.5, 3.9, 91.8, 59.2, 84.0, 64.0, 20.0, 38.0, 16.2}

suspicious = []
for m in re.finditer(r"([-+]?\d+\.\d)\\?%", tex):
    v = float(m.group(1))
    if not any(abs(v - k) < 0.05 for k in known):
        suspicious.append(m.group(1))
uniq = sorted(set(suspicious))
print(f"  {len(uniq)} distinct percentages with no matching table value:")
for u in uniq:
    ctx = tex[max(0, tex.find(u + "\\%") - 90):tex.find(u + "\\%") + 40]
    ctx = re.sub(r"\s+", " ", ctx)
    print(f"    {u:>7}%   ...{ctx[-105:]}...")

print()
print("=" * 78)
print("4. structural-claim consistency")
print("=" * 78)
checks = [
    ("reports the paired result vs LR-Trust",
     "p=0.13" in tex),
    ("reports the paired result vs GDM-DTM",
     "1.9\\times10^{-7}" in tex),
    ("reports the enlarged-training-set control",
     "sixfold" in tex and "2700" in tex),
    ("reports cross-architecture shape replication",
     "54.0" in tex or "complementary" in tex),
    ("discloses early stopping on a seed-level validation split",
     "early stopping selects epoch" in tex and "validation risk loss" in tex),
    ("states baselines receive the identical stopping rule",
     "identical split and the identical stopping rule" in tex),
    ("discloses common random numbers for the task proxy",
     "shared Monte Carlo stream" in tex),
    ("reports probe-level evaluation",
     "tab:probe_level" in tex),
    ("discloses baseline reimplementation scope",
     "paper-level reimplementations" in tex),
    ("discloses the removed tsr-0.09 fabrication",
     "0.09" in tex and "removed" in tex),
    ("discloses ns-3 shortfall",
     "neither tests nor refutes" in tex or "does not transfer" in tex),
    ("reports the duty-cycle sweep",
     "tab:duty_sweep" in tex),
    ("shuffle control reported",
     "time-shuffle" in tex or "time-permuted" in tex),
    ("13-dim legacy config referenced",
     "legacy_13dim" in tex or "legacy\\_13dim" in tex),
    ("states the modality-head negative result",
     "attack-modality" in tex),
]
for label_, ok in checks:
    print(f"  [{'x' if ok else ' '}] {label_}")