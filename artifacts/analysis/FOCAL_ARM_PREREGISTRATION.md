# Pre-registration for the focal-loss arm

Written **before** the arm was run, so that the acceptance lines cannot be
moved after the numbers are seen.

## What the arm changes

One thing: the risk loss. `marl_training.risk_loss = "focal"` with
`focal_gamma = 2.0`, which multiplies the binary cross-entropy by
`(1 - p_t)^gamma` per example. The generator, the attack mix, the feature set
(23 dims), the training seeds, the evaluation seeds, the decision threshold,
the auxiliary loss weights and the positive class weight are those of
`configs/spatial_position.json`.

The learned comparators (LR-Trust, MLP-Trust) are trained with the same
objective inside the same run, so the arm measures the objective rather than
the comparison protocol.

## Why the objective is the thing to change

Measured, not assumed. In the spatially inconsistent scenario, the forgers the
published arm misses still carry a larger neighbourhood-relative residual than
the benign population does: standardised residual 1.100 against 0.593, with a
90th percentile of 2.026 against 1.076 (`missed_forger_probe.py`). Their
evidence is present; the decision boundary leaves them on the wrong side.

Two alternatives were measured and rejected before this arm was designed:

* replacing the mixture with a maximum or a sum over the calibrated
  specialists is **worse**, not better: accuracy 87.1 against the mixture's
  93.6, with the position class collapsing to 48.7% (`specialist_decision_probe.py`);
* moving the decision threshold does not help either: at a matched 5% benign
  false-positive rate the aggregate accuracy is unchanged at 93.7%
  (`operating_point_probe.py`).

## Acceptance lines

The published arm is the reference: constant 87.2, dormant 93.4, on--off 91.7,
position-inconsistent 83.6, benign specificity 96.1, accuracy 93.8, F-score
89.4, class mean over the four attack classes 89.0.

The focal arm passes if **all** of the following hold.

1. class mean over the four attack classes **>= 90.0** (the published arm plus
   1.0 pp). This is the primary metric: it is the summary the four attack
   classes deserve, and it is not dominated by the 560 benign nodes.
2. aggregate accuracy **>= 93.3** (the published arm minus 0.5 pp). The
   minority classes may not be bought with the headline.
3. constant **>= 90.8** (the acceptance line the thirteen-dimensional arm set).
4. dormant **>= 95.6** (the same line).
5. on--off **>= 91.7** (not below the published arm).
6. position-inconsistent **>= 83.6** (not below the published arm).
7. benign specificity **>= 93.0** (at most 3.1 pp below the published arm).
8. no attack class regresses by more than 1.0 pp against the published arm.
9. the paired per-seed tests against the published arm are reported whatever
   the outcome, with the comparator trained the same way.

## What happens either way

* If the arm passes, the result is reported as a new, separately identified
  configuration. The published arm stays published and unchanged, and the
  manuscript says which configuration produced which number.
* If the arm fails, the numbers are reported as a negative result and the
  published arm remains the one the manuscript leads with. A failed arm is
  still a measurement, and the project rule is that a negative result is
  reported rather than dropped.

## What this arm cannot do

It cannot make the proposed model beat the feature-matched comparator, because
the comparator receives the same objective and the same evidence. What it can
do is raise the absolute detection rates and the class mean. If it does, the
manuscript reports the absolute numbers and says plainly that the comparator
improved by the same amount.
