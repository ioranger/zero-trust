"""Counterfactual sweep: what drives the rule-based collapse in the spatial
scenario?

The diagnostic showed that the five rule adapters score AUC ~0.45 in the
telemetry-forging scenario, which is worse than chance. Before that number is
reported anywhere it has to be clear which generator choice produces it, because
three of them are confounded in the current configuration:

  * ``reference_shift`` moves the channel-reference level, and the rule
    adapters embed the absolute reference profile in their scoring.
  * ``field_amplitude`` creates the spatial field that the neighbourhood block
    reads.
  * ``position_attack_ratio`` creates the telemetry-forging attackers.

This sweep varies one of them at a time against the same seeds and reports
the accuracy, the benign specificity, the AUC and the position-inconsistent
detection rate of the proposed-model configuration and of the rule-based
methods, so that each contribution can be attributed.

    python -u artifacts/analysis/diagnose_spatial_counterfactuals.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(r"F:\zero trust\zero-trust\artifacts\scripts")
sys.path.insert(0, str(SCRIPTS))

from baseline_reimplementations import ahp_entropy, fuba, galtrust, gdm_dtm, mfa  # noqa: E402
from reference_simulator import (  # noqa: E402
    BaselineConfig, load_config, simulate_trust_stream)
from diagnose_rule_threshold_transfer import (  # noqa: E402
    auc_low_is_malicious)

ROOT = Path(r"F:\zero trust\zero-trust")
BASE = ROOT / "artifacts/configs/spatial_position_nofeat.json"
SEEDS = [1000, 1001, 1002]
N = 400

VARIANTS = [
    ("baseline (shift .30, field .45, pos .34)", {}),
    ("reference_shift = 0", {"reference_shift": 0.0}),
    ("field_amplitude = 0 (no field)", {"field_amplitude": 0.0}),
    ("position_attack_ratio = 0 (no forger)", {"position_attack_ratio": 0.0}),
    ("shift 0 + field 0 + no forger", {"reference_shift": 0.0,
                                       "field_amplitude": 0.0,
                                       "position_attack_ratio": 0.0}),
]

RULES = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy"]


def run_variant(raw: dict) -> dict:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "cfg.json"
        p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        cfg = load_config(str(p))
        thr = cfg.raw["classification"]
        bcfg = BaselineConfig(
            mfa_threshold=float(thr["mfa_threshold"]),
            fuba_threshold=float(thr["fuba_threshold"]),
            galtrust_threshold=float(thr["galtrust_threshold"]),
            gdm_dtm_threshold=float(thr["gdm_dtm_threshold"]),
            ahp_entropy_threshold=float(thr.get("ahp_entropy_threshold", 0.62)),
            ahp_entropy_lambda=float(thr.get("ahp_entropy_lambda", 0.5)),
        )
        out = {m: {"acc": [], "spec": [], "auc": [], "pos": []} for m in RULES}
        for seed in SEEDS:
            streams, malicious, types = simulate_trust_stream(
                cfg, seed=seed, n_uavs=N, malicious_ratio=0.3, n_agents=5)
            is_pos = types == "position-inconsistent"
            noise = np.zeros(N)
            for m in RULES:
                if m == "MFA":
                    pred, trust = mfa(streams, cfg.warmup_steps, bcfg, noise)
                elif m == "FUBA":
                    pred, trust = fuba(streams, cfg.warmup_steps, bcfg, noise)
                elif m == "GALTrust":
                    pred, trust = galtrust(streams, cfg.warmup_steps, bcfg, noise)
                elif m == "GDM-DTM":
                    pred, trust = gdm_dtm(streams, cfg.warmup_steps, bcfg, noise)
                else:
                    pred, trust = ahp_entropy(streams, cfg.warmup_steps, bcfg, noise)
                out[m]["acc"].append(float(np.mean(pred == malicious)))
                out[m]["spec"].append(float(np.mean(~pred[~malicious])))
                out[m]["auc"].append(auc_low_is_malicious(trust, malicious))
                if is_pos.any():
                    out[m]["pos"].append(float(np.mean(pred[is_pos])))
        return out


def main() -> int:
    base_raw = json.loads(BASE.read_text(encoding="utf-8-sig"))
    base_raw["network"]["default_uavs"] = N

    print("=" * 112)
    print(f"SPATIAL COUNTERFACTUAL SWEEP -- {len(SEEDS)} seeds, n={N}, ratio=0.3")
    print("=" * 112)
    for label, patch in VARIANTS:
        raw = copy.deepcopy(base_raw)
        raw["spatial"].update(patch)
        res = run_variant(raw)
        print(f"\n--- {label}")
        print(f"{'method':<13}{'accuracy':>10}{'benign spec':>13}{'AUC':>8}{'pos-incons.':>13}")
        for m in RULES:
            d = res[m]
            pos = 100 * np.mean(d["pos"]) if d["pos"] else float("nan")
            print(f"{m:<13}{100*np.mean(d['acc']):>10.1f}"
                  f"{100*np.mean(d['spec']):>13.1f}"
                  f"{np.mean(d['auc']):>8.3f}{pos:>13.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
