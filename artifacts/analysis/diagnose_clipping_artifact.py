"""Is the forger's visibility caused by the field's spread under clipping?

The spatial field is zero-mean, but the generator clips values to [0.02, 0.98].
Adding a zero-mean spread to a distribution that is already near the upper
clip boundary removes more mass from the upper tail than the lower one, so the
clipped mean drifts below the reference. A forger that carries no field spread
does not drift, and is therefore offset from the benign population even though
its behaviour is benign.

This script sets the field amplitude to zero and compares, isolating that
effect from anything else.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

import reference_simulator as rs  # noqa: E402

base_cfg = json.loads((ROOT / "artifacts" / "configs" / "spatial_position.json")
                      .read_text(encoding="utf-8"))
N = int(base_cfg["network"]["default_uavs"])
AGENTS = int(base_cfg["network"]["default_thinker_agents"])


def run(amplitude, tag):
    cfg = json.loads(json.dumps(base_cfg))
    cfg["spatial"]["field_amplitude"] = amplitude
    obj = rs.Config(cfg, ROOT)
    rows = []
    for s in range(200, 208):
        streams, mal, atk = rs.simulate_trust_stream(
            obj, seed=s, n_uavs=N, malicious_ratio=0.30, n_agents=AGENTS)
        atk = np.array([str(a) for a in atk])
        t1 = streams[:, :, 0].mean(axis=0)
        benign = ~mal
        forg = mal & (atk == "position-inconsistent")
        rows.append((s, t1[benign].mean(), t1[benign].std(),
                     t1[forg].mean() if forg.any() else np.nan,
                     float(np.mean(streams[:, :, 0] >= 0.979)),
                     float(np.mean(streams[:, benign, 0] >= 0.979)),
                     float(np.mean(streams[:, forg, 0] >= 0.979)) if forg.any() else np.nan))
    print(f"\n--- field_amplitude = {amplitude} ({tag}) ---")
    print(f"{'seed':>6}{'benign T1':>12}{'sd':>8}{'forger T1':>12}"
          f"{'clip(all)':>12}{'clip(ben)':>12}{'clip(forg)':>12}")
    for r in rows:
        print(f"{r[0]:>6}{r[1]:>12.4f}{r[2]:>8.4f}{r[3]:>12.4f}"
              f"{r[4]:>12.4f}{r[5]:>12.4f}{r[6]:>12.4f}")
    b = np.mean([r[1] for r in rows])
    f = np.mean([r[3] for r in rows])
    sd = np.mean([r[2] for r in rows])
    print(f"  MEAN  benign={b:.4f}  forger={f:.4f}  gap={f - b:+.4f}  "
          f"effect d={(f - b) / sd:+.2f}")


print("=" * 88)
print("Does the zero-mean field survive the clip as a mean shift?")
print("=" * 88)
run(0.5, "current")
run(0.0, "field disabled, everything else identical")
