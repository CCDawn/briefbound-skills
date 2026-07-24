# 竞赛科研全流程参考（Competition Research Lifecycle Reference）

## 目录

- 运行模型与事实源
- Active 状态、实验晋升和 smoke/proxy gate
- 并行 lane、外部反馈与共享 artifact
- 任务、数据、研究、baseline、实验、消融、写作和提交阶段
- 默认响应骨架与范围约束

这份 reference 定义了面向竞赛型科研工作的阶段模型、证据账本、逐阶段 BRT gates、checklists、并行 lane 和路由规则。

## 运行模型

把竞赛科研项目视为一串带 gate 的阶段。每个阶段正式开始前，都要先回答四个问题：

1. 这个阶段结束后，应该具备什么行为或能力？
2. 在继续投入高成本工作前，哪些东西可以先被 review？
3. 什么 evidence 或 artifact 能证明这个阶段完成了？
4. 这一次明确不做什么？

这里的语言框架是 BRT，而不是额外再加一个独立业务步骤。

每一轮结束时，都要落到下面四种决策之一：

- `advance`：退出标准已满足，可以进入下一阶段。
- `iterate`：继续停留在当前阶段，因为 artifact 还不完整，或者信号还不够强。
- `recover`：回退到上游阶段，因为依赖项失效了。
- `stop`：因为时间、算力、访问权限或证据不足而暂停。

优先使用 [templates.md](templates.md)，避免每次从零发明 artifact 格式。

## Source of Truth 层

每次接手项目时，优先查找当前项目内最可信的 source of truth。常见文件名可以不同，但语义必须清楚：

- 规则层：竞赛说明、评分规则、提交格式、官方 FAQ、截止时间。
- 数据层：data manifest、split strategy、preprocessing log、schema notes、leakage report。
- 实验层：baseline record、experiment ledger、run logs、model registry、training decisions。
- 分析层：ablation table、error analysis、final model selection。
- 论文层：paper outline、claim map、figure/table provenance、reference list。
- 提交层：submission checklist、environment lock、reproduction notes、final bundle manifest。

如果 source of truth 不存在，不要从记忆补全。先创建最小版本，或向用户报告缺口。

## Active 状态规则

在第 4-8 阶段推进前，必须明确：

- active data version：当前有效数据、split 和 preprocessing 版本。
- active baseline：当前可信 baseline 或 final candidate。
- active metric：当前使用的评估方式和与官方评分的关系。
- active evidence：可用于论文 claim、表格和最终提交的证据集合。

如果工作区状态与 active 记录不一致，先停下并报告 drift。典型 drift 包括：

- 代码、config 或 seed 与 baseline 记录不一致。
- 表格指标无法追溯到 run。
- paper claim 引用了已失效或未知来源结果。
- public leaderboard 反馈与本地 validation 明显冲突。

## 实验晋升规则

每次训练、消融或方案变更都按 attempt 管理：

- 一个 attempt 只验证一个主要 hypothesis。
- 必须写清 based-on baseline、数据版本、改动变量、固定变量、预期信号、风险和验证命令。
- 如果正式训练成本高，attempt 先经过小样本 smoke gate，再决定是否进入 full run。
- 通过 gate 后才能晋升为 active baseline 或 active evidence。
- 未通过 gate 的 attempt 要记录 failure reason、lesson 和 avoid next time。
- 不要把两个未验证成功的实验直接叠加成新 baseline。

晋升条件：

- 数据版本、metric、config 和 seed 可追溯。
- 主指标有清楚 delta，关键次指标没有灾难性退化。
- 结果可以复现，或已明确说明复现成本和残余风险。
- 与 public leaderboard 或外部评测的关系被解释清楚。
- 能支撑的 claim 被限定在证据边界内。

拒绝或回退条件：

- 发现 leakage、metric bug、split 错误或评估脚本不一致。
- 结果依赖无法复现的本地状态。
- 多策略混杂导致无法归因。
- public leaderboard 显著回退，且没有被接受的 tradeoff 说明。
- 论文 claim 超过证据支持范围。

## 小样本 Smoke / Proxy Ranking Gate

