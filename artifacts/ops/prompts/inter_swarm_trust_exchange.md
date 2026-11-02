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

---

# Worked examples

The values below are generated from the artifact's own constants: the benign
reference `[0.80, 0.76, 0.72, 0.80]`, the evasive reference
`[0.74, 0.73, 0.72, 0.75]`, the on-off attack profile `[0.56, 0.70, 0.70,
0.52]`, per-step noise `sigma = 0.10`, per-node offsets `N(0, 0.08)` applied in
full to a benign node and scaled by 0.25 to an active attacker, outages on 3%
of steps with drops `[0.22, 0.26, 0.08, 0.17]`, a 120-step window, and
`T5 = 0.84 T5 + 0.16 mean(T1..T4)`.

Branch values are **trust in that dimension**, in `[0, 1]`, higher is better.
The S-TIM feature extractor uses the complement, so the two must not be mixed.

The example thresholds are `theta_high = 7.0`, `theta_low = 4.0`,
`sigma_th = 1.0`, `EPS_MAX = 0.12`. The weight head is the one the manuscript
reports: T1 0.322, T4 0.321, T5 0.140, T2 0.138, T3 0.080.

## 8.1 A benign node, both swarms see it

Local evidence, swarm A, node K7, `t = 1200 s`. The node's offsets are
`[+0.05, -0.03, +0.07, -0.02]`.

```
SWARM=A|NODE=K7|T=1200s|WINDOW=120s
T1 behaviour|value=0.85|std=0.10|source=local|raw=航迹RMSE=0.7m;心跳缺失=0/20;应答时延P95=+2.4%
T2 communication|value=0.73|std=0.11|source=local|raw=PDR=0.954;时延均值=43ms;RSSI=-74dBm
T3 energy|value=0.79|std=0.10|source=local|raw=平均功耗=10.9W;放电斜率=0.024%/s;突增=0次
T4 task|value=0.78|std=0.11|source=local|raw=任务成功率=0.96;结果校验=通过;提前返回=0
T5 history|value=0.788|std=0.009|source=local|raw=T5=0.788(EMA 0.84/0.16)
```

The peer's manager receives the same node over the wire, with its own window:

```
SWARM=B|ROUND=12|NODE=K7|T=1200s
T1 behaviour|value=0.83|conf=0.91|window=120s|raw=航迹RMSE=0.9m;心跳缺失=0/20;应答时延P95=+3.0%
T2 communication|value=0.75|conf=0.88|window=120s|raw=PDR=0.949;时延均值=45ms;RSSI=-73dBm
T3 energy|value=0.77|conf=0.90|window=120s|raw=平均功耗=11.1W;放电斜率=0.026%/s;突增=0次
T4 task|value=0.79|conf=0.89|window=120s|raw=任务成功率=0.95;结果校验=通过;提前返回=0
T5 history|value=0.787|conf=0.86|window=120s|raw=T5=0.787
```

