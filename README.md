# Structural Blind Spots of Window-Based Trust Aggregation in Low-Altitude UAV Networks

**Current manuscript: [`paper/template.pdf`](paper/template.pdf)** (source: `paper/template.tex`).

This repository contains the manuscript source, figures, and reproducible artifact for a supervised, shape-augmented trust-stream study of UAV task allocation. The method is named S-TIM (Shape-augmented Trust Inference Model). The main benchmark is synthetic; the bundled ns-3-derived input is a single short interface check.

**Archived earlier drafts** live in `paper/archive/` and are retained for audit only — they report numbers produced under a biased comparison protocol and are not the current results. See [`paper/archive/README.md`](paper/archive/README.md).

## Repository Layout

```text
.
├── paper/                 # Manuscript source, journal template, figures, and archived drafts
│   ├── template.tex       # Main LaTeX manuscript (current)
│   ├── template.pdf       # Latest compiled manuscript PDF (current)
│   ├── Definitions/       # MDPI LaTeX class used by the manuscript
│   ├── figures/           # Figures currently referenced by template.tex
│   └── archive/           # Superseded v4 renders, kept for audit; NOT current
├── artifacts/             # Reproducibility package for the reported experiments
│   ├── configs/           # Experiment configuration
│   ├── scripts/           # Training, evaluation, plotting, and trace-conversion scripts
│   ├── ns3/               # ns-3 scenario source for trace generation
│   └── outputs/           # Committed checkpoints, logs, tables, and generated artifact figures
├── Makefile               # Root build entry point for the manuscript PDF (macOS/Linux)
├── build.bat              # Windows equivalent of `make pdf`
└── README.md              # This overview
```

## Build the Manuscript

### macOS / Linux

From the repository root:

```bash
make pdf
```

### Windows

The `Makefile` uses Unix shell syntax and cannot run under `cmd`/PowerShell. Use
`build.bat` instead — it locates the MiKTeX binaries, runs `pdflatex` twice so
cross-references and citation numbers resolve, and reports errors with file/line:

```bat
build.bat          REM compile paper\template.tex -> paper\template.pdf
build.bat clean    REM remove intermediate files
build.bat open     REM compile, then open the PDF
```

If `pdflatex` is not found, edit the `MIKTEX_BIN` variable at the top of
`build.bat` to point at your MiKTeX `bin\x64` directory.

The command compiles `paper/template.tex` and writes `paper/template.pdf`. Build byproducts such as `.aux`, `.log`, `.fls`, and `.out` are ignored by Git.

To remove local LaTeX byproducts:

```bash
make clean
```

## Reproduce the Artifact

The executable replication package is under `artifacts/`. See `artifacts/README.md` for the full pipeline, including PyTorch MARL-surrogate training, learned baselines, statistical summaries, plotting scripts, and the ns-3 trace-conversion path.

The currently committed artifact outputs are intentionally preserved because they support the manuscript tables and figures.

## Working on this manuscript

`artifacts/ops/` holds the operating layer: the scripts that keep the
development tree and the git worktree in step, and the state of the manuscript
itself. Start with [`artifacts/ops/STATE.md`](artifacts/ops/STATE.md) for
where the paper stands and what is still open, and
[`artifacts/ops/README.md`](artifacts/ops/README.md) for the working cycle and
the checks that guard the manuscript.

## File Classification

- **Current manuscript PDF**: `paper/template.pdf`
- Manuscript source: `paper/template.tex`
- Journal class/template dependency: `paper/Definitions/mdpi.cls`
- Manuscript figures in active use: `paper/figures/`
- Superseded manuscript renders (audit only, biased v4 tables): `paper/archive/`
- Reproducibility code and experiment outputs: `artifacts/`
- Legacy comparison protocol retained only to audit the old tables: `artifacts/configs/legacy_paper_protocol.json`
- Local development environment: `.venv/` (ignored)
