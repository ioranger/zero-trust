# MTIM Reproducible Artifact

This directory contains the executable artifact for the revised MTIM manuscript.
It now includes:

- PyTorch offline parameterized MARL trust-policy surrogate training code, checkpoint output, and training logs.
- Learned LR-Trust and MLP-Trust baselines trained on the same diagnostic features and seeds as MTIM.
- Paper-level reimplementations of MFA, FUBA, GALTrust, and GDM-DTM over the same T1--T5 trust interface.
- Statistical scripts, raw per-seed logs, generated tables, and generated figures.
- An ns-3 UAV trace-generation scenario plus a converter from packet/mobility traces to MTIM T1--T5 trust streams.

Scope note: the PyTorch offline MARL trust-policy surrogate training path has been executed in
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

## Reproduce the PyTorch MARL-Surrogate Results

Run the full pipeline:

```bash
.venv/bin/python artifacts/scripts/train_marl_pytorch.py --config artifacts/configs/default.json --device cpu
.venv/bin/python artifacts/scripts/run_reference_experiment.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/summarize_results.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/evaluate_trace_driven.py --config artifacts/configs/default.json --trace artifacts/outputs/logs/ns3_trust_streams.csv
.venv/bin/python artifacts/scripts/plot_update_mechanism.py
.venv/bin/python artifacts/scripts/plot_results.py --config artifacts/configs/default.json
.venv/bin/python artifacts/scripts/plot_training_trace.py --config artifacts/configs/default.json
```

The training script writes a real PyTorch checkpoint, learned baseline
checkpoints, and training traces before the evaluation script runs.
`run_reference_experiment.py` intentionally fails if
`artifacts/outputs/logs/marl_policy.json` or
`artifacts/outputs/logs/learned_baselines.json` does not exist.

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
- `LR-Trust`: logistic risk classifier trained on MTIM's diagnostic features.
- `MLP-Trust`: two-layer neural risk classifier trained on MTIM's diagnostic
  features.

These are paper-level reimplementations under a common T1--T5 interface, not
official source code from the cited authors. Treat comparisons as controlled
reimplementations unless official code and original feature pipelines are added.

## Outputs

- `artifacts/outputs/checkpoints/mtim_marl_policy.pt`: trained PyTorch MTIM policy checkpoint.
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
- `artifacts/outputs/tables/ns3_trace_validation.csv`: single-trace ns-3-derived sanity-check results.
- `artifacts/outputs/figures/trust_value_evolution.png`: trust evolution figure.
- `artifacts/outputs/figures/update_mechanism.png`: MTIM state-update and artifact-provenance mechanism figure.
- `artifacts/outputs/figures/Fig5_energy_consumption.png`: comparative evaluation figure.
- `artifacts/outputs/figures/marl_training_trace.png`: PyTorch training diagnostics.

All random number generation is seeded through `artifacts/configs/default.json`.
Training uses seeds 0--9. Evaluation uses seeds 1000--1049.