用于训练很慢、正式验证昂贵、候选算法较多的项目。目标是快速判断候选是否值得进入正式训练，而不是产出论文结论。

Smoke 设计要求：

- 固定数据子集：从 active data version 中抽取代表性小样本，并记录抽样规则、样本数量和 seed。
- 固定训练预算：例如少量 batch、少量 clips、短 epoch、固定 step 上限或固定 wall time。
- 固定评估口径：至少包含一个 proxy metric、相对 active baseline delta、失败原因和资源指标。
- 固定运行环境：记录 GPU、batch size、frame config、precision、checkpoint/resume 方式。
- 同跑 baseline：active baseline 必须用同一个 smoke 跑一遍，否则候选的 proxy 分数不可比较。

Smoke 可以决策：

- `promote-to-full-run`：smoke 稳定、资源可接受、proxy metric 不差于 baseline，且符合假设。
- `reject`：启动失败、OOM、速度不可接受、proxy metric 明显低于 baseline，或行为与假设相反。
- `needs-more-evidence`：proxy metric 波动大、样本偏置明显、或与历史正式结果冲突。

Smoke 不能决策：

- 不能晋升 active baseline。
- 不能作为 paper claim 的主证据。
- 不能替代三 seed、full-horizon、held-out 或官方评测。

如果 smoke 与正式结果之间相关性未知，先用 2-3 个已有候选回放校准：确认 smoke 能区分明显好/坏方向，再用它筛选新算法。

## 并行 lane 模式

当用户要求并行推进、多 agent、快速探索或拆分工作时，先建立 lane board。每个 lane 都要有独立假设、边界和交付物。

推荐 lane：

- `data-audit`：审计数据版本、split、leakage、schema drift。
- `literature-forensics`：整理论文、公开 baseline、榜单方案和可迁移假设。
- `baseline-build`：建立最小端到端训练、验证、推理、提交链路。
- `training-ablation`：围绕一个变量或组件做受控实验。
- `leaderboard-alignment`：比较本地 validation、public leaderboard 和官方规则。
- `claim-audit`：审查论文 claim、表格、图和引用来源。
- `submission-check`：检查最终包、环境、复现说明和合规风险。

并行规则：

- lane 产物只是候选证据，不能直接晋升。
- 不让多个 lane 同时修改同一个主工作区文件。
- 每个 lane 结束时必须给出 `promote-candidate`、`reject`、`needs-more-evidence` 或 `proposal-only`。
- 合并前比较证据质量、diff 范围、风险、复现性和与 active baseline 的关系。

## 外部反馈规则

public leaderboard、线上评测、评审意见和人工复核都是外部反馈，但权重不同：

- public leaderboard 是强信号，但可能诱导过拟合，不能单独替代 clean validation。
- 官方 hidden/private 反馈优先级高于本地 proxy。
- 人工评审或 reviewer comment 只改变论文和实验优先级，不自动改写实验事实。
- 如果外部反馈推翻 active evidence，进入 `phase-recovery`，标记受影响 run、table、claim 和 submission bundle。

## 共享 artifact 预期

除非用户明确要求其他格式，否则每个阶段的 artifact 至少应该包含：

- 该阶段的目标
- 实际使用的输入或证据来源
- 该阶段做出的关键决策
- 当前仍然存在的开放风险
- 推进到下一步所需的动作

对实验和论文类产物，要保持 provenance 可见。记录数据版本、config、来源、citation，以及 table 或 figure 的来历。

## 阶段 1：任务定义（Task framing）

目的：
- 理解 competition objective、scoring metric、约束、时间线和交付物。

何时进入：
- 任务本身或规则仍然含糊
- 团队还不能清楚说出 metric、提交契约或 deliverables
- submission format、预算或合规假设仍然模糊

典型输入：
- competition brief
- evaluation rules
- submission format
- timeline 和 compute budget

Checklist：
- metric 和 ranking logic 已经用直白语言写清楚
- 允许和禁止使用的数据、工具都已经明确
- deliverables、截止时间、团队约束都已明确
- 潜在 leakage 或合规风险已经尽早点名
- source of truth 的存放位置已经约定

