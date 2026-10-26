"""Generate the leave-one-factor-out control configurations.

A reviewer asks why the trust factor carries so many channels when every
channel costs something. The answer has to be measured, not asserted: for
each factor in turn, the model is trained and evaluated without it, and the
detection metrics are compared with the published configuration.

Each configuration differs from configs/default.json in exactly one key,
``marl_training.disabled_factors``. The generator, the attack mix, the seeds,
the epochs, the early-stopping rule, the auxiliary weights and the decision
threshold are the published ones.

The rule-based comparators keep all five factors in every arm, so a dropped
factor is a cost carried by the proposed model alone. That is the honest
direction: the arm is handicapped relative to the baselines, and what it
loses is what the factor was worth to the proposed model.

Usage:
    python -u artifacts/analysis/make_factor_ablation_configs.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
CONFIGS = ROOT / "artifacts" / "configs"
FACTORS = ["T1", "T2", "T3", "T4", "T5"]

# (source configuration, prefix of the generated file names, one-line purpose)
FAMILIES = [
    ("default.json", "factor_ablation_",
     "the published scenario, 18-dimensional input"),
    ("spatial_position.json", "spatial_factor_ablation_",
     "the spatially inconsistent scenario, 23-dimensional input"),
]

# The decisive arm: only T1 and T4 are kept. It is the configuration a
# deployment would have to fall back to if it could not supply the
# communication, energy and historical channels, and it answers the reviewer
# question directly, because it is the smallest factor set that can plausibly
# keep the result.
COMBINED = ["T2", "T3", "T5"]

# Column-level diagnostics. The communication dimension reaches the model
# through three columns: its own recent mean and the two directed cross-factor
# gaps, which read (T2 + T3) against (T1 + T4). Removing the dimension
# removes all three at once, so these two arms separate the paths: one leaves
# only the recent mean, the other leaves only the gaps.
COLUMN_ARMS = [
    ("col_nogaps", ["directed_T2T3_minus_T1T4_gap", "directed_low_quantile_gap"]),
    ("col_noT2direct", ["1-T2_recent"]),
]


def write_column_variant(base: dict, dst: Path, disabled: list[str],
                         src_name: str, purpose: str) -> bool:
    cfg = json.loads(json.dumps(base))
    cfg["marl_training"]["disabled_features"] = disabled
    cfg["description"] = (
        f"Column-level diagnostic on {purpose}: the proposed model does not see "
        f"the feature columns {', '.join(disabled)}. Identical to "
        f"configs/{src_name} in every other respect, including the generator, the "
        f"attack mix, the train and evaluation seeds, the epochs, the "
        f"early-stopping rule, the auxiliary weights and the decision threshold."
    )
    dst.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    chk = json.loads(dst.read_text(encoding="utf-8"))
    same = all(chk[k] == base[k] for k in base
               if k not in ("marl_training", "description"))
    mt_same = all(chk["marl_training"][k] == base["marl_training"][k]
                  for k in base["marl_training"]
                  if k not in ("disabled_factors", "disabled_features"))
    print(f"wrote {dst.name}")
    print(f"    disabled_features = {chk['marl_training']['disabled_features']}"
          f"   everything else identical: {same and mt_same}")
    return same and mt_same


def write_variant(base: dict, dst: Path, disabled: list[str], src_name: str,
                  purpose: str) -> bool:
    cfg = json.loads(json.dumps(base))
    cfg["marl_training"]["disabled_factors"] = disabled
    cfg["description"] = (
        f"Leave-one-factor-out control on {purpose}: the proposed model never "
        f"sees {', '.join(disabled)}. Identical to configs/{src_name} in every "
        f"other respect, including the generator, the attack mix, the train and "
        f"evaluation seeds, the epochs, the early-stopping rule, the auxiliary "
        f"weights and the decision threshold. The rule-based comparators keep "
        f"all five factors, so the arm measures what the removed factors are "
        f"worth to the proposed model, not what a comparator would lose."
    )
    dst.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    chk = json.loads(dst.read_text(encoding="utf-8"))
    same = all(chk[k] == base[k] for k in base
               if k not in ("marl_training", "description"))
    mt_same = all(chk["marl_training"][k] == base["marl_training"][k]
                  for k in base["marl_training"] if k != "disabled_factors")
    print(f"wrote {dst.name}")
    print(f"    disabled_factors = {chk['marl_training']['disabled_factors']}"
          f"   everything else identical: {same and mt_same}")
    return same and mt_same


def main() -> int:
    for src_name, prefix, purpose in FAMILIES:
        base = json.loads((CONFIGS / src_name).read_text(encoding="utf-8-sig"))

        for factor in FACTORS:
            if not write_variant(base, CONFIGS / f"{prefix}drop_{factor}.json",
                                 [factor], src_name, purpose):
                return 1

        if not write_variant(base, CONFIGS / f"{prefix}drop_T2_T3_T5.json",
                             COMBINED, src_name, purpose):
            return 1

        for suffix, disabled in COLUMN_ARMS:
            if not write_column_variant(base, CONFIGS / f"{prefix}{suffix}.json",
                                         disabled, src_name, purpose):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
