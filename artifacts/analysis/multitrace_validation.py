"""Multi-trace validation: evaluate the models on several packet-level traces
and report only what those traces can actually measure.

The single-trace table the artifact shipped was produced from a 49-step trace,
which is shorter than the feature extractor's minimum window, so six of the
eighteen input columns were constant across every node and the numbers
measured a harness mismatch rather than the detector. This driver exists so
that the multi-seed validation the manuscript calls for can be run without
repeating that mistake:

  1. each raw trace is converted with the committed converter,
  2. the feature regime of the converted trace is assessed BEFORE its numbers
     are collected, and a trace that is not a valid measurement is excluded
     with the reason recorded,
  3. the surviving traces are evaluated with the committed harness, and
  4. the aggregate table states how many of the traces were valid measurements,
     so a table built from two of three traces cannot be read as three.

    python -u artifacts/analysis/multitrace_validation.py \
        --trace artifacts/outputs/logs/ns3_packet_trace.csv

    python -u artifacts/analysis/multitrace_validation.py \
        --trace-glob "artifacts/outputs/logs/ns3_trace_seed*.csv" \
        --out-table artifacts/outputs/tables/ns3_multitrace.csv
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
SCRIPTS = ROOT / "artifacts" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "artifacts" / "analysis"))

from trace_regime import assess_trace_file  # noqa: E402

PY = sys.executable


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", action="append", default=[],
                    help="a raw ns-3 trace CSV; may be repeated")
    ap.add_argument("--trace-glob", default=None,
                    help="a glob over raw ns-3 trace CSVs")
    ap.add_argument("--config", default="artifacts/configs/default.json")
    ap.add_argument("--out-table",
                    default="artifacts/outputs/tables/ns3_multitrace.csv")
    ap.add_argument("--out-verdict",
                    default="artifacts/outputs/tables/ns3_multitrace_verdict.json")
    ap.add_argument("--keep-invalid", action="store_true",
                    help="report the invalid traces anyway, clearly marked")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    traces = [Path(t) for t in args.trace]
    if args.trace_glob:
        traces.extend(sorted(Path().glob(args.trace_glob)))
    traces = [t for t in traces if t.exists()]
    if not traces:
        print("no traces given")
        return 2

    work = ROOT / "artifacts" / "outputs" / "logs" / "ns3_multitrace"
    work.mkdir(parents=True, exist_ok=True)

    rows, verdicts = [], []
    for trace in traces:
        print("=" * 100)
        print(f"trace: {trace}")
        print("=" * 100)

        converted = work / (trace.stem + "_streams.csv")
        rc = subprocess.run(
            [PY, "-u", str(SCRIPTS / "ns3_trace_to_trust.py"),
             "--trace", str(trace), "--output", str(converted)],
            cwd=str(ROOT)).returncode
        if rc != 0:
            print("  conversion failed, trace skipped")
            verdicts.append({"trace": str(trace), "valid": False,
                             "reasons": ["conversion failed"]})
            continue

        verdict = assess_trace_file(converted)
        print(verdict.summary())
        verdicts.append({"trace": str(trace),
                         "converted": str(converted),
                         "n_steps": verdict.n_steps,
                         "post_warmup_steps": verdict.post_warmup_steps,
                         "valid": verdict.valid,
                         "reasons": verdict.reasons})
        if not verdict.valid and not args.keep_invalid:
            print("  -> excluded: not a valid measurement")
            continue

        table = work / (trace.stem + "_metrics.csv")
        rc = subprocess.run(
            [PY, "-u", str(SCRIPTS / "evaluate_trace_driven.py"),
             "--config", args.config, "--trace", str(converted),
             "--seed", "1000", "--output", str(table)],
            cwd=str(ROOT)).returncode
        if rc != 0:
            print("  evaluation failed, trace skipped")
            continue
        d = pd.read_csv(table)
        d["trace_name"] = trace.stem
        d["valid_measurement"] = verdict.valid
        rows.append(d)
        print(f"  evaluated -> {table}")

    if not rows:
        print("\nno trace produced a table")
        out = Path(args.out_verdict)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"traces": verdicts, "evaluated": 0},
                                  indent=2), encoding="utf-8")
        return 1

    all_rows = pd.concat(rows, ignore_index=True)
    # A packet trace carries no task-allocation simulation, so there is no
    # task-success proxy to report here. The column is named for what it is.
    agg = (all_rows.groupby("method")
           .agg(traces=("accuracy", "size"),
                accuracy=("accuracy", "mean"), accuracy_sd=("accuracy", "std"),
                f_score=("f_score", "mean"), f_score_sd=("f_score", "std"),
                precision=("precision", "mean"), recall=("recall", "mean"),
                tp=("tp", "sum"), fp=("fp", "sum"), fn=("fn", "sum"))
           .reset_index())
    agg = agg.fillna(0.0)

    valid_traces = sum(1 for v in verdicts if v.get("valid"))
    print("\n" + "=" * 100)
    print(f"MULTI-TRACE AGGREGATE -- {valid_traces} of {len(verdicts)} traces "
          f"were valid measurements")
    print("=" * 100)
    print(agg.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    out_table = Path(args.out_table)
    out_table.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(out_table, index=False)
    all_rows.to_csv(out_table.with_name(out_table.stem + "_per_trace.csv"),
                    index=False)

    out_verdict = Path(args.out_verdict)
    out_verdict.parent.mkdir(parents=True, exist_ok=True)
    out_verdict.write_text(json.dumps(
        {"traces": verdicts, "evaluated": len(rows),
         "valid_measurements": valid_traces,
         "note": "a trace excluded here was shorter than the feature "
                 "extractor's minimum window or had degenerate input columns, "
                 "so its numbers would measure a harness mismatch"},
        indent=2), encoding="utf-8")
    print(f"\nwrote {out_table}")
    print(f"wrote {out_verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
