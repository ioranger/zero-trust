"""Build the configuration for the focal-loss arm.

The arm changes exactly one thing: the risk loss. The generator, the attack
mix, the feature set, the seeds, the thresholds and the auxiliary weights are
those of the published spatial configuration, so that a difference in the
result is a difference in the training objective and nothing else.

The comparator is trained with the same objective inside the same run, so the
arm measures the objective and not the comparison protocol.

    python -u artifacts/analysis/make_focal_config.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
CONFIGS = ROOT / "artifacts" / "configs"


def main() -> int:
    base = json.loads((CONFIGS / "spatial_position.json").read_text(encoding="utf-8"))

    focal = json.loads(json.dumps(base))
    focal.setdefault("marl_training", {})["risk_loss"] = "focal"
    focal["marl_training"]["focal_gamma"] = 2.0
    focal["description"] = (
        "Spatial scenario, all three evidence blocks (23 dims), with the focal "
        "risk loss instead of the plain binary cross-entropy. The modulating "
        "factor (1 - p_t)^gamma down-weights the easy examples and up-weights "
        "the hard ones, which is where the forgers that the published arm "
        "misses sit: their neighbourhood-relative residual is still larger "
        "than the benign population's. Everything else, including the "
        "generator, the attack mix, the seeds, the thresholds and the "
        "auxiliary weights, is the published configuration, and the learned "
        "comparators are trained with the same objective inside the same run."
    )

    out = CONFIGS / "spatial_position_focal.json"
    out.write_text(json.dumps(focal, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"  risk_loss  : {focal['marl_training']['risk_loss']}")
    print(f"  focal_gamma: {focal['marl_training']['focal_gamma']}")
    print(f"  shape      : {focal['marl_training'].get('shape_features')}")
    print(f"  spatial    : {focal['spatial'].get('features')}")
    print(f"  aux weights: value {focal['marl_training'].get('value_loss_weight', 'default')}, "
          f"weight {focal['marl_training'].get('weight_loss_weight', 'default')}, "
          f"action {focal['marl_training'].get('action_loss_weight', 'default')}, "
          f"modality {focal['marl_training'].get('modality_loss_weight', 'default')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
