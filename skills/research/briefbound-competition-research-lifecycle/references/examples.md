# 竞赛科研全流程示例（Competition Research Lifecycle Examples）

## 目录

- AI 与数学建模竞赛
- Workshop benchmark 与论文后期
- 数据泄漏和并行推进
- 榜单回退与 smoke 筛选

## 示例 1：AI 竞赛

用户请求：

```text
我们在做一个图像分类竞赛。请帮我把从数据清洗到最终论文的完整科研流程跑起来。
```

推荐响应形状：

```text
当前阶段: 数据准备
阶段模式: phase-execution
目标: 为图像分类任务建立一个可复现的数据处理流水线和验证集切分方案。
输入: 原始图片、标签、竞赛规则、算力预算
Source of truth: 竞赛规则、原始数据目录、标签文件、当前 preprocessing 脚本
Active baseline / evidence: 尚无 active baseline；先建立 active data version
建议做法:
- 审核标签质量和重复样本
- 明确切分策略
- 产出数据 manifest 和 preprocessing report
支持技能:
- 工程类 skill，用于编写 preprocessing 脚本
- briefbound-router，用于定义 phase gate
要产出的 artifact:
- data-manifest.json
- preprocessing-report.md
- split-strategy.md
- 使用数据就绪报告模板来承载本阶段 artifact
Briefbound gate:
- Behavior: 数据集可以被加载、切分并可复现地重新生成。
- Review: 在训练开始前检查 leakage、重复样本和 schema drift。
- Test: 重跑 preprocessing，并验证 manifest 和 split 输出一致。
范围约束: 在数据 artifact 稳定前，不进入模型选择。
退出标准:
- 切分方案可复现
- leakage 风险已经过审
- preprocessing 输出可重复生成
阶段决策: advance
下一步行动: 基于清洗后的数据假设，进入文献与方案研究阶段
```

## 示例 2：数学建模竞赛

用户请求：

```text
我们要做一个数学建模竞赛，需要一套覆盖假设、实验和最终报告写作的完整流程。
```

推荐响应形状：

```text
当前阶段: 任务定义
阶段模式: phase-execution
目标: 把题目要求转成可衡量的子问题、约束和报告要求。
输入: 赛题文本、交付规则、时间限制
Source of truth: 赛题 PDF、官方交付规则、时间线
Active baseline / evidence: 尚无；先建立项目状态账本和任务定义简报
建议做法:
- 抽取核心假设和目标函数
- 明确评估标准和交付契约
- 找出值得测试的建模分支
支持技能:
- briefbound-router，用于定义 phase gate
- 如果领域背景不清楚，使用当前可用的浏览/研究工具收集来源
要产出的 artifact:
- competition-brief.md
- metric-definition.md
- assumption-register.md
- 使用任务定义简报模板来承载本阶段 artifact
Briefbound gate:
- Behavior: 团队能够清楚复述题目、关键假设和评估逻辑。
- Review: 检查隐藏约束、不现实假设和时间风险。
- Test: 验证从题目到最终报告至少有一条最小可行路径。
范围约束: 在假设和交付要求没写清楚前，不进入实验阶段。
退出标准:
- 问题已经被拆解
- 假设已经显式化
- 候选建模方向已经排出优先级
阶段决策: advance
下一步行动: 围绕优先级最高的分支整理文献和先行方案 shortlist
```

## 示例 3：带 workshop paper 的 benchmark 提交

用户请求：

```text
帮我管理一个 NLP benchmark 的提交流程，里面要覆盖实验、消融和 workshop paper。
```

推荐响应形状：

```text
当前阶段: 文献与方案研究
阶段模式: phase-execution
目标: 建立一个方法 shortlist，并把它们转成具体的 experiment hypotheses。
输入: benchmark 描述、baseline repo、相关工作方向
Source of truth: benchmark 说明、baseline repo、已收集论文和公开方案
Active baseline / evidence: 尚无 active baseline；active evidence 限于已验证来源
建议做法:
- 用当前可用的研究工具收集核心论文、citation 路径、公开 baselines 和 benchmark 背景
- 用 briefbound-ai-research-loop 把来源集合、baseline 和实验假设标准化
- 按可行性和预期信号给方法排序
支持技能:
- 当前可用的浏览/研究工具
- briefbound-ai-research-loop
- briefbound-router
要产出的 artifact:
- literature-matrix.md
- method-candidates.md
- experiment-hypotheses.md
Briefbound gate:
- Behavior: 每个入围方法都能映射到一个具体实验。
- Review: 在实现前检查 novelty、可行性和证据质量。
- Test: 每个方法要么提升为 hypothesis card，要么被明确淘汰。
范围约束: 在 shortlist 稳定前，不进入论文写作。
退出标准:
- shortlisted methods 有证据支撑
- 每个方法都能映射到实验
- research sprawl 已控制
阶段决策: advance
下一步行动: 为最高优先级方法搭建最小 end-to-end baseline
```

