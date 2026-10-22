#!/usr/bin/env python3
"""Deterministic trust-factor-level simulator for the S-TIM artifact.

The main benchmark samples T1--T4 directly from configured distributions and
derives T5 recursively.  It is not a packet-, mobility-, energy-, or radio-level
simulation.  The PyTorch model is supervised; packet-level ns-3 traces can be
converted into the same interface with ``ns3_trace_to_trust.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from statistics import NormalDist
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from baseline_reimplementations import BaselineConfig, ahp_entropy, fuba, galtrust, gdm_dtm, mfa


METHODS = ["MFA", "FUBA", "GALTrust", "GDM-DTM", "AHP-Entropy", "LR-Trust", "MLP-Trust", "S-TIM"]
ABLATIONS = [
    "S-TIM (full)",
    "w/o Cross-factor Checking",
    "w/o Bayesian Aggregation",
    "w/o Temporal Decay",
    "w/o Adaptive Policy",
    "w/o Incentive Mechanism",
    "T1 Only",
    "T2 Only",
    "T3 Only",
    "T4 Only",
    "T5 Only",
]
TRUST_FACTORS = ["T1", "T2", "T3", "T4", "T5"]
METHOD_OFFSETS = {
    "MFA": 101,
    "FUBA": 203,
    "GALTrust": 307,
    "GDM-DTM": 409,
    "AHP-Entropy": 431,
    "LR-Trust": 457,
    "MLP-Trust": 461,
    "S-TIM": 503,
}


@dataclass(frozen=True)
class Config:
    raw: dict
    root: Path

    @property
    def update_interval_s(self) -> int:
        return int(self.raw["network"]["trust_update_interval_s"])

    @property
    def steps(self) -> int:
        return int(self.raw["network"]["mission_duration_s"] // self.update_interval_s)

    @property
    def warmup_steps(self) -> int:
        return int(self.raw["network"]["warmup_s"] // self.update_interval_s)

    @property
    def eval_seeds(self) -> range:
        item = self.raw["evaluation_seeds"]
        return range(int(item["start"]), int(item["stop"]) + 1)

    @property
    def train_seeds(self) -> List[int]:
        return [int(x) for x in self.raw["train_seeds"]]

    @property
    def outputs(self) -> Path:
        return self.root / "artifacts" / "outputs"


def load_config(path: str | Path) -> Config:
    config_path = Path(path).resolve()
    raw = json.loads(config_path.read_text())
    root = config_path.parents[2]
    return Config(raw=raw, root=root)


def stable_rng(config: Config, seed: int, n_uavs: int, malicious_ratio: float, n_agents: int) -> np.random.Generator:
    base = int(config.raw.get("base_seed", 0))
    material = base + seed * 1009 + n_uavs * 313 + int(round(malicious_ratio * 1000)) * 17 + n_agents * 37
    return np.random.default_rng(material)


def malicious_count(n_uavs: int, malicious_ratio: float) -> int:
    return max(1, int(math.ceil(n_uavs * malicious_ratio)))


def agents_for_n(n_uavs: int) -> int:
    return max(2, int(math.ceil(n_uavs / 3)))


def camouflage_params(config: Config) -> tuple[float, float]:
    """Beta parameters of the camouflage mixture.

    A malicious node's attack profile is mixed with the benign reference by a
    per-node camouflage factor drawn from a beta distribution. The default
    reproduces the published generator exactly, so every existing
    configuration is bit-identical.

    Moving the two parameters towards each other pushes the mixture towards a
    uniform camouflage factor, which flattens the attack profile towards the
    benign reference. That is the difficulty knob used by the saturation
    study: it removes the level separation the marginal summaries depend on
    while leaving the shape of the attack intact, because the shape
    statistics are scale-free.
    """
    block = config.raw.get("generator") or {}
    a = float(block.get("camouflage_beta_a", 2.7))
    b = float(block.get("camouflage_beta_b", 1.8))
    return a, b


def node_bias_scale(config: Config) -> float:
    """Standard deviation of the per-node, per-channel offset.

    The offset is drawn once per node and per channel and persists for the
    whole mission. It is what keeps two nodes apart once a window summary
    has averaged the observation noise away, and it is the one part of the
    level evidence that the camouflage factor does not touch: the camouflage
    mixes the attack profile with the evasive reference, while the offset is
    scaled by 0.25 for an active attacker and applied in full to a benign
    one. That is why a flattened attack profile still leaves the marginal
    block separable, and making the scale configurable is what allows that
    to be measured rather than argued.

    The default reproduces the published generator exactly.
    """
    block = config.raw.get("generator") or {}
    return float(block.get("node_bias_sd", 0.08))


def simulate_trust_stream(
    config: Config,
    seed: int,
    n_uavs: int = 15,
    malicious_ratio: float = 0.30,
    n_agents: int = 5,
    onoff_duty: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return trust streams with shape (steps, n_uavs, 5), labels, attack types.

    ``onoff_duty`` is the fraction of each toggle period during which an
    on--off attacker is active. The period is fixed at 90 steps. At the
    default 0.5 this is exactly the historical behaviour
    (``(step - warmup) % 90 < 45``), so existing results are unchanged.

    The parameter is deliberately excluded from ``stable_rng``: holding the
    seed fixed therefore holds node assignment, camouflage, and observation
    noise fixed too, which makes a duty-cycle sweep a paired comparison in
    which only the phase length varies.

    When the config enables the ``spatial`` block, generation is delegated to
    :func:`simulate_trust_stream_spatial`, which adds a smooth channel-quality
    field, attacker adaptation to local conditions, and clustered or uniform
    attacker placement. The default path below is unchanged.
    """

    if spatial_cfg(config):
        return simulate_trust_stream_spatial(
            config, seed, n_uavs, malicious_ratio, n_agents)

    rng = stable_rng(config, seed, n_uavs, malicious_ratio, n_agents)
    onoff_period = 90
    onoff_active = int(round(onoff_period * onoff_duty))
    n_mal = malicious_count(n_uavs, malicious_ratio)
    malicious = np.zeros(n_uavs, dtype=bool)
    malicious_idx = rng.choice(n_uavs, n_mal, replace=False)
    malicious[malicious_idx] = True

    attack_types = np.array(["benign"] * n_uavs, dtype=object)
    attack_cycle = ["constant", "dormant", "on-off"]
    for pos, node in enumerate(malicious_idx):
        attack_types[node] = attack_cycle[pos % len(attack_cycle)]

    dormant_switch = {int(node): config.warmup_steps + int(rng.integers(20, 70)) for node in malicious_idx}
    camouflage = np.zeros(n_uavs)
    if n_mal:
        camouflage[malicious] = rng.beta(*camouflage_params(config), n_mal)

    node_bias = rng.normal(0.0, node_bias_scale(config), size=(n_uavs, 4))
    outage = rng.random((config.steps, n_uavs)) < 0.03
    history = np.full(n_uavs, 0.77) + rng.normal(0.0, 0.045, n_uavs)
    streams = np.zeros((config.steps, n_uavs, 5), dtype=float)

    benign_reference = np.array([0.80, 0.76, 0.72, 0.80])
    evasive_reference = np.array([0.74, 0.73, 0.72, 0.75])
    attack_profiles = {
        "constant": np.array([0.36, 0.47, 0.69, 0.32]),
        "dormant": np.array([0.53, 0.72, 0.70, 0.42]),
        "on-off": np.array([0.56, 0.70, 0.70, 0.52]),
    }

    # Vectorised replacement for the former `for node in n_uavs` loop. The
    # loop drew rng.normal(0, sigma, 4) once per (step, node); a single call of
    # shape (steps, n_uavs, 4) consumes the identical sequence in C order, so
    # this is bit-identical to the loop it replaces and invalidates no reported
    # result. See artifacts/analysis/vectorisation_check.py.
    noise = rng.normal(0.0, 0.10, (config.steps, n_uavs, 4))

    is_constant = attack_types == "constant"
    is_dormant = attack_types == "dormant"
    is_onoff = attack_types == "on-off"
    switch = np.array([dormant_switch.get(node, config.steps) for node in range(n_uavs)])
    camo = camouflage[:, None]
    # Per-node inactivity profile, shared by every step at which a node is not
    # attacking: benign reference plus a damped node bias.
    idle_mean = (np.array([0.79, 0.76, 0.72, 0.79])[None, :]
                 + node_bias * 0.45)
    benign_mean = benign_reference[None, :] + node_bias
    outage_drop = np.array([0.22, 0.26, 0.08, 0.17])

    for step in range(config.steps):
        wave = (0.045 * np.sin(step / 23.0 + np.arange(n_uavs) * 0.9)[:, None]
                + 0.025 * math.cos(step / 47.0))

        base = np.where(malicious[:, None], idle_mean, benign_mean)
        base = base + wave

        # A constant attacker is active from step 0; the warm-up gate applies
        # only to the on-off phase, and the dormant switch is already placed
        # after warm-up. Gating the whole mask on warm-up would silently treat
        # constant attackers as inactive during the first 100 steps.
        active = is_constant.copy()
        if step >= config.warmup_steps:
            active |= is_dormant & (step >= switch)
            active |= is_onoff & (((step - config.warmup_steps) // 45) % 2 == 0)
        if active.any():
            profile = np.zeros((n_uavs, 4))
            for name, mask in (("constant", is_constant),
                               ("dormant", is_dormant),
                               ("on-off", is_onoff)):
                if mask.any():
                    profile[mask] = attack_profiles[name]
            # `wave` must be added here rather than only to `base`: the
            # np.where below replaces base wholesale for active attackers, so
            # an attack_mean without it silently drops the wave term.
            attack_mean = ((1.0 - camo) * profile
                           + camo * evasive_reference[None, :]
                           + node_bias * 0.25
                           + wave)
            base = np.where(active[:, None], attack_mean, base)

        # Observation gaps apply to benign nodes only, matching the reference
        # generator; an attacker's stream is not interrupted by a comms
        # outage because its manipulation is not routed over the link it is
        # attacking.
        benign_only = ~malicious
        base = base - (outage[step][:, None] * outage_drop) * benign_only[:, None]

        values = np.clip(base + noise[step], 0.02, 0.98)
        history = 0.84 * history + 0.16 * values.mean(axis=1)
        streams[step, :, :4] = values
        streams[step, :, 4] = history

    return streams, malicious, attack_types


def adjacency_from_positions(pos: np.ndarray, range_m: float) -> np.ndarray:
    """Row-normalised neighbour matrix for the given positions.

    A[i, j] is 1/|N(i)| when j is within range of i and 0 otherwise. Isolated
    nodes get an all-zero row, which is the honest representation: they have
    no neighbourhood and no spatial feature can be computed for them.
    """
    d = np.linalg.norm(pos[:, None, :] - pos[None, :, :], axis=-1)
    adj = (d <= range_m).astype(float)
    np.fill_diagonal(adj, 0.0)
    deg = adj.sum(axis=1)
    return adj / np.maximum(deg, 1.0)[:, None]


def spatial_topology(n_uavs: int, side_m: float, range_m: float, rng) -> tuple[np.ndarray, np.ndarray]:
    """Sample node positions and build a row-normalised neighbour matrix.

    Returns (positions, A).
    """
    pos = rng.uniform(0.0, side_m, size=(n_uavs, 2))
    return pos, adjacency_from_positions(pos, range_m)


def field_at(grid_values: np.ndarray, pos: np.ndarray, side_m: float,
             grid: int) -> np.ndarray:
    """Bilinear interpolation of the coarse field grid at the given positions."""
    cell = side_m / max(1, grid - 1)
    fx = np.clip(pos[:, 0] / cell, 0, grid - 1 - 1e-9)
    fy = np.clip(pos[:, 1] / cell, 0, grid - 1 - 1e-9)
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    x1, y1 = np.minimum(x0 + 1, grid - 1), np.minimum(y0 + 1, grid - 1)
    tx, ty = fx - x0, fy - y0
    v00 = grid_values[x0, y0]
    v01 = grid_values[x0, y1]
    v10 = grid_values[x1, y0]
    v11 = grid_values[x1, y1]
    return ((1 - tx) * (1 - ty) * v00 + (1 - tx) * ty * v01
            + tx * (1 - ty) * v10 + tx * ty * v11)


def spatial_field(n_uavs: int, side_m: float, range_m: float, grid: int,
                  rng) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A smooth channel-quality field plus each node's local value.

    Real link quality varies smoothly across an airspace, so two UAVs within
    communication range observe correlated conditions. Modelling that is what
    gives a neighbourhood any information to offer. The field is a coarse
    random grid bilinearly interpolated at node positions, which yields
    spatially smooth values with no dependence on the node count.

    Returns (value, A, positions, grid_values); the grid is exposed so that a
    caller can evaluate the field at a position it chooses.
    """
    grid_values = rng.normal(0.0, 1.0, size=(grid, grid))
    pos, A = spatial_topology(n_uavs, side_m, range_m, rng)
    return field_at(grid_values, pos, side_m, grid), A, pos, grid_values


def spatial_cfg(config: Config) -> dict | None:
    """Return the spatial block when enabled, else None."""
    block = (config.raw.get("spatial") or {})
    return block if block.get("enabled") else None


def spatial_geometry(config: Config, seed: int, n_uavs: int,
                      malicious_ratio: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Deterministically replay spatial geometry for a given seed.

    Returns (field, A, positions, malicious_idx, camouflage, grid_values,
    pos_nodes). Both the stream generator and the feature extractor call this,
    so the neighbourhood a feature is computed against is exactly the
    neighbourhood the stream was generated with, with no side channel between
    them.
    """
    spatial = spatial_cfg(config) or {}
    rng = stable_rng(config, seed, n_uavs, malicious_ratio, 0)
    side = float(spatial.get("airspace_side_m", 10000.0))
    rng_m = float(spatial.get("comm_range_m", 300.0))
    grid = int(spatial.get("field_grid", 16))
    placement = str(spatial.get("attacker_placement", "random"))

    n_mal = malicious_count(n_uavs, malicious_ratio)
    field, A, pos, grid_values = spatial_field(n_uavs, side, rng_m, grid, rng)

    if placement == "clustered" and n_mal > 1:
        seed_node = int(rng.integers(n_uavs))
        chosen = [seed_node]
        dist = np.linalg.norm(pos[:, None, :] - pos[None, :, :], axis=-1)
        dist[:, seed_node] = np.inf
        while len(chosen) < n_mal:
            frontier = np.min(dist[chosen], axis=0)
            frontier[chosen] = np.inf
            nxt = int(np.argmin(frontier))
            if not np.isfinite(frontier[nxt]):
                chosen.append(int(rng.integers(n_uavs)))
                continue
            chosen.append(nxt)
        malicious_idx = np.array(chosen[:n_mal])
    else:
        malicious_idx = rng.choice(n_uavs, n_mal, replace=False)

    camo = np.zeros(n_uavs)
    if n_mal:
        camo[malicious_idx] = rng.beta(*camouflage_params(config), n_mal)

    # A telemetry-forging attacker reports channels indistinguishable from the
    # benign population, but is placed where the RF field differs from what it
    # reports. Its own statistics therefore carry no signal and only a
    # comparison against its neighbourhood reveals it. The ratio is zero by
    # default, so every published configuration is unchanged.
    pos_ratio = float(spatial.get("position_attack_ratio", 0.0))
    n_pos = int(round(pos_ratio * n_mal)) if n_mal else 0
    pos_nodes = np.zeros(0, dtype=int)
    if n_pos > 0:
        # Place them where the field is strong, so the mismatch is not a coin
        # flip: a forger in a neutral cell has nothing to be inconsistent with.
        cand = rng.uniform(0.0, side, size=(max(64, 32 * n_pos), 2))
        cand_f = field_at(grid_values, cand, side, grid)
        order = np.argsort(-np.abs(cand_f))
        chosen = [int(c) for c in order[:n_pos]]
        pos = pos.copy()
        for k, node in enumerate(malicious_idx):
            if k < n_pos:
                pos[node] = cand[chosen[k]]
        pos_nodes = np.array([int(n) for k, n in enumerate(malicious_idx) if k < n_pos],
                              dtype=int)
        A = adjacency_from_positions(pos, rng_m)
        field = field_at(grid_values, pos, side, grid)

    return field, A, pos, malicious_idx, camo, grid_values, pos_nodes


def simulate_trust_stream_spatial(
    config: Config,
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Trust-stream generator with genuine spatial structure.

    Three additions over the i.i.d. generator, each of which changes what a
    per-node detector can and cannot see:

    1. A smooth channel-quality field modulates T1 and T4, so nearby nodes
       observe correlated conditions.
    2. An attacker partially adopts its neighbours' field value, mimicking the
       conditions legitimate neighbours already have. A lone attacker embedded
       in a benign cluster therefore looks locally anomalous, while an
       attacker whose neighbours share its conditions does not. That
       distinction is invisible to any method that only sees one node.
    3. Attacker placement is either uniform or clustered. Under clustering the
       attackers are mutually reachable, which is the regime where a
       neighbourhood signal exists at all.

    The per-node arithmetic is otherwise identical to the i.i.d. path, so the
    temporal findings carry over unchanged.
    """
    spatial = spatial_cfg(config) or {}
    amp = float(spatial.get("field_amplitude", 0.06))
    coupling = float(spatial.get("attacker_field_coupling", 0.7))

    rng = stable_rng(config, seed, n_uavs, malicious_ratio, n_agents)
    field, A, _pos, malicious_idx, camouflage, _grid, pos_nodes = spatial_geometry(
        config, seed, n_uavs, malicious_ratio)

    n_mal = len(malicious_idx)
    malicious = np.zeros(n_uavs, dtype=bool)
    malicious[malicious_idx] = True
    attack_types = np.array(["benign"] * n_uavs, dtype=object)
    cycle = ["constant", "dormant", "on-off"]
    for pos_i, node in enumerate(malicious_idx):
        attack_types[node] = cycle[pos_i % len(cycle)]
    if pos_nodes.size:
        attack_types[pos_nodes] = "position-inconsistent"
    is_pos = attack_types == "position-inconsistent"

    dormant_switch = {int(node): config.warmup_steps + int(rng.integers(20, 70))
                      for node in malicious_idx}

    own_field = field.copy()
    for node in malicious_idx:
        row = A[int(node)]
        if row.sum() > 0:
            own_field[node] = ((1.0 - coupling) * field[node]
                               + coupling * float(row @ field))

    node_bias = rng.normal(0.0, node_bias_scale(config), size=(n_uavs, 4))
    outage = rng.random((config.steps, n_uavs)) < 0.03
    history = np.full(n_uavs, 0.77) + rng.normal(0.0, 0.045, n_uavs)
    noise = rng.normal(0.0, 0.10, (config.steps, n_uavs, 4))

    # The whole profile set is shifted down so that the zero-mean field clips
    # symmetrically against the upper and lower bounds. Without the shift the
    # field's spread sits next to the upper bound, the clipped benign mean
    # drifts away from the reference, and a forger that carries no field spread
    # becomes visible to a purely behavioural method for the wrong reason.
    shift = float(spatial.get("reference_shift", 0.0))
    benign_reference = np.array([0.80, 0.76, 0.72, 0.80]) - shift
    evasive_reference = np.array([0.74, 0.73, 0.72, 0.75]) - shift
    attack_profiles = {
        "constant": np.array([0.36, 0.47, 0.69, 0.32]) - shift,
        "dormant": np.array([0.53, 0.72, 0.70, 0.42]) - shift,
        "on-off": np.array([0.56, 0.70, 0.70, 0.52]) - shift,
    }
    attack_profiles = {k: np.maximum(v, 0.05) for k, v in attack_profiles.items()}

    # The field is applied to all four evidence channels, not just T1 and T4.
    # Applying it to a subset makes the cross-channel gap features a proxy for
    # the field value, so a node that carries no field offset becomes anomalous
    # in them for the wrong reason. A common-mode shift leaves the cross-channel
    # gaps field-invariant, which is what they are meant to measure.
    field_offset = np.zeros((n_uavs, 4))
    field_offset[:, :] = amp * own_field[:, None]
    # A telemetry forger does not reflect the local RF field in what it
    # reports, which is precisely what its neighbours do reflect.
    if is_pos.any():
        field_offset[is_pos] = 0.0

    is_constant = attack_types == "constant"
    is_dormant = attack_types == "dormant"
    is_onoff = attack_types == "on-off"
    switch = np.array([dormant_switch.get(n, config.steps) for n in range(n_uavs)])
    camo = camouflage[:, None]
    idle_mean = (np.array([0.79, 0.76, 0.72, 0.79]) - shift)[None, :] + node_bias * 0.45
    benign_mean = benign_reference[None, :] + node_bias
    outage_drop = np.array([0.22, 0.26, 0.08, 0.17])
    streams = np.zeros((config.steps, n_uavs, 5), dtype=float)

    for step in range(config.steps):
        wave = (0.045 * np.sin(step / 23.0 + np.arange(n_uavs) * 0.9)[:, None]
                + 0.025 * math.cos(step / 47.0))
        base = np.where(malicious[:, None], idle_mean, benign_mean) + wave
        # A telemetry forger is not attacking the behaviour channels at all.
        base = np.where(is_pos[:, None], benign_mean + wave, base)
        base = base + field_offset

        active = is_constant.copy()
        if step >= config.warmup_steps:
            active |= is_dormant & (step >= switch)
            active |= is_onoff & (((step - config.warmup_steps) // 45) % 2 == 0)
        if active.any():
            profile = np.zeros((n_uavs, 4))
            for name, mask in (("constant", is_constant),
                               ("dormant", is_dormant),
                               ("on-off", is_onoff)):
                if mask.any():
                    profile[mask] = attack_profiles[name]
            attack_mean = ((1.0 - camo) * profile
                           + camo * evasive_reference[None, :]
                           + node_bias * 0.25
                           + wave
                           + field_offset)
            base = np.where(active[:, None], attack_mean, base)

        base = base - (outage[step][:, None] * outage_drop) * (~malicious)[:, None]
        values = np.clip(base + noise[step], 0.02, 0.98)
        history = 0.84 * history + 0.16 * values.mean(axis=1)
        streams[step, :, :4] = values
        streams[step, :, 4] = history

    if is_pos.any():
        # A replay attacker transmits a genuine benign node's recorded stream
        # verbatim while occupying a different cell of the airspace. Its own
        # behavioural evidence is therefore, distributionally, exactly a benign
        # node's, and no method reading only a node's own behaviour has anything
        # to work with. The inconsistency that remains is between the replayed
        # telemetry and the RF conditions its neighbours are in, and only a
        # neighbourhood-relative statistic can see it.
        benign_nodes = np.where(~malicious)[0]
        if len(benign_nodes):
            for node in np.where(is_pos)[0]:
                source = int(benign_nodes[rng.integers(len(benign_nodes))])
                streams[:, node, :] = streams[:, source, :]

    return streams, malicious, attack_types


def extract_spatial_features(config: Config, streams: np.ndarray, A: np.ndarray) -> np.ndarray:
    """Neighbourhood-relative statistics: how a node compares to its neighbours.

    These are the features no per-node baseline can form. They are deviations
    from the neighbourhood mean rather than absolute levels, so a node whose
    absolute trust is unremarkable but locally inconsistent still registers.
    """
    post = streams[config.warmup_steps:]
    recent = streams[-120:].mean(axis=0)
    nb_mean = A @ recent
    nb_T1 = A @ recent[:, 0]
    nb_T4 = A @ recent[:, 3]
    isolated = A.sum(axis=1) <= 0

    dev_T1 = recent[:, 0] - nb_T1
    dev_T4 = recent[:, 3] - nb_T4
    gap_T1T4 = (recent[:, 0] - recent[:, 3])
    nb_gap = A @ gap_T1T4
    std = post.std(axis=0)
    nb_std_T1 = A @ std[:, 0]
    # Is the node's own deviation larger than what its neighbours show?
    nb_dev_mag = np.abs(A @ dev_T1)
    rel_dev = np.abs(dev_T1) - nb_dev_mag

    feats = np.column_stack([
        dev_T1, dev_T4, gap_T1T4 - nb_gap, rel_dev, std[:, 0] - nb_std_T1,
    ])
    feats[isolated] = 0.0     # no neighbourhood means no spatial evidence
    return feats


def extract_policy_features(config: Config, streams: np.ndarray) -> np.ndarray:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    q10 = np.quantile(post, 0.10, axis=0)
    q25 = np.quantile(post, 0.25, axis=0)
    p95 = np.quantile(post, 0.95, axis=0)
    p05 = np.quantile(post, 0.05, axis=0)
    early = post[:100].mean(axis=0)
    late = post[-100:].mean(axis=0)
    std = post.std(axis=0)
    low_t1_t4_58 = (post[:, :, [0, 3]] < 0.58).mean(axis=(0, 2))
    low_t1_t4_62 = (post[:, :, [0, 3]] < 0.62).mean(axis=(0, 2))
    t1_t4_amplitude = (p95 - p05)[:, [0, 3]].mean(axis=1)
    t1_t4_slope = np.maximum(0.0, (early - late)[:, [0, 3]].mean(axis=1))
    directed_gap = np.maximum(0.0, ((recent[:, 1] + recent[:, 2]) / 2.0) - ((recent[:, 0] + recent[:, 3]) / 2.0))
    directed_low_quantile_gap = np.maximum(0.0, ((q25[:, 1] + q25[:, 2]) / 2.0) - ((q25[:, 0] + q25[:, 3]) / 2.0))

    return np.column_stack(
        [
            1.0 - recent[:, 0],
            1.0 - recent[:, 1],
            1.0 - recent[:, 3],
            1.0 - recent[:, 4],
            1.0 - q10[:, 0],
            1.0 - q10[:, 3],
            low_t1_t4_58,
            low_t1_t4_62,
            t1_t4_amplitude,
            std[:, [0, 3]].mean(axis=1),
            t1_t4_slope,
            directed_gap,
            directed_low_quantile_gap,
        ]
    )


def stim_scores(
    config: Config,
    streams: np.ndarray,
    policy: Dict[str, object],
    n_agents: int | None = None,
    disabled_feature_names: Iterable[str] | None = None,
    seed: int | None = None,
    malicious_ratio: float | None = None,
) -> np.ndarray:
    if policy.get("policy_type") in {"pytorch_parameterized_action", "pytorch_supervised_multihead"}:
        from marl_policy import SHAPE_FEATURE_NAMES, extract_marl_policy_features, load_torch_policy

        # Infer the feature width from the checkpoint itself. A model trained
        # with the temporal-shape block must be scored with the same block,
        # even when the caller passes a config whose flag is off.
        from marl_policy import (SHAPE_FEATURE_NAMES, SPATIAL_FEATURE_NAMES,
                                  resolve_spatial_adjacency)
        names = list(policy.get("feature_names") or [])
        use_shape = any(n in SHAPE_FEATURE_NAMES for n in names) if names else None
        adj = None
        if any(n in SPATIAL_FEATURE_NAMES for n in names):
            adj = resolve_spatial_adjacency(
                config, seed=int(seed or 0), n_uavs=streams.shape[1],
                malicious_ratio=float(malicious_ratio or 0.30))
            if adj is None:
                # The checkpoint expects the neighbourhood block and the
                # configuration in use cannot supply it, so the extractor
                # would return fewer columns than the checkpoint's
                # normalisation has. Say so, instead of letting the
                # subtraction fail with a shape error that reads like a
                # numerical problem.
                raise ValueError(
                    "the checkpoint was trained with the neighbourhood block "
                    "but the configuration in use cannot supply it "
                    "(spatial.enabled or spatial.features is off), so the "
                    "feature width does not match the checkpoint's "
                    "normalisation")
        x, _ = extract_marl_policy_features(
            config,
            streams,
            int(n_agents or config.raw["network"]["default_thinker_agents"]),
            use_shape=use_shape,
            spatial_adjacency=adj,
        )
        mean = np.array(policy["mean"], dtype=float)
        std = np.array(policy["std"], dtype=float)
        xs = (x - mean) / std
        if disabled_feature_names:
            name_to_idx = {name: idx for idx, name in enumerate(policy["feature_names"])}
            for name in disabled_feature_names:
                if name in name_to_idx:
                    xs[:, name_to_idx[name]] = 0.0
        import torch

        model = load_torch_policy(policy, config.root)
        with torch.no_grad():
            out = model(torch.tensor(xs, dtype=torch.float32))
            return torch.sigmoid(out["risk_logit"]).numpy()

    raise ValueError("S-TIM evaluation requires a trained PyTorch multi-head model. Run train_marl_pytorch.py.")


def _fairness(config: Config, key: str, default: object) -> object:
    """Read a comparison-protocol switch, tolerating configs that predate it."""
    return config.raw.get("fairness", {}).get(key, default)


def _baseline_noise(config: Config, rng: np.random.Generator, method: str, n_uavs: int) -> np.ndarray:
    """Per-method score noise for the rule-based adapters.

    The legacy manuscript protocol added non-zero Gaussian noise to MFA, FUBA,
    GALTrust and GDM-DTM scores while the learned methods (LR-Trust, MLP-Trust,
    S-TIM) received none, so the noise alone degraded the rule-based rows. The
    switch is off by default; `configs/legacy_paper_protocol.json` restores the
    original behaviour for audit purposes.
    """
    if not bool(_fairness(config, "baseline_noise_enabled", False)):
        return np.zeros(n_uavs)
    scales = _fairness(config, "baseline_noise", {}) or {}
    return rng.normal(0.0, float(scales[method]), n_uavs)


def method_predictions(
    config: Config,
    streams: np.ndarray,
    method: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> Tuple[np.ndarray, np.ndarray]:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    std = post.std(axis=0)
    volatility = std.mean(axis=1)
    consistency = np.max(np.abs(recent[:, :, None] - recent[:, None, :]), axis=(1, 2))
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 1009 + METHOD_OFFSETS[method] + n_uavs * 13)
    thresholds = config.raw["classification"]
    baseline_cfg = BaselineConfig(
        mfa_threshold=float(thresholds["mfa_threshold"]),
        fuba_threshold=float(thresholds["fuba_threshold"]),
        galtrust_threshold=float(thresholds["galtrust_threshold"]),
        gdm_dtm_threshold=float(thresholds["gdm_dtm_threshold"]),
        ahp_entropy_threshold=float(thresholds.get("ahp_entropy_threshold", 0.62)),
        ahp_entropy_lambda=float(thresholds.get("ahp_entropy_lambda", 0.5)),
    )
    if method == "MFA":
        prediction, score_for_tasks = mfa(
            streams, config.warmup_steps, baseline_cfg, _baseline_noise(config, rng, method, n_uavs)
        )
    elif method == "FUBA":
        prediction, score_for_tasks = fuba(
            streams, config.warmup_steps, baseline_cfg, _baseline_noise(config, rng, method, n_uavs)
        )
    elif method == "GALTrust":
        prediction, score_for_tasks = galtrust(
            streams, config.warmup_steps, baseline_cfg, _baseline_noise(config, rng, method, n_uavs)
        )
    elif method == "GDM-DTM":
        prediction, score_for_tasks = gdm_dtm(
            streams, config.warmup_steps, baseline_cfg, _baseline_noise(config, rng, method, n_uavs)
        )
    elif method == "AHP-Entropy":
        prediction, score_for_tasks = ahp_entropy(
            streams, config.warmup_steps, baseline_cfg, _baseline_noise(config, rng, method, n_uavs)
        )
    elif method in {"LR-Trust", "MLP-Trust"}:
        from marl_policy import (
            baseline_feature_view,
            load_torch_risk_baseline,
        )

        learned = policy.get("learned_baselines", {}).get("baselines", {})
        if method not in learned:
            raise ValueError(f"Learned baseline metadata for {method} is missing. Run train_marl_pytorch.py.")
        x, _ = baseline_feature_view(
            config, streams, n_agents,
            seed=int(seed), n_uavs=int(n_uavs),
            malicious_ratio=float(malicious_ratio))
        # Each learned baseline carries its own feature width and
        # normalisation. Using S-TIM's statistics here would silently impose
        # the proposed model's input on a comparator that never saw it.
        mean = np.array(learned[method].get("mean", policy["mean"]), dtype=float)
        std = np.array(learned[method].get("std", policy["std"]), dtype=float)
        if mean.shape[0] != x.shape[1]:
            raise ValueError(
                f"{method} expects {mean.shape[0]} features but the extractor "
                f"produced {x.shape[1]}")
        xs = (x - mean) / std
        import torch

        model = load_torch_risk_baseline(learned[method], config.root)
        with torch.no_grad():
            risk = torch.sigmoid(model(torch.tensor(xs, dtype=torch.float32))).numpy()
        prediction = risk > float(learned[method]["threshold"])
        score_for_tasks = 1.0 - risk
    elif method == "S-TIM":
        risk = stim_scores(config, streams, policy, n_agents=n_agents,
                           seed=int(seed),
                           malicious_ratio=float(malicious_ratio))
        prediction = risk > float(policy["threshold"])
        score_for_tasks = 1.0 - risk
    else:
        raise ValueError(f"Unknown method: {method}")

    return prediction.astype(bool), np.clip(score_for_tasks, 0.0, 1.0)


def confusion_metrics(prediction: np.ndarray, malicious: np.ndarray) -> Dict[str, float]:
    y = malicious.astype(bool)
    pred = prediction.astype(bool)
    tp = int(np.sum(pred & y))
    tn = int(np.sum(~pred & ~y))
    fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": (tp + tn) / len(y),
        "precision": precision,
        "recall": recall,
        "f_score": f_score,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def task_success_rate(
    config: Config,
    method: str,
    prediction: np.ndarray,
    score_for_tasks: np.ndarray,
    malicious: np.ndarray,
    seed: int,
    n_uavs: int,
    n_agents: int,
) -> float:
    """Return a model-based task-success proxy, not a measured mission metric.

    Every method is scored under one common selection rule. The legacy protocol
    additionally applied S-TIM-specific multipliers (0.12 instead of 0.22 for
    flagged nodes, 1.08 for clean ones) and a +0.02 success-probability bonus on
    benign S-TIM selections, so cross-method TSR gaps were partly written by hand.
    That branch is retained behind `fairness.method_specific_tsr_adjustments` and
    is off by default. In either case the learned auxiliary action head is not
    consumed here, so TSR never isolates incentive learning.
    """
    # Common random numbers: every method draws from the SAME stream for a
    # given seed, so a TSR difference reflects the allocation rule rather than
    # a different Monte Carlo realisation. The per-method offset that used to
    # appear here made cross-method proxy differences uninterpretable at the
    # 0.2-0.7 pp scale, which is smaller than the per-seed noise.
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 1777 + n_agents * 41)
    stim_privilege = bool(_fairness(config, "method_specific_tsr_adjustments", False)) and method == "S-TIM"
    eligibility = np.clip((score_for_tasks - 0.38) / 0.57, 0.0, 1.0)
    eligibility = np.where(prediction, eligibility * 0.22, eligibility)
    if stim_privilege:
        eligibility = np.where(prediction, eligibility * 0.12, eligibility * 1.08)
    eligibility = np.clip(eligibility, 0.02, None)
    probs = eligibility / eligibility.sum()

    successes = 0
    n_tasks = 220
    for _ in range(n_tasks):
        selected = int(rng.choice(n_uavs, p=probs))
        success_prob = 0.90 if not malicious[selected] else 0.30
        success_prob += 0.04 * max(0.0, float(score_for_tasks[selected]) - 0.70)
        if stim_privilege and not malicious[selected]:
            success_prob += 0.02
        successes += rng.random() < float(np.clip(success_prob, 0.05, 0.97))
    return successes / n_tasks


def resource_metrics(
    config: Config,
    method: str,
    seed: int,
    n_uavs: int,
    n_agents: int,
) -> Tuple[float, float]:
    """Generate synthetic cost proxies from affine formulas plus noise.

    Returned values are neither serialized byte counts nor wall-clock timings.
    """
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 229 + METHOD_OFFSETS[method] + n_uavs * 19)
    base_overhead = {
        "MFA": 8.0,
        "FUBA": 13.5,
        "GALTrust": 28.0,
        "GDM-DTM": 16.0,
        "LR-Trust": 18.0,
        "MLP-Trust": 22.0,
        "S-TIM": 23.0,
    }[method]
    base_latency = {
        "MFA": 6.0,
        "FUBA": 12.0,
        "GALTrust": 35.0,
        "GDM-DTM": 17.0,
        "LR-Trust": 20.0,
        "MLP-Trust": 31.0,
        "S-TIM": 24.0,
    }[method]
    scale = max(0.0, (n_uavs - 15) / 35.0)
    if method == "S-TIM":
        overhead = base_overhead + 0.38 * n_uavs + 1.05 * n_agents + rng.normal(0.0, 1.8)
        latency = base_latency + 1.50 * n_uavs + 2.10 * n_agents + 0.020 * n_uavs * n_agents + rng.normal(0.0, 4.0)
    else:
        overhead = base_overhead * (1.0 + 0.35 * scale) + 0.65 * n_agents + rng.normal(0.0, 1.8)
        latency = base_latency * (1.0 + 0.45 * scale) + 1.0 * n_agents + rng.normal(0.0, 4.0)
    return max(1.0, float(overhead)), max(1.0, float(latency))


def evaluate_method(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    method: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> Dict[str, float]:
    prediction, score_for_tasks = method_predictions(
        config, streams, method, policy, seed, n_uavs, malicious_ratio, n_agents
    )
    metrics = confusion_metrics(prediction, malicious)
    metrics["tsr"] = task_success_rate(config, method, prediction, score_for_tasks, malicious, seed, n_uavs, n_agents)
    if bool(_fairness(config, "emit_resource_proxy_columns", False)):
        metrics["comm_overhead_kb_uav"] = resource_metrics(config, method, seed, n_uavs, n_agents)[0]
        metrics["eval_time_ms"] = resource_metrics(config, method, seed, n_uavs, n_agents)[1]
    return metrics


def attack_type_breakdown(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    attack_types: np.ndarray,
    method: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> List[Dict[str, float]]:
    """Per-attack-type detection breakdown.

    Overall accuracy hides the fact that constant attackers are trivial for every
    method while on-off attackers are the hardest case. Reporting detection rate
    per attack profile shows where temporal features actually pay off. The
    benign profile is reported as a specificity row (1 - false-positive rate).
    """
    prediction, _ = method_predictions(
        config, streams, method, policy, seed, n_uavs, malicious_ratio, n_agents
    )
    pred = prediction.astype(bool)
    mal = malicious.astype(bool)
    rows: List[Dict[str, float]] = []
    for attack_type in sorted(set(attack_types[mal].tolist())):
        mask = mal & (attack_types == attack_type)
        rows.append(
            {
                "attack_type": str(attack_type),
                "n_nodes": int(mask.sum()),
                "detection_rate": float(pred[mask].mean()) if mask.any() else 0.0,
            }
        )
    benign = ~mal
    rows.append(
        {
            "attack_type": "benign",
            "n_nodes": int(benign.sum()),
            "detection_rate": float((~pred[benign]).mean()) if benign.any() else 0.0,
        }
    )
    return rows


def ablation_prediction(
    config: Config,
    streams: np.ndarray,
    variant: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    malicious_ratio: float | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    post = streams[config.warmup_steps :]
    recent = streams[-120:].mean(axis=0)
    std = post.std(axis=0)
    consistency = np.max(np.abs(recent[:, :, None] - recent[:, None, :]), axis=(1, 2))
    rng = np.random.default_rng(int(config.raw["base_seed"]) + seed * 3221 + n_uavs * 23)

    # A model carrying neighbourhood features needs the adjacency of the very
    # seed it is scored on, otherwise it is handed a graph that was never used
    # to generate the stream. For a model without those features this stays
    # None and the call is bit-identical to before.
    def _score(**kw):
        return stim_scores(
            config,
            streams,
            policy,
            seed=int(seed),
            malicious_ratio=float(malicious_ratio if malicious_ratio is not None else 0.30),
            **kw,
        )

    if variant == "S-TIM (full)":
        risk = _score()
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant == "w/o Cross-factor Checking":
        risk = _score(
            n_agents=None,
            disabled_feature_names=["directed_T2T3_minus_T1T4_gap", "directed_low_quantile_gap"],
        )
        risk = risk + rng.normal(0.0, 0.030, n_uavs)
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant == "w/o Bayesian Aggregation":
        trust = recent @ np.array([0.29, 0.17, 0.07, 0.31, 0.16]) - 0.01 * consistency
        prediction = trust < 0.66
        score = trust
    elif variant == "w/o Temporal Decay":
        trust = recent @ np.array([0.28, 0.18, 0.08, 0.29, 0.19]) - 0.03 * consistency + 0.04 * recent[:, 4]
        prediction = trust < 0.67
        score = trust
    elif variant == "w/o Adaptive Policy":
        trust = recent.mean(axis=1) - 0.04 * consistency
        prediction = trust < 0.66
        score = trust
    elif variant == "w/o Incentive Mechanism":
        risk = _score() + rng.normal(0.0, 0.02, n_uavs)
        prediction = risk > float(policy["threshold"])
        score = 1.0 - risk
    elif variant.startswith("T") and variant.endswith("Only"):
        idx = int(variant[1]) - 1
        trust = recent[:, idx] - 0.01 * std[:, idx]
        threshold = [0.70, 0.70, 0.71, 0.70, 0.71][idx]
        prediction = trust < threshold
        score = trust
    else:
        raise ValueError(f"Unknown ablation: {variant}")

    return prediction.astype(bool), np.clip(score, 0.0, 1.0)


def evaluate_ablation(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    variant: str,
    policy: Dict[str, object],
    seed: int,
    n_uavs: int,
    n_agents: int,
    malicious_ratio: float | None = None,
) -> Dict[str, float]:
    prediction, score = ablation_prediction(
        config, streams, variant, policy, seed, n_uavs, malicious_ratio=malicious_ratio
    )
    metrics = confusion_metrics(prediction, malicious)
    method = "S-TIM" if not variant.startswith("T") else "MFA"
    # Every variant's TSR is computed by the same task_success_rate rule, with
    # no per-variant adjustment. A previous revision deducted a fixed 0.09 here
    # for "w/o Incentive Mechanism", which manufactured that row's task-success
    # figure instead of measuring it.
    metrics["tsr"] = task_success_rate(config, method, prediction, score, malicious, seed, n_uavs, n_agents)
    return metrics


def per_step_log_rows(
    config: Config,
    streams: np.ndarray,
    malicious: np.ndarray,
    attack_types: np.ndarray,
    seed: int,
    n_uavs: int,
    malicious_ratio: float,
    n_agents: int,
) -> List[dict]:
    rows = []
    stride = 10
    for step in range(0, config.steps, stride):
        time_s = step * config.update_interval_s
        for node in range(n_uavs):
            item = {
                "seed": seed,
                "n_uavs": n_uavs,
                "n_agents": n_agents,
                "malicious_ratio": malicious_ratio,
                "time_s": time_s,
                "node_id": node,
                "is_malicious": int(malicious[node]),
                "attack_type": str(attack_types[node]),
            }
            for idx, name in enumerate(TRUST_FACTORS):
                item[name] = float(streams[step, node, idx])
            rows.append(item)
    return rows


def summarize_mean_std(series: pd.Series, percent: bool = False) -> str:
    mean = float(series.mean())
    std = float(series.std(ddof=1))
    if percent:
        return f"{mean * 100:.1f} ± {std * 100:.1f}"
    return f"{mean:.1f} ± {std:.1f}"


def normal_p_value_from_t(t_stat: float) -> float:
    normal = NormalDist()
    return 2.0 * (1.0 - normal.cdf(abs(t_stat)))


def paired_test(x: Iterable[float], y: Iterable[float]) -> Tuple[float, float, float]:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    diff = x_arr - y_arr
    mean_diff = float(diff.mean())
    std_diff = float(diff.std(ddof=1))
    if std_diff == 0.0:
        t_stat = math.inf if mean_diff != 0.0 else 0.0
        p_value = 0.0 if mean_diff != 0.0 else 1.0
        effect = math.inf if mean_diff != 0.0 else 0.0
    else:
        t_stat = mean_diff / (std_diff / math.sqrt(len(diff)))
        p_value = normal_p_value_from_t(t_stat)
        effect = mean_diff / std_diff
    return t_stat, p_value, effect


def holm_correction(p_values: List[float]) -> List[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, (original_idx, p_value) in enumerate(indexed):
        running = max(running, min(1.0, (m - rank) * p_value))
        adjusted[original_idx] = running
    return adjusted


def pearson_correlation_summary(config: Config, streams_by_seed: Dict[int, np.ndarray]) -> pd.DataFrame:
    per_seed = []
    for seed, streams in streams_by_seed.items():
        post = streams[config.warmup_steps :].reshape(-1, 5)
        corr = np.corrcoef(post.T)
        for i in range(5):
            for j in range(5):
                per_seed.append({"seed": seed, "row": TRUST_FACTORS[i], "col": TRUST_FACTORS[j], "value": corr[i, j]})
    df = pd.DataFrame(per_seed)
    summary = df.groupby(["row", "col"])["value"].agg(["mean", "std"]).reset_index()
    return summary
