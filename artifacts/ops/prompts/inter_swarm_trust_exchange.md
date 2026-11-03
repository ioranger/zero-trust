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

## 2. Evidence packet (edge observer to its own manager)

Five lines, one per branch. `value` is the trust in that dimension in
`[0, 1]`, higher is better; `spread` is the dispersion of the branch over
the window. The S-TIM feature extractor uses the complement of the branch
value, so the two must not be mixed.

```
SWARM={SWARM_ID}|K={NODE_ID}|T={T}s|W={W}s
T1={v}±{s}
T2={v}±{s}
T3={v}±{s}
T4={v}±{s}
T5={v}±{s}
```

The raw observation is **not** sent by default. It is requested in a dispute
round, which keeps the common packet small and makes an unverifiable claim
cheap to challenge:

```
SWARM={SWARM_ID}|K={NODE_ID}|T={T}s|D={BRANCH}
{BRANCH}={v}±{s}|raw={a}
```

## 3. Wire format (manager agent to peer manager agent)

```
SWARM={SWARM_ID}|R={r}|K={NODE_ID}|T={T}s
T1={v}±{s}
T2={v}±{s}
T3={v}±{s}
T4={v}±{s}
T5={v}±{s}
```

There is no self-reported confidence field. A peer that lies would have an
incentive to inflate it, so it cannot be used as evidence; the receiver
derives the weight from the disagreement instead.

## 4. Per-round driver prompt (what the harness sends to each manager)

```
【本轮参数】
R={r}  T={T}s  SWARM={SWARM_ID}  PEER={PEER_ID}  K={NODE_ID}

【本地观测】
{LOCAL_EVIDENCE_PACKET}

【对端报文】
{PEER_PACKET 或 NONE}

【任务】
1. 用本地观测给出五个分支的估计 T_hat_jk(t)。
2. 逐分支校验对端报文，算出 eps、phi，标出采纳或拒绝；被拒的分支可向对端
   发起一次争议轮，索取该分支的原始观测。
3. 融合出总分 T_k(t) 与离散度 sigma_k(t)。
4. 按三分类给出判定：C=Trusted 当 T_k >= theta_high 且 sigma_k <= sigma_th；
   C=Suspicious 当 theta_low <= T_k < theta_high 或 sigma_k > sigma_th；
   C=Malicious 当 T_k < theta_low 且 sigma_k <= sigma_th。
5. 在预算 {BUDGET} 内给出激励动作 pi，五个档位 {-2,-1,0,1,2}，
   c(pi)=|pi|，效用 U_k = T_k * (1 + {DELTA} * I(pi>0)) - {KAPPA} * I(T_k < theta_low)。
6. 写明判定由哪个分支决定，以及缺什么证据。

【输出契约】
K={NODE_ID}
LOCAL={v1,v2,v3,v4,v5}
CHECK T1:{local},{peer},{eps},{phi},{y|n}
CHECK T2:...
CHECK T3:...
CHECK T4:...
CHECK T5:...
T={fused}  SIGMA={disp}  CLASS={Trusted|Suspicious|Malicious|UNCERTAIN}
PI={-2..2}  BY={branch}  WHY={...}
GAPS={...}
```

## 5. Scenario configuration block

