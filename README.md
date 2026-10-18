# Trust-Stream Evaluation for Low-Altitude UAV Networks

This repository contains the manuscript source, figures, and reproducible artifact for a supervised MTIM trust-stream proof of concept. The main benchmark is synthetic; the bundled ns-3-derived input is a single short interface check.

## Repository Layout

```text
.
├── paper/                 # Manuscript source, journal template, figures, and archived PDFs
│   ├── template.tex       # Main LaTeX manuscript
│   ├── template.pdf       # Latest compiled manuscript PDF
│   ├── Definitions/       # MDPI LaTeX class used by the manuscript
│   ├── figures/           # Figures currently referenced by template.tex
│   └── archive/           # Older PDFs and unused/reference figures
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

## File Classification

- Manuscript source: `paper/template.tex`
- Journal class/template dependency: `paper/Definitions/mdpi.cls`
- Manuscript figures in active use: `paper/figures/`
- Historical manuscript outputs and unused reference images: `paper/archive/`
- Reproducibility code and experiment outputs: `artifacts/`
- Local development environment: `.venv/` (ignored)
