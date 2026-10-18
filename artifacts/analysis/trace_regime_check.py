"""Confirm the trace path feeds the model a feature regime it never saw.

Hypothesis: evaluate_trace_driven.py rewrites the warm-up for a 49-step
trace, leaving 40 post-warm-up steps. The shape block bails out to zeros when
fewer than 122 steps are available, so all five shape features are constant on
the trace while the model was trained on non-degenerate values. The marginal
block is also computed over a 40-step window instead of 400, with early/late
windows overlapping completely.

If that holds, the trace result measures a harness mismatch, not the detector's
robustness, and the manuscript should say so instead of reporting it as an
external-validity failure of the method.
"""
import copy
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ART = Path(r"F:\zero trust\zero-trust\artifacts")
sys.path.insert(0, str(ART / "scripts"))
sys.path.insert(0, r"F:\zero trust\zero-trust\artifacts\scripts")

from evaluate_trace_driven import config_for_trace, trace_to_streams  # noqa: E402
from marl_policy import (  # noqa: E402
    _SHAPE_ACF_MAX_LAG,
    extract_marl_policy_features,
    extract_shape_features,
)
from reference_simulator import load_config, simulate_trust_stream  # noqa: E402

config = load_config(ART / "configs" / "default.json")
trace = pd.read_csv(ART / "outputs" / "logs" / "ns3_trust_streams.csv")
streams, labels, types = trace_to_streams(trace)
tcfg = config_for_trace(config, streams.shape[0])

print("=" * 84)
print("trace feature regime vs training regime")
print("=" * 84)
print(f"  trace steps                     : {streams.shape[0]}")
print(f"  training steps                  : {config.steps}")
print(f"  trace warm-up steps used        : {tcfg.warmup_steps}")
print(f"  training warm-up steps          : {config.warmup_steps}")
print(f"  trace post-warm-up steps        : {streams.shape[0] - tcfg.warmup_steps}")
print(f"  training post-warm-up steps     : {config.steps - config.warmup_steps}")
print(f"  shape block needs at least      : {_SHAPE_ACF_MAX_LAG + 2} steps")
print()

tshape = extract_shape_features(tcfg, streams)
print("shape block on the trace (per node, first 5)")
print("-" * 84)
for i in range(min(5, streams.shape[1])):
    lab = "MAL" if labels[i] else "ben"
    print(f"  node {i:2d} ({lab:4s}) {np.array2string(tshape[i], precision=4)}")
print(f"  all-zero across every node: {bool(np.all(tshape == 0.0))}")
print()

# training regime, same generator
st, mal, _ = simulate_trust_stream(config, seed=100, n_uavs=streams.shape[1],
                                   malicious_ratio=0.30, n_agents=5)
sshape = extract_shape_features(config, st)
print("shape block on simulator streams (same generator, training regime)")
print("-" * 84)
for i in range(min(5, streams.shape[1])):
    lab = "MAL" if mal[i] else "ben"
    print(f"  node {i:2d} ({lab:4s}) {np.array2string(sshape[i], precision=4)}")
print(f"  all-zero across every node: {bool(np.all(sshape == 0.0))}")
print()

# window overlap inside the 13 marginal block
post_trace = streams.shape[0] - tcfg.warmup_steps
print("marginal block window geometry")
print("-" * 84)
print(f"  trace    post={post_trace:3d}  early[:100] late[-100:] overlap="
      f"{max(0, 200 - post_trace)} steps")
print(f"  training post={config.steps - config.warmup_steps:3d}  early[:100] "
      f"late[-100:] overlap=0 steps")
print(f"  trace    recent = mean of last min(120, {streams.shape[0]}) steps "
      f"-> covers {min(120, streams.shape[0])}/{streams.shape[0]} of the trace "
      f"(warm-up included)")
print()

# feature-space shift under the standardisation the model applies
xs_tr, names = extract_marl_policy_features(tcfg, streams, 5)
xs_trn, _ = extract_marl_policy_features(config, st, 5)
mean, std = xs_trn.mean(axis=0), xs_trn.std(axis=0) + 1e-6
z = (xs_tr - mean) / std

# A column is degenerate on the trace when every node gets the same value.
# Compare column-wise on the 18-dim matrix itself, not against the 5-dim block.
per_col_range = xs_tr.max(axis=0) - xs_tr.min(axis=0)
degenerate = [i for i in range(xs_tr.shape[1]) if per_col_range[i] < 1e-12]
print(f"columns constant across every node on the trace: "
      f"{len(degenerate)} of {xs_tr.shape[1]}")
print(f"  which are: {[names[i] for i in degenerate]}")
print()
print("  standardised values on the degenerate columns: "
      f"{np.unique(np.round(z[:, degenerate], 3)) if degenerate else 'n/a'}")
print()
print("  A sigmoid trained to separate benign from malicious on non-degenerate")
print("  shape values receives, for those columns, one fixed input on every")
print("  node. Whether that fixed input falls on the malicious side is a")
print("  property of the training normalisation, not of the trace.")
print()
print("  the remaining columns are not degenerate but are still computed over a")
print("  40-step window with early/late fully overlapped and a recent mean that")
print("  includes warm-up -- a regime no training stream ever presented.")