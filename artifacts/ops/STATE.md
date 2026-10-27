# State of the manuscript

Written for whoever picks the work up next, on this machine or another one.
Everything below is checked by the scripts in `artifacts/analysis/`, and the
numbers are the ones the committed tables carry.

## What the paper is

`paper/template.pdf` (31 pages, 4 figures, 11 tables, 39 references, all cited).

S-TIM is a supervised encoder over per-node trust-stream summaries. The claim
is located in the **representation**, not in the network: the summarisation
step that conventional trust aggregation performs has two structural blind
spots, one temporal and one spatial, and the paper measures both.

- Temporal: the marginal window summaries that rule-based aggregators consume
  cannot express intermittency, so the periodic on-off attackers are detected
  at 0.0-38.0% against 88.0% once five scale-free temporal-shape statistics
  are added.
- Spatial: an attacker whose own telemetry is indistinguishable from the
  benign population is invisible to every method that scores one node at a
  time, at 2.1% detection, and five neighbourhood-relative statistics raise
  the same model to 83.6% (a paired gain of +81.5 pp, p<0.0001).

The comparators are five rule-based adapters: MFA, FUBA, GALTrust, GDM-DTM
and AHP-Entropy. They are paper-level reimplementations over a common T1-T5
interface, and the manuscript says so wherever the numbers appear.

## The claims that are deliberately narrower than they could be

- The gain is located in the representation rather than in the encoder, and
  the fusion-mechanism control is reported as a null result.
- The cross-validation mechanism of Section 3.4 and the chi-squared anomaly
  equation belong to the stated design; the released implementation does not
  run them, and the manuscript says so in the section, in the algorithm table
  and in the guard that checks the artifact for the threshold.
- The leave-one-factor-out control shows that only two of the five trust
  dimensions carry the result in this generator, that the energy and the
  historical dimension are inert, and that the communication dimension is
  worth different things in the two scenarios. That is reported rather than
  argued away.
- The task-success number is a simulator proxy, and the proxy differences sit
  inside the seed-level standard deviation.

## What the reviewer questions produced

Two reviewer-shaped questions drove most of the recent work.

**"Why so many trust dimensions, when every one costs compute?"** The
leave-one-factor-out control in Table 11 answers it: six arms per scenario,
each removing one dimension, each retrained and re-evaluated, compared with
the published configuration re-run on the same code path. The comparators keep
all five dimensions in every arm, so each row measures what the dimension is
worth to the proposed model alone. The reasons behind the four findings are
structural and readable off the generator: the shape and neighbourhood blocks
are computed on T1 and T4, T5 is a smoothed mean of the other four, and the
energy channel is the one the generator makes hardest to read.

**"Do the figures and the tables say the same thing as the text?"** The
`audit_float_correspondence.py` check was written for that: every cell of every
table against its data source, every prose claim against the configuration that
backs it, and every name a caption promises against the boxes the figure
draws. It found five mismatches, all of which are fixed.

## Verifying the current state

```powershell
cmd /c 'F:\zero trust\zero-trust\build.bat'
$py = 'F:\zero trust\py310\python.exe'
$an = 'F:\zero trust\zero-trust\artifacts\analysis'
foreach ($s in 'latex_warnings.py','verify_new_tables.py','paper_consistency_check.py',
                'check_bibliography_coverage.py','check_no_agent_terms.py',
                'check_abstract_claims.py','audit_float_correspondence.py',
                'audit_floats.py','audit_sparse_pages.py') {
    & $py -u (Join-Path $an $s)
}
```

All nine must exit 0. The build must report 31 pages and no LaTeX warnings.

## Open items

1. **The target journal and the deadline are still unknown.** They decide how
   hard the wording has to work and whether the abstract has to come down from
   262 words.
2. **No learned comparator appears in the paper.** The artifact trains two
   (LR-Trust and MLP-Trust) and the replication package carries them, but
   the manuscript reports only the five rule-based adapters. In the published
   scenario MLP-Trust reaches 97.5% accuracy against 97.1% for S-TIM, so
   adding it as a row is a decision with consequences, not a formatting
   choice.

## The commit chain on `ioranger-patch-1`

The branch is the published line. The recent commits, in order, are the audit
trail: the leave-one-factor-out control and the figure/table audit, the
explanation of why each trust dimension behaves as it does, and the layout fix
that closed the hole between the two figures.
