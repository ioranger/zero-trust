# Pre-registration for the focal-loss gamma sweep

Written **before** the sweep was run. The focal arm with $\gamma = 2$ has
already been run and reported (it failed its acceptance lines and is in the
repository as `spatial_position_focal`); the sweep below asks whether a
milder non-saturating objective keeps that arm's advantage over the
feature-matched control without giving up the absolute rates.

## What was measured at $\gamma = 2$

| | published (BCE) | focal $\gamma=2$ | focal MLP |
|---|---|---|---|
| class mean | 89.0 | 84.9 | 62.5 |
| constant | 87.2 | 80.2 | 73.1 |
| dormant | 93.4 | 90.4 | 88.6 |
| on--off | 91.7 | 87.5 | 87.2 |
| position | 83.6 | 81.3 | 1.2 |
| benign spec. | 96.1 | 97.7 | 98.6 |
| accuracy | 93.8 | 93.8 | 85.5 |

Two things happened at once. The absolute rates fell, because a
non-saturating objective gives up the margin that a perfectly separable
training split rewards. And the comparison against the feature-matched
control reversed: under BCE the proposed model trails the control on the level
classes by 1.9 and 2.2 points, and under the focal objective it leads by
7.1 ($p<0.0001$) and 1.8 ($p=0.012$) points. The auxiliary supervision is
therefore not inert: it is a regulariser whose value depends on whether the
risk loss still has a gradient on the training split.

## The sweep

Two additional values of the modulating factor, $\gamma \in \{0.5,\;1.0\}$,
each with everything else identical to the published spatial configuration and
each with the feature-matched comparators trained under the same objective
inside the same run.

**Selection rule.** The reported configuration is the one whose **class mean
over the four attack classes on the twelve held-out validation seeds** is the
higher of the two. The evaluation seeds are used once, for the selected value,
and the evaluation results of both values are reported whether or not one of
them is selected.

**Acceptance lines** are the same as for the $\gamma = 2$ arm, plus one new
line that the $\gamma = 2$ arm could not have met, because the point of the
sweep is to keep the absolute rates:

1. class mean over the four attack classes **>= 89.0** (the published arm's
   value; the $\gamma=2$ arm reached 84.9).
2. aggregate accuracy **>= 93.3**.
3. constant **>= 87.2** (not below the published arm; the $\gamma=2$ arm
   reached 80.2). The stricter 90.8 line is reported as well.
4. dormant **>= 93.4** (not below the published arm).
5. on--off **>= 91.7** (not below the published arm).
6. position-inconsistent **>= 83.6** (not below the published arm).
7. benign specificity **>= 93.0**.
8. no attack class regresses by more than 1.0 pp against the published arm.
9. the proposed model leads the feature-matched control on the level classes
   by a paired margin that is significant at $p<0.05$, which is what the
   $\gamma=2$ arm achieved and what the published objective does not.

## What happens either way

* If one value passes, the manuscript reports it as a separately identified
  configuration, with the $\gamma=2$ arm and the published arm reported next
  to it.
* If none passes, all three arms are reported as a negative result, the
  published arm remains the one the manuscript leads with, and the mechanism
  found at $\gamma=2$---that the auxiliary supervision becomes a significant
  advantage as soon as the risk loss stops saturating---is reported as the
  mechanistic result it is.
* The two arms are compared to the feature-matched control only under the same
  objective, so no comparison in this sweep can be attributed to the training
  signal rather than to the evidence.
