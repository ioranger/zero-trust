# S-TIM Reproducible Artifact

Repository note: manuscript sources and publication figures are organized under
`paper/`. This directory is reserved for executable replication materials and
generated experiment outputs.

This directory contains the executable artifact for the current manuscript, whose
method is named S-TIM (Shape-augmented Trust Inference Model). It includes:

- PyTorch supervised encoder training, checkpoint output, and training logs, with a
  seed-level validation split and early stopping applied identically to the proposed
  model and to both learned baselines.
- The five-dimensional temporal-shape feature block, gated by
  `marl_training.shape_features` in the configs.
- Learned LR-Trust and MLP-Trust baselines trained on the same diagnostic features
  and seeds as S-TIM.
- Paper-level reimplementations of MFA, FUBA, GALTrust, and GDM-DTM over the same
  T1--T5 trust interface. These are our implementations, not the cited authors' code;
  the manuscript states that scope wherever they are compared.
- Statistical scripts, raw per-seed logs, generated tables, and generated figures.
- `analysis/` holding the probe-level evaluation, the duty-cycle sweep, the shape-block
  pre-screen, and a manuscript/CSV consistency checker.
- An ns-3 UAV trace-generation scenario plus a converter from packet/mobility traces
  to S-TIM T1--T5 trust streams.

Scope note: the PyTorch supervised trust-model training path has been executed in
this workspace. The ns-3 scenario was also built against `ns-3-dev-git` and run as a short
500 s smoke test with seed 1000. The generated trace is committed as
`artifacts/outputs/logs/ns3_packet_trace.csv` and the converted T1--T5 stream is
committed as `artifacts/outputs/logs/ns3_trust_streams.csv`. The manuscript's
main tables still come from the 50-seed trust-stream evaluation, not from ns-3
batch experiments.

## Environment

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r artifacts/requirements.txt
```

In this Codex workspace the commands were run with:

```bash
uv venv .venv --python /Users/jackkang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
uv pip install --python .venv/bin/python numpy pandas matplotlib scipy torch
```

## Reproduce the PyTorch Supervised Results

Run the full pipeline:

```bash
.venv/bin/python artifacts/scripts/train_marl_pytorch.py --config artifacts/configs/default.json --device cpu
.venv/bin/python artifacts/scripts/run_reference_experiment.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/summarize_results.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/evaluate_trace_driven.py --config artifacts/configs/default.json --trace artifacts/outputs/logs/ns3_trust_streams.csv
.venv/bin/python artifacts/scripts/plot_results.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/plot_training_trace.py --config artifacts/configs/default.json
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/analysis/build_architecture_figures.ps1
```

The training script writes a PyTorch checkpoint, learned baseline
checkpoints, and training traces before the evaluation script runs.
`run_reference_experiment.py` intentionally fails if
`artifacts/outputs/logs/marl_policy.json` or
`artifacts/outputs/logs/learned_baselines.json` does not exist.

## Channel-Focused Leave-One-Dimension-Out Study

The published leave-one-factor-out control prices the five trust dimensions
against the published generator, in which the adversary drives all four
observable channels down together, so the evidence one dimension carries is
largely duplicated in the dimensions that were kept. The study in this section
is the stronger adversary the manuscript's threat model allows: one that
manipulates a single dimension at a time, so that the dimension an attacker
manipulates is the only place where evidence about it exists. The
representation in this scenario is dimension-aligned, four columns per
dimension and each computed from that dimension alone, and the temporal-shape
block is off, because it is computed on T1 and T4 and would carry one
dimension's evidence into another dimension's arm.
The arms come in one family: the deployment arms, in which the input carries a
subset of the five dimensions and nothing else. They are grouped by the number of
dimensions the deployment observes, k: the leave-one-dimension-out arms observe
four, the three-dimension arms observe three, the two-dimension arms observe two,
and the single-dimension arms observe one. The reference observes all five. The
enumeration is exhaustive: all thirty-one non-empty subsets of the five dimensions
are trained and evaluated under one protocol, one arm each, so no budget and no
subset is missing. Together they price the dimension set from every side and form
a single monotone budget series whose bands do not overlap, in which the
configuration that observes all five dimensions is the best arm on every metric:
no dimension is dispensable, because removing any one of them costs accuracy, and
no dimension is sufficient on its own, because a deployment that observes a single
dimension cannot see the attackers that use the other four.

```bash
.venv/bin/python artifacts/analysis/make_channel_profile_configs.py
.venv/bin/python artifacts/analysis/run_channel_profile_ablation.py --work-root /tmp/zt_channel_profile
.venv/bin/python artifacts/analysis/channel_profile_ablation_report.py
.venv/bin/python artifacts/analysis/make_budget_table.py
.venv/bin/python artifacts/analysis/plot_dimension_budget.py
```

The runner trains and evaluates every arm in its own working tree, because the
checkpoint path of the training script is fixed relative to the root of the
configuration, and it keeps the five files per arm that the report reads in
`artifacts/analysis/runs/`. The configurations are `configs/channel_profile.json`,
its `configs/channel_profile_drop_T*.json` variants, which remove one dimension
from the input, and its `configs/channel_profile_only_T*.json` variants, which
keep every one, two and three dimension subset and nothing else. The single
two-dimension subset that has no `only_` configuration of its own, {T1, T4}, is
the leave-three-dimensions-out configuration `channel_profile_drop_T2_T3_T5`. The paired per-seed result
of the leave-one-dimension-out arms is written to
`artifacts/outputs/tables/channel_profile_ablation.csv`, the single-dimension
arms to `artifacts/outputs/tables/channel_profile_only_dimension.csv`, the whole
budget series to `artifacts/outputs/tables/channel_profile_dimension_budget.csv`
and its LaTeX body to `artifacts/outputs/tables/channel_profile_dimension_budget.tex`,
and the code-level component arms run on this generator to
`artifacts/outputs/tables/channel_profile_component_ablation.csv`. The figure
`paper/figures/dimension_budget.png` is drawn from the budget table by
`artifacts/analysis/plot_dimension_budget.py`.

## Spatial Scenario at a Matched Operating Point

The spatially inconsistent scenario compares six methods, and the five rule-based
comparators carry fixed thresholds that were set in the spatially uniform
generator. In that scenario those thresholds land at a 70--79% benign
false-positive rate: the comparators flag roughly three quarters of the benign
population, so their per-class detection rates at those thresholds are not
comparable to a detector's. This study places every method at a common benign
false-positive rate, using the recipe the manuscript already applies to its
probe-level tables: the cut is the one whose achievable benign false-positive
rate is closest to 5%, selected on the twelve held-out validation seeds of the
headline spatial configuration and then applied unchanged to the twenty
evaluation seeds. The proposed model keeps its deployed cut of 0.60, which
selects 3.9%, so the comparators are moved and the proposed model is not
re-tuned.

```bash
python -u artifacts/analysis/spatial_matched_operating_point.py
```

The script first reproduces the deployed-threshold numbers of the published
table cell for cell from the same code path, so that the corrected columns and
the published ones come from one computation. It then reports the matched-rate
numbers, the paired per-seed tests of the proposed model against the strongest
comparator on each metric, and the strongest rule adapter at the matched rate
for every configuration of the robustness table. The console transcript is kept
as `artifacts/analysis/spatial_matched_operating_point.txt`.

## ns-3 Trace Path

To generate packet/mobility traces in an ns-3 source tree:

```bash
cp artifacts/ns3/mtim_uav_trust.cc /path/to/ns-3/scratch/mtim_uav_trust.cc
cd /path/to/ns-3
./ns3 run "scratch/mtim_uav_trust --nUavs=15 --maliciousRatio=0.30 --seed=1000 --duration=500 --csv=/absolute/path/ns3_packet_trace.csv"
```

Convert the trace to T1--T5 trust streams:

```bash
.venv/bin/python artifacts/scripts/ns3_trace_to_trust.py \
  --trace /absolute/path/ns3_packet_trace.csv \
  --output artifacts/outputs/logs/ns3_trust_streams.csv
