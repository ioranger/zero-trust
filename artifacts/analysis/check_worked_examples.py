"""Recompute the worked examples of the cross-swarm prompt template.

Every number in the template's examples is produced here from the stated
rules, so the document and the arithmetic cannot drift apart.
"""

from __future__ import annotations

import math

GAMMA = 2.0
SIGMA0 = 0.1
EPS_MAX = 0.12
OMEGA = {"T1": 0.322, "T2": 0.138, "T3": 0.080, "T4": 0.321, "T5": 0.140}
ORDER = ["T1", "T2", "T3", "T4", "T5"]

CASES = {
    "8.1 benign, honest peer": {
        "local": {"T1": 0.85, "T2": 0.73, "T3": 0.79, "T4": 0.78, "T5": 0.788},
        "peer": {"T1": 0.83, "T2": 0.75, "T3": 0.77, "T4": 0.79, "T5": 0.787},
    },
    "8.2 benign, lying peer": {
        "local": {"T1": 0.85, "T2": 0.73, "T3": 0.79, "T4": 0.78, "T5": 0.788},
        "peer": {"T1": 0.63, "T2": 0.75, "T3": 0.77, "T4": 0.64, "T5": 0.700},
    },
    "8.3 on-off attacker": {
        "local": {"T1": 0.778, "T2": 0.747, "T3": 0.722, "T4": 0.762, "T5": 0.752},
        "peer": {"T1": 0.774, "T2": 0.749, "T3": 0.721, "T4": 0.766, "T5": 0.751},
    },
}

THETA_HIGH, THETA_LOW, SIGMA_TH = 7.0, 4.0, 1.0


def run(name: str, case: dict) -> None:
    local, peer = case["local"], case["peer"]
    print("=" * 92)
    print(name)
    print("=" * 92)
    fused, vars_, total, var_sum = {}, {}, 0.0, 0.0
    for m in ORDER:
        eps = abs(local[m] - peer[m])
        accepted = eps <= EPS_MAX
        if accepted:
            wp = math.exp(-GAMMA * eps)
            wl = 1.0
            wsum = wl + wp
            wl, wp = wl / wsum, wp / wsum
        else:
            wl, wp = 1.0, 0.0
        f = wl * local[m] + wp * peer[m]
        v = wl * (local[m] - f) ** 2 + wp * (peer[m] - f) ** 2 + SIGMA0
        fused[m], vars_[m] = f, v
        total += OMEGA[m] * f
        var_sum += OMEGA[m] * v
        print(f"  {m}: eps={eps:.3f} accepted={'yes' if accepted else 'no'} "
              f"w_local={wl:.3f} w_peer={wp:.3f} phi_peer={wp:.3f} fused={f:.4f}")
    t_k = 10.0 * total
    sigma = math.sqrt(var_sum)
    cls = ("Trusted" if t_k >= THETA_HIGH and sigma <= SIGMA_TH else
           "Malicious" if t_k < THETA_LOW and sigma <= SIGMA_TH else
           "Suspicious")
    print(f"  FUSED_T={t_k:.2f}  DISPERSION={sigma:.2f}  CLASS={cls}")
    print()


def main() -> int:
    for name, case in CASES.items():
        run(name, case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
