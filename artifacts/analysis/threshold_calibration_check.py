"""Is the constant-attack deficit a calibration difference or a representation
difference?

The spatial scenario's configuration switches the modality loss off, so the
8.7 points that the shape block appears to cost the proposed model on
constant attackers cannot be attributed to the modality head. Two other
explanations remain, and they need different fixes:

  calibration   the two models put the decision threshold 0.60 at different
                points of their score distributions, so the comparison is
                between two operating points rather than between two
                representations. A threshold sweep would show the two
                curves crossing, and the deficit would be an artefact of the
                fixed cut.
  representation
                the proposed model's score simply does not separate the
                constant attackers as well, at any cut. A threshold sweep
                would show its curve below the control's everywhere.

This script scores the published 18-dimensional spatial arm over its
evaluation seeds and computes the curve for both learners, so the question
is answered by the data rather than by argument.

    python -u artifacts/analysis/threshold_calibration_check.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402

RUN = ROOT / "artifacts" / "runs" / "spatial_position_18dim"
CONFIG = ROOT / "artifacts" / "configs" / "spatial_position_nofeat.json"
CLASSES = ["constant", "dormant", "on-off", "position-inconsistent"]


def main() -> int:
    cfg = rs.load_config(str(CONFIG))
    policy = json.loads((RUN / "logs" / "marl_policy.json").read_text())
    policy["learned_baselines"] = json.loads(
        (RUN / "logs" / "learned_baselines.json").read_text())
    # The saved checkpoint paths are relative to the repository root and point
    # at the default outputs directory, which holds whatever was trained last.
    # The arm under test is in the run directory, so the paths are made
    # absolute and point there.
    policy["checkpoint_path"] = str(RUN / "checkpoints" / "stim_marl_policy.pt")
    for _name, _meta in policy["learned_baselines"]["baselines"].items():
        _meta["checkpoint_path"] = str(RUN / "checkpoints" /
                                       Path(str(_meta["checkpoint_path"])).name)

    print("=" * 100)
    print("configuration of the arm under test")
    print("=" * 100)
    mt = cfg.raw["marl_training"]
    for k in ("modality_loss_weight", "weight_loss_weight", "action_loss_weight",
              "value_loss_weight", "decision_threshold", "epochs",
              "shape_features"):
        print(f"  marl_training.{k:<24}{mt.get(k, '(default)')}")
    print(f"  spatial.features                  "
          f"{(cfg.raw.get('spatial') or {}).get('features')}")
    print(f"  policy.threshold                   {policy.get('threshold')}")
    print(f"  policy.fusion                      {policy.get('fusion', 'single')}")

    rows = []
    for seed in cfg.eval_seeds:
        streams, malicious, atk = rs.simulate_trust_stream(
            cfg, seed=seed, n_uavs=int(cfg.raw["network"]["default_uavs"]),
            malicious_ratio=0.30,
            n_agents=int(cfg.raw["network"]["default_thinker_agents"]))
        types = np.array([str(a).strip().lower() for a in atk])
        for method in ("S-TIM", "MLP-Trust"):
            _pred, score = rs.method_predictions(
                cfg, streams, method, policy, seed=seed,
                n_uavs=int(cfg.raw["network"]["default_uavs"]),
                malicious_ratio=0.30,
                n_agents=int(cfg.raw["network"]["default_thinker_agents"]))
            risk = 1.0 - np.asarray(score, dtype=float)
            rows.append(pd.DataFrame({
                "seed": seed, "method": method, "risk": risk,
                "malicious": malicious,
                "type": types,
            }))
    d = pd.concat(rows, ignore_index=True)
    d.to_csv(ROOT / "artifacts" / "outputs" / "tables" /
             "spatial18_threshold_sweep_scores.csv", index=False)
    print(f"\nscored {len(d)} node-method rows over {d['seed'].nunique()} seeds")

    print()
    print("=" * 100)
    print("1. the operating point the published threshold 0.60 selects")
    print("=" * 100)
    print(f"{'method':<12}{'recall':>10}{'specificity':>13}{'accuracy':>11}"
          f"{'const':>8}{'dorm':>8}{'on-off':>9}{'pos-inc':>9}")
    print("-" * 100)
    for method in ("S-TIM", "MLP-Trust"):
        g = d[d["method"] == method]
        mal = g["malicious"].to_numpy(bool)
        risk = g["risk"].to_numpy(float)
        types = g["type"].to_numpy()
        flag = risk > 0.60
        rec = float(flag[mal].mean())
        spec = float((~flag[~mal]).mean())
        acc = float((flag == mal).mean())
        per = []
        for c in CLASSES:
            m = mal & (types == c)
            per.append(float(flag[m].mean()) * 100 if m.any() else float("nan"))
        print(f"{method:<12}{rec * 100:>9.1f}%{spec * 100:>12.1f}%"
              f"{acc * 100:>10.1f}%" + "".join(f"{v:>8.1f}" for v in per))

    print()
    print("=" * 100)
    print("2. the curve: at a matched specificity, what recall does each reach?")
    print("=" * 100)
    thresholds = [round(0.05 * k, 2) for k in range(1, 19)]
    print(f"{'threshold':>10}" + "".join(f"{m:>26}" for m in
                                         ("S-TIM", "MLP-Trust")))
    print(f"{'':>10}" + "".join(f"{'recall':>10}{'specif.':>9}{'const':>7}"
                                for _ in (0, 1)))
    print("-" * 100)
    for t in thresholds:
        row = f"{t:>10.2f}"
        for method in ("S-TIM", "MLP-Trust"):
            g = d[d["method"] == method]
            mal = g["malicious"].to_numpy(bool)
            risk = g["risk"].to_numpy(float)
            types = g["type"].to_numpy()
            flag = risk > t
            rec = float(flag[mal].mean()) * 100
            spec = float((~flag[~mal]).mean()) * 100
            cm = mal & (types == "constant")
            con = float(flag[cm].mean()) * 100 if cm.any() else float("nan")
            row += f"{rec:>10.1f}{spec:>9.1f}{con:>7.1f}"
        print(row)

    print()
    print("=" * 100)
    print("3. the same curve reduced to: recall at a matched specificity")
    print("=" * 100)
    curves = {}
    for method in ("S-TIM", "MLP-Trust"):
        g = d[d["method"] == method]
        mal = g["malicious"].to_numpy(bool)
        risk = g["risk"].to_numpy(float)
        types = g["type"].to_numpy()
        pts = []
        for t in np.quantile(risk, np.linspace(0.001, 0.999, 400)):
            flag = risk > t
            pts.append(((~flag[~mal]).mean(), float(flag[mal].mean()),
                        float(flag[mal & (types == "constant")].mean())))
        curves[method] = sorted(pts)
    for spec_target in (0.90, 0.93, 0.95, 0.96, 0.97, 0.974):
        line = f"  specificity {spec_target * 100:>5.1f}%   "
        for method in ("S-TIM", "MLP-Trust"):
            # The operating point is the one whose specificity is the largest
            # that does not exceed the target, and its recall is read there.
            cand = [p for p in curves[method] if p[0] <= spec_target]
            if not cand:
                line += f"{method}: unreachable          "
                continue
            best = max(cand, key=lambda p: p[0])
            line += (f"{method}: recall {best[1] * 100:>5.1f}% "
                     f"(const {best[2] * 100:>5.1f}%)   ")
        print(line)

    print()
    print("=" * 100)
    print("4. area under the curve: all nodes, and the constant class against the benign")
    print("=" * 100)

    def auc_of(pos: np.ndarray, neg: np.ndarray, scores: np.ndarray) -> float:
        """Area under the ROC for one positive set against one negative set."""
        s = np.concatenate([scores[pos], scores[neg]])
        y = np.concatenate([np.ones(pos.sum()), np.zeros(neg.sum())])
        order = np.argsort(s, kind="mergesort")
        s, y = s[order], y[order]
        ranks = np.empty(len(s), dtype=float)
        ranks[np.argsort(order, kind="mergesort")] = np.arange(1, len(s) + 1)
        # average the ranks of tied scores
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] == s[i]:
                j += 1
            if j > i:
                ranks[i:j + 1] = (i + 1 + j + 1) / 2.0
            i = j + 1
        npos, nneg = int(pos.sum()), int(neg.sum())
        if npos == 0 or nneg == 0:
            return float("nan")
        return float((ranks[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))

    for method in ("S-TIM", "MLP-Trust"):
        g = d[d["method"] == method]
        mal = g["malicious"].to_numpy(bool)
        risk = g["risk"].to_numpy(float)
        types = g["type"].to_numpy()
        benign = ~mal
        cm = mal & (types == "constant")
        print(f"  {method:<12} AUC all nodes "
              f"{auc_of(mal, benign, risk):.4f}   "
              f"AUC constant vs benign {auc_of(cm, benign, risk):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
