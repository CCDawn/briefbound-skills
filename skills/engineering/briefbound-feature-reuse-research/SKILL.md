---
name: briefbound-feature-reuse-research
description: Use when a complex feature has an unresolved reuse decision and external projects, libraries, standards, examples, or in-project modules could materially change architecture, dependencies, scope, or implementation; do not use for routine work already covered by local patterns or standard platform capabilities.
license: MIT
---

# Briefbound Feature Reuse Research

## 目标

复杂功能在方案制定中遇到外部复用取舍时，做只读复用研究：搜索相关项目、库、模块、官方示例和成熟实现，评估是否值得复用、改造、只参考，或自研。

本 skill 不写代码、不安装依赖、不复制外部代码进项目；输出可交给 `briefbound-planning` 的复用决策。

## Briefbound task contract

- Context Boundary: 用户目标、当前项目可复用点、网络/本地搜索范围、排除范围、许可证和依赖边界。
- Output Contract: 搜索范围、候选评估、复用决策、Implementation Boundary、Verification Strategy 和 planning handoff。
- Allowed Action: 只读搜索和只读本地代码/文档检查；不安装依赖、不运行外部代码、不复制外部代码、不扩大用户未确认范围。
- Success Evidence: 当前项目复用点已查，候选有链接或本地证据，许可证/集成风险已判断，复用决策能作为 `briefbound-planning` 输入。
- Stop Condition: 研究产出复用决策即止；无法搜索、许可证不明、需求不清或复用会改变用户未确认范围时停止；试用/安装/复制外部代码移交原开发 owner 或按授权继续。
- Route Out: 原开发 owner、`briefbound-planning`、继续复用研究、`briefbound-router` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文，完成只报状态、产出、证据和剩余风险；代码、命令、路径、错误原文、API/协议、skill 名和枚举保留原样；Route Out 仅以 Briefbound task contract 为准，末行 `下一步建议: <一个具体动作>`，限于决策类建议，不交回可自行执行的步骤。

## 进入条件

使用前确认：

- 用户目标是新增功能、模块、能力、工作流、复杂 UI、集成、解析器、编辑器、搜索、可视化、导入导出、算法或可复用子系统；
- 功能复杂度足以影响方案选择，且外部生态可能已有成熟实现；
- 搜索结果会改变实现路径、依赖选择、风险、成本或验证方式；
- 允许联网搜索。若当前不能联网，说明限制，并用本地已有依赖、文档和代码做降级研究。

至少需要一个强信号：成熟领域引擎/协议/标准、重要新依赖、跨模块子系统、项目内无稳定模式、用户明确要求外部复用，或 QUICK 搜索可显著避免高成本自研。文件数量和“网上可能有项目”不算强信号。

不使用本 skill：

- 单点小改、样式调整、普通 bug 修复、机械重构；
- 用户明确要求从零实现；
- 功能高度私有，外部实现没有可比价值；
- 复用只会增加依赖、许可证、维护或集成负担。

## 研究范围

按功能类型选择 2-4 类来源，不要盲目铺开：

- 官方文档和官方示例：框架、SDK、协议、浏览器/API、平台能力。
- 包管理器生态：npm、PyPI、Cargo、Go modules、Maven、NuGet 等。
- GitHub 项目：相似产品、组件库、插件、参考实现、算法实现。
- 当前项目内复用：已有模块、工具函数、设计系统、服务接口、测试 helper。
- 标准/论文/规范：协议、格式、算法、互操作行为。

优先级：

1. 当前项目已有可复用模块；
2. 官方推荐库或官方示例；
3. 活跃、许可证清晰、测试充分的成熟库；
4. 可参考的开源项目设计；
5. 自研。

默认先 `QUICK`：检查项目内复用点，再查看 2-4 个最相关的官方来源、成熟库或 GitHub 项目；决策已稳定就停止，不为凑候选扩大搜索。只有许可证、架构适配或关键能力仍无法判断时才进入 `DEEP`。

## 候选筛选

每个候选必须有明确价值，不凑数。最多保留 3-5 个候选。

候选字段：

- Name / Link：名称和来源链接；
- Capability Fit：覆盖目标功能的哪些部分；
- License：许可证是否允许当前项目使用；
- Activity：维护活跃度、近期提交、issue 状态、发布频率；
- Integration Cost：接入成本、依赖体积、框架/语言/运行时兼容；
- Adaptation Cost：需要改造的程度；
- Testability：是否容易写测试和验证；
- Project Fit：是否符合当前架构、代码风格、依赖边界和长期维护能力；
- Risk：供应链、弃维护、过度依赖、API 不稳定、性能或可扩展性风险。

如果找不到有价值候选，也要输出 `BUILD_IN_HOUSE`，并说明搜索证据和自研边界。

## 决策规则

输出一个主决策：

- `REUSE`：直接引入库或模块，适合成熟、低集成成本、许可证清晰、测试充分。
- `ADAPT`：借用模块或局部实现思路，需要包装、裁剪或适配当前架构。
- `REFERENCE_ONLY`：只参考设计、API、数据结构、交互或测试思路，不引入依赖。
- `BUILD_IN_HOUSE`：自研，原因可能是需求特殊、候选不活跃、许可证不合适、集成成本高或依赖风险大。
- `BLOCKED`：无法搜索、许可证不明、需求不清或必须用户选择。

评估权重：

- 用户目标贴合度 > 当前项目适配度 > 维护活跃度 > 可测试性 > 集成成本 > 依赖体积。
- 不因为“有现成库”就默认复用；复用必须降低总体成本或风险。
- 不因为“能自研”就跳过研究；复杂常见功能必须解释为什么不复用。

## 输出契约

```text
复用研究:
- 目标功能:
- 搜索范围:
- 当前项目已有复用点:
- 结论: REUSE / ADAPT / REFERENCE_ONLY / BUILD_IN_HOUSE / BLOCKED
- 推荐原因:

候选评估:
- 候选: 名称 / 链接
  - Fit:
  - License:
  - Activity:
  - Integration Cost:
  - Adaptation Cost:
  - Testability:
  - Project Fit:
  - Risk:
  - Verdict: keep / reject；原因...

复用决策:
- Decision:
- Dependency Impact:
- Implementation Boundary:
- Verification Strategy:
- Rejected Alternatives:
- Planning Handoff: 进入 briefbound-planning 时必须携带的复用决策、依赖边界、验证策略和 rejected alternatives

下一步:
默认路由：<从 Briefbound task contract 的 Route Out 选择一个>，原因...
执行规则：复用决策与实现边界清楚、且不超出当前授权范围时，携带决策与证据回原开发 owner 直接实施；仅当决策会引入需要用户裁决的依赖/架构取舍、迁移风险或超出授权的用户可见影响时，先做一轮协作校准（说明推荐、排除项、取舍），需要执行契约时才进入 `briefbound-planning`。
```

## 质量门槛

- 必须给链接或本地证据；不能写“可能有库”“应该可以参考”。
- 必须说明被拒绝候选为什么不适合。
- 许可证不清时不能推荐 `REUSE`。
- 未检查当前项目已有模块时，不能推荐外部依赖。
- 不安装、不运行、不复制外部代码；需要试用库时移交原开发 owner，需要执行契约时才进入 `briefbound-planning`。
- 搜索耗时大时先做 QUICK 研究，再建议是否继续 DEEP。
- 进入原开发 owner 或 `briefbound-planning` 前，必须把 `复用决策` 作为输入，不重复研究。
- 协作校准与进入 `briefbound-planning` 的触发条件，以执行规则为准。
