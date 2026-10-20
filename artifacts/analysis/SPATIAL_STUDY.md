# Spatio-temporal complementarity study

This file records what the spatial (neighbourhood-relative) block buys, what it
costs, and which generator artefacts had to be removed before the question
could be asked at all. Every number here is derived from the committed arm logs
under `artifacts/analysis/runs/` or from the generator itself, and every
command that reproduces them is listed at the end.

## 1. Why a new attack class was needed

The three existing attack profiles -- `constant`, `dormant`, `on-off` -- are all
*behavioural*. They differ in what a node's own channel time series looks like,
so any method that reads one node's channels can, in principle, separate them.
The published result is that window-based aggregation cannot, because it
summarises each channel into marginal statistics over a trailing window and the
intermittent attacker is indistinguishable from a noisy benign node after that
summarisation. The shape block restores the missing information.

That story only covers attacks that live in the behaviour channels. It says
nothing about an attacker whose behaviour is clean. Such an attacker is the
common case in the literature on sophisticated UAV intrusion: it produces
well-formed telemetry and is caught by nothing, because every method in the
pool scores a single node.

The generator therefore gained a fourth profile, `position-inconsistent`:

  * it reports channels that are drawn from the benign population, so its own
    marginal statistics are statistically identical to a benign node's
    (`artifacts/analysis/diagnose_forger_visibility.py` measures the effect
    sizes: every behavioural feature has |Cohen's d| <= 0.04);
  * it is placed in an airspace cell whose RF field differs from the one it
    reports, so its *neighbours* carry a field offset that it does not.

Only a neighbourhood-relative statistic can see such a node. This is the
sharpest available test of whether the spatial block is a distinct source of
information or a re-description of the behavioural one.

## 2. Two generator artefacts that had to be fixed first

Both were found by diagnosis scripts kept in `artifacts/analysis/`, and both
would have produced a false answer rather than an ugly one.

  * **The field was a channel-subset proxy.** The field offset was applied to
    T1 and T4 only, which turned the cross-channel gap features into proxies
    for the field value. A node carrying no field offset then looked anomalous
    in the gaps for the wrong reason. The field is now applied to all four
    evidence channels as a common mode, which leaves the cross-channel gaps
    field-invariant.
    (`diagnose_clipping_artifact.py`.)

  * **The zero-mean field became a non-zero mean shift under asymmetric
    clipping.** With a benign reference of 0.80 and bounds of [0.02, 0.98], the
    positive excursions of the field clip while the negative ones do not, so
    the clipped benign mean drifts away from the reference and a forger that
    carries no field spread becomes visible to a purely behavioural method for
    the wrong reason. The reference is now shifted down by
    `spatial.reference_shift` so the clipping is symmetric against both bounds.

## 3. The comparison protocol

Every arm in the ladder shares the generator, the attack mix, the seeds
(evaluation seeds 1000-1018) and the thresholds. The arms differ only in which
feature blocks the model is given:

| Arm | Marginal (13) | Shape (5) | Spatial (5) | Width |
|---|---|---|---|---|
| `spatial_position_13dim` | yes | no | no | 13 |
| `spatial_position_18dim` | yes | yes | no | 18 |
| `spatial_position_23dim` | yes | yes | yes | 23 |

The neighbourhood block is withheld from LR-Trust and MLP-Trust in the main
protocol, because both are per-node aggregators by construction; handing them a
neighbourhood-relative feature would turn the comparison into a statement
about input width rather than about architecture. The
`spatial_position_fusion` arm reverses that on purpose, so that the linear
head, the MLP head and the multi-head policy consume the identical 23-dimensional
vector and any difference between them is attributable to the fusion mechanism.
`check_fusion_switch.py` verifies that the switch is a no-op for every other
configuration.

## 4. Results

### 4.1 The published table is untouched

`artifacts/analysis/compare_snapshot_to_published.py` compares the re-run of
`default.json` against the committed Table 2 and finds **24/24 cells exact**.
The generator changes therefore do not touch the published path.

### 4.2 The modality ladder

S-TIM, per attack class, same 20 seeds, one feature block apart:

| Features | constant | dormant | on-off | position-inconsistent | benign (specificity) |
|---|---|---|---|---|---|
| 13 dims (marginal) | 90.8 | 95.6 | 79.1 | 5.1 | 95.1 |
| 18 dims (+ shape) | 82.1 | 92.2 | 89.3 | 2.1 | 97.4 |
| 23 dims (+ spatial) | 87.2 | 93.4 | 91.7 | **83.6** | 96.1 |

Each block closes a blind spot the others cannot, and the blind spots are
disjoint:

  * the **shape** block closes the intermittent-attacker blind spot: on-off
    detection rises 79.1 -> 89.3 (+10.3 pp, p < 0.0001) when it is added.
  * the **spatial** block closes the telemetry-forging blind spot: 2.1 -> 83.6
    (+81.5 pp, p < 0.0001) when it is added.

The two blocks are not substitutes. The 18-dimensional model is at 2.1% on the
forger, and the 23-dimensional model is at 91.7% on the intermittent attacker,
which is the same level the shape block already reached.
### 4.3 What each block costs

The blocks are not free, and the paper reports this rather than only the
headline:

| Step | constant | dormant | on-off | position-inconsistent | benign spec |
|---|---|---|---|---|---|
| + shape (13 -> 18) | **-8.7** (p<0.0001) | **-3.4** (p=0.0001) | +10.3 (p<0.0001) | -3.0 (p=0.0002) | +2.3 (p<0.0001) |
| + spatial (18 -> 23) | +5.1 (p=0.0003) | +1.2 (p=0.055) | +2.4 (p=0.0002) | **+81.5** (p<0.0001) | -1.3 (p<0.0001) |
| net (13 -> 23) | -3.6 (p=0.0007) | -2.2 (p=0.0019) | **+12.6** (p<0.0001) | **+78.5** (p<0.0001) | +1.0 (p=0.0007) |

So the shape block buys the on-off blind spot at the cost of 8.7 pp on constant
attackers, and the spatial block both closes the second blind spot and recovers
most of that cost. The net cost of the full 23-dimensional representation is
3.6 pp on constant and 2.2 pp on dormant, against +12.6 pp on on-off and
+78.5 pp on position-inconsistent.

This is the opposite of the probe-level verdict, which found that concatenating
the blocks drags the other classes down (constant 78.7 -> 66.3, dormant
97.3 -> 92.2, on-off 94.6 -> 88.0). The probe concatenated blocks and fitted a
linear model with equal weight on each; the trained model does not. The
difference between the two is what the fusion-mechanism ablation measures, and
it is the argument for the learned fusion over a fixed rule.

### 4.4 The proposed model against the traditional methods

Overall detection in the same scenario (19 evaluation seeds, 800 nodes,
malicious ratio 0.3):

| Method | accuracy | F1 | TSR | position-inconsistent |
|---|---|---|---|---|
| MFA / FUBA / GALTrust / GDM-DTM / AHP-Entropy | 39.7 - 44.0 | 44.9 - 45.5 | 74.5 - 75.9 | 67.9 - 77.1 (at a collapsed threshold, see below) |
| LR-Trust (per-node linear) | 81.4 | 63.2 | 81.5 | 6.2 |
| MLP-Trust (per-node MLP) | 86.0 | 72.8 | 82.2 | 4.2 |
| **S-TIM (18 dims, no spatial)** | 85.8 | 71.1 | 82.5 | 2.1 |
| **S-TIM (23 dims)** | **93.8** | **89.4** | **88.9** | **83.6** |

Two observations matter for the paper.

  * Without the neighbourhood block the proposed model and the feature-matched
    control are indistinguishable (85.8 vs 85.8 accuracy, 71.1 vs 72.4 F1),
    exactly as in the published i.i.d. scenario. The separation appears only in
    the scenario that contains an attack class the behavioural representation
    cannot express. A richer representation is only observable where the threat
    model needs it.
  * The separation above is a separation of representations, not of
    architectures, because the main protocol withholds the neighbourhood block
    from the per-node baselines. Section 4.5 removes that asymmetry and shows
    that a nonlinear per-node learner given the same vector reaches the same
    ceiling. The manuscript states this rather than banking the gap.

### 4.5 The fusion mechanism, with the representation held fixed

The main protocol withholds the neighbourhood block from LR-Trust and
MLP-Trust, so the separation in the table above is a separation of
*representations*. The `spatial_position_fusion` arm removes that asymmetry:
all three learners consume the identical 23-dimensional vector and differ only
in how they combine it.

| Learner on the same 23-dim vector | position-inconsistent | constant | dormant | on-off | benign spec |
|---|---|---|---|---|---|
| LR-Trust (linear head) | 60.8 (+54.6) | 50.8 (**-6.3**) | 86.1 (-3.3) | 82.1 (-4.2) | 91.3 (-2.2) |
| MLP-Trust (single MLP head) | **84.5 (+80.2)** | 88.9 (-0.2, n.s.) | 93.9 (-1.7) | 92.5 (+0.1, n.s.) | 95.6 (-0.6) |
| S-TIM (multi-head policy) | 83.6 (+81.5) | 87.2 (+5.1 vs 18 dims) | 93.4 (+1.2) | 91.7 (+2.4) | 96.1 (-1.3) |

Overall accuracy / F1 / TSR in the same arm:

| Method | 23 dims, baselines per-node (protocol) | 23 dims, baselines get the block |
|---|---|---|
| LR-Trust | 81.4 / 63.2 / 81.5 | 84.6 / 72.8 / 85.3 |
| MLP-Trust | 86.0 / 72.8 / 82.2 | **93.7 / 89.5 / 88.9** |
| S-TIM | 93.8 / 89.4 / 88.9 | 93.8 / 89.4 / 88.9 (identical) |

Three findings, and the middle one is a negative result that the manuscript has
to carry:

  * **The representation is the lever.** Handing MLP-Trust the same vector
    raises it from 4.2% to 84.5% on the forger (+80.2 pp, p < 0.0001) and from
    72.8% to 89.5% F1 overall. The information was never in the network.
  * **The nonlinearity is what buys it without interference.** The linear head
    extracts less of the forger signal (60.8% against 84.5%) *and* pays for it
    on the classes it already handled: -6.3 pp on constant, -4.2 pp on on-off.
    The MLP head extracts all of it and pays -0.2 pp (not significant) on
    constant. A linear combination of a per-node block and a neighbourhood-
    relative block cannot express the interaction between them; a nonlinear one
    can, and that is what stops the blocks from dragging each other down.
  * **The multi-head architecture adds nothing over a single nonlinear head.**
    S-TIM and MLP-Trust are within about one point of each other on every
    class and every metric once they see the same vector (S-TIM's numbers are
    bit-identical across the two arms, which also confirms that the switch
    touches the baselines and nothing else). This is the same conclusion the
    four-arm architecture control reached from the opposite direction, and it
    is reported rather than hidden: the paper's claim is about the
    representation, and the spatial study does not change that.

### 4.6 The rule-based methods in this scenario
The five rule adapters score about 40% accuracy with a benign specificity of
25-36% in this scenario, against 75-88% accuracy and 92-100% specificity in
the published scenario. That number cannot be read as "the rule baselines
cannot see this attack", because their scores are built around the generator's
absolute channel-reference profile (0.80 / 0.76 / 0.72 / 0.80 / 0.75) and the
spatial scenario moves that level. `diagnose_rule_threshold_transfer.py` and
`diagnose_spatial_counterfactuals.py` separate the two effects:

| Variant | accuracy | benign specificity | AUC |
|---|---|---|---|
| shift 0, no field, no forger | 85.0 | 93.7 | 0.925 |
| field on, forger on (the reported scenario) | 38.1 | 16.9 | 0.559 |
| shift 0, field on, forger on | 55.5 | 56.0 | 0.557 |
| shift on, no field, forger on | 30.0 | 0.0 | 0.796 |

Two distinct effects, both real:

  * the **spatial field** costs the rule adapters their ranking quality
    (AUC 0.925 -> 0.56): they score absolute channel levels, and the field
    makes an absolute level a function of where a node is rather than of what
    it is doing;
  * the **reference shift** moves their operating point, because their
    thresholds are fixed constants and their profiles are absolute.

Neither is recoverable by re-thresholding. The best F1 any of them reaches on
the same seed is **46.7%**, against **46.2%** for the trivial classifier that
labels every node malicious at a malicious ratio of 0.3. Their scores are at
the trivial-classifier level in this scenario, which is a stronger statement
than "the threshold was wrong", and it is reported with the diagnostic that
produced it rather than as a bare number.

### 4.7 Why only a neighbourhood-relative statistic sees the forger

`diagnose_forger_visibility.py` measures the effect size of every feature
against the benign population:

| Feature block | largest \|Cohen's d\| against benign |
|---|---|
| behavioural (13 marginal) | 0.03 |
| temporal shape (5) | 0.04 |
| **spatial neighbourhood (5)** | **1.99** (`spatial_rel_dev`), **1.14** (`spatial_std_dev`) | |

The forger's own channels are statistically indistinguishable from a benign
node's (raw T1 mean 0.4885 against 0.4868), and the two strongest separating
statistics are exactly the neighbourhood-relative ones. This is the mechanism
behind the +81.5 pp, and it is why the paper can say the spatial block is a
distinct source of information rather than a re-description of the behavioural
one.

## 5. Reproducing

```powershell
python -u artifacts/analysis/spatial_study_report.py
```

runs the published-table check, the modality ladder with its paired tests, the
fusion-mechanism ablation, the threshold-transfer diagnostic and the
counterfactual sweep in one pass and writes the two table files
`modality_ladder.txt` and `fusion_ablation.txt` next to the script.
