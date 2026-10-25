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
python -u artifacts/analysis/finalise_modality_study.py    # modality ladder + fusion ablation
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
| `position_attack_probe.py` | Is the spatial block complementary to the behaviour channels, or an addition to them? Per-attack-class probe detection for the marginal, shape and spatial blocks. |
| `modality_complementarity.py` | The same question for the real trained models: per-attack-class detection per feature-block combination, with a paired test across seeds. |
| `paired_method_comparison.py` | The proposed model against its feature-matched control inside each arm, paired over seeds. |
| `spatial_main_table.py` | The published comparison over all eight methods, repeated in the scenario that can discriminate. |
| `dataeff_table.py` | The data-efficiency control: the proposed model against its control at 12, 24 and 60 training seeds and three supervision variants. |
| `dataeff_probe.py` | A fast probe of the same question, without the full training loop. |
| `robustness_table.py` | Whether the spatial separation survives moving one parameter of the headline configuration. |
| `trace_regime.py` | Whether a trace is a measurement the feature extractor can make at all, with the reasons it is not. |
| `syntax_check_scenario.py` | Compiles the ns-3 scenario for syntax and type checking against stand-in headers, so a rewrite is checked before ns-3 is built. |
| `multitrace_validation.py` | Runs several traces through conversion, the regime gate and the evaluation harness, and aggregates only the ones that are valid measurements. |
| `selftest_multitrace_harness.py` | Proves the multi-trace harness end to end without ns-3, and checks that the gate still rejects the short bundled trace. |
| `saturation_sweep.py` | How camouflage strength affects separability and modality recoverability. |
| `spatial_study_report.py` | Runs the whole spatio-temporal study in one pass and writes the two table files. |
| `SPATIAL_STUDY.md` | The written study: what the spatial block buys, what it costs, and which generator artefacts had to be removed first. |
| `finalise_modality_study.py` | Builds the modality ladder and the fusion-mechanism ablation from the committed arm logs. |
| `check_fusion_switch.py` | Is the fusion-mechanism switch a strict no-op for every configuration that does not ask for it? |
| `compare_snapshot_to_published.py` | Does a given run snapshot reproduce the published Table 2 cell for cell? |
| `compact_arm.py` | Extracts the four files an arm needs out of a full run snapshot. |
| `diagnose_rule_threshold_transfer.py` | Is the rule-based collapse a threshold-transfer failure or an information failure? |
| `diagnose_spatial_counterfactuals.py` | Which generator choice causes the rule-based collapse: the field, the reference shift or the forger? |
| `diagnose_forger_visibility.py` | Per-feature effect sizes of the telemetry-replay attacker against the benign population. |
| `diagnose_clipping_artifact.py` | Isolates the clipping artefact that turned a zero-mean field into a non-zero mean shift. |
| `verify_citations_crossref.py` | Checks every citation's metadata against the Crossref record. |
| `crossref_lookup_titles.py` | Finds DOIs and metadata for candidate references by querying Crossref by title. |
| `compile_check.py` | Byte-compiles the scripts so a syntax error cannot reach a background arm. |
| `inspect_attack_type_log.py` | Shows the seed, method and attack-type structure of a per-seed attack log, including its duplicate rows. |
| `diff_devtree_vs_gitwork.py` | Lists the files that differ between the development tree and the git worktree. |
| `patch_text.py` | Applies exact-text replacements to a file and refuses to write if a match is missing or ambiguous. |
| `latex_warnings.py` | Reports the LaTeX warnings that matter: undefined references, overfull and underfull boxes, errors. |
| `list_code_paths.py` | Lists the repository-internal file paths that appear in the manuscript, so none of them reaches a reviewer-facing paper. |
| `list_repo_talk.py` | Lists the sentences that point at a place in the package rather than at the method or the result. |
| `list_bold_cells.py` | Lists every bold cell of every table, so the emphasis can be checked against the table it sits in. |
| `check_bold_semantics.py` | Checks that a bold cell in a method-comparison table marks a column the proposed model actually leads. |
| `audit_consistency.py` | Checks the manuscript mechanically: labels against references, figure and table numbering, the counts it states, and the terminology it uses. |
| `audit_numbers.py` | Locates every occurrence of the quantities the manuscript quotes repeatedly, so the values can be compared across the abstract, the tables and the conclusions. |
| `switch_interval_column_check.py` | Measures the switch-interval statistic of the shape block across nodes on the generated streams, which is how the claim that the column is degenerate there was checked and found false. |
| `same_vector_control.py` | Prints the fusion arm, in which every learned comparator receives the identical 23-dimensional vector, the same threshold and the same seeds: the comparison that separates the representation from the network, and the one the manuscript does not report. |
| `list_marl_zeros.py` | Lists the sentences in the manuscript that name multi-agent reinforcement learning or zero trust, separating the self-positioning contrasts from the related work that is kept. |
| `rename_agent_terms.py` | Renames the agent vocabulary of the manuscript to the observer vocabulary, with an assertion on every replacement so that a wrong edit cannot pass. |
| `check_no_agent_terms.py` | Fails if the manuscript body or a figure source mentions an agent: the guard for the rule that the figures and the text describe the same pipeline. |
| `check_abstract_claims.py` | Checks every qualitative claim the abstract makes against the tables the paper is built on, and prints the numbers each statement rests on. |
| `make_factor_ablation_configs.py` | Generates the leave-one-factor-out control configurations, each differing from the published or spatial configuration in exactly one key. |
| `run_factor_ablation.ps1` | Builds the leave-one-factor-out arms, one per removed dimension, and snapshots each of them. |
| `factor_ablation_report.py` | Reports what each trust dimension is worth to the proposed model, checks that the comparators do not move across the arms, and checks that the published configuration re-run reproduces the committed table. |
| `render_figure.py` | Rasterises a standalone TikZ figure into the PNG the manuscript includes, pinned to the width of the PNG it replaces. |
| `check_bibliography_coverage.py` | Checks that every bibliography entry is still cited and every citation resolves, which is what a removed related-work subsection can break. |
| `bold_table_cells.py` | Sets the bold cells: the proposed model's lead in the comparison tables, the best value in the column in the ablation tables. |
| `table_type_sizes.py` | Measures the type size each table ends up with in the built PDF and reports the factor that would give it a common size. |
| `set_table_scales.py` | Sets the tables' resizebox factors so that they share a type size and none overflows the text width. |
| `fix_table_notes.py` | Puts each table's note on its own line below the table, rather than beside it. |
| `extract_search_results.py` | Reassembles a chunked search artifact and prints its result list. |
| `pdf_find_page.py` | Finds the page on which a phrase appears in the built PDF. |
| `spatial_arms_final_compare.py` | Puts the five spatial-scenario arms side by side: per-class detection rate, the class-macro-average, the population-weighted accuracy and the paired tests, so the two summaries can be read together. |
| `fusion_protocol_check.py` | The main protocol against the same-input fusion protocol, per class and per method: it shows that the spatial advantage is a property of the neighbourhood block, not of the encoder. |
| `gate_routing_probe.py` | Where the block-routed gate sends each attack class, and what the per-class rates would be if the routing were forced: it separates a routing failure from a branch failure. |
| `operating_point_probe.py` | The same arms at a matched benign false-positive rate: each method's cut is chosen on the held-out validation seeds, and the AUCs are reported next to the rates. |
| `run_spatial_arms.ps1` | Builds the two diagnostic arms in sequence and snapshots each one into `artifacts/runs/<arm>`. |