Routing：
- 用 `ccdawn-brt` 锁定范围和阶段退出标准
- 如果领域背景、历史 baselines 或 policy context 还不清楚，使用当前可用的浏览/研究工具收集来源，再交给 `ccdawn-ai-research-loop` 收敛

BRT gate：
- Behavior: 团队可以准确说出目标 metric、允许使用的数据，以及最终 deliverables。
- Review: 检查是否误读规则、遗漏隐藏约束、忽略 leakage 风险或低估截止时间风险。
- Test: 如果可行，跑通或检查一条最小可提交路径。

Artifacts：
- `competition-brief.md`
- `metric-definition.md`
- `submission-checklist.md`
- 最小 research ledger 或 project status 记录
- 使用 [templates.md](templates.md) 中的任务定义模板

退出标准：
- metric 和 ranking logic 已明确
- submission contract 已理解
- 约束和开放风险已记录

Recovery signals：
- metric 被理解错了
- 规则暗示了另一套 validation 或 submission contract
- 必需 deliverables 发现得太晚

## 阶段 2：数据准备（Data preparation）

目的：
- 把原始 competition data 转换为可复现的训练、验证和推理输入。

何时进入：
- 任务规则已经足够清楚
- 原始数据虽然存在，但还不能被稳定复现、审计或正确划分

典型输入：
- raw datasets
- metadata
- labels
- schema notes

Checklist：
- dataset 来源和版本可识别
- split 逻辑已经写清并可复现
- leakage、重复样本、噪声等已知风险已经记录
- preprocessing 输出可以重新生成
- active data version 已经命名

BRT gate：
- Behavior: 数据可以被可复现地加载、版本化、切分和审计。
- Review: 检查 leakage、重复样本、类别失衡、缺失值、schema drift 和 label noise。
- Test: 生成一个确定性的 manifest，或一个可重复的 preprocessing 输出。

Artifacts：
- `data-manifest.json`
- `preprocessing-report.md`
- `split-strategy.md`
- 使用 [templates.md](templates.md) 中的数据就绪模板

退出标准：
- dataset 版本可识别
- train、validation 和 test 的处理方式可复现
- 已知数据风险已记录
- active data version 可以被下游实验引用

Recovery signals：
- 实验结果依赖了一个不稳定或未记录的 split
- preprocessing 不能重复运行
- 后期发现 leakage 或 schema drift

## 阶段 3：文献与方案研究（Literature and solution research）

目的：
- 找出与本次 competition 相关的方法、先验、baseline 和可迁移思路。

何时进入：
- baseline 方向还没有定
- 团队手里只有原始资料，还没有排好序的方法 shortlist
- related work 和公开 baselines 还是散的

Routing：
- 当前可用的浏览/研究工具：学术论文、citation、leaderboard、repo、公开方案和领域背景
- `ccdawn-ai-research-loop`：把来源、baseline 和假设标准化为可验证的研究 lane

Checklist：
- 来源已经按方法、数据集、metric 或 claim 分组
- 每个候选方法都有可行性和预期信号说明
- shortlist 已经排过优先级，而不是一堆开放候选
- 每个入围方法都能映射到一个可测试实验
- 每个候选方法都能说明需要哪类数据、算力和 baseline 改动

BRT gate：
- Behavior: 候选方案被转换成具体的 experiment hypotheses。
- Review: 检查 novelty、feasibility、算力匹配度和证据质量。
- Test: 每个候选方法都要么映射成可测试实验，要么被明确淘汰。

Artifacts：
- `literature-matrix.md`
- `method-candidates.md`
- `experiment-hypotheses.md`
- 使用 [templates.md](templates.md) 中的 research evidence 和 hypothesis 模板

退出标准：
- 已经有排好序的方法 shortlist
- 每个入围方法都有 rationale 和预期信号
- research sprawl 已被控制
- 入围方法已转成 attempt 或 lane 候选

Recovery signals：
- shortlist 建立在模糊偏好上，而不是证据上
- 没有候选方法能干净地映射到实验
- 写论文时暴露出 related work 覆盖缺口

