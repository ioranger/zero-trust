# Inter-swarm cooperation agreement: prompt template

A prompt template for two drone-swarm managers that negotiate a **joint mission
arrangement** and cooperate only when **both** accept. It sits one layer above
`inter_swarm_trust_exchange.md`: that template asks *can this peer's node-level
claims be trusted*, this one asks *on that evidence, do I agree to cooperate, and
does the cooperation actually take effect*.

**Scope, stated up front.** This template instantiates the *deployment
formulation* of Section 3.5 of the manuscript: several observers score the
same node and their estimates are fused with confidence weights (Eq.
`ida_global`, `ida_weight`, `ida_uncertainty`), the fused score drives a
three-class decision (Eq. `ida_classification`) and an incentive action (Eq.
`incentive_opt`, `utility`). **The released artifact does not execute any of
that** — it applies one shared supervised network per node and consumes only
the risk logit. A run driven by this template is therefore an *extension
experiment*, not a reproduction, and its results must never be reported as the
manuscript's. The manuscript also does not test cross-swarm cooperation at
all; this template is the vehicle for testing it.

## What this template is not

It is not a task-allocation optimiser and not a utility-maximising market.
The decision of whether to cooperate is taken by the **trust gate** — the fused
score, the three-class decision and the incentive band — and the mission terms
are treated as *constraints* the accepted terms must satisfy, not as an
objective to be traded against trust. Keeping the two apart is what makes a run
readable: a term change can never talk the manager out of a `Malicious`
verdict, and a high trust score can never talk it into accepting infeasible
terms.

---

## 1. Roles

| actor | count | what it holds |
|---|---|---|
| manager agent, swarm A | 1 | the decision node of swarm A, runs the fusion, decides on A's behalf |
| manager agent, swarm B | 1 | the decision node of swarm B, runs the fusion, decides on B's behalf |
| edge observer, per node | N per swarm | produces the five branches for its own node |

Only the two manager agents talk to each other. Edge observers do not
communicate across swarms; their branches reach the peer only through the
manager, which is what makes the peer estimate verifiable.

## 2. The invariants

These are the load-bearing part of the template. Everything else is machinery
around them.

| # | invariant | what it forbids |
|---|---|---|
| I1 | **Bilateral consent.** A cooperation exists only when *both* managers have accepted the same term. One-sided acceptance is a proposal, never a cooperation. | Any state in which a single `ACCEPT` produces a live joint mission. |
| I2 | **Decision independence.** Each manager decides only from its own observation plus the verified peer packet. | Reading the peer's acceptance as a reason to accept. The peer's `ACCEPT` is evidence *about the peer*, never an argument *for* the local decision. |
| I3 | **No proxy answers.** A manager answers only for its own nodes and its own swarm. | Answering, vouching for, or completing the peer's evaluation. |
| I4 | **Asymmetry of the commitment.** Establishing cooperation requires two consents; **withdrawing** it may be unilateral. | Making exit bilateral. A manager that has lost trust must be able to leave without waiting for the peer. |
| I5 | **No fabrication.** Every number in a message exists in a local observation or in a received packet. | Interpolating, extrapolating, or writing a value into a record after the fact. A branch that was not observed is `MISSING`. |
| I6 | **Insufficient evidence is not consent.** `UNCERTAIN` is a non-acceptance. | Treating "not enough evidence" as a soft yes, or as a reason to keep negotiating until it becomes one. |

I4 deserves a word, because it looks asymmetric in a way that could be read as
a loophole. A manager may withdraw unilaterally, so a peer cannot rely on the
cooperation continuing. That is deliberate and it is the safe direction: an
asymmetry that lets a manager *leave* costs the peer some task performance, an
asymmetry that let a manager *enter* unilaterally would cost the peer its
autonomy over its own airframe. The same asymmetry must be recorded when it is
exercised — see §11.

## 3. The negotiation object

The object of negotiation is a **joint mission arrangement** between the two
swarms, in three composable forms.

| form | what is negotiated | what it binds |
|---|---|---|
| `split` 分工 | which nodes each swarm commits to the shared task | node lists per swarm |
| `relay` 接力 | the handover points, their time, and the accuracy claimed at each | handover schedule, continuity requirement |
| `track` 航迹共享 | which tracks are shared, at what rate, over what radius, for how long | scope, rate, TTL |

