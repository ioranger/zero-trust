"""Rename the agent vocabulary of the manuscript to the observer vocabulary.

The main figure no longer shows agents, so the text must not describe them
either. The paper keeps the whole formulation: the decentralised system model,
the Dec-POMDP elements, the multi-observer aggregation equations and the
algorithm table all stay, because they are the stated design target and the
manuscript marks them as not executed by the released implementation. Only the
words change.

Every replacement is asserted: the old string has to occur exactly once, so a
silently wrong edit cannot pass. Re-running the script on an already migrated
file is a no-op.

Usage:
    python -u artifacts/analysis/rename_agent_terms.py
"""

from __future__ import annotations

from pathlib import Path

TEX = Path(r"F:\zero trust\zero-trust\paper\template.tex")

# (old, new) pairs, in the order they appear in the manuscript
REPLACEMENTS: list[tuple[str, str]] = [
    (
        r"and an incentive action $\pi_{jk}(t)$ for the local Thinker Agent $j$ that supervises $U_k$:",
        r"and an incentive action $\pi_{jk}(t)$ for the local observer $j$ that supervises $U_k$:",
    ),
    (
        r"where $o_j(t)$ is the partial observation available to agent $j$,",
        r"where $o_j(t)$ is the partial observation available to observer $j$,",
    ),
    (
        "The intended architecture divides observation across local agents and forwards their estimates to a decision node. "
        "The executable artifact is simpler. It applies one shared supervised network independently to each node's "
        "diagnostic feature vector. Agent assignments do not enter the feature extractor,",
        "The intended architecture divides observation across local observers and forwards their estimates to a decision "
        "node. The executable artifact is simpler. It applies one shared supervised network independently to each node's "
        "diagnostic feature vector. Observer assignments do not enter the feature extractor,",
    ),
    (
        "The intended architecture divides observation across local agents and forwards their estimates to a decision node. "
        "It is retained here to define a possible deployment target,",
        "The intended architecture divides observation across local observers and forwards their estimates to a decision "
        "node. It is retained here to define a possible deployment target,",
    ),
    (
        r"the observation $o_j(t)$ of Thinker Agent $j$ contains the local trust sub-scores and its own confidence "
        r"scores for its supervised subset $\mathcal{N}_j$",
        r"the observation $o_j(t)$ of local observer $j$ contains the local trust sub-scores and its own confidence "
        r"scores for its assigned observation set $\mathcal{N}_j$",
    ),
    (
        "The following aggregation equations specify an unevaluated extension for deployments in which several agents "
        "observe the same node.",
        "The following aggregation equations specify an unevaluated extension for deployments in which several local "
        "observers report on the same node.",
    ),
    (
        r"\textbf{Total Trust Score Aggregation}: The Intelligent Decision Agent combines the individual trust scores "
        r"from all Thinker Agents that have observed node $k$:",
        r"\textbf{Total Trust Score Aggregation}: The decision node combines the individual trust scores from all local "
        r"observers that have reported on node $k$:",
    ),
    (
        r"the mean absolute error of agent $j$ for node $k$ over time",
        r"the mean absolute error of observer $j$ for node $k$ over time",
    ),
    (
        "The decision agent classifies nodes from the total score and the dispersion,",
        "The decision node classifies nodes from the total score and the dispersion,",
    ),
    (
        "dashed boxes are the parts it leaves open: merging the observations of several agents over one node,",
        "dashed boxes are the parts it leaves open: merging the observations of several local observers over one node,",
    ),
    (
        "are never observable by the Thinker Agents during execution.",
        "are never observable to the evaluated detector during execution.",
    ),
    (
        r"\textbf{Input:} Current trust vectors $\{\mathbf{T}_k(t)\}_{k=1}^{N}$ and agent assignments "
        r"$\{\mathcal{N}_j\}_{j=1}^{M}$.}\\",
        r"\textbf{Input:} Current trust vectors $\{\mathbf{T}_k(t)\}_{k=1}^{N}$ and observer assignments "
        r"$\{\mathcal{N}_j\}_{j=1}^{M}$.}\\",
    ),
    (
        r"1 & For each Thinker Agent $j = 1,\dots,M$, collect local observations",
        r"1 & For each local observer $j = 1,\dots,M$, collect local observations",
    ),
    (
        "Because $M$ affects the generator's random seed but does not enter the policy features, these curves do not "
        "isolate an agent-count effect.",
        "Because $M$ affects the generator's random seed but does not enter the policy features, these curves do not "
        "isolate an effect of that parameter.",
    ),
    (
        "Since $M$ is not a policy feature, the curves do not identify a causal agent-count effect.",
        "Since $M$ is not a policy feature, the curves do not identify a causal effect of that parameter.",
    ),
    (
        "implement genuine agent-local observations and aggregation,",
        "implement genuine multi-point observations and aggregation,",
    ),
]


def main() -> int:
    # byte level, so the line endings of the manuscript are never rewritten
    text = TEX.read_bytes().decode("utf-8")

    changed = 0
    already = 0
    for old, new in REPLACEMENTS:
        n_old = text.count(old)
        n_new = text.count(new)
        if n_old == 1:
            text = text.replace(old, new)
            changed += 1
        elif n_old == 0 and n_new >= 1:
            already += 1
        else:
            print(f"[FAIL] old occurs {n_old}x, new occurs {n_new}x for:\n  {old[:110]}")
            return 1

    TEX.write_bytes(text.encode("utf-8"))
    print(f"[OK] applied {changed} replacement(s); {already} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
