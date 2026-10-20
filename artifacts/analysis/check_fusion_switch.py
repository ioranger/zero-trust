"""Check that the fusion-mechanism switch is a strict no-op for every
configuration that does not ask for it, and that it does what it says when it
is on.

Training and inference now share one function -- marl_policy.baseline_feature_view --
so the width a baseline is trained at is necessarily the width it is scored at.
This script exercises that function directly for every configuration in the
matrix, and checks the published protocol against the switch-on protocol.

    python -u artifacts/analysis/check_fusion_switch.py
"""

import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(r"F:\zero trust\zero-trust\artifacts\scripts")
sys.path.insert(0, str(SCRIPTS))

from marl_policy import (  # noqa: E402
    baseline_feature_view,
    baselines_get_spatial_block,
    extract_marl_policy_features,
    resolve_spatial_adjacency,
)
from reference_simulator import load_config, simulate_trust_stream  # noqa: E402

ROOT = Path(r"F:\zero trust\zero-trust")
CONFIGS = [
    "artifacts/configs/default.json",
    "artifacts/configs/spatial_position.json",
    "artifacts/configs/spatial_position_nofeat.json",
    "artifacts/configs/spatial_position_13dim.json",
]


def widths(cfg, n=40):
    """Return (S-TIM width, baseline width) under the config's own switch.

    The baseline view is queried twice: once bare, and once with the
    neighbourhood adjacency passed in explicitly, the way the training path
    calls it. Both must give the same answer, otherwise the published protocol
    could be widened by a caller that happens to hold an adjacency.
    """
    streams, _, _ = simulate_trust_stream(
        cfg, seed=100, n_uavs=n, malicious_ratio=0.3,
        n_agents=int(cfg.raw["network"]["default_thinker_agents"]))
    adj = resolve_spatial_adjacency(cfg, 100, n, 0.3)
    x_stim, _ = extract_marl_policy_features(
        cfg, streams, 5, spatial_adjacency=adj)
    x_bare, _ = baseline_feature_view(
        cfg, streams, 5, seed=100, n_uavs=n, malicious_ratio=0.3)
    x_with_adj, _ = baseline_feature_view(
        cfg, streams, 5, seed=100, n_uavs=n, malicious_ratio=0.3,
        spatial_adjacency=adj)
    assert x_bare.shape[1] == x_with_adj.shape[1], (
        f"baseline width depends on whether the caller passes an adjacency: "
        f"{x_bare.shape[1]} vs {x_with_adj.shape[1]}")
    return x_stim.shape[1], x_bare.shape[1]


def main() -> int:
    print("=" * 96)
    print("FUSION SWITCH -- default-off no-op check")
    print("=" * 96)
    bad = 0
    for rel in CONFIGS:
        cfg = load_config(str(ROOT / rel))
        flag = baselines_get_spatial_block(cfg)
        w_stim, w_base = widths(cfg)
        note = ("per-node baselines get the neighbourhood block"
                if flag else "per-node baselines are withheld the block")
        print(f"\n{rel}")
        print(f"  switch = {flag}")
        print(f"  S-TIM width = {w_stim}, baseline width = {w_base}   ({note})")
        if not flag and w_stim == w_base and w_stim > 18:
            print("  -> UNEXPECTED: with the switch off the baselines must not "
                  "receive the neighbourhood block")
            bad += 1
        elif not flag:
            print("  -> OK")

    # Positive control: same config, switch on.
    print("\n" + "=" * 96)
    print("POSITIVE CONTROL -- same config with the switch forced on")
    print("=" * 96)
    src = json.loads((ROOT / "artifacts/configs/spatial_position.json")
                     .read_text(encoding="utf-8-sig"))
    src.setdefault("fairness", {})["learned_baselines_get_spatial_block"] = True
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "fusion_on.json"
        p.write_text(json.dumps(src, indent=2), encoding="utf-8")
        cfg = load_config(str(p))
        w_stim, w_base = widths(cfg)
        print(f"  switch = {baselines_get_spatial_block(cfg)}")
        print(f"  S-TIM width = {w_stim}, baseline width = {w_base}")
        ok = (w_stim == w_base == 23)
        print(f"  -> {'OK' if ok else 'MISMATCH'}")
        if not ok:
            bad += 1

    print("\n" + ("ALL CHECKS PASSED" if bad == 0 else f"{bad} CHECK(S) FAILED"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
