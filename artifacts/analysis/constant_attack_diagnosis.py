"""Why the constant-attack detection rate falls when the shape block is added.

The manuscript reports that adding the five shape statistics costs 8.7 pp on
constant attackers and 3.4 pp on dormant ones, and that the neighbourhood
block recovers 5.1 pp of the first. This script asks what the shape block
actually carries for those classes, in the spatial scenario and in the plain
one, and measures the level separation that the constant attacker has to
work with once the spatial field is superimposed.

The measurements are of three kinds:

  * the effect size of every feature, benign against one attack class, per
    block, so that the question "does this block carry any signal for this
    class" has a number attached;
  * the margin a constant attacker has against its own neighbourhood, before
    and after the spatial field is applied, which is what the field can
    destroy;
  * the rate at which the field drives a channel into the clip, because a
    clipped channel cannot separate anything.

    python -u artifacts/analysis/constant_attack_diagnosis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402
from marl_policy import extract_marl_policy_features  # noqa: E402

BLOCKS = {
    "marginal": list(range(0, 13)),
    "shape": list(range(13, 18)),
}


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    pooled = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    if pooled <= 0:
        return 0.0
    return float(abs(a.mean() - b.mean()) / np.sqrt(pooled))


def run(config_path: str, label: str, seeds, n_uavs: int) -> None:
    cfg = rs.load_config(str(ROOT / config_path))
    agents = int(cfg.raw["network"]["default_thinker_agents"])
    spatial = rs.spatial_cfg(cfg) is not None

    rows = []
    for s in seeds:
        if spatial:
            streams, malicious, atk = rs.simulate_trust_stream_spatial(
                cfg, seed=s, n_uavs=n_uavs, malicious_ratio=0.30,
                n_agents=agents)
        else:
            streams, malicious, atk = rs.simulate_trust_stream(
                cfg, seed=s, n_uavs=n_uavs, malicious_ratio=0.30,
                n_agents=agents)
        adj = None
        if spatial:
            from marl_policy import resolve_spatial_adjacency
            adj = resolve_spatial_adjacency(cfg, s, n_uavs, 0.30)
        feats, names = extract_marl_policy_features(
            cfg, streams, agents, use_shape=True, spatial_adjacency=adj)
        types = np.array([str(a).strip().lower() for a in atk])
        benign = ~malicious
        for at in sorted(set(types[malicious])):
            m = malicious & (types == at)
            rec = {"seed": s, "class": at, "n": int(m.sum())}
            for bname, idx in BLOCKS.items():
                for j in idx:
                    rec[f"{names[j]}|{bname}"] = cohens_d(
                        feats[m, j], feats[benign, j])
            rows.append(rec)

    df = pd.DataFrame(rows)
    print("=" * 104)
    print(f"{label}  (n_uavs={n_uavs}, seeds={len(list(seeds))})")
    print("=" * 104)
    for bname in BLOCKS:
        cols = [c for c in df.columns if c.endswith("|" + bname)]
        sub = df[cols].abs().mean()
        print(f"  mean |effect size| of the {bname} block, benign against each class")
        for at in df["class"].unique():
            vals = df[df["class"] == at][cols].abs().mean()
            print(f"    {at:<24} {vals.mean():>6.2f}   (per feature: "
                  f"{', '.join(f'{v:.2f}' for v in vals.values)})")
        print()

    # The margin a constant attacker keeps against its own neighbourhood.
    if spatial:
        print("  margin of a constant attacker against its own neighbourhood")
        print(f"  {'seed':>6}{'n_const':>10}{'T1 margin':>12}"
              f"{'T4 margin':>12}{'clipped %':>12}")
        for s in seeds:
            streams, malicious, atk = rs.simulate_trust_stream_spatial(
                cfg, seed=s, n_uavs=n_uavs, malicious_ratio=0.30,
                n_agents=agents)
            from marl_policy import resolve_spatial_adjacency
            adj = resolve_spatial_adjacency(cfg, s, n_uavs, 0.30)
            types = np.array([str(a).strip().lower() for a in atk])
            const = malicious & (types == "constant")
            post = streams[cfg.warmup_steps:, :, :4]
            recent = post.mean(axis=0)
            nb = adj @ recent
            m1 = (recent[:, 0] - nb[:, 0])[const]
            m4 = (recent[:, 3] - nb[:, 3])[const]
            clip = float(np.mean((post[:, const, :] <= 0.0201)
                                 | (post[:, const, :] >= 0.9799)))
            print(f"  {s:>6}{int(const.sum()):>10}{m1.mean():>12.3f}"
                  f"{m4.mean():>12.3f}{clip * 100:>11.1f}%")
        print()


def main() -> int:
    plain = json.loads((ROOT / "artifacts" / "configs" / "default.json")
                       .read_text(encoding="utf-8-sig"))
    print("=" * 104)
    print("WHAT EACH BLOCK CARRIES, PER ATTACK CLASS")
    print("=" * 104)
    run("artifacts/configs/default.json", "PLAIN SCENARIO (no spatial field)",
        range(1000, 1008), 30)
    run("artifacts/configs/spatial_position.json", "SPATIAL SCENARIO",
        range(1000, 1008), 800)
    return 0


if __name__ == "__main__":
    sys.exit(main())