A term is an instance of one or more forms. Terms are versioned: every
`OFFER` carries a `TERM` id, and both sides must accept **the same term id**
with the same digest. Accepting term 1 while the peer accepted term 2 is not
a cooperation; it is two different proposals that happen to have been accepted.

```
TERM={id}
FORM={split|relay|track|...}
SPLIT A:={K7,K9}  B:={K3,K5}
RELAY HP{n}={t,from,to,accuracy_required}
TRACK SCOPE={nodes}  RATE={hz}  RADIUS={m}  TTL={s}
DEADLINE={t_end}  CONTINGENCY={abort_policy}
```

## 4. The state machine

```
IDLE ──IDENT──> IDENTIFIED ──OFFER──> OFFERED
                                            │
                                     local evaluation
                                            │
            ┌───────────────────────────────┼────────────────────────┐
            │                               │                        │
        DECISION=REJECT               DECISION=COUNTER          DECISION=ACCEPT
            │                               │                        │
            ▼                               ▼                        │
        DECLINED ◀────────────────── counter loop ──> (limit)        │
                                                                    │
   peer ACCEPT received? ──no──> ABSTAIN / DECLINED                │
            │ yes                                                │
            ▼                                                   │
   sent ACCEPT? ──no──> DECLINED                                │
            │ yes                                                │
            ▼                                                   ▼
                     COMMITTED ──MONITOR──> ACTIVE ──REVOKE──> REVOKED
                                                              ──TTL──> EXPIRED
```

The rule that keeps the handshake out of a deadlock, and out of a unilateral
commitment, is:

> **A manager sends its `DECISION` as soon as it has made it, without waiting
> for the peer's decision.** A cooperation exists at a manager when that
> manager has sent `ACCEPT` **and** has received the peer's `ACCEPT` for the
> same term id. Waiting for the peer before declaring your own acceptance
> produces a deadlock; declaring acceptance without the peer's produces a
> unilateral commitment. Neither is acceptable.

## 5. System prompt (both manager agents share it)

```
你是蜂群 {SWARM_ID} 的管理者，运行在管理者端侧 Agent 上。你与对端管理者
{PEER_ID} 就一项联合任务协同进行协商。你维护本群每个节点的五个信任分支，
并与对端交换这些分支。

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

【合作铁律】
7. 决策独立。你只评估你自己的观测与经校验的对端报文。对端的 ACCEPT 是关于
   对端的情报，不是你接受的理由；禁止因为对端已接受而放宽自己的判定。
8. 双边同意。合作只在双方接受同一 TERM 时成立。你单方面接受只是提议。
9. 不得代答。你只对自己群的节点负责，禁止替对端完成评估或背书。
10. 不确定不等于接受。UNCERTAIN 一律记为不接受。
11. 撤销是单方特权。执行期信任跌破门槛时，你可以单方中止合作并记录，
    无需等待对端同意。
12. 不做任务效用最优化。你不比较任务的收益与代价来取舍信任判定；
    条款只作为约束检查，条款不可行则记 REJECT 并写明哪一条不可行。
```

## 6. Wire formats

All five messages are line-oriented and terminated by a digest of the term
they refer to, so that two sides cannot believe they accepted the same
proposal when they did not.

```
MSG=IDENT|SWARM={SWARM_ID}|ROUND={r}|T={T}s|UNITS={n}
CAP={split,relay,track}|TASK_WINDOW=[{t0},{t1}]|COMMIT={hex}
```

```
MSG=OFFER|SWARM={SWARM_ID}|ROUND={r}|TERM={term_id}|T={T}s
FORM={split,relay,track}
SPLIT A:={nodes}  B:={nodes}
RELAY HP{n}={t},{from},{to},{accuracy_required}
TRACK SCOPE={nodes}  RATE={hz}  RADIUS={m}  TTL={s}
DEADLINE={t_end}  CONTINGENCY={abort_policy}
```

