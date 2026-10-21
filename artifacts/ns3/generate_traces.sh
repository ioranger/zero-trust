#!/bin/bash
# Generate packet-level traces from the UAV trust scenario.
#
# Runs inside an ns-3 environment (the official Docker image, or an ns-3
# checkout under WSL). The scenario is copied into ns-3's scratch directory
# first, because ns-3 only runs scenarios it knows about.
#
# The mission duration is chosen so that the trace lands in exactly the
# feature extractor's training regime. The harness rewrites the warm-up to
# one fifth of the trace, so a 500-step trace with the scenario's 10-second
# interval leaves 100 warm-up steps and 400 post-warm-up steps, which is the
# same geometry the model was trained on. A shorter trace would not be a
# measurement at all, and artifacts/analysis/trace_regime.py refuses to treat
# it as one.
#
# Environment:
#   SCENARIO_SRC   path to mtim_uav_trust.cc (default ../mtim_uav_trust.cc)
#   OUTDIR         where the CSV traces are written (default /out)
#   SEEDS          space-separated list of seeds
#   DURATION       mission duration in seconds (default 5000 -> 500 steps)
#   NUAVS          number of UAV nodes (default 15)
#   MALICIOUS_RATIO fraction of malicious nodes (default 0.30)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO_SRC="${SCENARIO_SRC:-$SCRIPT_DIR/mtim_uav_trust.cc}"
OUTDIR="${OUTDIR:-/out}"
SEEDS="${SEEDS:-2000 2001 2002 2003 2004}"
DURATION="${DURATION:-5000}"
NUAVS="${NUAVS:-15}"
MALICIOUS_RATIO="${MALICIOUS_RATIO:-0.30}"

if [ ! -f "$SCENARIO_SRC" ]; then
    echo "scenario source not found: $SCENARIO_SRC" >&2
    exit 1
fi

# Locate the ns-3 root: the directory that contains the ./ns3 runner.
NS3_ROOT="${NS3_ROOT:-$(cd "$SCRIPT_DIR" && pwd)}"
while [ "$NS3_ROOT" != "/" ] && [ ! -x "$NS3_ROOT/ns3" ]; do
    NS3_ROOT="$(dirname "$NS3_ROOT")"
done
if [ ! -x "$NS3_ROOT/ns3" ]; then
    echo "could not find the ns-3 runner; set NS3_ROOT" >&2
    exit 1
fi

mkdir -p "$NS3_ROOT/scratch" "$OUTDIR"
cp "$SCENARIO_SRC" "$NS3_ROOT/scratch/mtim_uav_trust.cc"

INTERVAL=10
STEPS=$((DURATION / INTERVAL))
echo "ns-3 root      : $NS3_ROOT"
echo "duration        : ${DURATION}s -> ${STEPS} steps at ${INTERVAL}s"
echo "warm-up         : $((STEPS / 5)) steps, leaving $((STEPS - STEPS / 5)) post-warm-up"
echo "seeds           : $SEEDS"
echo "output directory: $OUTDIR"
echo

cd "$NS3_ROOT"

for seed in $SEEDS; do
    out="$OUTDIR/trace_seed${seed}.csv"
    echo "--- seed $seed -> $out"
    ./ns3 run "scratch/mtim_uav_trust --nUavs=${NUAVS} --maliciousRatio=${MALICIOUS_RATIO} --seed=${seed} --duration=${DURATION} --csv=${out}"
    if [ ! -s "$out" ]; then
        echo "trace for seed $seed is empty" >&2
        exit 1
    fi
    rows=$(wc -l < "$out")
    echo "    $rows rows"
done

echo
echo "traces written to $OUTDIR"
