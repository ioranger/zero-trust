"""Create the two configurations the constant-attack diagnosis calls for.

spatial_position_riskonly  the 18-dimensional spatial configuration with every
    auxiliary loss weight at zero. It separates the three auxiliary losses
    that are active in the published spatial configuration (value 0.10,
    trust-weight 0.25, incentive-action 0.20; the modality loss is already
    zero there) from the encoder itself.

spatial_position_gated  the 23-dimensional spatial configuration with the
    block-routed fusion, in which each evidence block has its own encoder, a
    per-node gate mixes the block specialists, and the auxiliary heads read
    the branch embeddings with the gradient path to the branch encoders
    removed.

Neither configuration touches the published ones.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
CFG = ROOT / "artifacts" / "configs"


def load(name: str) -> dict:
    return json.loads((CFG / name).read_text(encoding="utf-8-sig"))


def write(name: str, raw: dict) -> None:
    path = CFG / name
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path.name}")


def main() -> int:
    # --- the 18-dimensional control with the auxiliary losses off ----------
    risk_only = load("spatial_position_nofeat.json")
    mt = risk_only.setdefault("marl_training", {})
    mt["weight_loss_weight"] = 0.0
    mt["action_loss_weight"] = 0.0
    mt["value_loss_weight"] = 0.0
    mt["modality_loss_weight"] = 0.0
    risk_only["description"] = (
        "Spatial scenario, marginal plus shape features (18 dims), with every "
        "auxiliary loss weight at zero. This is the control that separates the "
        "three auxiliary losses the published spatial configuration activates "
        "from the encoder itself; the modality loss is already zero in the "
        "published configuration."
    )
    write("spatial_position_riskonly.json", risk_only)

    # --- the 23-dimensional block-routed configuration --------------------
    gated = copy.deepcopy(load("spatial_position.json"))
    gated.setdefault("marl_training", {})["fusion"] = "gated"
    # The modality head is a measurement instrument in the block-routed form:
    # it reads the branch embeddings detached, so its loss trains the head
    # and nothing else. With a zero weight it would stay at its
    # initialisation and report nothing.
    gated["marl_training"]["modality_loss_weight"] = 0.30
    gated["description"] = (
        "Spatial scenario, all three evidence blocks (23 dims), with the "
        "block-routed fusion. Each block has its own encoder and its own risk "
        "specialist, a per-node gate mixes the specialists, and the auxiliary "
        "heads read the branch embeddings detached, so their losses cannot "
        "reach the branch encoders. The gate is trained by the risk loss "
        "alone."
    )
    write("spatial_position_gated.json", gated)

    # --- a smoke configuration for the block-routed fusion ---------------
    smoke = copy.deepcopy(gated)
    smoke.setdefault("marl_training", {})["epochs"] = 2
    smoke["train_seeds"] = list(range(100, 104))
    smoke["evaluation_seeds"] = {"start": 1000, "stop": 1002}
    smoke.setdefault("network", {})["default_uavs"] = 60
    smoke["description"] = (
        "Two-epoch smoke configuration for the block-routed fusion, used to "
        "check that the architecture trains and scores before a full run."
    )
    write("smoke_spatial_gated.json", smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
