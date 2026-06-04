#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert ns-3 UAV trace CSV to MTIM T1--T5 trust streams.")
    parser.add_argument("--trace", required=True, help="CSV emitted by artifacts/ns3/mtim_uav_trust.cc")
    parser.add_argument("--output", default="artifacts/outputs/logs/ns3_trust_streams.csv")
    parser.add_argument("--history-beta", type=float, default=0.84)
    return parser.parse_args()


def normalize_inverse(series: pd.Series, q_hi: float = 0.95) -> pd.Series:
    hi = float(series.quantile(q_hi))
    if hi <= 0:
        return pd.Series(np.ones(len(series)), index=series.index)
    return (1.0 - series / hi).clip(0.0, 1.0)


def main() -> None:
    args = parse_args()
    trace = pd.read_csv(args.trace)
    required = {
        "time_s",
        "node_id",
        "tx_packets",
        "rx_packets",
        "dropped_packets",
        "path_deviation_m",
        "energy_ratio",
        "task_assigned",
        "task_completed",
        "is_malicious",
        "attack_type",
    }
    missing = required - set(trace.columns)
    if missing:
        raise ValueError(f"Trace is missing required columns: {sorted(missing)}")

    rows = []
    history = {}
    for time_s, part in trace.sort_values(["time_s", "node_id"]).groupby("time_s", sort=True):
        part = part.copy()
        pdr = (part["rx_packets"] + 1.0) / (part["tx_packets"] + 1.0)
        drop_ratio = part["dropped_packets"] / (part["tx_packets"] + part["dropped_packets"] + 1.0)
        task_ratio = (part["task_completed"] + 1.0) / (part["task_assigned"] + 1.0)
        path_score = normalize_inverse(part["path_deviation_m"])
        t1 = (0.55 * path_score + 0.45 * (1.0 - drop_ratio)).clip(0.0, 1.0)
        t2 = (0.70 * pdr + 0.30 * (1.0 - drop_ratio)).clip(0.0, 1.0)
        t3 = part["energy_ratio"].clip(0.0, 1.0)
        t4 = task_ratio.clip(0.0, 1.0)

        for idx, (_, row) in enumerate(part.iterrows()):
            node = int(row["node_id"])
            instant = float(np.mean([t1.iloc[idx], t2.iloc[idx], t3.iloc[idx], t4.iloc[idx]]))
            prev = history.get(node, 0.77)
            hist = float(args.history_beta * prev + (1.0 - args.history_beta) * instant)
            history[node] = hist
            rows.append(
                {
                    "time_s": float(time_s),
                    "node_id": node,
                    "is_malicious": int(row["is_malicious"]),
                    "attack_type": str(row["attack_type"]),
                    "T1": float(t1.iloc[idx]),
                    "T2": float(t2.iloc[idx]),
                    "T3": float(t3.iloc[idx]),
                    "T4": float(t4.iloc[idx]),
                    "T5": hist,
                }
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"Wrote {len(rows)} trust-stream rows to {output}")


if __name__ == "__main__":
    main()