## The method set the manuscript reports, and the one the artifact trains

The manuscript's comparison tables list five comparators, all rule-based:
MFA, FUBA, GALTrust, GDM-DTM and AHP-Entropy. No learned comparator is
reported as a competitor. The artifact still trains two, because the
pre-registered controls and the diagnostic scripts need them:

* a per-node learned baseline (LR-Trust) and a same-feature neural control
  (MLP-Trust, a two-layer risk classifier on the identical diagnostic features
  and seeds);
* the focal-loss arms were run with both of them trained **under the same
  objective inside the same run**, and their verdicts are the negative result
  the manuscript reports (`FOCAL_ARM_PREREGISTRATION.md`,
  `FOCAL_GAMMA_SWEEP_PREREGISTRATION.md`, `evaluate_focal_arm.py`,
  `evaluate_focal_sweep.py`);
* the fusion-mechanism control measures what the linear head extracts from the
  neighbourhood block against the proposed model, which needs both a linear and
  a nonlinear consumer of the same vector (`fusion_protocol_check.py`);
* the operating-point diagnostic compares the two learners at a matched benign
  false-positive rate (`operating_point_probe.py`).

The manuscript does not report those controls as competitors, so the tables
here are a superset of the manuscript's, and the generated figures are
restricted to the reported set. Deleting them from the artifact would remove
the instruments those measurements are made with and would change no number the
manuscript prints.

## `runs/`

`runs/<arm>/` holds the four log files each arm needs: the per-seed detection
metrics, the per-seed attack-type breakdown, the trained policy metadata and
the arm's summary table. The full run snapshots under `artifacts/runs/` are
regenerable and are not committed.

