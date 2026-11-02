# Inter-swarm trust exchange: prompt template

A prompt template for simulating two swarms whose managers exchange the five
trust branches through their on-device agents. It is written against the
S-TIM notation, so a run can be compared with the manuscript's numbers.

**Scope, stated up front.** This template instantiates the *deployment
formulation* of Section 3.5 of the manuscript: several observers score the
same node and their estimates are fused with confidence weights
(Eq. `ida_global`, `ida_weight`, `ida_uncertainty`), the fused score drives a
three-class decision (Eq. `ida_classification`) and an incentive action
(Eq. `incentive_opt`, `utility`). **The released artifact does not execute any
of that** — it applies one shared supervised network per node and consumes
only the risk logit. A run driven by this template is therefore an
*extension experiment*, not a reproduction, and its results must never be
reported as the manuscript's.

## Roles

| actor | count | what it holds |
|---|---|---|
| manager agent, swarm A | 1 | the decision node of swarm A, runs the fusion |
| manager agent, swarm B | 1 | the decision node of swarm B, runs the fusion |
| edge observer, per node | N per swarm | produces the five branches for its own node |

Only the two manager agents talk to each other. Edge observers do not
communicate across swarms; their branches reach the peer only through the
manager, which is what makes the peer estimate verifiable.

---

## 1. System prompt (both manager agents share it)

```
你是蜂群 {SWARM_ID} 的信任管理者，运行在管理者端侧 Agent 上。你维护本群每个
节点的五个信任分支，并与对端管理者的端侧 Agent 交换这些分支。

【五个信任分支】
T1 行为一致性 behaviour：飞离航线、跳过的例行心跳、应答时序偏离
T2 通信可靠性 communication：链路丢包率、时延、RSSI
T3 能量行为 energy：功耗曲线、异常放电、突增
T4 任务质量 task：任务完成质量、结果被篡改、提前或延迟返回
T5 历史记忆 history：T1-T4 的指数平滑记忆（EMA，0.84 保留旧值、0.16 取新值），
   是记忆项，不是独立的传感器

【铁律】
1. 只使用【本地观测】与【对端报文】里真实出现的数据。缺失的分支写 MISSING，
   禁止推测、插值、外推或编造任何数值。
2. 对端分支默认不可信。先校验后采信：逐分支与本地观测比对，误差大于
   {EPS_MAX} 的分支一律拒绝，并记为 rejected。
3. 融合按置信度加权：对端估计与本地估计的平均绝对误差 eps 越大，权重越小，
   phi = exp(-{GAMMA} * eps) / sum_j exp(-{GAMMA} * eps_j)。只有一个分支
   通过校验时，phi 取 1.0。
4. 结论必须指名道姓：给出每个分支的本地值、对端值、eps、phi、是否采纳，
   并说明最终判定由哪一个分支决定。
5. 证据不足时输出 UNCERTAIN，并写明缺哪一项证据。不要凑一个分数。
6. 严格按【输出契约】的字段输出，不要输出协议之外的解释。
```

## 2. Evidence packet (what an edge observer hands to its manager)

```
SWARM={SWARM_ID}|NODE={NODE_ID}|T={T}s|WINDOW={W}s
T1 behaviour|value={v}|std={s}|source=local|raw={a}
T2 communication|value={v}|std={s}|source=local|raw={a}
T3 energy|value={v}|std={s}|source=local|raw={a}
T4 task|value={v}|std={s}|source=local|raw={a}
T5 history|value={v}|std={s}|source=local|raw={a}
```

`raw` is the raw observation the branch was computed from. It is what makes
the peer packet checkable rather than merely assertable.

## 3. Wire format (manager agent to peer manager agent)

```
SWARM={SWARM_ID}|ROUND={r}|NODE={NODE_ID}|T={T}s
T1 behaviour|value={v}|conf={c}|window={w}s|raw={a}
T2 communication|value={v}|conf={c}|window={w}s|raw={a}
T3 energy|value={v}|conf={c}|window={w}s|raw={a}
T4 task|value={v}|conf={c}|window={w}s|raw={a}
T5 history|value={v}|conf={c}|window={w}s|raw={a}
```

