# Briefbound Router Routing Practice

只在 Briefbound Router 无法从主文件稳定选择 owner 时读取。先检查本轮 Available skills；未出现的 skill 不能成为 owner，也不为普通任务临时安装。

## 仲裁顺序

1. 锁定可观察结果、对象、允许动作和成功证据。
2. 选择能直接产生下一结果的最具体 owner，而不是流程阶段名。
3. 只在 primary owner 缺少专属工具、知识或独立证据时增加一个 support skill。
4. `Next Output` 或 `Success Evidence` 仍含糊时，先查证；`LOW` 用一次集中讨论，`BLOCKED` 只问一个必要问题。

## 核心路由表

| 用户信号 | Primary owner | 默认重量 | 下一产出 |
|---|---|---|---|
| 修 bug、异常、失败测试有明确对象 | `briefbound-bug-review` | FAST/COMPACT | 根因状态、最小修复、验证 |
| 性能目标/回归或热路径测量 | `briefbound-performance-engineering` | PROFILE | baseline、瓶颈、before/after |
| 多职责巨型文件、结构妨碍导航/测试/协作，或明确要求职责拆分 | `briefbound-code-structure-guard` | FAST/COMPACT | STAY/CHECK/SPLIT 与最小结构修改 |
| 审 PR、diff、branch、commit、merge readiness | `briefbound-pr-review` | COMPACT | findings-first 审阅结论 |
| 源码学习、项目拆解 | `briefbound-project-dissection` | COMPACT | 教学报告与 diagram-design 配图 |
| 审整仓、架构、技术债、测试体系、接手摸底 | `briefbound-project-review` | COMPACT | 风险排序 findings 与执行队列 |
| 评价流程、方案、skill、输出质量，且无更具体 owner | `briefbound-router` | MICRO/COMPACT | 按需读取 evaluation 参考 |
| 新建或重定 UI/UX、信息层级、交互模型、响应式或无障碍决策 | `briefbound-ui-design` | FAST/COMPACT | 必要时先交付隔离预览，再形成可实施 UI 契约 |
| 品牌表达、视觉方向、字体、色彩、构图、图像或动效语言 | `briefbound-visual-design` | COMPACT | 必要时先交付隔离预览，再形成语境化视觉契约 |
| 架构、流程、时序、ER/UML、定量图表或 Mermaid/draw.io/Excalidraw 重绘 | `briefbound-diagram-design` | FAST/COMPACT | 可编辑 HTML/SVG、所需 PNG、保真说明与结构/视觉验收 |
| 已获 `APPROVED` 或有依据的 `PREVIEW_SKIPPED`，需要组件、状态、响应式和无障碍生产实现 | `briefbound-frontend-engineering` | FAST/COMPACT | 前端代码与浏览器运行证据 |
| 审查已有页面、隔离预览、截图、UI 流程、视觉回归、响应式或无障碍 | `briefbound-ui-review` | COMPACT | findings、预审建议与浏览器证据 |
| 跨组件 token、主题、variants、共享组件 API 或 Figma/code 一致性 | `briefbound-design-system` | COMPACT/FULL | 系统契约、渐进迁移与消费者证据 |
| 复杂功能存在实质性的外部复用决策 | `briefbound-feature-reuse-research` | COMPACT | 复用/借鉴/自建判断 |
| 目标已对齐且需要真实设计选择、迁移、跨边界契约或独立任务图 | `briefbound-planning` | COMPACT/FULL | 最小实施方案；必要时内含 TASK_GRAPH |
| 已明确的新行为/实现契约需要 RED，或用户明确要求 TDD | `briefbound-bdd-tdd-development` | COMPACT | 紧凑 RED/GREEN 实现 |
| AI/ML baseline、假设、消融、方向选择 | `briefbound-ai-research-loop` | COMPACT/FULL | 研究闭环或下一实验 |
| 单条 benchmark/score/baseline promotion lane | `briefbound-score-loop` | COMPACT/FULL | candidate 评估与晋升结论 |
| 重要研究 claim、反直觉结果、baseline 晋升审查 | `briefbound-research-rigor-review` | COMPACT | ACCEPT/QUALIFY/REJECT |
| 竞赛/benchmark 全生命周期 | `briefbound-ai-research-loop` | FULL | 按需读取竞赛阶段参考 |
| 用户明确需要持久目标、反复迭代和 stop condition，且无专项 owner | `briefbound-router` | COMPACT/FULL | runtime 中的目标循环 |
| 需求已对齐，多个现有同项目会话可通过平级协商互助完成各自任务并共同集成 | `briefbound-multi-agent-orchestration` | COMPACT/FULL | 协作 agreement、各自交付与集成验证 |
| 多会话进度、冲突、暂停恢复、讨论或合并 | `briefbound-thread-coordination` | COMPACT | registry 状态或协调闭环 |
| 用户/项目明确要求 memory、dashboard、跨会话恢复 | `briefbound-project-memory` | FAST/COMPACT | 持久 delta 或恢复上下文 |
| 已知存在临时产物、旧 branch/worktree/claim，或用户明确要求清理 | `briefbound-development-cleanup` | FAST/COMPACT | CLEAN/DEFERRED/BLOCKED |
| 当前 diff/PR 是否过度设计 | `briefbound-simplification-audit` | COMPACT | 可删与保留判断 |
| 整仓/子系统冗余复杂度与依赖膨胀 | `briefbound-simplification-audit` | COMPACT | 排序后的精简队列 |