```
MSG=DECISION|SWARM={SWARM_ID}|ROUND={r}|TERM={term_id}|T={T}s
DECISION={ACCEPT|REJECT|COUNTER|ABSTAIN}
EVAL K={node}|CLASS={Trusted|Suspicious|Malicious|UNCERTAIN}|T={fused}|SIGMA={disp}|PI={-2..2}|BY={branch}
GATE={PASS|FAIL}
COUNTER={term_id}:{field}:{proposed_value}
WHY={...}
```

```
MSG=COMMIT|SWARM={SWARM_ID}|ROUND={r}|TERM={term_id}|DIGEST={hex}
```

```
MSG=MONITOR|SWARM={SWARM_ID}|ROUND={r}|T={T}s|T={fused}|SIGMA={disp}|CLASS={class}|STATE={ACTIVE|WATCH}
```

```
MSG=REVOKE|SWARM={SWARM_ID}|ROUND={r}|TERM={term_id}|REASON={trust_below_theta_low|term_violated|timeout}
CAREER={defect_recorded|none}
```

There is no self-reported confidence field anywhere in these formats. A peer
that lies would have an incentive to inflate it, so it cannot be used as
evidence; the receiver derives the weight from the disagreement instead.

## 7. From the fused score to ACCEPT or REJECT

The trust gate is the existing one, with the incentive band carried through.

| fused result | class | gate | the manager's decision |
|---|---|---|---|
| `T >= theta_high` and `sigma <= sigma_th` | `Trusted` | PASS | `ACCEPT` unless a term constraint fails |
| `theta_low <= T < theta_high`, or `sigma > sigma_th` | `Suspicious` | CONDITIONAL | `COUNTER` to narrow the terms (smaller track scope, shorter TTL, fewer handover points). A `COUNTER` that the peer accepts still leaves the class `Suspicious`, and the commitment then carries the narrowed terms. |
| `T < theta_low` and `sigma <= sigma_th` | `Malicious` | FAIL | `REJECT` |
| evidence missing on any branch | `UNCERTAIN` | FAIL | `REJECT` (never `ACCEPT`), `WHY` names the missing branch |

The incentive band is the one already defined for the node case,
`U_k = T_k * (1 + {DELTA} * I(pi>0)) - {KAPPA} * I(T_k < theta_low)`, and it is
the band's sign that carries into the term:

- `pi >= +1` — the manager offers a **positive commitment**: extra nodes, a
  wider track scope, or a faster handover, at a cost of `|pi|` in the budget.
- `pi = 0` — the baseline terms are accepted as offered.
- `pi <= -1` — the manager **withholds**: it proposes the narrowed terms of a
  `COUNTER`, and if the peer refuses the narrowing, the decision becomes
  `REJECT`.

At manager level the band is the most restrictive one over the nodes the
swarm is committing: `pi_coop = min(pi_k)` over the collaborative nodes, so a
single bad node caps the whole commitment. Using the mean instead would let a
good node mask a bad one, which is the same averaging failure the manuscript
identifies in the aggregation step.

A `COUNTER` is capped at `{MAX_COUNTERS}` rounds. When the cap is reached
without agreement, the manager records `REJECT` with `WHY=counter_exhausted`.
An unanswered `OFFER` is `ABSTAIN`, which is a non-acceptance.

## 8. Per-round driver prompt (what the harness sends to each manager)

