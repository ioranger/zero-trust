# Repository Structure

This file records the content classification after repository cleanup.

## `paper/`

Manuscript-facing files.

- `template.tex`: main LaTeX source.
- `template.pdf`: latest compiled PDF.
- `Definitions/mdpi.cls`: MDPI LaTeX class required by `template.tex`.
- `figures/`: current figures referenced by the manuscript:
  - `ov2.png`: MTIM framework overview.
  - `update.png`: MTIM state-update and artifact-provenance mechanism.
  - `trust_value_evolution.png`: trust evolution curve.
  - `Fig5_energy_consumption.png`: comparative evaluation figure.
- `archive/`: historical PDFs and unused/reference figures retained for traceability.

## `artifacts/`

Executable replication package.

- `configs/`: centralized experiment parameters.
- `scripts/`: PyTorch training, trust-stream simulation, baseline reimplementation, statistical summarization, plotting, and trace conversion.
- `ns3/`: ns-3 scenario source used to generate a packet/mobility trace.
- `outputs/checkpoints/`: trained PyTorch checkpoints.
- `outputs/logs/`: raw training/evaluation logs and trace streams.
- `outputs/tables/`: CSV tables used by the manuscript.
- `outputs/figures/`: generated artifact figures.

## Root Files

- `Makefile`: root entry point for compiling the manuscript.
- `.gitignore`: local environment and build-output ignore rules.
- `README.md`: project overview and quick-start instructions.

## Removed From Versioned Content

LaTeX intermediate files are no longer tracked:

- `*.aux`
- `*.bbl`
- `*.blg`
- `*.fdb_latexmk`
- `*.fls`
- `*.log`
- `*.out`
- `*.synctex.gz`

These files are generated during compilation and do not carry stable research content.