系统或插件 skill 仅在本轮 Available skills 中真实存在且比 Briefbound fallback 更具体时使用，例如官方文档、浏览器、GitHub、PDF、表格或图像工具。候选安装资料属于 `github-skill-candidates.md`，不属于运行时路由表。

## 相邻边界

- PR/diff 正确性由 PR review 主责；只有目标明确指向删减时才叠加 simplification review。
- 普通功能仍由当前开发 owner 主责；代码结构守卫只在本轮目标文件出现职责膨胀证据时辅助，行数或“以后可能变大”不能单独抢占 owner。
- 明确要求拆分巨型文件时由代码结构守卫主责；整仓寻找大文件和技术债仍交 project review，当前 diff 的无效抽象仍交 simplification review。
- UI PR 仍由 PR review 主责；只有需要真实界面证据时才把 UI review 作为 support，不重复审查同一代码风险。
- 单页面或单组件问题不升级为 design system；只有共享事实源、多个消费者或迁移契约成为主要问题时才进入该 owner。
- UI design 决定任务、结构和交互；visual design 决定品牌与视觉表达。普通产品 UI 不因“更好看”自动加载两个 owner。
- 前端写入先按 `ui-preview-approval.md` 判定 `PREVIEW_REQUIRED / PREVIEW_SKIPPED`。新页面、布局/交互/视觉方向或跨组件 UI 结果尚未确认时必须先生成隔离网页；文案、明确小修或已批准设计可跳过。
- “设计并实现”由主要设计 owner 先交付预览并等待用户批准；收到 `APPROVED` 后继续落地和一次正式浏览器验收，不再串联 Frontend Engineering。只有方案单独交付、跨 owner handoff，或进入时已有批准证据才由 Frontend Engineering 主责。
- Design System 负责契约和代表性消费者，不把同一迁移机械拆给页面 owner；只有剩余页面形成独立交付边界时才切换。
- 具体 bug 交给 bug owner；整仓测试健康度和架构风险交给 project review。
- Bug Review 持有从根因到修复的完整闭环；必要 RED/GREEN 是其内部测试锚点，不再二次加载 TDD skill。TDD 只主责已明确的新行为或实现契约。
- planning 解决设计分叉，并仅在真实独立边界存在时内嵌 `TASK_GRAPH`；`NO_SPLIT` 不产生额外阶段。
- Briefbound Router 负责对齐后的有界会话发现；现有平级会话的持续协商和共同集成由 multi-agent orchestration 主责；单次建议、冲突或恢复只用 thread coordination。
- orchestration 不创建子 Agent、不接管任何会话任务；每个 Agent 保留 bug、UI、研究或测试专项 owner，没有双向正收益时各自继续。
- 实验 metric 未提升不是 TDD RED；确定性 harness/parser/schema bug 才进入工程 TDD。
- UI 文件的机械修改可用 `PREVIEW_SKIPPED` 留在 FAST_PATH；产品、交互或视觉结果未定时由 UI design/visual design 主责并先预览，结果已获 `APPROVED` 且主要工作是生产实现时由 frontend engineering 主责。
- 普通完成由当前 owner 收口；正式跨阶段证据包才进入 completion summary。

## 多动作推进

同一请求产生多个后续动作时：

- 按依赖、用户价值、误改风险和验证成本排序，不按严重度机械排序。
- `SAFE_DIRECT` 在已有执行许可下依次修复并验证，不完成一个就停下来询问。
- `PLAN_THEN_EXECUTE` 先形成必要方案，再自动回到执行。
- `DEFERRED` 只记录触发条件；`BLOCKED` 才停止并问一个问题。
- 只有用户必须选择顺序、范围或高风险动作时才展示选项。

## 路由失败信号

- 明确小改被升级为 planning、task graph、TDD、worktree、子代理或 completion summary。
- 只输出“建议进入某 skill”，却说不出下一产出和成功证据。
- 推荐候选宽泛，无法说明具体行为差异和错判成本。
- 需求 `LOW` 时只路由不对齐，或把本地可查问题抛给用户。
- 多个 `SAFE_DIRECT` 项只推荐一个，却没有依赖、权限或风险阻塞。
- 把发送 pause 当作已暂停，或 owner 在 `resumePendingAgentIds` 清零前结束。
- 把未安装 skill 当作唯一 owner，或为普通任务搜索/安装新 skill。
- 为同一子任务同时加载功能重叠的 review、TDD、debug 或 summary skill。
- 未先完成意图对齐和双向价值判断就建立协作，或把平级会话当作可派发 worker。
- 完成后无真实残留仍加载 cleanup，或有残留却只输出泛化提醒。

出现这些信号时回到 Briefbound Router 主文件，重新选择最具体 owner 和最低充分流程重量。