## 阶段 4：Baseline 系统（Baseline system）

目的：
- 搭出一个最小但完整的 end-to-end 系统，能训练、验证、推理并提交。

何时进入：
- 团队已经选定起步方法或 reference baseline
- 数据和 metric 处理已经稳定到足以进入实现

典型输入：
- prepared data
- reference model choice
- 默认训练 recipe

Checklist：
- 至少存在一条可复现的端到端运行路径
- metric 计算和 competition contract 一致
- configs、seeds 和环境假设已记录
- 可以生成至少一个有效 submission artifact
- active baseline 已经命名并绑定数据版本、metric 和 config

BRT gate：
- Behavior: 至少有一个可复现 baseline 能跑完整个 competition loop。
- Review: 检查接口不匹配、复现性缺口、日志缺失和无效比较。
- Test: 验证至少一次可重复运行，以及至少一个有效提交产物。

Artifacts：
- `baseline-run.md`
- `reproducibility-log.md`
- baseline config files
- 使用 [templates.md](templates.md) 中的 baseline 运行模板

退出标准：
- 训练和推理链路可运行
- metric 计算可信
- baseline 分数已连同 config 和 seed 记录下来
- 后续实验可以明确 based-on 这个 baseline

Recovery signals：
- metric 代码与官方 scoring 不一致
- 运行无法复现
- 无法生成有效的 end-to-end submission

## 阶段 5：训练与实验（Training and experimentation）

目的：
- 通过有纪律的实验设计和执行来提升表现。

何时进入：
- baseline loop 已可用
- 已经有值得测试的 hypothesis list
- 算力预算和日志纪律已经明确

典型输入：
- baseline system
- hypothesis list
- compute budget

Checklist：
- 每次 run 只改动一组受控变量
- 每次 run 都记录 config、seed 和 metric 输出
- 死路和有效方向都被明确记下
- 下一轮是否推进，基于 evidence 而不是记忆
- 每次 run 都能映射到一个 attempt id 和父 baseline
- 高成本 full run 前已经跑过 smoke gate，或明确说明为什么跳过

BRT gate：
- Behavior: 每个实验都围绕一个清晰 hypothesis，只改动受控变量。
- Review: 检查混杂因素、缺失日志、随机性失控、smoke 子集偏置和算力浪费。
- Test: 先用 smoke 验证可运行性和 proxy 排名，再为 full run 记录 config、seed、model version、metric 输出和备注。

Artifacts：
- `experiments/`
- `runs/`
- `model-registry.md`
- `training-decisions.md`
- experiment ledger 或 attempt cards
- smoke run records 或 proxy ranking table
- 使用 [templates.md](templates.md) 中的 experiment card 模板

退出标准：
- 实验可归因、可比较
- 有希望的方向和噪声已经区分开
- 死路已被记录，避免重复试错
- 晋升和拒绝决策都有可追溯证据
- full run 候选经过 smoke 排序，且跳过/拒绝理由清楚

Recovery signals：
- runs 因为 config 漂移而不可比较
- 团队无法解释分数为什么变化
- public leaderboard 反馈取代了本地验证纪律
- smoke 排名与正式结果持续冲突，说明 proxy gate 失效

## 阶段 6：分析与消融（Analysis and ablation）

目的：
- 解释性能为什么变化，并识别真正起作用的组件。

何时进入：
- 已经有多组有意义的 runs 可比较
- 方法选择开始收敛到最终方案
- 团队需要为 claims 提供证据，而不只是分数

Checklist：
- 至少有一个 comparative 或 ablation 视图能隔离关键改动
- 错误模式或 failure modes 已经写出来
- 最终模型选择有证据说明
- claim 用语没有超出证据支持范围
- final candidate 的证据边界已经写清楚

BRT gate：
- Behavior: 团队不仅能展示 leaderboard 变化，还能用证据解释方法选择。
- Review: 检查是否过拟合 public feedback、是否把不稳定胜利说得过满、是否提出无支撑的因果 claim。
- Test: 产出至少一个能够隔离关键选择的 ablation 或 comparative analysis。