```

The smoke test in this workspace generated 735 packet/mobility observation rows
plus a header row. The current manuscript tables are generated from the seeded
trust-stream environment, not from ns-3 traces. Replace that input path only
after running multi-seed ns-3 batch experiments and validating the traces.

To reproduce the trace-driven sanity-check table reported in the manuscript:

```bash
.venv/bin/python artifacts/scripts/evaluate_trace_driven.py \
  --config artifacts/configs/default.json \
  --trace artifacts/outputs/logs/ns3_trust_streams.csv
```

## Baseline Reimplementation Protocol

Baseline code is centralized in `artifacts/scripts/baseline_reimplementations.py`.
It implements:

- `MFA`: equal-weight multi-factor averaging.
- `FUBA`: fuzzy UAV behavior analytics style membership fusion over behavior,
  communication, energy, task, and history trust.
- `GALTrust`: anomaly-profile adapter approximating GAN/type-2 fuzzy scoring at
  the shared trust-feature interface.
- `GDM-DTM`: group decision-making dynamic trust adapter with consistency
  penalty.
- `LR-Trust`: logistic risk classifier trained on S-TIM's diagnostic features.
- `MLP-Trust`: two-layer neural risk classifier trained on S-TIM's diagnostic
  features.

These are paper-level reimplementations under a common T1--T5 interface, not
official source code from the cited authors. Treat comparisons as controlled
reimplementations unless official code and original feature pipelines are added.

## Outputs

- `artifacts/outputs/checkpoints/stim_marl_policy.pt`: trained PyTorch S-TIM encoder checkpoint.
- `artifacts/outputs/checkpoints/lr_trust.pt`: trained LR-Trust checkpoint.
- `artifacts/outputs/checkpoints/mlp_trust.pt`: trained MLP-Trust checkpoint.
- `artifacts/outputs/logs/marl_training_trace.csv`: epoch-level training loss and metrics.
- `artifacts/outputs/logs/learned_baseline_training_trace.csv`: learned-baseline training diagnostics.
- `artifacts/outputs/logs/marl_policy.json`: policy metadata, feature normalization, checkpoint path.
- `artifacts/outputs/logs/learned_baselines.json`: learned-baseline metadata and checkpoint paths.
- `artifacts/outputs/logs/ns3_packet_trace.csv`: bundled ns-3-derived packet/mobility trace.
- `artifacts/outputs/logs/ns3_trust_streams.csv`: T1--T5 stream converted from the bundled ns-3-derived trace.
- `artifacts/outputs/logs/per_seed_metrics.csv`: per-method, per-seed evaluation metrics.
- `artifacts/outputs/logs/per_seed_ablation.csv`: per-seed ablation metrics.
- `artifacts/outputs/logs/per_step_trust_streams.csv`: sampled per-step T1--T5 trust streams.
- `artifacts/outputs/tables/baseline_comparison.csv`: main baseline comparison.
- `artifacts/outputs/tables/multi_ratio.csv`: malicious-ratio robustness results.
- `artifacts/outputs/tables/ablation.csv`: component ablation results.
- `artifacts/outputs/tables/scalability.csv`: swarm-size scalability results.
- `artifacts/outputs/tables/correlation.csv`: trust-factor Pearson correlations.
- `artifacts/outputs/tables/statistical_tests.csv`: paired tests with Holm correction.
- `artifacts/outputs/tables/channel_profile_ablation.csv`: paired per-seed cost of each trust dimension under the channel-focused adversary.
- `artifacts/outputs/tables/channel_profile_only_dimension.csv`: paired per-seed cost of each single-dimension arm under the channel-focused adversary.
- `artifacts/outputs/tables/channel_profile_dimension_budget.csv`: the dimension-budget series, all thirty-one deployment arms grouped by the number of dimensions they observe.
- `artifacts/outputs/tables/channel_profile_component_ablation.csv`: code-level component ablation run on the channel-focused generator.
- `artifacts/outputs/tables/ns3_trace_validation.csv`: single-trace ns-3-derived sanity-check results.
- `artifacts/outputs/tables/spatial_matched_operating_point.csv`: the six methods of the spatially inconsistent scenario at their deployed thresholds and at a matched benign false-positive rate.
- `artifacts/outputs/tables/spatial_matched_robustness.csv`: the strongest rule adapter at the matched rate, for every configuration of the robustness table.
- `artifacts/outputs/figures/trust_value_evolution.png`: generated trust evolution figure.
- `artifacts/outputs/figures/ratio_dynamics_tsr.png`: generated comparative evaluation figure.
- `artifacts/outputs/figures/pipeline.png`: the executed pipeline (built from `paper/figures/pipeline_tikz.tex`).
- `paper/figures/dimension_budget.png`: accuracy and detection against the observation budget of a deployment.
- `artifacts/outputs/figures/deployment.png`: the intended deployment and its unimplemented extensions (built from `paper/figures/deployment_tikz.tex`).
- `artifacts/outputs/figures/marl_training_trace.png`: PyTorch training diagnostics.

All random number generation is seeded through `artifacts/configs/default.json`.
Training uses seeds 0--9. Evaluation uses seeds 1000--1049.

## Interpretation Boundaries

- The main benchmark samples normalized T1--T4 trust factors directly and derives T5 recursively. Physical-layer descriptors do not drive the main tables.
- The channel-focused scenario changes two things relative to the published generator: the adversary manipulates one dimension at a time, and T5 is supplied by an external reputation channel instead of being recomputed locally from T1--T4, because a term that is a function of the other four cannot be manipulated on its own. It is reported alongside the published leave-one-factor-out control, not in place of it, and it does not change any published number.
- The model is **supervised**. It does not implement temporal-difference learning, policy gradients, or online adaptation, so it is not a reinforcement learner despite the historical file name `train_marl_pytorch.py`.
- The encoder carries auxiliary trust-weight, action and value heads. Inference consumes **only the risk logit**, and those targets are deterministic functions of the input and the class label. On paired seeds the encoder is statistically indistinguishable from a same-feature single-head MLP (p = 0.51, 0.56, 0.26). The manuscript reports this as a null result and does not claim the heads help.
- Detection accuracy is saturated at this difficulty for learned methods: every learned variant exceeds 97% on the aggregate metric. The representation question is therefore evaluated separately in `analysis/probe_level_eval.py`, where a logistic probe still discriminates (91.6% with 13 marginal features, 95.3% with the shape block added).
- The task-success calculation applies method-specific allocation rules and does not consume the learned action head. Treat TSR as a descriptive simulator proxy. All methods draw it from one shared Monte Carlo stream, so a proxy gap reflects the allocation rule rather than a different task draw.
- `configs/legacy_paper_protocol.json` reproduces the biased v4 tables and **must not be used for new analysis**. It is retained only so the earlier published numbers can be audited.
- Communication and latency values are generated by affine cost formulas with noise, not measured bytes or runtime. They are disabled by default via `fairness.emit_resource_proxy_columns`.
- The observer count (the configuration key is still `default_thinker_agents`) does not enter the current feature extractor. Confidence-weighted multi-observer fusion and collusion tests are not implemented.
- FUBA, GALTrust, and GDM-DTM are local adapters over a common interface, not official implementations. Results against them describe our reimplementations.
