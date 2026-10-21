"""Generate the data-efficiency sweep configurations.

The published configuration supervises the value, trust-weight and
incentive-action heads, but not the modality head, and all three of those
targets are functions of the binary risk label or of the features the risk head
already receives. The modality label is the only auxiliary target in the
network that is not, and the information probe shows it is 96.7% recoverable
from the marginal features in the 60-seed regime. Recoverable is not the same
as free: with few training seeds the risk head has no way to tell a constant
attacker from an intermittent one, because both carry y = 1, and the features
alone are not enough to learn that distinction from a handful of examples.

This sweep varies the number of training seeds and, at each size, whether the
modality head is supervised:

  dataeff_k<K>_mod    modality supervised at weight 0.30, other auxiliary
                      losses off
  dataeff_k<K>_risk   every auxiliary loss off

The gap between the two isolates the value of the extra supervision, and the
comparison of the first against MLP-Trust, which consumes the identical
features and carries no auxiliary head at all, is the one that can show the
proposed model ahead of its feature-matched control.

    python -u artifacts/analysis/make_dataeff_configs.py
"""

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust\artifacts\configs")
BASE = ROOT / "default.json"
SIZES = [12, 24]

# Three supervision variants, each matching one of the existing 60-seed arms:
#   mod      the modality head supervised at 0.30, every other auxiliary loss off
#            (matches heads_mod_only.json)
#   risk     every auxiliary loss off (matches heads_risk_only.json)
#   pub      the published configuration: value, trust-weight and
#            incentive-action supervised, modality not (matches default.json)
VARIANTS = {
    "mod": ({"modality_loss_weight": 0.3, "weight_loss_weight": 0.0,
             "action_loss_weight": 0.0, "value_loss_weight": 0.0},
            "the modality head supervised at weight 0.30 and every other "
            "auxiliary loss off"),
    "risk": ({"modality_loss_weight": 0.0, "weight_loss_weight": 0.0,
              "action_loss_weight": 0.0, "value_loss_weight": 0.0},
             "every auxiliary loss off"),
    "pub": ({"modality_loss_weight": 0.0, "weight_loss_weight": 0.25,
             "action_loss_weight": 0.20, "value_loss_weight": 0.10},
            "the published configuration, in which the value, trust-weight and "
            "incentive-action heads are supervised and the modality head is not"),
}

DESC = (
    "Data-efficiency arm: the published configuration with {k} training seeds "
    "and {aux}. The modality label is the only auxiliary target that is not a "
    "function of the binary risk label, so it is the only auxiliary supervision "
    "that can carry information the risk head does not already receive; the "
    "question is whether that difference is worth anything when the training "
    "set is small enough to matter.")


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8-sig"))
    for k in SIZES:
        for arm, (weights, aux_desc) in VARIANTS.items():
            cfg = json.loads(json.dumps(base))
            cfg["train_seeds"] = list(range(100, 100 + k))
            cfg["marl_training"].update(weights)
            cfg["description"] = DESC.format(k=k, aux=aux_desc)
            path = ROOT / f"dataeff_k{k}_{arm}.json"
            path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {path.name}: seeds={k} aux={weights}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
