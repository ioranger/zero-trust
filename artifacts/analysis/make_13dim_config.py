"""Generate the 13-dim marginal-only control config for the position scenario.

The three-row complementarity table needs one arm per feature-block
combination, all sharing the same generator, attack mix and seeds:

    13-dim  marginal only                      shape_features=false, spatial.features=false
    18-dim  marginal + shape                   shape_features=true,  spatial.features=false
    23-dim  marginal + shape + spatial         shape_features=true,  spatial.features=true

The 18-dim and 23-dim arms already exist as hand-written configs. This script
derives the 13-dim one from the 18-dim one so the three differ in exactly the
feature flags and in nothing else.
"""

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust\artifacts\configs")
SRC = ROOT / "spatial_position_nofeat.json"
DST = ROOT / "spatial_position_13dim.json"

DESC = ("Marginal-feature-only control for the telemetry-forging scenario: the "
        "temporal-shape block and the spatial neighbourhood block are both off, "
        "so the model sees the 13 marginal aggregates and nothing else. Same "
        "generator, attack mix, seeds and thresholds as spatial_position.json; "
        "differs only in which feature blocks are supplied.")

cfg = json.loads(SRC.read_text(encoding="utf-8-sig"))
cfg["marl_training"]["shape_features"] = False
cfg["spatial"]["features"] = False
cfg["description"] = DESC

DST.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

chk = json.loads(DST.read_text(encoding="utf-8"))
print(f"wrote {DST}")
print(f"  shape_features   = {chk['marl_training']['shape_features']}")
print(f"  spatial.features = {chk['spatial']['features']}")
print(f"  spatial.enabled  = {chk['spatial']['enabled']}")
print(f"  base_seed        = {chk['base_seed']}")
print(f"  evaluation_seeds = {chk['evaluation_seeds']}")
print(f"  position ratio   = {chk['spatial']['position_attack_ratio']}")
