"""Build the configurations for the focal-loss gamma sweep.

Each configuration changes the modulating factor of the focal risk loss and
nothing else: the generator, the attack mix, the feature set, the seeds, the
thresholds and the auxiliary weights are those of the published spatial
configuration, and the learned comparators are trained with the same
objective inside the same run.

    python -u artifacts/analysis/make_focal_gamma_configs.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
CONFIGS = ROOT / "artifacts" / "configs"
GAMMAS = [0.5, 1.0]


def main() -> int:
    base = json.loads((CONFIGS / "spatial_position.json").read_text(encoding="utf-8"))
    for gamma in GAMMAS:
        cfg = json.loads(json.dumps(base))
        cfg.setdefault("marl_training", {})["risk_loss"] = "focal"
        cfg["marl_training"]["focal_gamma"] = gamma
        name = f"spatial_position_focal_g{str(gamma).replace('.', '')}"
        cfg["description"] = (
            f"Spatial scenario, all three evidence blocks (23 dims), with the focal "
            f"risk loss at gamma = {gamma}. Part of the pre-registered gamma sweep in "
            f"artifacts/analysis/FOCAL_GAMMA_SWEEP_PREREGISTRATION.md; the modulating "
            f"factor (1 - p_t)^gamma down-weights the easy examples and up-weights the "
            f"hard ones. Everything else, including the generator, the attack mix, the "
            f"seeds, the thresholds and the auxiliary weights, is the published "
            f"configuration, and the learned comparators are trained with the same "
            f"objective inside the same run."
        )
        out = CONFIGS / f"{name}.json"
        out.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}  (gamma={gamma})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