Artifacts：
- `ablation-table.md`
- `error-analysis.md`
- `final-model-selection.md`
- 使用 [templates.md](templates.md) 中的 ablation 和最终选择模板

退出标准：
- 主要 claims 有证据支撑
- failure modes 已经理解到足以描述
- 最终方案有合理依据
- active evidence 已经能支撑第 7 阶段的论文大纲

Recovery signals：
- 当前方法只是在噪声大或不稳定的证据上获胜
- 团队说不清为什么提升了这个 final method
- 写论文时才发现证据还没整理好

## 阶段 7：论文写作（Paper writing）

目的：
- 把已经验证过的研究记录整理成一篇连贯的论文或报告。

何时进入：
- 最终模型故事已经稳定到可以描述
- tables、figures 或核心实验事实已经存在
- 团队可以清楚说出 contribution，而不是靠猜

Routing：
- 当前可用的论文写作 owner：当 claims、tables、figures 和 references 已组织好时使用
- `ccdawn-ai-research-loop`：当 related work、方法定位或实验方向仍然松散时使用
- `ccdawn-research-rigor-review`：当 draft、结构化 outline 或重要 baseline claim 已存在时使用

BRT gate：
- Behavior: 论文中的每个重要 claim 都能追溯到实验、table、定性案例或 citation。
- Review: 检查 overclaiming、缺失 limitations、related work 定位薄弱和 citation 缺口。
- Test: 验证 abstract、contributions、method、results 和 limitations 是否与 evidence 对齐。

Checklist：
- paper outline 是按现有 evidence 来组织的
- 每条 contribution statement 都有对应支撑材料
- limitations 和不确定性都被明确写出
- references、tables 和 figures 在内部保持一致
- 每个重要 claim 都标记 accepted、needs-evidence、revise 或 drop

Artifacts：
- `paper-outline.md`
- `figures/`
- `tables/`
- manuscript draft
- 使用 [templates.md](templates.md) 中的 paper evidence map 模板

退出标准：
- draft 结构完整
- claims 可追溯
- references 和 figures 一致
- draft 没有引用 stale run、stale table 或未知来源数字

Recovery signals：
- abstract claims 超出了 evidence
- results section 使用了来历不清的 tables
- related work 太薄，无法支撑定位

## 阶段 8：提交打包（Submission packaging）

目的：
- 组装 competition 最终要求的代码、模型、报告、附录和提交文件。

何时进入：
- final draft 或 final model 已经选定
- deliverables 已知且大体齐全
- 当前重点已经从探索转向 handoff 或 submission risk

BRT gate：
- Behavior: 最终包可以被提交或移交，不依赖隐藏状态。
- Review: 检查缺失文件、环境假设、命名不一致和合规问题。
- Test: 执行最终打包 checklist，并在可能时做一次干净环境复现。

Checklist：
- 必需文件都在，且命名正确
- 环境和复现说明可用
- 最终 claims 与提交 artifact 指向同一版结果
- handoff 所需的剩余风险已经记录
- final bundle 与 active baseline、active evidence 一致

Artifacts：
- final submission bundle
- `submission-notes.md`
- `environment-lock.md`
- final bundle manifest
- 使用 [templates.md](templates.md) 中的 submission checklist 模板

退出标准：
- 必需 deliverables 已齐备
- 复现说明可用
- 最终风险已记录
- 最终包和论文/报告指向同一套 accepted evidence

Recovery signals：
- 最终文件依赖未记录的本地状态
- submission bundle 和 paper 指向了不同结果
- 临门一脚打包时才暴露出上游 artifact 缺口

## 默认响应骨架

当这个 skill 被触发时，按下面格式响应：

```text
当前阶段:
阶段模式:
目标:
Source of truth:
Active baseline / evidence:
建议做法:
支持技能:
要产出的 artifact:
BRT gate:
- Behavior:
- Review:
- Test:
范围约束:
退出标准:
阶段决策:
下一步行动:
```

## 范围约束

这套 workflow 覆盖的是竞赛科研全流程。它不能替代领域专业知识，不能虚构结果，也不能把论文写作当成证据收集的替代品。
