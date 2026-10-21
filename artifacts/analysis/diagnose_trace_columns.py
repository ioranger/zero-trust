"""Diagnose the degenerate columns in a converted trace."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))
sys.path.insert(0, str(ROOT / "artifacts" / "analysis"))

from evaluate_trace_driven import config_for_trace, trace_to_streams  # noqa: E402
from marl_policy import extract_marl_policy_features  # noqa: E402
from reference_simulator import load_config  # noqa: E402

cfg = load_config(str(ROOT / "artifacts" / "configs" / "default.json"))

for name in sys.argv[1:]:
    p = ROOT / "artifacts" / "outputs" / "logs" / "ns3_multitrace" / (name + "_streams.csv")
    if not p.exists():
        print(f"{name}: missing")
        continue
    d = pd.read_csv(p)
    streams, labels, types = trace_to_streams(d)
    tcfg = config_for_trace(cfg, streams.shape[0])
    xs, names = extract_marl_policy_features(tcfg, streams, 5)
    rng = xs.max(axis=0) - xs.min(axis=0)
    deg = [names[i] for i in range(xs.shape[1]) if rng[i] < 1e-12]
    print(f"=== {name}: {len(deg)} degenerate -> {deg}")
    post = streams[tcfg.warmup_steps:]
    for i, ch in enumerate(("T1", "T2", "T3", "T4", "T5")):
        v = post[:, :, i]
        print(f"    {ch}: min {v.min():.3f} max {v.max():.3f} "
              f"mean {v.mean():.3f}  per-node mean range "
              f"{v.mean(axis=0).max() - v.mean(axis=0).min():.4f}")
