"""Self-test for the multi-trace validation harness.

The harness that a real packet-level validation needs cannot be exercised
until ns-3 is available, and shipping an unexercised harness is how the
previous single-trace table ended up reporting a number that measured nothing.
This script proves the plumbing end to end without ns-3:

  1. it synthesises traces in the ns-3 trace schema at the step count of a
     training stream, so that the converter, the regime gate and the
     evaluation harness all see a trace in the feature extractor's operating
     regime,
  2. it runs the committed multi-trace driver over them,
  3. it asserts that the regime gate accepted them, that the aggregate table
     covers all eight methods, and that the gate still rejects the bundled
     49-step trace.

The synthesised traces are a harness self-test and nothing more. They are not
packet-level evidence and are not written into any manuscript table; the
regime gate is what tells the difference, and the point of this script is to
exercise the path that the real traces will take.

    python -u artifacts/analysis/selftest_multitrace_harness.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
SCRIPTS = ROOT / "artifacts" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "artifacts" / "analysis"))

from reference_simulator import load_config, simulate_trust_stream  # noqa: E402
from trace_regime import assess_trace_file  # noqa: E402

PY = sys.executable
SEEDS = [2000, 2001, 2002]


def synth_trace(config, seed: int, path: Path) -> None:
    """Write a trace in the ns-3 schema whose step count matches training.

    The mapping from the simulator's trust streams back to the raw trace
    columns is an approximation, and it is deliberately labelled as one: this
    is a plumbing test, not a fidelity test.
    """
    n = int(config.raw["network"]["default_uavs"])
    agents = int(config.raw["network"]["default_thinker_agents"])
    streams, malicious, types = simulate_trust_stream(
        config, seed=seed, n_uavs=n, malicious_ratio=0.30, n_agents=agents)
    steps = streams.shape[0]
    interval = int(config.raw["network"]["trust_update_interval_s"])
    rows = []
    scale = 1000.0
    for t in range(steps):
        for node in range(n):
            t1, t2, t3, t4 = (float(streams[t, node, i]) for i in range(4))
            rows.append({
                "time_s": round((t + 1) * interval, 4),
                "node_id": node,
                "x_m": 0.0,
                "y_m": 0.0,
                "is_malicious": int(malicious[node]),
                "attack_type": str(types[node]),
                "attack_active": int(malicious[node]),
                "tx_packets": int(scale),
                "rx_packets": int(scale * max(0.0, min(1.0, t2))),
                "dropped_packets": int(scale * (1.0 - max(0.0, min(1.0, t2)))),
                "path_deviation_m": round((1.0 - max(0.0, min(1.0, t1))) * 1000.0, 4),
                "energy_ratio": round(max(0.0, min(1.0, t3)), 4),
                "task_assigned": 100,
                "task_completed": int(100 * max(0.0, min(1.0, t4))),
            })
    pd.DataFrame(rows).to_csv(path, index=False)


def convert(raw: Path, out: Path) -> None:
    """Convert a raw ns-3 trace into T1--T5 with the committed converter."""
    rc = subprocess.run(
        [PY, "-u", str(SCRIPTS / "ns3_trace_to_trust.py"),
         "--trace", str(raw), "--output", str(out)],
        cwd=str(ROOT)).returncode
    if rc != 0:
        raise RuntimeError(f"conversion of {raw} failed")


def ensure_matching_policy(config) -> None:
    """Make sure the checkpoint on disk matches the configuration under test.

    The artifact's outputs directory holds the checkpoint of the last arm that
    was run, which is not necessarily the one the trace harness evaluates
    against. Scoring a checkpoint with a different feature width produces a
    shape error at best and a meaningless table at worst, so the self-test
    trains the configuration it needs when the widths disagree.
    """
    import json
    from marl_policy import SHAPE_FEATURE_NAMES, SPATIAL_FEATURE_NAMES

    policy_path = ROOT / "artifacts" / "outputs" / "logs" / "marl_policy.json"
    if policy_path.exists():
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        names = list(policy.get("feature_names") or [])
        wants_spatial = any(n in SPATIAL_FEATURE_NAMES for n in names)
        wants_shape = any(n in SHAPE_FEATURE_NAMES for n in names)
        cfg_shape = bool(config.raw["marl_training"].get("shape_features", False))
        cfg_spatial = bool((config.raw.get("spatial") or {}).get("features", False))
        if wants_shape == cfg_shape and wants_spatial == cfg_spatial:
            print(f"checkpoint on disk matches the configuration "
                  f"({len(names)} features)")
            return
        print(f"checkpoint on disk has {len(names)} features "
              f"(shape={wants_shape}, spatial={wants_spatial}) but the "
              f"configuration needs shape={cfg_shape}, spatial={cfg_spatial}")
    else:
        print("no checkpoint on disk")

    print("training the configuration under test")
    rc = subprocess.run(
        [PY, "-u", str(SCRIPTS / "train_marl_pytorch.py"),
         "--config", "artifacts/configs/default.json"],
        cwd=str(ROOT)).returncode
    if rc != 0:
        raise RuntimeError("training the configuration under test failed")


def main() -> int:
    config = load_config(str(ROOT / "artifacts" / "configs" / "default.json"))
    failures = []
    ensure_matching_policy(config)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        traces = []
        for seed in SEEDS:
            p = tmpdir / f"trace_seed{seed}.csv"
            synth_trace(config, seed, p)
            traces.append(p)
            print(f"synthesised {p.name}: "
                  f"{sum(1 for _ in p.open()) - 1} rows")

        # 1. the regime gate must accept a trace in the training regime.
        #    The gate reads the converted stream, so the committed converter
        #    runs first, exactly as the driver does.
        for p in traces:
            converted = tmpdir / (p.stem + "_streams.csv")
            convert(p, converted)
            v = assess_trace_file(converted, config)
            print(f"\n{v.summary()}")
            if not v.valid:
                failures.append(f"regime gate rejected a {v.n_steps}-step trace")

        # 2. the multi-trace driver must produce an aggregate table
        out_table = tmpdir / "aggregate.csv"
        out_verdict = tmpdir / "verdict.json"
        args = [PY, "-u", str(ROOT / "artifacts" / "analysis" /
                              "multitrace_validation.py")]
        for p in traces:
            args += ["--trace", str(p)]
        args += ["--out-table", str(out_table), "--out-verdict", str(out_verdict)]
        rc = subprocess.run(args, cwd=str(ROOT)).returncode
        if rc != 0:
            failures.append("multi-trace driver failed on valid traces")
        elif not out_table.exists():
            failures.append("multi-trace driver produced no aggregate table")
        else:
            agg = pd.read_csv(out_table)
            print("\naggregate produced by the driver:")
            print(agg.to_string(index=False))
            if len(agg) != 8:
                failures.append(f"aggregate covers {len(agg)} methods, expected 8")
            import json
            verdict = json.loads(out_verdict.read_text())
            if verdict.get("valid_measurements") != len(traces):
                failures.append(
                    f"driver counted {verdict.get('valid_measurements')} valid "
                    f"measurements, expected {len(traces)}")

        # 3. the gate must still reject the bundled short trace
        bundled = ROOT / "artifacts" / "outputs" / "logs" / "ns3_trust_streams.csv"
        if bundled.exists():
            v = assess_trace_file(bundled, config)
            print(f"\nbundled trace: valid={v.valid}")
            if v.valid:
                failures.append("the regime gate accepted the 49-step trace")
        else:
            print("\nbundled trace not present, skipping the rejection check")

    print("\n" + "=" * 80)
    if failures:
        print(f"SELF-TEST FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SELF-TEST PASSED: the multi-trace harness accepts a training-regime "
          "trace, rejects the short one, and produces an aggregate table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