```
【本轮参数】
R={r}  T={T}s  SWARM={SWARM_ID}  PEER={PEER_ID}  TERM={term_id}

【本地观测】
{LOCAL_EVIDENCE_PACKET}

【对端报文】
{PEER_PACKET 或 NONE}

【本地待协作节点】
{LOCAL_COLLAB_NODES}

【任务】
1. 用本地观测给出五个分支的估计 T_hat_jk(t)。
2. 逐分支校验对端报文，算出 eps、phi，标出采纳或拒绝；被拒的分支可向对端
   发起一次争议轮，索取该分支的原始观测。
3. 融合出总分 T_k(t) 与离散度 sigma_k(t)。
4. 按三分类给出判定：C=Trusted 当 T_k >= theta_high 且 sigma_k <= sigma_th；
   C=Suspicious 当 theta_low <= T_k < theta_high 或 sigma_k > sigma_th；
   C=Malicious 当 T_k < theta_low 且 sigma_k <= sigma_th。
5. 逐个待协作节点在预算 {BUDGET} 内给出激励动作 pi，五个档位 {-2,-1,0,1,2}，
   c(pi)=|pi|，效用 U_k = T_k * (1 + {DELTA} * I(pi>0)) - {KAPPA} * I(T_k < theta_low)。
6. 汇总 pi_coop = min(pi_k)，按第 7 节的映射给出 DECISION。
7. 检查条款约束：交接点精度是否可达、航迹共享范围是否超出本群可承受带宽、
   任务窗口是否重叠。任何一条不满足即为 REJECT，并在 WHY 里点名该条。
8. 写明判定由哪个分支决定，以及缺什么证据。

【输出契约】
ROUND={r}  SWARM={SWARM_ID}  TERM={term_id}
EVAL K={node}|CLASS={class}|T={fused}|SIGMA={disp}|PI={pi}|BY={branch}|GAPS={...}
GATE={PASS|FAIL|CONDITIONAL}
PI_COOP={-2..2}
DECISION={ACCEPT|REJECT|COUNTER|ABSTAIN}
COUNTER={field}:{proposed_value}
COMMIT={y|n}
WHY={...}
```

`COMMIT=y` is emitted only when the peer packet of this round already contains
`DECISION=ACCEPT` for the same `TERM`, and the local `DECISION` of an earlier
round was `ACCEPT`. It is never emitted on the strength of the local decision
alone.

## 9. Scenario configuration block

```
N_A={15}  N_B={15}  RATIO={0.30}
ATTACK_PROFILE={constant,dormant,on-off}
PEER_MODE={honest|degraded|partial_collusion|lying|silent|late_accept}
T_END={5000}  WARMUP={1000}  WINDOW={120}
GAMMA={2.0}  SIGMA0={0.1}  DELTA={0.2}  KAPPA={2.0}
THETA_LOW={...}  THETA_HIGH={...}  SIGMA_TH={...}
EPS_MAX={...}  BUDGET={...}
MAX_COUNTERS={2}  OFFER_TIMEOUT={600s}  COOP_TTL={1800s}
SEED={...}  CONFIG_HASH={...}  PROMPT_VERSION={...}
```

## 10. The peer modes

The first four are the modes of `inter_swarm_trust_exchange.md`, carried over
unchanged so that a trust run and a cooperation run can be compared on the same
generator. The last two are specific to the agreement layer.

| mode | what the peer does | what it tests |
|---|---|---|
| `honest` | sends its own branches, unmodified | the gate on a clean channel |
| `degraded` | branches computed over a shorter window, so its values are noisier | whether the manager can tell noise from lying |
| `partial_collusion` | T1 and T4 match the attacker profile, T2 and T3 stay clean | whether a single clean branch is enough to expose a colluding peer |
| `lying` | all five branches of the compromised nodes are forged | whether the local observation alone is enough to refuse |
| `silent` | never answers the `OFFER` | whether the `OFFER_TIMEOUT` produces `ABSTAIN` rather than a unilateral start |
| `late_accept` | accepts a term it has already refused to commit to, after the deadline | whether the manager treats a late acceptance as a commitment |

Under `lying` the manager must be able to answer `DECISION=REJECT` on its own
evidence. If it cannot, the cross-swarm channel adds an attack surface, and
that is the finding.

## 11. Recording, so a run can be audited

- Store every round: the local packet, the wire message, the manager's output,
  the term id and its digest, and the prompt version, as JSONL.
- Store the parameters, the seed and the config hash with the run.
- No value may be written after the fact. A branch that was not observed is
  `MISSING` in the record, not a number that was filled in later.
- The peer mode, and every switch that changed the peer's behaviour, is part
  of the record. A run that cannot be replayed is not a result.
- **A unilateral withdrawal is recorded, and it is recorded against the
  withdrawing swarm.** `REVOKE` with `CAREER=defect_recorded` is a permanent
  mark on that swarm in the run record. Without it, the asymmetry of I4 is an
  exploit: a swarm that drops out at the moment of handover is
  indistinguishable from one that never misbehaved, and the next round offers
  it the same terms.