## 4. Per-round driver prompt (what the harness sends to each manager)

```
【本轮参数】
ROUND={r}  TIME={T}s  SWARM={SWARM_ID}  PEER_SWARM={PEER_ID}  NODE={NODE_ID}

【本地观测】
{LOCAL_EVIDENCE_PACKET}

【对端报文】
{PEER_PACKET 或 NONE}

【任务】
1. 用本地观测为该节点给出五个分支的估计 T_hat_jk(t)。
2. 逐分支校验对端报文，算出 eps、phi，标出采纳或拒绝。
3. 融合出总分 T_k(t) 与离散度 sigma_k(t)。
4. 按三分类给出判定：C=Trusted 当 T_k >= theta_high 且 sigma_k <= sigma_th；
   C=Suspicious 当 theta_low <= T_k < theta_high 或 sigma_k > sigma_th；
   C=Malicious 当 T_k < theta_low 且 sigma_k <= sigma_th。
5. 在预算 {BUDGET} 内给出激励动作 pi，五个档位 {-2,-1,0,1,2}，
   c(pi)=|pi|，效用 U_k = T_k * (1 + {DELTA} * I(pi>0)) - {KAPPA} * I(T_k < theta_low)。
6. 写明判定由哪个分支决定，以及缺什么证据。

【输出契约】
NODE={NODE_ID}
LOCAL_ESTIMATE T1={v} T2={v} T3={v} T4={v} T5={v}
BRANCH_CHECK T1: local={v} peer={v} eps={v} phi={v} accepted={yes|no} reason={...}
BRANCH_CHECK T2: ...
BRANCH_CHECK T3: ...
BRANCH_CHECK T4: ...
BRANCH_CHECK T5: ...
FUSED_T={v}  DISPERSION={v}  CLASS={Trusted|Suspicious|Malicious|UNCERTAIN}
ACTION pi={-2..2}  decided_by={branch}  reason={...}
EVIDENCE_GAPS={...}
```

## 5. Scenario configuration block

```
N_A={15}  N_B={15}  MALICIOUS_RATIO={0.30}
ATTACK_PROFILE={constant,dormant,on-off}   # the spatial forger is a separate variant
PEER_MODE={honest|partial_collusion|lying|degraded}
T_END={5000}  WARMUP={1000}  WINDOW={120}
GAMMA={2.0}  SIGMA0={0.1}  DELTA={0.2}  KAPPA={2.0}
THETA_LOW={...}  THETA_HIGH={...}  SIGMA_TH={...}
EPS_MAX={...}  BUDGET={...}
SEED={...}  CONFIG_HASH={...}  PROMPT_VERSION={...}
```

## 6. The peer modes

This is the part worth running. The manuscript lists colluding peer reports
and decision-node compromise as stress cases it does **not** test; the
cross-swarm exchange is the vehicle for testing them.

| mode | what the peer sends | what it tests |
|---|---|---|
| `honest` | its own branches, unmodified | the fusion weights on a clean channel |
| `degraded` | branches computed over a shorter window, so its values are noisier | whether the manager can tell noise from lying |
| `partial_collusion` | T1 and T4 match the attacker profile, T2 and T3 stay clean | whether a single clean branch is enough to expose a colluding peer |
| `lying` | all five branches of the compromised nodes are forged | whether the local observation alone is enough to refuse |

Under `lying` the manager must be able to answer `CLASS=Malicious` on its own
evidence. If it cannot, the cross-swarm channel adds an attack surface, and
that is the finding.

## 7. Recording, so a run can be audited

- Store every round: the local packet, the wire packet, the manager's output,
  and the prompt version, as JSONL.
- Store the parameters, the seed and the config hash with the run.
- No value may be written after the fact. A branch that was not observed is
  `MISSING` in the record, not a number that was filled in later.
- The peer mode, and every switch that changed the peer's behaviour, is part
  of the record. A run that cannot be replayed is not a result.
