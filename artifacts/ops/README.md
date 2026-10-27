# Operating layer

The manuscript and the artifact live in this repository. The scripts in this
directory are the layer that keeps the two working trees on a development
machine in step, and they are what a second machine needs in order to continue
the work.

## Why there are two trees

The development tree holds the editable source:

    F:\zero trust\zero-trust      the source of truth, edited directly
    F:\zero trust\gitwork          a git worktree of the same repository

The development tree is not a git repository. `stage_migration.py` copies it
into the worktree, the worktree is committed and pushed, and the published
numbers come from the worktree. A run that writes into
`artifacts/outputs` must therefore be followed by
`git checkout -- artifacts/outputs` before the next commit, or the outputs of
the run are staged by accident.

## The scripts

| script | what it does |
|---|---|
| `stage_migration.py` | Copies `paper/`, `artifacts/` and `slides/` from the development tree into the worktree, skipping the regenerable intermediates. Run it after editing the development tree, before committing. |
| `sync_paper_only.py` | A narrower copy that leaves `artifacts/outputs` alone. Use it while a run is producing outputs, so the staging does not overwrite the files the run is writing. |
| `push_retry.ps1` | Pushes with a backoff, because the connection to the remote drops often enough that a single attempt is not enough. |
| `build_session_bundle.py` | Packages the local runtime session (the state database and the message log) so that the same conversation can be continued on another machine. |

All of them expect the two trees at the paths above. On a new machine, either
keep the same layout or edit the paths at the top of each script. The copies in
this directory are the ones that travel with the repository; the development
machine also keeps them in F:\zero trust\realdata, next to the one-off
scripts of the earlier phases.

## A normal cycle

```powershell
# 1. edit the development tree
# 2. stage it into the worktree
& 'F:\zero trust\realdata\stage_migration.py'    # the copy that edits the worktree
# 3. build and check
cmd /c 'F:\zero trust\zero-trust\build.bat'
& 'F:\zero trust\py310\python.exe' -u 'F:\zero trust\zero-trust\artifacts\analysis\verify_new_tables.py'
# 4. commit and push from the worktree
git -C 'F:\zero trust\gitwork' add -- paper artifacts
git -C 'F:\zero trust\gitwork' commit -F <message file>
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\zero trust\realdata\push_retry.ps1'
```

## The checks that guard the manuscript

Run all of them after a change to the manuscript. Each one fails loudly rather
than reporting a difference quietly.

| script | what it protects |
|---|---|
| `latex_warnings.py` | Undefined references, overfull and underfull boxes, errors. |
| `verify_new_tables.py` | Every cell of the tables that were rebuilt from the run logs, and the p values the prose quotes. |
| `paper_consistency_check.py` | The structural claims of the manuscript: the paired results, the disclosed limitations, the fixed threshold, the ablation controls. |
| `check_bibliography_coverage.py` | Every bibliography entry is cited and every citation resolves. |
| `check_no_agent_terms.py` | No agent vocabulary in the manuscript body or the figure sources. |
| `check_abstract_claims.py` | Every qualitative claim in the abstract against the tables it rests on. |
| `audit_float_correspondence.py` | Every figure and table against its data source, and every prose claim against the configuration that backs it. |
| `audit_floats.py` | Every float is referenced, with the page it lands on. |
| `audit_sparse_pages.py` | No page of the built paper is left almost empty by a float. |

## Rebuilding the numbers

The runs behind the tables are committed under `artifacts/analysis/runs/`, and
the per-arm configurations are in `artifacts/configs/`. A single arm is
rebuilt with the runner in `artifacts/analysis/run_factor_ablation.ps1`, which
is also the example of how a control arm is produced: one configuration
switch, everything else held fixed.
