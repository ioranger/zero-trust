"""Inspect the structure of a per-seed attack-type metrics log.

Answers: how many seeds, which attack types, how many rows per
(seed, method, attack_type) -- i.e. whether the file carries duplicates that
have to be collapsed before any mean is computed.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")


def main() -> int:
    path = Path(sys.argv[1])
    df = pd.read_csv(path)
    print(f"file      : {path}")
    print(f"rows      : {len(df)}")
    print(f"columns   : {list(df.columns)}")
    for col in ("seed", "n_uavs", "n_agents", "malicious_ratio", "method", "attack_type"):
        if col in df.columns:
            vals = sorted(df[col].dropna().unique().tolist())
            show = vals if len(vals) <= 12 else vals[:6] + ["..."] + vals[-3:]
            print(f"{col:<16}: n={len(vals)}  {show}")
    key = [c for c in ("seed", "method", "attack_type") if c in df.columns]
    if key:
        dup = df.duplicated(subset=key).sum()
        grp = df.groupby(key, dropna=False).size()
        print(f"duplicate rows on {key}: {dup}")
        print(f"rows per key: min={grp.min()} max={grp.max()} median={grp.median()}")
        print(f"unique keys : {len(grp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