## 示例 4：论文后期整理

用户请求：

```text
我们已经有结果和表格了。请用这套竞赛 workflow 帮我们把最终论文初稿整理干净。
```

推荐响应形状：

```text
当前阶段: 论文写作
阶段模式: phase-execution
目标: 把已经验证的结果、tables 和 related work 整理成一篇完整的竞赛论文草稿。
输入: 实验日志、figures、tables、references、最终模型选择
Source of truth: run logs、ablation table、figure provenance、reference list
Active baseline / evidence: 使用 final-model-selection 中 accepted 的 runs 和 tables
建议做法:
- 按证据组织 claims
- 用 briefbound-research-rigor-review 审查 abstract、contributions 和 results sections
- 等证据组织稳定后，再路由到 paper-writing skill
支持技能:
- briefbound-ai-research-loop
- briefbound-research-rigor-review
- 当前可用的论文写作 owner
- briefbound-router
要产出的 artifact:
- paper-outline.md
- figures/
- tables/
- manuscript draft
Briefbound gate:
- Behavior: 每个重要 claim 都能追溯到 table、figure、experiment 或 citation。
- Review: 检查 overclaiming、缺失 limitations 和 related-work 定位偏弱的问题。
- Test: 检查 abstract 和 contribution statements 是否能从当前 evidence pack 得到支撑。
范围约束: 在 claim traceability 没清干净前，不进入最终 submission packaging。
退出标准:
- 每个 claim 都可追溯
- limitations 已明确
- 草稿结构完整
阶段决策: advance
下一步行动: 组装 submission bundle，并执行最终合规检查
```

## 示例 5：后期发现数据泄漏

用户请求：

```text
我们已经做到消融阶段了，结果刚发现验证集切分泄漏了实体身份。这套 workflow 应该怎么回退？
```

推荐响应形状：

```text
当前阶段: 数据准备
阶段模式: phase-recovery
目标: 重建一个有效的切分策略，并把下游证据重新稳定下来。
输入: 当前 split 逻辑、泄漏发现、受影响实验、竞赛规则
Source of truth: split-strategy、leakage report、experiment ledger、竞赛规则
Active baseline / evidence: 受影响 runs 暂时标记 stale；active evidence 回退到泄漏前可验证记录
建议做法:
- 先隔离哪些 runs 已被污染
- 修复 split 策略并重新生成数据 artifacts
- 在 rerun 前，把下游实验和 claims 标记为 stale
支持技能:
- briefbound-router
- 工程类 skill，用于 preprocessing 和 reruns
要产出的 artifact:
- updated split-strategy.md
- leakage-incident.md
- rerun-priority-list.md
Briefbound gate:
- Behavior: 下游实验依赖一个有效且已记录的 split。
- Review: 检查泄漏影响的是 ranking logic、features，还是只是 validation partition。
- Test: 重跑 preprocessing，并验证修复后的 split 具有确定性。
范围约束: 在失效结果未重跑前，不继续论文写作。
退出标准:
- 泄漏机制已被理解
- 受影响 runs 已被标记或退休
- 修复后的 split 可复现
阶段决策: recover
下一步行动: 基于修复后的 split，重跑 baseline 和已晋级实验
```

## 示例 6：并行推进训练、文献和论文审计

用户请求：

```text
我们离截止还有一周，请把训练优化、related work 补强和论文 claim 审计并行推进。
```

推荐响应形状：

```text
当前阶段: 训练与实验 / 论文写作
阶段模式: parallel-lanes
目标: 在不破坏 active baseline 和证据链的前提下，并行推进性能、文献定位和论文审计。
输入: 当前 baseline、experiment ledger、论文草稿、references、public leaderboard 反馈
Source of truth: experiment ledger、run logs、paper claim map、submission checklist
Active baseline / evidence: 使用当前 accepted baseline；论文只引用 accepted evidence
建议做法:
- 建立 lane board，拆成 training-ablation、literature-forensics、claim-audit、submission-check
- 每个 lane 只交付一个候选结果或审计报告
- 所有候选结果回到主流程后再决定是否晋升
支持技能:
- briefbound-ai-research-loop
- briefbound-research-rigor-review
- briefbound-router
要产出的 artifact:
- parallel lane board
- attempt cards
- updated claim map
- submission risk list
Briefbound gate:
- Behavior: 并行任务都围绕独立假设推进，不互相污染 active baseline。
- Review: 检查 lane 是否越界、是否修改同一文件、是否把候选结果当成 accepted evidence。
- Test: 每个 lane 返回证据、风险、决策建议和 lesson。
范围约束: 不把未验证的训练提升、未审计的文献结论或未追溯的 table 写入最终论文。
退出标准:
- 每个 lane 都有明确决策
- 可晋升候选已经回到主流程验证
- stale 或不足证据已标记
阶段决策: iterate
下一步行动: 先验证 training-ablation 的最佳候选，再更新论文 evidence map
```

