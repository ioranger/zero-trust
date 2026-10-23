# Spatio-Temporal Residual Shape (STS) block — executable design

Status: **proposal, not implemented, and not scheduled.** Nothing in this document
has been written into the generator, the feature extractor, or the manuscript.
This file exists so the design can be reviewed before any of it is built.

**Not on the manuscript's critical path.** The work that would test it has been
deferred: the two diagnostic arms that were run in the meantime
(`spatial_position_riskonly` and `spatial_position_gated`) both came back
negative, and the manuscript now carries that result instead of a proposal. The
measurements that settle the question are in `operating_point_probe.py` and
`fusion_protocol_check.py`.

Owner: the S-TIM artifact, `F:\zero trust\zero-trust`
Related: `artifacts/analysis/SPATIAL_STUDY.md`, `artifacts/analysis/modality_complementarity.py`

---

## 0. What this is for, and what would falsify it

The manuscript's two blind spots are closed by two feature blocks. The claim
under test is a *structural* one: a window-based trust aggregator cannot
express evidence that is not a summary of the node's own level. The paper
currently supports that claim with three blocks and no fourth.

This proposal adds a fourth block and, more importantly, gives the paper a
**complete structural frame** instead of a collection of blocks:

| | level (window summary) | shape (temporal form) |
|---|---|---|
| **the node itself** | marginal, 13 dims | shape, 5 dims |
| **the node against its neighbours** | neighbourhood, 5 dims | **STS, 5 dims — proposed** |

The current 23 dimensions are exactly this 2x2 with one cell empty. The
spatial block is the only one that is *time-aggregated before it is compared
to the neighbourhood*:

```python
# artifacts/scripts/reference_simulator.py, extract_spatial_features
recent = streams[-120:].mean(axis=0)      # <- time-aggregated first
nb_T1  = A @ recent[:, 0]
dev_T1 = recent[:, 0] - nb_T1
```

So the manuscript's "Spatio-Temporal Trust Inference" has no actual
spatio-temporal interaction: the spatial block carries no time structure and
the temporal block carries no spatial structure. STS closes that.

**Falsification criteria, declared before the work starts:**

* **F1** If the STS block is constant across nodes, or a probe cannot separate
  the position-inconsistent attackers from the benign population using the STS
  block *alone*, the block carries no signal on the existing scenario. The
  design then stops. This is a legitimate negative result and is reported as
  one; the block is not shipped.
* **F2** If a candidate attacker construction leaves detectable structure in
  the attacker's *own* marginal or shape features, that construction does not
  isolate the STS block and is rejected.
* **F3** If STS improves nothing over the 23-dimensional representation on the
  spatial scenario, at equal training budget and equal features for the
  control, the block is not worth the width and is dropped.

Nothing below is written into the published configuration. Every new key
defaults to the current behaviour, and the published table must reproduce
24/24 afterwards.

---

## 1. Why the existing three blocks cannot see it

Verified against the generator, not assumed.

### 1.1 The spatial field is a per-node constant

`spatial_geometry()` computes the RF field once per seed from static
positions; there is no mobility in the spatial scenario. `field_offset` is
therefore constant in time for every node:

```python
field_offset[:, :] = amp * own_field[:, None]
```

### 1.2 The forger's spatial inconsistency is a constant offset

A position-inconsistent attacker has its field offset zeroed and then
replaces its whole stream with a genuine benign node's recorded stream:

```python
field_offset[is_pos] = 0.0          # does not reflect the local RF field
...
streams[:, node, :] = streams[:, source, :]   # verbatim replay
```

So the forger's neighbourhood-relative deviation
`d(t) = x_forger(t) - mean_{j in N} x_j(t)` is a series whose *mean* is far
from zero (its neighbours carry a field offset it does not) but whose
*temporal form* is that of the benign node it copies.

### 1.3 Consequence

