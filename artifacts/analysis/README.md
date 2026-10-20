# Analysis scripts

Every script here is runnable from the repository root and reads only files
that are committed to this repository, so the numbers in the manuscript can be
re-derived without re-running the generator.

```powershell
python -u artifacts/analysis/paper_consistency_check.py   # Table 2 + structural claims
python -u artifacts/analysis/verify_new_tables.py         # the two new tables
python -u artifacts/analysis/arch_control_report.py        # four-arm architecture control
python -u artifacts/analysis/modality_probe.py             # information-provenance probe
python -u artifacts/analysis/probe_level_eval.py           # probe-level marginal vs shape
python -u artifacts/analysis/duty_sweep.py                 # paired duty-cycle sweep
python -u artifacts/analysis/trace_regime_check.py         # ns-3 trace regime diagnosis
```

## What each one establishes

| Script | Question it answers |
|---|---|
| `paper_consistency_check.py` | Does the manuscript's Table 2 still match the committed CSV, and are the fifteen structural claims still present? |
| `verify_new_tables.py` | Do `tab:method_class` and `tab:arch_controls` match the reproduced per-seed logs cell by cell? |
| `arch_control_report.py` | Does making every auxiliary head participate change detection? Four arms, same encoder, same features, paired seeds. |
| `modality_probe.py` | Why does auxiliary supervision change nothing? It predicts the attack-modality label from the features directly, without touching the network. |
| `probe_level_eval.py` | What does the shape block add, and how much of that is sequence order rather than added dimensionality? |
| `duty_sweep.py` | How far does the blind spot extend as the attacker's duty cycle falls? |
| `trace_regime_check.py` | Why does the 49-step ns-3 trace degenerate six of the eighteen input columns? |

## `runs/`

`runs/<arm>/` holds the four log files each arm needs: the per-seed detection
metrics, the per-seed attack-type breakdown, the trained policy metadata and
the arm's summary table. The full run snapshots under `artifacts/runs/` are
regenerable and are not committed.

| Arm | Configuration |
|---|---|
| `paper_18dim_check` | the published configuration: value 0.10, trust-weight 0.25, incentive-action 0.20, modality 0.00 |
| `heads_risk_only` | control: all four auxiliary loss weights 0 |
| `heads_mod_only` | only the modality head supervised, weight 0.30 |
| `heads_full` | all four auxiliary heads supervised |
| `marginal_13dim` | the 13-dimensional ablation with no shape block |

To regenerate an arm from scratch:

```powershell
python -u artifacts/scripts/train_marl_pytorch.py     --config artifacts/configs/heads_mod_only.json
python -u artifacts/scripts/run_reference_experiment.py --config artifacts/configs/heads_mod_only.json
python -u artifacts/scripts/summarize_results.py       --config artifacts/configs/heads_mod_only.json
```

## A note on the auxiliary heads

The four-arm control and the information probe together establish a result
that is easy to misread as a weakness. The modality head is the auxiliary
head that should have been able to help, because its target is the one
auxiliary label the binary risk label cannot express: constant, dormant and
on--off attackers all carry `y = 1`. Once it is switched on it learns
(0.983 validation accuracy against a chance level of 0.250), and yet no
detection metric moves, because `modality_probe.py` shows the modality label
is already 96.7% recoverable from the marginal features the risk head
already receives. The auxiliary head can therefore only re-encode information
the risk head already has, and the shared encoder pays for the auxiliary
objective in capacity instead of gaining from it. The one separation the arms
do produce runs the wrong way and is reported in the manuscript rather than
omitted: modality supervision lowers the task-success proxy by 0.22 pp
(`p = 0.021`) against the same-feature MLP and by 0.15 pp (`p = 0.049`)
against the published configuration.

The conclusion is that the binding constraint is the representation, not the
network, which is the paper's central claim rather than a limitation of it.
