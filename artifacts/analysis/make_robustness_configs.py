"""Generate the robustness sweep configurations for the spatial scenario.

The spatial scenario is now the manuscript's headline detector result, and a
new headline invites the question a reviewer asks first: does the separation
hold outside the parameter point it was measured at, or was that point lucky.

Each configuration below changes exactly one parameter of the headline
configuration and leaves everything else identical, so a difference in the
result is attributable to that parameter:

  field030 / field060   the amplitude of the radio field
  ratio020 / ratio050   the fraction of the malicious population that
                        transmits replayed benign telemetry

    python -u artifacts/analysis/make_robustness_configs.py
"""

import json
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust\artifacts\configs")
BASE = ROOT / "spatial_position.json"

VARIANTS = {
    "field030": ("spatial", 0.30, None,
                 "the headline configuration with the radio-field amplitude "
                 "lowered from 0.45 to 0.30, everything else unchanged"),
    "field060": ("spatial", 0.60, None,
                 "the headline configuration with the radio-field amplitude "
                 "raised from 0.45 to 0.60, everything else unchanged"),
    "ratio020": ("spatial", None, 0.20,
                 "the headline configuration with the position-attack ratio "
                 "lowered from 0.34 to 0.20, everything else unchanged"),
    "ratio050": ("spatial", None, 0.50,
                 "the headline configuration with the position-attack ratio "
                 "raised from 0.34 to 0.50, everything else unchanged"),
}


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8-sig"))
    for name, (where, amp, ratio, desc) in VARIANTS.items():
        cfg = json.loads(json.dumps(base))
        cfg["description"] = (
            "Robustness sweep: " + desc + ". The generator, the attack mix, "
            "the seeds and the thresholds are those of the headline spatial "
            "configuration.")
        if amp is not None:
            cfg["spatial"]["field_amplitude"] = amp
        if ratio is not None:
            cfg["spatial"]["position_attack_ratio"] = ratio
        path = ROOT / f"spatial_position_{name}.json"
        path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        changed = ("field_amplitude=%s" % amp) if amp is not None else \
                  ("position_attack_ratio=%s" % ratio)
        print(f"wrote {path.name}: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