The neighbourhood block sees the level of `d` and therefore detects the
forger (83.6% in the published spatial scenario). The STS block would see the
*form* of `d`, and on the current attacker that form is a benign node's own
form. **On the existing scenario the STS block is expected to be weak**, and
probe P1 (§4) is the test of that expectation.

This is the uncomfortable but important finding in this design: the block is
structurally justified and empirically empty at the same time. A fourth
attacker class is needed to fill it.

---

## 2. The missing attacker class

The existing three attack classes are organised along one axis (is the attack
periodic?) and the position-inconsistent class adds a second (is the
attacker's *own* telemetry clean?). What is missing is an attacker whose
**inconsistency is intermittent**.

### 2.1 Construction: the intermittent field-reflector

A node that reflects the local RF field *only part of the time*.

* **Consistent phase.** It reports a genuine benign node's telemetry, with the
  local field offset added, so that what it reports is what a node in its own
  cell would report. `x_reported(t) = x_source(t) + (field_local - field_source)`.
  Its neighbourhood deviation is then approximately zero.
* **Inconsistent phase.** It reports the same benign node's telemetry
  verbatim, with no local field correction. Its neighbourhood deviation is the
  full field mismatch, the same magnitude the current forger produces.
* **Duty cycle.** The phase alternates on a fixed period, as the temporal
  on-off attacker does.

### 2.2 What each block sees

| block | consistent phase | inconsistent phase | time-averaged | form |
|---|---|---|---|---|
| marginal | benign | benign | benign | benign |
| shape (own) | benign series | benign series, joined at the phase boundary | mostly benign | **a periodic join — see F2** |
| neighbourhood | ~0 | large | **diluted by the duty cycle** | not represented |
| **STS** | ~0 | large | not represented | **periodic two-level structure** |

The neighbourhood block's *level* signal is diluted by the duty cycle, which
is exactly the failure mode STS is meant to catch: the same dilution that
makes the temporal on-off attacker invisible to a window summary makes the
intermittent field-reflector invisible to a time-averaged spatial statistic.

### 2.3 The confound, stated up front (F2)

The phase boundary joins two different series, and the join may be visible in
the attacker's *own* shape features. If the join is a clean square wave, the
existing shape block detects the attacker and STS is not the mechanism that
does.

Two candidate mitigations, to be tried in this order:

* **M1 — smooth handover.** Make the phase boundary itself a transition the
  attacker can plausibly have: instead of switching abruptly, the forger
  blends over a few steps. The join then produces no flip and no two-level
  structure.
* **M2 — random phase boundaries.** Replace the fixed duty cycle with
  stochastic switching at the same mean rate. A random switch produces a
  Poisson-like flip process, which the *periodic* shape statistics
  (`shape_acf_excess`, `shape_switch_cv`) are designed to ignore — they are
  scale-free and period-agnostic, and the manuscript's own time-shuffle
  control attributes +10.6pp of AUC to sequence order, so an irregular switch
  pattern is deliberately hard for them.

M2 is the more elegant construction and is preferred; M1 is the fallback.

**F2 is the gate.** If neither M1 nor M2 produces an attacker whose own
marginal and shape features are clean, the construction is rejected and the
STS block has no attacker. The honest outcome at that point is that the 2x2
frame is complete but its fourth cell is empty on this threat model, which is
a limitation to report rather than a block to ship.

---

## 3. Formal definition

Let `x(t) ∈ R^{n×4}` be the four behaviour channels at step `t`, and `A` the
row-normalised neighbour matrix (`adjacency_from_positions`).

```
d(t) = x(t) − A x(t)          ∈ R^{n×4},   per step, per channel
```

For node `i` and channel `c ∈ {T1, T4}` (the two channels the existing shape
block uses, `_SHAPE_ATTACK_CHANNELS = (0, 3)`), take the post-warm-up slice

```
d̃_i,c(t) = d(t)[i, c]      for t ∈ [warmup, steps)
```

and apply the **existing** `shape_features()` from `marl_policy.py` to it,
then average over the two channels exactly as `extract_shape_features()` does.

Result: 5 dimensions per node.

### 3.1 The property that makes this block consistent with the shape block

All five shape statistics are **shift-invariant and scale-invariant**:

| statistic | shift-invariant | scale-invariant | why |
|---|---|---|---|
| `shape_acf_excess` | yes | yes | the ACF is computed on the mean-removed series |
| `shape_acf_prominence` | yes | yes | same |
| `shape_flip_rate` | yes | yes | it is built from `np.diff` |
| `shape_two_level` | yes | yes | it is a ratio of quantile spreads |
| `shape_switch_cv` | yes | yes | it is built from the gaps between flips of `np.diff` |

So the STS block is **automatically orthogonal to the neighbourhood block**:
the neighbourhood block measures the *level* of `d`, the STS block measures
only its *form*. No mean removal is needed, and the two blocks cannot
duplicate each other.

This was checked rather than assumed. Applying `shape_features()` to a series
`x`, to `x + 5.0`, to `2.5x` and to `-2.5x` returns the same five values to
within 2.8e-17, so the invariance holds exactly, including under a negative
scale. It should still be asserted in a unit test before the block ships,
because the property is what makes the two blocks independent and a future
edit to `shape_features()` could break it silently.

### 3.2 Edge cases to handle explicitly

* **Isolated nodes.** `A.sum(axis=1) <= 0` gives `d(t) = x(t)`, so the STS
  block would silently contain the node's *own* shape. The existing block
  zeroes isolated nodes (`feats[isolated] = 0.0`); STS must do the same.
* **Window length.** `shape_features()` returns zeros when
  `n < _SHAPE_ACF_MAX_LAG + 2 = 122`. The post-warm-up window is 400 steps
  in the published configurations, so the block is defined; a shorter trace
  gets zeros, which the regime gate already rejects.
* **Post-warm-up alignment.** Use `streams[config.warmup_steps:]`, the same
  slice `extract_shape_features()` uses, so the two temporal blocks see the
  same interval.

---

## 4. Probe P1 — do not build before measuring

**P1 is a half-day script and it gates the whole proposal.** It measures,
on the *existing* spatial configuration (19 evaluation seeds, 800 UAVs):

1. Is the STS block constant across nodes? (the analogue of the
   `shape_switch_cv` degeneracy already disclosed on the packet traces)
2. Can a probe on the STS block alone separate the position-inconsistent
   attackers from the benign population? Report the area under the curve.
3. Same question for the current neighbourhood block, as the reference.
4. Does the deviation series `d(t)` of a forger actually differ in *form*
   from that of a benign node, or only in level? (Direct measurement: the
   shift- and scale-normalised standard deviation of `d̃` per node.)

**Decision rule.** If P1 shows no separation at all, the block is empty on
the current threat model, and the next step is the attacker construction in
§2, not more feature engineering.

P1 is implemented as `artifacts/analysis/sts_probe.py`. It must not touch
the generator.

---

## 5. Implementation plan

Ordered so that each step is verifiable and reversible.

### Step 1 — P1 probe (no generator change)

New file `artifacts/analysis/sts_probe.py`. Reads the committed spatial
run's streams, computes the STS block with a local copy of the definition,
and reports items 1–4 above. **No code in `artifacts/scripts/` changes.**

### Step 2 — the feature block behind a switch

`artifacts/scripts/reference_simulator.py`

* **Keep `extract_spatial_features()` byte-identical.** Add a new function
  next to it:

  ```python
  def extract_spatiotemporal_features(config: Config, streams: np.ndarray,
                                      A: np.ndarray) -> np.ndarray:
      """Shape statistics of the neighbourhood-relative deviation series."""
  ```

  It returns `(n_nodes, 5)`, zeroed for isolated nodes.

* Add the name list next to `SPATIAL_FEATURE_NAMES` in
  `artifacts/scripts/marl_policy.py`:

  ```python
  SPATIOTEMPORAL_FEATURE_NAMES = [
      "sts_acf_excess", "sts_acf_prominence", "sts_flip_rate",
      "sts_two_level", "sts_switch_cv",
  ]
  ```

`artifacts/scripts/marl_policy.py`

* New gate next to `spatial_features_enabled()`:

  ```python
  def spatiotemporal_features_enabled(config: Config) -> bool:
      return bool((config.raw.get("spatial") or {}).get(
          "spatiotemporal_features", False))
  ```

* In `extract_marl_policy_features()`, append the new block **after** the
  existing spatial block, guarded by the gate and by
  `spatial_adjacency is not None`. Feature width goes 23 → 28 for the
  configurations that enable it, and **stays 23 for every published
  configuration**.

* `baseline_feature_view()` is **not** changed. The per-node baselines never
  receive a neighbourhood-relative block, and the STS block is
  neighbourhood-relative by definition. If the baselines were given it, the
  comparison would become about input width rather than about architecture,
  which is exactly the point the paper's protocol exists to prevent. The
  fusion-mechanism ablation's switch (`fairness.learned_baselines_get_spatial_block`)
  must **not** be extended to it.

### Step 3 — the attacker construction (only if P1 is inconclusive)

`artifacts/scripts/reference_simulator.py`, in the spatial generator.

* New config keys under `spatial`:

  | key | default | meaning |
  |---|---|---|
  | `forger_duty` | `1.0` | fraction of the window in the inconsistent phase; `1.0` reproduces today's always-inconsistent forger |
  | `forger_period` | `90` | phase period in steps, matching the temporal on-off attacker's half-period |
  | `forger_mode` | `"static"` | `"static"` or `"alternating"`; the latter is M2 of §2.3 |

* The generator's forger handling moves from a single end-of-loop copy to a
  phase-aware copy:

  ```python
  # current, at the end of generation
  streams[:, node, :] = streams[:, source, :]

  # proposed: copy only the inconsistent-phase steps, and apply the local
  # field correction on the consistent-phase steps
  ```

  The local field correction needs the source's own field offset, so
  `field_offset` must be snapshotted before it is zeroed for the forgers.

* **The default must be bit-identical.** `forger_duty = 1.0` with
  `forger_mode = "static"` has to reproduce today's stream exactly, and the
  published spatial table has to reproduce cell for cell. This is the
  regression gate, and it is the same discipline as
  `compare_snapshot_to_published.py`.

### Step 4 — the ladder

`artifacts/analysis/sts_ladder.py`, extending the existing
`modality_complementarity.py` pattern:

| configuration | dimensions | what it isolates |
|---|---|---|
| marginal only | 13 | the published level baseline |
| + shape | 18 | the temporal block |
| + neighbourhood | 23 | the spatial block, the published S-TIM |
| + STS | 28 | the proposed block |

Each row is trained and evaluated on the same seeds with the same budget, and
reported per attack class, so the ladder answers "which block closed which
blind spot" in the same form the paper already uses for Table 13.

### Step 5 — the attacker-family ablation

With the intermittent forger in the generator, a second ladder over the
attacker class:

| attacker | marginal | shape | neighbourhood | STS |
|---|---|---|---|---|
| constant / dormant / on-off | detects | misses | weak | weak |
| position-inconsistent (static) | misses | misses | detects | weak |
| **position-inconsistent (intermittent)** | misses | misses | **diluted** | **detects** |

The third row is the claim. If it does not hold, the block is reported as
uninformative and the paper says so.

---

## 6. Acceptance criteria, pre-registered

Numeric, and fixed before running:

* **A1** Published artifacts unchanged: `compare_snapshot_to_published.py`
  reports 24/24, and the published spatial table reproduces cell for cell
  from a fresh run of `configs/spatial_position.json`.
* **A2** The 28-dimensional model beats the 23-dimensional model on the
  position-inconsistent attackers of the *existing* scenario by at least
  5pp of detection rate, paired over the same 19 seeds at `p < 0.05`.
  If the block is only useful for the new attacker class, A2 is relaxed to
  "not worse" and the claim is moved entirely onto the new class.
* **A3** The new attacker class is invisible to the marginal and shape
  blocks: their detection rate on it is below 20%.
* **A4** The neighbourhood block is *degraded* on the new class relative to
  the static forger, by at least 10pp, confirming that time-averaging
  dilutes the signal. This is the mechanism claim, and it is falsifiable
  independently of the STS block.
* **A5** The STS block is not constant across nodes (no new degenerate
  column), checked by the same test the regime gate applies to the packet
  traces.
* **A6** The per-node baselines are unchanged in every row: they never
  receive the neighbourhood or the STS block.
* **A7** A parameter-matched control: the MLP-Trust baseline widened and
  deepened to the same parameter count as the new model, so that a gain
  cannot be attributed to capacity.

---

## 7. Risks and kill criteria

| risk | likelihood | consequence | kill criterion |
|---|---|---|---|
| P1 shows the block is empty on the current scenario | high | the block needs a new attacker to mean anything | if P1 is negative **and** the construction in §2 fails F2, the block is not shipped and the negative result is reported |
| the phase boundary is visible in the attacker's own shape features | medium | the existing shape block detects the attacker and STS is redundant | F2, with M1 then M2 tried in that order |
| the STS block adds width without adding information | medium | a wider model that is no better | A2 relaxed, and the block dropped if it cannot be shown to add anything |
| the generator change perturbs the published spatial scenario | low | a silently different benchmark | A1, which is a hard gate on the default path |
| "another block" reads as feature-shopping | high | a reviewer objection that the frame does not answer | the 2x2 argument in §0, and A2's pairing, have to be the presentation, not a table of gains |
| the new attacker is judged artificial | high | the strongest objection to the whole scenario family | the construction has to be motivated by an attacker that is *plausible*, not by the feature it defeats; "reflects the RF field only part of the time" is plausible, "designed so that STS sees it" is not |

---

## 8. Workload

| step | effort | depends on |
|---|---|---|
| P1 probe | half a day | nothing |
| feature block behind a switch | one day | P1 |
| attacker construction (M1, then M2) | one to two days | P1 is negative or inconclusive |
| ladder and ablation scripts | one day | the block exists |
| parameter-matched control | half a day | the new model exists |
| packet-trace variant (positions in the trace) | one day, optional | the block exists and the main path holds |

The optional last item is worth flagging: the ns-3 trace already carries
`x_m` and `y_m` per node per step, so a **time-varying** adjacency can be
built from the trace, which the generated scenario does not have. That would
put the fourth block on real packet data, where the manuscript currently has
no evidence for its central claim. It is the highest-value item on the list
and the one that is hardest to say no to.

---

## 9. Explicitly out of scope for this proposal

* Changing the published configuration, or the published 23-dimensional
  protocol. The 23-dimensional model stays the published one.
* The decision-layer work discussed separately (modality routing, per-node
  adaptive thresholds). It is a different proposal with a different risk
  profile and should be decided on its own merits.
* A learned temporal encoder over the raw window. It is the only mechanism
  that is structurally not reducible to the fixed vector, and it needs a data
  budget argument before it can be attempted.
* Any change to the rule-based baselines. Their fixed weighting is their
  definition, not a defect to be fixed.

---

## 10. The one-paragraph version

The paper's three feature blocks are three cells of a 2x2: the node's own
level, the node's own temporal form, and the node's level relative to its
neighbours. The fourth cell — the temporal form of the node's inconsistency
with its neighbours — is empty, and filling it requires an attacker whose
spatial inconsistency is intermittent, because a time-averaged spatial
statistic dilutes exactly the signal an intermittent inconsistency leaves.
The proposal is to add the block behind a default-off switch, to add that
attacker to the threat model behind a default-off switch, and to test the
claim with a paired ladder and a parameter-matched control, with the
falsification criteria declared in advance. If the block turns out to be
empty on the current threat model, that is reported as a negative result and
nothing is shipped.