| Arm | Configuration |
|---|---|
| `paper_18dim_check` | the published configuration: value 0.10, trust-weight 0.25, incentive-action 0.20, modality 0.00 |
| `paper_18dim_recheck` | the published configuration re-run after the generator changes; reproduces Table 2 cell for cell |
| `heads_risk_only` | control: all four auxiliary loss weights 0 |
| `heads_mod_only` | only the modality head supervised, weight 0.30 |
| `heads_full` | all four auxiliary heads supervised |
| `marginal_13dim` | the 13-dimensional ablation with no shape block |
| `spatial_position_13dim` | telemetry-forging scenario, marginal features only (13 dims) |
| `spatial_position_18dim` | telemetry-forging scenario, marginal + shape (18 dims) |
| `spatial_position_23dim` | telemetry-forging scenario, marginal + shape + spatial (23 dims) |
| `spatial_position_fusion` | the same 23 dims fed to every learner, so the linear, MLP and multi-head fusion can be compared on one input |
| `spatial_position_riskonly` | diagnostic arm: telemetry-forging scenario, marginal + shape (18 dims), all four auxiliary loss weights 0 |
| `spatial_position_gated` | diagnostic arm: telemetry-forging scenario, all 23 dims, block-routed fusion with the auxiliary heads detached from the branch encoders |

To regenerate an arm from scratch:

```powershell
python -u artifacts/scripts/train_marl_pytorch.py     --config artifacts/configs/heads_mod_only.json
python -u artifacts/scripts/run_reference_experiment.py --config artifacts/configs/heads_mod_only.json
python -u artifacts/scripts/summarize_results.py       --config artifacts/configs/heads_mod_only.json
```

## The packet-level trace path

The manuscript no longer reports the packet-level results. The path below
stays in the package so that the external check the manuscript describes can
be run, but its numbers are not among the results the paper prints.

The bundled ns-3 trace holds 49 update steps, which is shorter than the
feature extractor's minimum window, so the table it produced measured a harness
mismatch rather than the detector. The path for a real multi-seed validation
is in place and gated:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '..\realdata\run_ns3_traces.ps1'
```

generates the traces with ns-3 (the official Docker image, or an ns-3
checkout under WSL), converts them, checks each one against the feature
extractor's operating regime, evaluates the survivors and aggregates them.
`selftest_multitrace_harness.py` exercises that chain without ns-3, and
`trace_regime.py` can be pointed at any converted trace to see the verdict.
`artifacts/ns3/ENVIRONMENT.md` records what an ns-3 environment needs, what
was tried, and the exact commands for each route.

## The comparison protocol for the neighbourhood block

The main protocol withholds the neighbourhood block from LR-Trust and
MLP-Trust, because both are per-node aggregators by construction: handing
them a neighbourhood-relative feature would turn the comparison into a
statement about input width rather than about architecture. The switch
`fairness.learned_baselines_get_spatial_block` reverses that on purpose for
the fusion-mechanism ablation, where the point is to hold the feature vector
fixed and vary only how the blocks are combined. `check_fusion_switch.py`
verifies that the switch is a no-op for every other configuration, including
the one that passes an adjacency in explicitly.

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

### The telemetry-forging scenario is where this stops being a clean result

The four-arm control above runs on the i.i.d. scenario, where the generator
leaves so much level margin that no auxiliary objective can erode it. The
spatial scenario is the case where it can, and the two diagnostic arms measure
it. All numbers are from `spatial_arms_final_compare.py`, paired over the same
20 evaluation seeds.

`spatial_position_riskonly` re-runs the 18-dimensional spatial arm with the
three auxiliary loss weights at zero, so the pair
`spatial_position_18dim` / `spatial_position_riskonly` isolates exactly those
three losses: same features, same generator, same thresholds. The constant
attack class rises from 82.1 to 87.8 (`p < 0.0001`), so the three auxiliary
losses cost 5.7 pp of the 8.7 pp gap against the 13-dimensional arm at that
setting. They are the main cause, but not the whole cause: 3.0 pp remains, and
that residual comparison is confounded, because the 13-dimensional arm runs
with the three auxiliary losses still active. Removing the losses also costs
the classes they were helping: on-off drops 2.5 pp (`p = 0.0008`) and
position-inconsistent drops 1.3 pp (`p = 0.0043`).

`spatial_position_gated` separates the blocks into one encoder each and reads
the auxiliary heads off the branch embeddings detached, so their losses cannot
reach the branches. Against the published 23-dimensional arm it is
statistically indistinguishable on every attack class (constant `p = 0.66`,
dormant `p = 0.58`, on-off `p = 0.49`, position-inconsistent `p = 0.72`) and
only benign improves (`+0.4 pp`, `p = 0.0081`). The block routing therefore
does not repair the level classes either: constant stays at 87.6, which is
3.2 pp below the 13-dimensional arm (`p = 0.0009`). Note that this arm still
runs the three auxiliary losses at their default weights, so the 5.7 pp the
risk-only arm removed is still inside it.

The next decisive arm follows from the two together: 23 dimensions, block
routed, all four auxiliary weights at zero. If the auxiliary objectives are
what hold the level classes down and the block routing preserves the on-off
and position-inconsistent gains, constant should land near 93 instead of 87.6.
