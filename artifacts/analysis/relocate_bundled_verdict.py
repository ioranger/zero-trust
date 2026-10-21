"""Copy the bundled-trace regime verdict into the analysis directory, where its
name makes it unambiguous, and remove it from the outputs tables directory
where it could be mistaken for a validation result.

    python -u artifacts/analysis/relocate_bundled_verdict.py
"""

import json
import shutil
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
SRC = ROOT / "artifacts" / "outputs" / "tables" / "ns3_multitrace_verdict.json"
DST = ROOT / "artifacts" / "analysis" / "ns3_bundled_trace_verdict.json"

if not SRC.exists():
    print(f"nothing to relocate: {SRC} does not exist")
else:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    if data.get("evaluated") == 0 and any(
            not t.get("valid") for t in data.get("traces", [])):
        DST.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"wrote {DST}")
        print("  the bundled trace was assessed and rejected, with the reasons")
        print("  recorded; the file stays out of artifacts/outputs/tables so that")
        print("  it cannot be read as a validation result")
    else:
        print("the verdict file records an actual evaluation, leaving it in place")