## 示例 7：线上榜单回退

用户请求：

```text
我们本地 validation 涨了，但 public leaderboard 掉了很多，现在怎么办？
```

推荐响应形状：

```text
当前阶段: 训练与实验
阶段模式: phase-recovery
目标: 判断本地提升是否过拟合 validation 或违反真实评测分布，并恢复到可信 baseline。
输入: 本地 run 记录、public leaderboard 分数、当前提交包、上一版 accepted baseline
Source of truth: experiment ledger、leaderboard submission history、metric-definition、baseline-run
Active baseline / evidence: 暂停当前候选晋升；回到上一版 accepted baseline 做比较
建议做法:
- 记录 leaderboard delta 和对应提交包版本
- 对比当前候选与上一版 active baseline 的数据、config、metric 和 diff
- 检查 validation split 是否与 leaderboard 分布错位
- 如果无法解释回退，拒绝当前候选并保留 lesson
支持技能:
- briefbound-router
- 工程类 skill，用于复现实验和比较 diff
要产出的 artifact:
- leaderboard-feedback-record
- rejected attempt card 或 needs-more-evidence attempt card
- avoid-next-time 规则
Briefbound gate:
- Behavior: 不从线上回退的候选继续叠加实验。
- Review: 检查本地 proxy 是否误导、是否存在 split 或 metric mismatch。
- Test: 复现上一版 active baseline，并比较同一套 validation 指标。
范围约束: 在解释 leaderboard 回退前，不提交新的叠加策略。
退出标准:
- 当前候选被拒绝、保留为待验证，或被明确接受 tradeoff
- active baseline 已恢复或确认
- lesson 已写入实验账本
阶段决策: recover
下一步行动: 从恢复后的 active baseline 重新设计一个单假设 attempt
```

## 示例 8：训练很慢，需要小样本 smoke 筛算法

用户请求：

```text
正式训练太慢了。我要先用小样本 smoke 判断几个架构改动哪个更值得跑正式实验。
```

推荐响应形状：

```text
当前阶段: 训练与实验
阶段模式: phase-execution
目标: 建立小样本 smoke gate，用低成本 proxy ranking 筛掉明显无效的架构候选。
输入: active baseline、候选算法 diff、训练脚本、验证脚本、算力预算
Source of truth: experiment ledger、active data version、baseline run、smoke 脚本或 smoke plan
Active baseline / evidence: active baseline 保持不变；smoke 结果只作为候选筛选证据
建议做法:
- 从 active data version 固定一个代表性 smoke subset
- 让 active baseline 和每个候选算法都跑同一个 smoke
- 记录 proxy metric、delta、耗时、显存峰值、OOM 和失败原因
- 只把 smoke 结果用于 promote-to-full-run / reject / needs-more-evidence
- 对进入 full run 的候选，再跑正式 full validation 或三 seed
支持技能:
- briefbound-router
- 工程类 skill，用于写 smoke runner、日志解析和 ranking 表
要产出的 artifact:
- smoke run records
- proxy ranking table
- updated attempt cards
Briefbound gate:
- Behavior: 每个候选先通过同一小样本 smoke，再决定是否进入正式训练。
- Review: 检查 smoke 子集是否偏置、baseline 是否同跑、proxy metric 是否和正式目标一致。
- Test: smoke 能发现启动失败、OOM、明显退化和资源不可接受的候选。
范围约束: smoke 分数不能写成论文主结果，不能替代正式 full-horizon / 三 seed / held-out 评估。
退出标准:
- baseline 和候选都完成同一 smoke
- 每个候选都有 promote-to-full-run、reject 或 needs-more-evidence 决策
- full run 队列只包含通过 smoke gate 的候选
阶段决策: iterate
下一步行动: 对 ranking 第一的候选启动正式验证，并保留 smoke 与正式结果的一致性记录
```
