"""Create the configuration for the position-attack prototype.

Based on configs/spatial_features.json with the telemetry-forging attacker
enabled. Everything else is inherited from the spatial configuration that was
already reproduced, so the only difference from the spatial run is the new
attack class.
"""

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
CFG = ROOT / "artifacts" / "configs"

base = json.loads((CFG / "spatial_features.json").read_text(encoding="utf-8"))
base["description"] = (
    "Spatial generator with the telemetry-forging attacker enabled. A fraction "
    "of the malicious nodes report channels indistinguishable from the benign "
    "population but are placed where the RF field differs from what they "
    "report, so only a neighbourhood-relative statistic can see them. This is "
    "the configuration that tests whether the spatial block is complementary "
    "to the behaviour channels rather than an addition to them.")
base["spatial"]["position_attack_ratio"] = 0.34
base["spatial"]["features"] = True
out = CFG / "spatial_position.json"
out.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
print("spatial block:")
for k, v in base["spatial"].items():
    print(f"  {k:<28} {v}")