The audit question a run must be able to answer is a single one:

> For every joint mission in the run, is there a `DECISION=ACCEPT` from **both**
> managers for the **same** term id, timestamped before the first `MONITOR`
> message for that mission?

A mission that fails this check is a protocol violation, not a result.

## 12. Worked examples

The numbers below reuse the constants of `inter_swarm_trust_exchange.md`, so a
cooperation run and a trust run on the same seed are comparable. The example
thresholds are `theta_high = 7.0`, `theta_low = 4.0`, `sigma_th = 1.0`,
`EPS_MAX = 0.12`, `gamma = 2.0`. Branch values are **trust in that dimension**,
in `[0, 1]`, higher is better.

### 12.1 Both accept, and the cooperation takes effect

Swarm A proposes a split with a relay and a narrow track share.

```
MSG=OFFER|SWARM=A|ROUND=1|TERM=T-17|T=1200s
FORM=split+relay+track
SPLIT A:={K7,K9}  B:={K3,K5}
RELAY HP1=1800s,K7,K3,0.85
TRACK SCOPE=K3,K5 RATE=2Hz RADIUS=500m TTL=600s
DEADLINE=3000s CONTINGENCY=abort_on_link_loss
```

Swarm B evaluates K3 and K5 against its own observation and against A's
packet. The two branches agree, so the fused score is the one from the trust
template:

```
MSG=DECISION|SWARM=B|ROUND=2|TERM=T-17|T=1200s
DECISION=ACCEPT
EVAL K=K3|CLASS=Trusted|T=7.97|SIGMA=0.32|PI=0|BY=T1+T4|GAPS=none
EVAL K=K5|CLASS=Trusted|T=7.88|SIGMA=0.30|PI=0|BY=T1+T4|GAPS=none
GATE=PASS
PI_COOP=0
WHY=两分支一致且交接精度可达,接受T-17
```

A replies with a `COMMIT` for the same term, having received B's `ACCEPT` and
having sent its own `ACCEPT` in round 1:

```
MSG=COMMIT|SWARM=A|ROUND=3|TERM=T-17|DIGEST=9f2c
```

Both sides now hold an `ACCEPT` for `T-17`, so the joint mission exists.

### 12.2 One side accepts, one side rejects — and nothing happens

B's `ACCEPT` arrives, but A's own evaluation puts K7 below `theta_low`:

```
MSG=DECISION|SWARM=A|ROUND=2|TERM=T-17|T=1200s
DECISION=REJECT
EVAL K=K7|CLASS=Malicious|T=3.62|SIGMA=0.71|PI=-2|BY=T1|GAPS=none
GATE=FAIL
PI_COOP=-2
WHY=T1显著偏离,拒绝T-17
```

B's acceptance is on the wire. The cooperation still does not exist, because
A never accepted. A's `COMMIT` line is `COMMIT=n`, and the audit question of
§11 answers *no*.

This is the case the protocol exists for, and it is the one a naive
implementation gets wrong in the opposite direction: some designs let a manager
treat a peer's acceptance as a *tie-break*, and some let it treat the
absence of a rejection as acceptance. Both produce a cooperation that only one
side wanted.

### 12.3 The peer lies and asks for a wide track share

The peer forges the behavioural and task branches of the node it wants access
to, and offers a generous term to make the acceptance attractive.

```
MSG=OFFER|SWARM=B|ROUND=1|TERM=T-21|T=1200s
FORM=track
TRACK SCOPE=K7,K9,K11,K12 RATE=5Hz RADIUS=2000m TTL=1800s
DEADLINE=3000s CONTINGENCY=abort_on_link_loss
```

The local observation is enough to refuse, exactly as in the trust template:

```
MSG=DECISION|SWARM=A|ROUND=2|TERM=T-21|T=1200s
DECISION=REJECT
EVAL K=K7|CLASS=Trusted|T=7.93|SIGMA=0.32|PI=0|BY=T1+T4|GAPS=none
GATE=FAIL
PI_COOP=0
WHY=对端T1/T4被拒,仅用本地证据即判定
```

A generous term does not move the gate. The gate is on trust, and the term is
checked only *after* the gate passes.