```
N_A={15}  N_B={15}  RATIO={0.30}
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

The example thresholds are `theta_high = 7.0`, `theta_low = 4.0`,
`sigma_th = 1.0`, `EPS_MAX = 0.12`. The weight head is the one the manuscript
reports: T1 0.322, T4 0.321, T5 0.140, T2 0.138, T3 0.080.

## 8.1 A benign node, both swarms see it

Local, swarm A, node K7, `t = 1200 s`. The node's offsets are
`[+0.05, -0.03, +0.07, -0.02]`.

```
SWARM=A|K=K7|T=1200s|W=120s
T1=0.85±0.10
T2=0.73±0.11
T3=0.79±0.10
T4=0.78±0.11
T5=0.788±0.009
```

The peer manager receives it over the wire, with its own window:

```
SWARM=B|R=12|K=K7|T=1200s
T1=0.83±0.12
T2=0.75±0.12
T3=0.77±0.11
T4=0.79±0.12
T5=0.787±0.010
```

The manager's reply. Weights per branch: `w_peer proportional to
exp(-gamma * eps)`, `gamma = 2.0`, `w_local proportional to 1`.

```
K=K7
LOCAL=0.85,0.73,0.79,0.78,0.788
CHECK T1:0.85,0.83,0.020,0.490,y
CHECK T2:0.73,0.75,0.020,0.490,y
CHECK T3:0.79,0.77,0.020,0.490,y
CHECK T4:0.78,0.79,0.010,0.495,y
CHECK T5:0.788,0.787,0.001,0.500,y
T=7.97  SIGMA=0.32  CLASS=Trusted
PI=0  BY=T1+T4  WHY=五个分支两端一致且无异常,维持信任
GAPS=none
```

## 8.2 A lying peer

The peer forges the behavioural and task branches of the same node.

```
SWARM=B|R=13|K=K7|T=1300s
T1=0.63±0.10
T2=0.75±0.12
T3=0.77±0.11
T4=0.64±0.10
T5=0.700±0.010
```

```
K=K7
CHECK T1:0.85,0.63,0.220,0.000,n
CHECK T2:0.73,0.75,0.020,0.490,y
CHECK T3:0.79,0.77,0.020,0.490,y
CHECK T4:0.78,0.64,0.140,0.000,n
CHECK T5:0.788,0.700,0.088,0.456,y
T=7.93  SIGMA=0.32  CLASS=Trusted
PI=0  BY=T1+T4  WHY=对端T1/T4被拒,仅用本地证据即判定
GAPS=对端 T1/T4 被拒,建议复核跨群链路或隔离该观察者
```

The two forged branches are refused on the local evidence alone, and the
verdict is unchanged. That is the behaviour the `lying` mode is meant to
test: the cross-swarm channel must not be able to move the decision.

A dispute round then asks the peer for the evidence behind one branch:

```
SWARM=A|K=K7|T=1300s|D=T1
T1=0.85±0.10|raw=航迹RMSE=0.7m;心跳缺失=0/20;应答时延P95=+2.4%
```

## 8.3 An intermittent attacker, and the blind spot it survives

Node K12 is an on-off attacker with camouflage 0.35 and offsets
`[+0.02, -0.01, +0.01, +0.03]`. At `t = 1200 s` it has been active for 21 of
the 121 steps in the window, so the window mean is mostly its idle profile and
the level branches barely see it.

```
SWARM=A|K=K12|T=1200s|W=120s
T1=0.778±0.124
T2=0.747±0.113
T3=0.722±0.104
T4=0.762±0.119
T5=0.752±0.011
```

The peer's values agree, because both windows are diluted in the same way.

```
SWARM=B|R=12|K=K12|T=1200s
T1=0.774±0.121
T2=0.749±0.115
T3=0.721±0.106
T4=0.766±0.118
T5=0.751±0.011
```

```
K=K12
CHECK T1:0.778,0.774,0.004,0.498,y
CHECK T2:0.747,0.749,0.002,0.499,y
CHECK T3:0.722,0.721,0.001,0.500,y
CHECK T4:0.762,0.766,0.004,0.498,y
CHECK T5:0.752,0.751,0.001,0.500,y
T=7.61  SIGMA=0.32  CLASS=Trusted
PI=0  BY=T1+T4  WHY=五个分支两端一致
GAPS=窗口内活动占比异常(21/121)但分支值无法体现
```

**This is the finding the protocol must be designed around.** The
intermittent attacker is judged `Trusted`, and it is judged so *because* the
two managers agreed: the five branches are level aggregates, and agreement
between two level aggregates carries no evidence about intermittency. The
cross-swarm exchange propagates exactly the representation the manuscript
identifies as blind.

Two consequences for the protocol:

1. **The packet must carry more than the five levels.** The dispersion field
   already leaks the intermittency (`0.124` against a benign `0.10`), but it
   is not part of what the fusion consumes. Either the manager is given the
   five scale-free shape statistics of the peer's own channels, or the
   exchange carries the windowed series summary rather than the collapsed
   value.
2. **A manager must be able to decide without the peer.** The `lying` mode
   exists so that the protocol cannot be improved into something that only
   works when the peer is honest.

Without the first change, the inter-swarm channel is a second copy of the
blind spot rather than a remedy for it.
