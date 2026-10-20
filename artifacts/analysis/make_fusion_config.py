"""Generate the fusion-mechanism ablation config.

Same generator, attack mix, seeds and feature blocks as spatial_position.json
(23 dims for the proposed model). The single difference is that LR-Trust and
MLP-Trust are also handed the neighbourhood block, so all three learners see
the identical feature vector and any difference between them comes from how
the blocks are combined.

This arm is a control of the proposed model, not a competitor: the main
protocol deliberately withholds the neighbourhood block from the per-node
baselines, and that protocol is untouched.
"""

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust\artifacts\configs")
SRC = ROOT / "spatial_position.json"
DST = ROOT / "spatial_position_fusion.json"

DESC = ("Fusion-mechanism ablation. Identical to spatial_position.json in "
        "generator, attack mix, seeds and feature blocks, except that the "
        "learned per-node baselines are also handed the neighbourhood block. "
        "All three learners therefore consume the identical 23-dimensional "
        "vector, and any difference between them is attributable to how the "
        "blocks are combined rather than to what was available. This is a "
        "control of the proposed model; the main protocol withholds the block "
        "from the per-node baselines and is not modified.")

cfg = json.loads(SRC.read_text(encoding="utf-8-sig"))
cfg.setdefault("fairness", {})["learned_baselines_get_spatial_block"] = True
cfg["description"] = DESC

DST.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

chk = json.loads(DST.read_text(encoding="utf-8"))
print(f"wrote {DST}")
print(f"  shape_features   = {chk['marl_training']['shape_features']}")
print(f"  spatial.features = {chk['spatial']['features']}")
print(f"  baseline switch  = {chk['fairness']['learned_baselines_get_spatial_block']}")
print(f"  evaluation_seeds = {chk['evaluation_seeds']}")
print(f"  base_seed        = {chk['base_seed']}")
