# Archived Manuscript Renders

These PDFs are the **superseded v4 manuscript** and are retained for audit
only. They are **not** the current paper.

## Why they are archived

The v4 tables were produced under a comparison protocol that was biased in
favour of the proposed method. `artifacts/configs/legacy_paper_protocol.json`
documents the three artefacts involved:

- per-method Gaussian score noise injected into the rule-based adapters only
  (MFA 0.035, FUBA 0.030, GALTrust 0.025, GDM-DTM 0.026), which depressed
  those baselines by roughly 20 percentage points;
- method-specific task-allocation and success-probability adjustments applied
  to the proposed model;
- cost and latency columns produced by closed-form affine expressions rather
  than by measurement.

Under the unbiased protocol in `artifacts/configs/default.json` the rule
baselines recover (MFA 84.8, FUBA 87.2, GDM-DTM 87.6) and the proposed model no
longer exceeds a same-feature MLP. The v4 abstract's claim of "+10.6 pp over
GDM-DTM, consistently exceeding all compared baselines" does not survive that
correction.

The legacy protocol configuration is kept on purpose: it reproduces the old
numbers so the discrepancy can be audited rather than merely asserted.

## Contents

| File | Description |
|------|-------------|
| `template_v4_legacy.pdf` | v4 render, title "MARL-based Trust Evaluation for Zero-Trust Low-Altitude UAV Networks" |
| `template_v4_legacy_alt.pdf` | Earlier v4 render of the same manuscript, retained for completeness |

## Current manuscript

See `../template.pdf`. The current version is titled *Structural Blind Spots
of Window-Based Trust Aggregation in Low-Altitude UAV Networks* and its method
is named S-TIM.
