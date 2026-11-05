# completion-v1 结果快照

这组小型文件支持上一级设计文档中的数值核对。它们来自独立的本地任务模拟器，
与仓库原有 `artifacts/outputs/` 的合成信任流实验不同，不能混合统计。

| 文件 | 用途 |
|---|---|
| `protocol.lock.json` | 固定任务预算、数据划分、基础环境及实验源码哈希 |
| `selection.lock.json` | 在测试前选定的门槛、参考 baseline 和模型锁定记录的哈希 |
| `model_candidates.json` | MLP/GBDT 的候选配置、验证损失及收敛警告 |
| `test_runs.csv` | 880 次对照运行的逐运行指标 |
| `summary.csv` | 11 种策略的总体均值 |
| `scenario_summary.csv` | 每种策略在 10 个场景中的均值 |
| `paired_comparison.json` | M1/M2/M3 相对预选参考 baseline 的完整 seed 配对区间 |
| `validation.json` | 本地任务、投票、能量与哈希核验记录 |
| `completion_results.png` | 主指标比较图 |
| `SHA256SUMS.txt` | 本目录上述快照文件的内容校验值 |
| `SOURCE_SHA256SUMS.txt` | 发布前本地原始文件的校验值 |

发布副本的文本换行统一为 LF，数值和 JSON 字段保持原样。`SHA256SUMS.txt` 校验 GitHub 上的发布字节；
`SOURCE_SHA256SUMS.txt` 保留本地原始字节的哈希。锁定记录内部的哈希仍指向原始实验文件，
不能直接拿它们核验经过换行规范化的发布副本。

主指标为 `effective_completed_tasks`，每次提供 96 个任务，时间窗口为 240 秒。
`effective_completion_rate` 的分母是全部提供的任务，拒绝任务不从分母中删除。
`tasks_completed` 表示处理/验收流程结束，包含失败任务，不能直接当作有效任务完成数。

总体均值对 10 个场景等权，每个场景有 8 个测试 seed。重复的节点、任务和方法运行不能当成新的独立环境样本。
`selection_wall_ms` 是本地 wall-clock 测量，不是已经计入仿真时钟或能耗的实机推理开销。

模型在训练 seed 8100–8103 上拟合，在 8200–8201 上选型，在 8300–8301 上校准策略，
最后使用 8400–8407 测试。所有图和汇总来自这些固定结果，没有为了此次发布重训或改门槛。
MLP 使用三个初始化的均值集成，固定迭代预算下出现未达到收敛判据的警告，因此不声称达到 MLP 最优性能。

完整模拟器、模型权重和压缩事件轨迹没有包含在这次**方案文档发布**中。源码哈希是版本线索，
`validation.json` 是本地验证记录；它们不能替代公开代码和原始轨迹，也不能仅靠这份快照重现全部检查。
当前文件足以重新计算表格均值和基于逐运行结果的配对差值，完整复现仍需后续发布匹配的实验包。
