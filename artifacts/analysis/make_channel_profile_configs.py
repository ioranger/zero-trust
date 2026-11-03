"""Generate the channel-focused scenario configurations.

The published generator drives all four observable channels down together, so
the evidence a removed dimension carries is largely still present in the
dimensions that were kept. The manuscript's threat model says something
stronger -- an adversary may manipulate any subset of the five dimensions
independently -- and the channel-focused scenario is that case: every
attacker manipulates exactly one dimension and is bit-identical to a benign
node on the other four.

The scenario also uses a dimension-aligned representation: four columns per
dimension, each computed from that dimension alone, so no dimension is priced
through a different number of columns than another. The temporal-shape block
is off in this scenario because it is computed on T1 and T4 and would carry
one dimension's evidence into another dimension's arm.

Every generated configuration differs from configs/default.json in the
channel_profile block, in marl_training.shape_features and, for the
leave-one-dimension-out arms, in marl_training.disabled_factors. The
generator, the seeds, the epochs, the early-stopping rule, the auxiliary
weights and the decision threshold are the published ones.

Usage:
    python -u artifacts/analysis/make_channel_profile_configs.py
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "artifacts" / "configs"

BASE = "default.json"
PREFIX = "channel_profile"
FACTORS = ["T1", "T2", "T3", "T4", "T5"]

# The arm that keeps only the two dimensions the published representation is
# built on. Under the channel-focused adversary it also removes the evidence
# about the three attackers that use the other dimensions.
COMBINED = ["T2", "T3", "T5"]

# The dimension-budget arms: the model observes a subset of the five
# dimensions and nothing else. The single-dimension arms price a deployment
# that observes one channel, these price every two- and three-dimension
# subset, and the leave-one-dimension-out arms of the published study price
# the four-dimension case. Together the five budgets give the series the
# manuscript reports.
#
# Every non-empty subset of the five dimensions is covered, so the study is
# exhaustive over the observation budgets it claims to price. The one
# subset that is not written here is {T1, T4}, because the
# leave-three-dimensions-out configuration already is that arm under the
# name configs/channel_profile_drop_T2_T3_T5.json.
SKIP_SUBSETS = {("T1", "T4")}


def subsets(size: int) -> list[tuple[str, ...]]:
    return [c for c in combinations(FACTORS, size) if c not in SKIP_SUBSETS]

SCENARIO = {
    "enabled": True,
    # How far an attacker drives the dimension it manipulates. The
    # depression is the same on every dimension, so no dimension is priced
    # through an easier or a harder attack than another.
    "depression": 0.40,
    "patterns": ["constant", "dormant", "on-off"],
}

BASE_CONFIG: dict = {}


def write_variant(disabled: list[str], name: str, purpose: str) -> bool:
    cfg = json.loads(json.dumps(BASE_CONFIG))
    cfg["marl_training"]["disabled_factors"] = disabled
    cfg["description"] = purpose
    dst = CONFIGS / name
    dst.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    chk = json.loads(dst.read_text(encoding="utf-8"))
    same = all(chk[k] == BASE_CONFIG[k] for k in BASE_CONFIG
               if k not in ("marl_training", "description", "channel_profile"))
    mt_same = all(chk["marl_training"][k] == BASE_CONFIG["marl_training"][k]
                  for k in BASE_CONFIG["marl_training"]
                  if k != "disabled_factors")
    print(f"wrote {dst.name}")
    print(f"    disabled_factors = {chk['marl_training']['disabled_factors']}"
          f"   everything else identical: {same and mt_same}")
    return same and mt_same


def main() -> int:
    global BASE_CONFIG
    BASE_CONFIG = json.loads(
        (CONFIGS / BASE).read_text(encoding="utf-8-sig"))
    BASE_CONFIG["channel_profile"] = json.loads(json.dumps(SCENARIO))
    BASE_CONFIG["marl_training"]["shape_features"] = False
    BASE_CONFIG["description"] = (
        "Channel-focused adversary scenario: every attacker manipulates "
        "exactly one trust dimension and is indistinguishable from a benign "
        "node on the other four, so the dimension an attacker manipulates is "
        "the only place where evidence about it exists. The representation "
        "is dimension-aligned (four columns per dimension, each computed "
        "from that dimension alone) and the temporal-shape block is off, "
        "because it is computed on T1 and T4 only. Identical to "
        f"configs/{BASE} in the generator settings, the seeds, the epochs, "
        "the early-stopping rule, the auxiliary weights and the decision "
        "threshold."
    )

    if not write_variant([], f"{PREFIX}.json", BASE_CONFIG["description"]):
        return 1
    for factor in FACTORS:
        purpose = (
            "Leave-one-dimension-out arm of the channel-focused scenario: "
            f"the proposed model never sees {factor}. Identical to "
            f"configs/{PREFIX}.json in every other respect. The rule-based "
            "comparators keep all five dimensions, so the arm measures what "
            "the removed dimension is worth to the proposed model alone."
        )
        if not write_variant([factor], f"{PREFIX}_drop_{factor}.json", purpose):
            return 1
    purpose = (
        "Leave-three-dimensions-out arm of the channel-focused scenario: "
        "only T1 and T4 are kept. It answers the reviewer question directly, "
        "because it is the smallest factor set that can plausibly keep the "
        "result in the published representation."
    )
    if not write_variant(COMBINED, f"{PREFIX}_drop_T2_T3_T5.json", purpose):
        return 1
    for factor in FACTORS:
        purpose = (
            "Single-dimension arm of the channel-focused scenario: the "
            f"proposed model sees only {factor} and nothing else. Identical "
            f"to configs/{PREFIX}.json in every other respect. The arm "
            "answers the other half of the joint-optimality question: a "
            "deployment that observes one dimension cannot see the four "
            "attackers that use the other four."
        )
        if not write_variant([f for f in FACTORS if f != factor],
                             f"{PREFIX}_only_{factor}.json", purpose):
            return 1
    for size in (2, 3):
        for combo in subsets(size):
            name = "_".join(combo)
            kept_text = " and ".join(combo)
            purpose = (
                f"{size}-dimension arm of the channel-focused scenario: the "
                f"proposed model sees only {kept_text} and nothing else, so "
                "it cannot see the attackers that use the dimensions it does "
                f"not observe. Identical to configs/{PREFIX}.json in every "
                "other respect."
            )
            if not write_variant([f for f in FACTORS if f not in combo],
                                 f"{PREFIX}_only_{name}.json", purpose):
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
