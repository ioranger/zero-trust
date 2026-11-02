"""Recompute the worked examples of the cross-swarm prompt template.

Every number in the template's examples is produced here from the stated
rules, so the document and the arithmetic cannot drift apart. The script parses
the `CHECK` lines and the `T=`/`SIGMA=` lines out of the document itself and
compares them with what the rules produce.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
DOC = ROOT / "artifacts" / "ops" / "prompts" / "inter_swarm_trust_exchange.md"

GAMMA = 2.0
SIGMA0 = 0.1
EPS_MAX = 0.12
OMEGA = {"T1": 0.322, "T2": 0.138, "T3": 0.080, "T4": 0.321, "T5": 0.140}
ORDER = ["T1", "T2", "T3", "T4", "T5"]
THETA_HIGH, THETA_LOW, SIGMA_TH = 7.0, 4.0, 1.0

CASES = {
    "8.1": {
        "local": {"T1": 0.85, "T2": 0.73, "T3": 0.79, "T4": 0.78, "T5": 0.788},
        "peer": {"T1": 0.83, "T2": 0.75, "T3": 0.77, "T4": 0.79, "T5": 0.787},
    },
    "8.2": {
        "local": {"T1": 0.85, "T2": 0.73, "T3": 0.79, "T4": 0.78, "T5": 0.788},
        "peer": {"T1": 0.63, "T2": 0.75, "T3": 0.77, "T4": 0.64, "T5": 0.700},
    },
    "8.3": {
        "local": {"T1": 0.778, "T2": 0.747, "T3": 0.722, "T4": 0.762, "T5": 0.752},
        "peer": {"T1": 0.774, "T2": 0.749, "T3": 0.721, "T4": 0.766, "T5": 0.751},
    },
}

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def compute(case: dict):
    local, peer = case["local"], case["peer"]
    rows, total, var_sum = [], 0.0, 0.0
    for m in ORDER:
        eps = abs(local[m] - peer[m])
        accepted = eps <= EPS_MAX
        if accepted:
            wp = math.exp(-GAMMA * eps)
            wl = 1.0 / (1.0 + wp)
            wp = wp / (1.0 + math.exp(-GAMMA * eps)) if False else wp / (1.0 + wp)
        else:
            wl, wp = 1.0, 0.0
        f = wl * local[m] + wp * peer[m]
        v = wl * (local[m] - f) ** 2 + wp * (peer[m] - f) ** 2 + SIGMA0
        rows.append((m, local[m], peer[m], eps, wp, accepted, f))
        total += OMEGA[m] * f
        var_sum += OMEGA[m] * v
    t_k = 10.0 * total
    sigma = math.sqrt(var_sum)
    return rows, t_k, sigma


def doc_blocks() -> dict[str, list[str]]:
    text = DOC.read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    for key in CASES:
        m = re.search(r"## " + re.escape(key) + r" .*?(?=\n## |\Z)", text, re.S)
        out[key] = m.group(0).splitlines() if m else []
    return out


def main() -> int:
    blocks = doc_blocks()
    for key, case in CASES.items():
        rows, t_k, sigma = compute(case)
        print("=" * 92)
        print(f"{key}  computed T={t_k:.2f}  SIGMA={sigma:.2f}")
        print("=" * 92)
        body = "\n".join(blocks.get(key, []))
        for m, local, peer, eps, wp, accepted, f in rows:
            line = next((l for l in blocks.get(key, []) if l.strip().startswith(f"CHECK {m}:")), None)
            if line is None:
                check(f"{key} {m} has a CHECK line", False)
                continue
            vals = [v.strip() for v in line.strip().split(":", 1)[1].split(",")]
            got_eps, got_phi, got_ok = float(vals[2]), float(vals[3]), vals[4]
            ok = (abs(got_eps - eps) < 0.0006 and abs(got_phi - wp) < 0.0006
                  and (got_ok == "y") == accepted
                  and abs(float(vals[0]) - local) < 1e-9
                  and abs(float(vals[1]) - peer) < 1e-9)
            check(f"{key} CHECK {m}", ok,
                  f"doc eps={got_eps} phi={got_phi} ok={got_ok} | computed "
                  f"eps={eps:.3f} phi={wp:.3f} ok={'y' if accepted else 'n'}")
        tl = next((l for l in blocks.get(key, []) if l.strip().startswith("T=")), None)
        if tl is None:
            check(f"{key} has a T= line", False)
        else:
            nums = re.findall(r"[\d.]+", tl)
            got_t, got_s = float(nums[0]), float(nums[1])
            check(f"{key} fused T and SIGMA",
                  abs(got_t - t_k) < 0.005 and abs(got_s - sigma) < 0.005,
                  f"doc T={got_t} SIGMA={got_s} | computed T={t_k:.2f} SIGMA={sigma:.2f}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Every number in the worked examples matches the stated rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
