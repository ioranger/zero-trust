"""Is a trace a measurement the feature extractor can actually make?

The bundled trace produced a table that read as an external-validity failure
of the detector. It was not: the trace holds 49 update steps, the shape block
is defined only for windows of at least 122, and the early and late windows of
the marginal block overlap completely. Six of the eighteen input columns were
therefore constant across every node, and the numbers in that table measured a
harness mismatch rather than the detector.

This module turns that diagnosis into a reusable verdict, so a trace is
checked *before* its numbers are reported and an invalid one can be excluded
with a stated reason rather than silently averaged in.

    python -u artifacts/analysis/trace_regime.py <converted-trace.csv> [...]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"F:\zero trust\zero-trust")
sys.path.insert(0, str(ROOT / "artifacts" / "scripts"))

from evaluate_trace_driven import config_for_trace, trace_to_streams  # noqa: E402
from marl_policy import (  # noqa: E402
    _SHAPE_ACF_MAX_LAG,
    extract_marl_policy_features,
    extract_shape_features,
)
from reference_simulator import load_config  # noqa: E402

# The marginal block compares an early window of 100 steps with a late window
# of 100 steps. When the post-warm-up stream is shorter than 200 steps the two
# windows overlap, the difference is identically zero, and the positive-slope
# column degenerates.
_WINDOW = 100
_MIN_SHAPE_STEPS = _SHAPE_ACF_MAX_LAG + 2


@dataclass
class RegimeVerdict:
    trace: str
    n_steps: int = 0
    n_nodes: int = 0
    warmup_steps: int = 0
    post_warmup_steps: int = 0
    shape_available: bool = False
    window_overlap_steps: int = 0
    degenerate_columns: list = field(default_factory=list)
    shape_all_zero: bool = False
    valid: bool = False
    reasons: list = field(default_factory=list)
    hard_reasons: list = field(default_factory=list)

    def summary(self) -> str:
        state = "VALID" if self.valid else "NOT A MEASUREMENT"
        lines = [f"{self.trace}: {state}"]
        lines.append(f"  steps {self.n_steps}, nodes {self.n_nodes}, "
                     f"warm-up {self.warmup_steps}, "
                     f"post-warm-up {self.post_warmup_steps}")
        lines.append(f"  shape block available: {self.shape_available} "
                     f"(needs at least {_MIN_SHAPE_STEPS} steps)")
        lines.append(f"  early/late window overlap: {self.window_overlap_steps} steps")
        lines.append(f"  columns constant across every node: "
                     f"{len(self.degenerate_columns)}")
        if self.degenerate_columns:
            lines.append(f"    {self.degenerate_columns}")
        lines.append(f"  shape block all-zero on every node: {self.shape_all_zero}")
        for r in self.hard_reasons:
            lines.append(f"  - {r}")
        for r in self.reasons:
            lines.append(f"  . {r}")
        return "\n".join(lines)


def assess_trace(config, streams: np.ndarray, trace_name: str) -> RegimeVerdict:
    """Decide whether the feature extractor can measure anything on this trace."""
    v = RegimeVerdict(trace=trace_name)
    v.n_steps = int(streams.shape[0])
    v.n_nodes = int(streams.shape[1])
    tcfg = config_for_trace(config, v.n_steps)
    v.warmup_steps = int(tcfg.warmup_steps)
    v.post_warmup_steps = v.n_steps - v.warmup_steps

    v.shape_available = v.post_warmup_steps >= _MIN_SHAPE_STEPS
    if not v.shape_available:
        v.hard_reasons.append(
            f"only {v.post_warmup_steps} post-warm-up steps; the shape block "
            f"needs at least {_MIN_SHAPE_STEPS} and returns zeros below that")

    v.window_overlap_steps = max(0, 2 * _WINDOW - v.post_warmup_steps)
    if v.window_overlap_steps > 0:
        v.hard_reasons.append(
            f"the early and late {_WINDOW}-step windows overlap by "
            f"{v.window_overlap_steps} steps, so the positive-slope column is "
            f"identically zero")

    xs, names = extract_marl_policy_features(tcfg, streams, 5)
    per_col_range = xs.max(axis=0) - xs.min(axis=0)
    v.degenerate_columns = [names[i] for i in range(xs.shape[1])
                            if per_col_range[i] < 1e-12]
    if v.degenerate_columns:
        # A column that is constant across nodes carries no information in that
        # column, but it does not invalidate the others. It is disclosed rather
        # than used to drop the whole trace, because the geometry checks above
        # are what make a trace meaningless, and those are hard failures.
        v.reasons.append(
            f"{len(v.degenerate_columns)} of {xs.shape[1]} input columns are "
            f"constant across every node, so the model receives one fixed "
            f"input for them: {v.degenerate_columns}")

    v.shape_all_zero = bool(np.all(extract_shape_features(tcfg, streams) == 0.0))
    if v.shape_all_zero:
        v.hard_reasons.append("the shape block is all-zero, so the temporal "
                              "evidence is absent")

    v.valid = not v.hard_reasons
    return v


def assess_trace_file(path: Path, config=None) -> RegimeVerdict:
    if config is None:
        config = load_config(str(ROOT / "artifacts" / "configs" / "default.json"))
    trace = pd.read_csv(path)
    streams, _, _ = trace_to_streams(trace)
    return assess_trace(config, streams, str(path))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    config = load_config(str(ROOT / "artifacts" / "configs" / "default.json"))
    bad = 0
    for arg in sys.argv[1:]:
        v = assess_trace_file(Path(arg), config)
        print(v.summary())
        print()
        if not v.valid:
            bad += 1
    print(f"{len(sys.argv) - 1} trace(s) checked, {bad} of them not a "
          f"measurement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
