"""Isolate the modality auxiliary head inside the spatial scenario.

The 13-versus-18 dimensional comparison shows that adding the shape block
costs the proposed model 8.7 points on constant attackers and costs the
feature-matched MLP nothing. The two arms share the generator, the seeds and
the feature vector, so the difference is in the head. This script compares
the proposed model with the modality loss on against the same model with it
off, on the seeds the two arms share.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
RUN = ROOT / "artifacts" / "runs" / "spatial_position_18dim"
ON = RUN / "logs" / "per_seed_attack_type_metrics.csv"
OFF = RUN / "_no_modality" / "per_seed_attack_type_metrics.csv"

TYPES = ["constant", "dormant", "on-off", "position-inconsistent", "benign"]
PROPOSED_ON = "S-TIM"
PROPOSED_OFF = "MTIM"


def load(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d.dropna(subset=["seed", "method", "attack_type", "detection_rate"])
    d["seed"] = d["seed"].astype(int)
    d["detection_rate"] = d["detection_rate"].astype(float)
    return (d.groupby(["seed", "method", "attack_type"], as_index=False)
             ["detection_rate"].mean())


def paired(a: pd.Series, b: pd.Series):
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    n = len(m)
    if n < 2:
        return None
    d = m["a"] - m["b"]
    sd = d.std(ddof=1)
    if sd == 0:
        return (d.mean(), float("inf") if d.mean() else 0.0, 0.0 if d.mean() else 1.0, 0.0, n)
    t = d.mean() / (sd / math.sqrt(n))
    try:
        from scipy import stats  # type: ignore
        p = float(2.0 * stats.t.sf(abs(t), df=n - 1))
    except Exception:
        p = math.erfc(abs(t) / math.sqrt(2.0))
    return (d.mean(), t, p, d.mean() / sd, n)


def main() -> int:
    on = load(ON)
    off = load(OFF)
    seeds = sorted(set(on["seed"]) & set(off["seed"]))
    on = on[on["seed"].isin(seeds)]
    off = off[off["seed"].isin(seeds)]
    print(f"shared seeds: {len(seeds)}  ({seeds[0]}..{seeds[-1]})")

    print()
    print("=" * 92)
    print("proposed model, modality auxiliary loss ON  minus  the same model with it OFF")
    print("=" * 92)
    print(f"{'class':<24}{'ON':>10}{'OFF':>10}{'delta pp':>12}{'t':>9}"
          f"{'p':>11}{'n':>5}")
    print("-" * 92)
    for t in TYPES:
        a = on[(on["method"] == PROPOSED_ON) & (on["attack_type"] == t)] \
            .set_index("seed")["detection_rate"]
        b = off[(off["method"] == PROPOSED_OFF) & (off["attack_type"] == t)] \
            .set_index("seed")["detection_rate"]
        res = paired(a, b)
        if res is None:
            continue
        md, tt, pp, dd, n = res
        print(f"{t:<24}{a.mean() * 100:>9.1f}%{b.mean() * 100:>9.1f}%"
              f"{md * 100:>12.1f}{tt:>9.2f}{pp:>11.4f}{n:>5}")

    print()
    print("=" * 92)
    print("the feature-matched control, same two arms (it has no auxiliary head)")
    print("=" * 92)
    for t in TYPES:
        a = on[(on["method"] == "MLP-Trust") & (on["attack_type"] == t)] \
            .set_index("seed")["detection_rate"]
        b = off[(off["method"] == "MLP-Trust") & (off["attack_type"] == t)] \
            .set_index("seed")["detection_rate"]
        res = paired(a, b)
        if res is None:
            continue
        md, tt, pp, dd, n = res
        print(f"{t:<24}{a.mean() * 100:>9.1f}%{b.mean() * 100:>9.1f}%"
              f"{md * 100:>12.1f}{tt:>9.2f}{pp:>11.4f}{n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