The manager's reply. Weights per branch: `w_peer proportional to
exp(-gamma * eps)`, `gamma = 2.0`, `w_local proportional to 1`.

```
NODE=K7
LOCAL_ESTIMATE T1=0.85 T2=0.73 T3=0.79 T4=0.78 T5=0.788
BRANCH_CHECK T1: local=0.85 peer=0.83 eps=0.020 phi=0.490 accepted=yes reason=两端一致
BRANCH_CHECK T2: local=0.73 peer=0.75 eps=0.020 phi=0.490 accepted=yes reason=两端一致
BRANCH_CHECK T3: local=0.79 peer=0.77 eps=0.020 phi=0.490 accepted=yes reason=两端一致
BRANCH_CHECK T4: local=0.78 peer=0.79 eps=0.010 phi=0.495 accepted=yes reason=两端一致
BRANCH_CHECK T5: local=0.788 peer=0.787 eps=0.001 phi=0.500 accepted=yes reason=两端一致
FUSED_T=7.97  DISPERSION=0.32  CLASS=Trusted
ACTION pi=0  decided_by=T1+T4  reason=五个分支两端一致且无异常,维持信任
EVIDENCE_GAPS=none
```

## 8.2 A lying peer

The peer forges the behavioural and task branches of the same node.

```
SWARM=B|ROUND=13|NODE=K7|T=1300s
T1 behaviour|value=0.63|conf=0.99|window=120s|raw=航迹RMSE=3.2m;心跳缺失=4/20
T2 communication|value=0.75|conf=0.88|window=120s|raw=PDR=0.949;时延均值=45ms
T3 energy|value=0.77|conf=0.90|window=120s|raw=平均功耗=11.1W
T4 task|value=0.64|conf=0.98|window=120s|raw=任务成功率=0.71;结果校验=异常
T5 history|value=0.700|conf=0.95|window=120s|raw=T5=0.700
```

```
NODE=K7
BRANCH_CHECK T1: local=0.85 peer=0.63 eps=0.220 phi=0.000 accepted=no reason=偏差超EPS_MAX且对端自报置信度反而升高
BRANCH_CHECK T2: local=0.73 peer=0.75 eps=0.020 phi=0.490 accepted=yes reason=两端一致
BRANCH_CHECK T3: local=0.79 peer=0.77 eps=0.020 phi=0.490 accepted=yes reason=两端一致
BRANCH_CHECK T4: local=0.78 peer=0.64 eps=0.140 phi=0.000 accepted=no reason=偏差超EPS_MAX
BRANCH_CHECK T5: local=0.788 peer=0.700 eps=0.088 phi=0.456 accepted=yes reason=偏差可接受
FUSED_T=7.93  DISPERSION=0.32  CLASS=Trusted
ACTION pi=0  decided_by=T1+T4  reason=对端T1/T4被拒,仅用本地证据即可判定
EVIDENCE_GAPS=对端 T1/T4 被拒,建议复核跨群链路或隔离该对端观察者
```

The two forged branches are refused on the local evidence alone, and the
verdict is unchanged. That is the behaviour the `lying` mode is meant to
test: the cross-swarm channel must not be able to move the decision.

## 8.3 An intermittent attacker, and the blind spot it survives

Node K12 is an on-off attacker with camouflage 0.35 and offsets
`[+0.02, -0.01, +0.01, +0.03]`. At `t = 1200 s` it has been active for 21 of
the 121 steps in the window, so the window mean is mostly its idle profile and
the level branches barely see it.

```
SWARM=A|NODE=K12|T=1200s|WINDOW=120s
T1 behaviour|value=0.778|std=0.124|source=local|raw=航迹RMSE=0.6m;心跳缺失=0/20;活动占比=21/121
T2 communication|value=0.747|std=0.113|source=local|raw=PDR=0.951;时延均值=44ms;RSSI=-73dBm
T3 energy|value=0.722|std=0.104|source=local|raw=平均功耗=11.0W;放电斜率=0.025%/s;突增=0次
T4 task|value=0.762|std=0.119|source=local|raw=任务成功率=0.95;结果校验=通过;提前返回=0
T5 history|value=0.752|std=0.011|source=local|raw=T5=0.752(EMA 0.84/0.16)
```

The peer's values agree, because both windows are diluted in the same way.

```
SWARM=B|ROUND=12|NODE=K12|T=1200s
T1 behaviour|value=0.774|conf=0.90|window=120s|raw=活动占比=20/120
T2 communication|value=0.749|conf=0.89|window=120s|raw=PDR=0.949
T3 energy|value=0.721|conf=0.88|window=120s|raw=平均功耗=11.2W
T4 task|value=0.766|conf=0.88|window=120s|raw=任务成功率=0.96
T5 history|value=0.751|conf=0.87|window=120s|raw=T5=0.751
```

```
NODE=K12
BRANCH_CHECK T1: local=0.778 peer=0.774 eps=0.004 phi=0.498 accepted=yes reason=两端一致
BRANCH_CHECK T2: local=0.747 peer=0.749 eps=0.002 phi=0.499 accepted=yes reason=两端一致
BRANCH_CHECK T3: local=0.722 peer=0.721 eps=0.001 phi=0.500 accepted=yes reason=两端一致
BRANCH_CHECK T4: local=0.762 peer=0.766 eps=0.004 phi=0.498 accepted=yes reason=两端一致
BRANCH_CHECK T5: local=0.752 peer=0.751 eps=0.001 phi=0.500 accepted=yes reason=两端一致
FUSED_T=7.61  DISPERSION=0.32  CLASS=Trusted
ACTION pi=0  decided_by=T1+T4  reason=五个分支两端一致
EVIDENCE_GAPS=窗口内活动占比异常(21/121)但分支值无法体现
```

**This is the finding the protocol must be designed around.** The
intermittent attacker is judged `Trusted`, and it is judged so *because* the
two managers agreed: the five branches are level aggregates, and agreement
between two level aggregates carries no evidence about intermittency. The
cross-swarm exchange propagates exactly the representation the manuscript
identifies as blind.

Two consequences for the protocol:

1. **The packet must carry more than the five levels.** The `raw` field and
   the `std` field already leak the intermittency (`活动占比=21/121`, `std`
   0.124 against a benign 0.10), but they are not part of what the fusion
   consumes. Either the manager is given the five scale-free shape statistics
   of the peer's own channels, or the exchange carries the windowed series
   summary rather than the collapsed value.
2. **A manager must be able to decide without the peer.** The `lying` mode
   exists so that the protocol cannot be improved into something that only
   works when the peer is honest.

Without the first change, the inter-swarm channel is a second copy of the
blind spot rather than a remedy for it.