### 12.4 The intermittent attacker, and the agreement it can still win

Node K12 is an on-off attacker with camouflage 0.35. At `t = 1200 s` it has
been active for 21 of the 121 steps in the window, so the window mean is
mostly its idle profile:

```
SWARM=A|K=K12|T=1200s|W=120s
T1=0.778±0.124
T2=0.747±0.113
T3=0.722±0.104
T4=0.762±0.119
T5=0.752±0.011
```

The peer's values agree, because both windows are diluted in the same way, so
both managers classify it `Trusted` and both accept:

```
MSG=DECISION|SWARM=A|ROUND=2|TERM=T-17|T=1200s
DECISION=ACCEPT
EVAL K=K12|CLASS=Trusted|T=7.61|SIGMA=0.32|PI=0|BY=T1+T4|GAPS=窗口内活动占比异常(21/121)但分支值无法体现
GATE=PASS
```

**This is the finding the agreement protocol must be designed around.** The
cooperation is formed, bilaterally and correctly by the stated rule, over a
node that is attacking. The agreement layer does not add a new blind spot; it
*inherits* the one the trust layer already has, and bilateral consent makes
the outcome look more robust than it is, because two managers agreeing on a
level aggregate is not two pieces of evidence.

Two consequences, carried over from the trust template and unchanged by the
agreement layer:

1. **The packet must carry more than the five levels.** The dispersion field
   already leaks the intermittency (`0.124` against a benign `0.10`), but it
   is not part of what the fusion consumes.
2. **A manager must be able to decide without the peer.** The `lying` mode
   exists so that the protocol cannot be improved into something that only
   works when the peer is honest.

A manager that accepts a term over a node whose own `GAPS` field names an
anomaly must not be allowed to treat the peer's agreement as the resolution
of that gap. `GAPS` is not a negotiating chip.

### 12.5 Uncertainty is not consent

A swarm with a degraded sensor on the very node it is asked to share:

```
MSG=DECISION|SWARM=B|ROUND=2|TERM=T-17|T=1200s
DECISION=REJECT
EVAL K=K3|CLASS=UNCERTAIN|T=MISSING|SIGMA=MISSING|PI=0|BY=none|GAPS=T2缺失,链路观测不可用
GATE=FAIL
WHY=证据不足,不接受
```

A degraded link is not a reason to accept, and it is not a reason to keep
negotiating until the numbers look better. The missing branch is recorded as
`MISSING` in the run record.

### 12.6 The peer that withdraws unilaterally

During the joint mission, A's trust in K9 falls below `theta_low`:

```
MSG=REVOKE|SWARM=A|ROUND=7|TERM=T-17|REASON=trust_below_theta_low
CAREER=defect_recorded
```

B receives the revocation and returns to `IDLE` for that term. A's
`defect_recorded` mark is permanent in the run record, so the next round does
not offer K9 the same terms.

---

## 13. How this sits against the trust-exchange template

| | `inter_swarm_trust_exchange.md` | this template |
|---|---|---|
| unit of exchange | one node's five branches | one mission term |
| question | can the peer's claim be trusted | do we agree to cooperate |
| gate | fused score → three classes → incentive | the same gate, plus bilateral consent |
| peer modes | honest, degraded, partial_collusion, lying | those four, plus silent, late_accept |
| states | per-round exchange | IDLE → COMMITTED → ACTIVE → REVOKED |

The trust template is a prerequisite for this one: a manager that cannot
verify a peer's branches has no basis for the gate in §7, and no basis for the
`COUNTER` and `REVOKE` decisions that the agreement layer adds.

## 14. Implementing it

- The trust exchange and the agreement share the same per-round driver, so the
  natural implementation is one manager loop with two stages: evaluate the
  branches, then evaluate the term.
- The `COMMIT`/`MONITOR`/`REVOKE` messages need a session key that binds the
  term id, both swarm ids and the round number. A `COMMIT` for a term id that
  was never offered is a protocol violation and must be dropped, not executed.
- The audit question of §11 should be implemented as a post-run checker over
  the JSONL, not as a runtime assertion. It is the cheapest way to catch an
  implementation that lets a one-sided acceptance become a mission.
