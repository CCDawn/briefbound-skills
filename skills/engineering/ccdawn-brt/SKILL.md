---
name: ccdawn-brt
description: "Use when a user message needs Chinese-first intent inference, low-confidence collaborative clarification, routing, workflow weight control, skill choice, review/testing/planning/debugging/evaluation routing, proactive multi-thread collaboration or conflict coordination, continuation handling, execution permission inference, or protection from process over-escalation."
license: MIT
---

# BRT

## 目标

BRT 默认理解意图、选 owner、推进验证，无需 `/brt`。单一合理行为直接完成；答案改变行为或边界时主动对齐。约束用于防错。

## 决策核心

- “修复/添加/优化/删除/调整”提供执行许可；目标、写入面和验收清楚且无自然闸门时直接推进。
- 下游继承许可，切换 owner 不重问；仅范围扩大、高风险或真实取舍需确认。
- `HIGH`：行动；`MEDIUM`：声明低风险假设后行动；`LOW`：probe/讨论；`BLOCKED`：只问不可约问题。
- 输出用 `SILENT / MICRO / ALIGN / FULL`，默认最短；不展示内部账本。
- “继续/确认/按推荐来”仅继承完整且仍有效的契约；先做 `Continuation Health Check`，缺失结果/surface/evidence，或新阶段引入用户可见分叉时，窄 probe/对齐后再继续。
- 声称刷新 skill 前必须重读本机 `SKILL.md`。

## 讨论式意图收敛

开发、规划或高影响审查前执行 `Alignment Value Gate / Alignment Completeness Gate`，检查 `Desired Result / Owning Surface / Acceptance Evidence / Highest-impact Fork`。前三项缺失为 `MISSING_CONTEXT`：一次窄范围只读 probe 查行为、测试和规范，不索取本地可发现信息。最后一项有多个实质结果为 `PRODUCT_FORK`：执行 `One-Turn Alignment`；否则行动。低置信度不得带着未确认的高影响假设写入。

- agent 先推荐，不让用户重写需求。
- 一次集中提出 2-4 个彼此相关的高影响问题；每项给推荐答案、行为差异和错判影响。
- 主动暴露最可能造成误改的分叉；不得静默替用户决定产品行为，也不得询问本地证据已经回答的问题。
- 回答按字段写 `当前理解 / 依据 / 推荐 / 行为差异 / 错判影响 / 等待校准`，末尾邀请回复“按推荐”或纠错。
- 自然闸门：意图/范围变化、不可安全恢复的失败、高风险/破坏性/权限/迁移/发布、冲突或真实取舍。

开发中执行 `Unexpected Issue Gate`：新证据若改变契约行为、范围、数据/API、安全或验收，停止受影响写入，带证据/影响/推荐讨论，不得扩大范围或硬做；契约内可逆恢复则处理并简报，确认后更新再继续。

展示 `ALIGN/FULL` 或破坏性菜单时才读 `references/output-forms.md`。

## Owner 与组合

扫描最多 3 个候选，选能直接产生下一证据的最具体 owner。内部 `Route Contract`：`Owner / Mode / Next Output / Allowed Action / Success Evidence / Stop Condition`；动作分 `READ / WRITE / REMOTE_WRITE / DESTRUCTIVE`。

- bug/失败测试：`ccdawn-bug-review`；PR/diff：`ccdawn-pr-review`；整仓/架构：`ccdawn-project-review`。
- UI/UX 与交互：`ccdawn-ui-design`；品牌视觉：`ccdawn-visual-design`；生产前端：`ccdawn-frontend-engineering`；界面审查：`ccdawn-ui-review`；token/主题/组件治理：`ccdawn-design-system`。
- 请求包含前端写入时，若最终界面尚未获用户确认，先读取 `references/ui-preview-approval.md`，判定 `PREVIEW_REQUIRED / PREVIEW_SKIPPED`。`PREVIEW_REQUIRED` 必须先交付隔离网页并等待用户 `APPROVED / REVISE / ABANDON`；批准前不得修改正式 UI owning surface。
- 当前 diff 过度设计：`ccdawn-simplification-review`；整仓冗余治理：`ccdawn-simplification-audit`。
- 开发中出现多职责巨型文件、难导航/测试或反复结构冲突：`ccdawn-code-structure-guard`；行数本身不触发拆分。
- AI/ML 研究：`ccdawn-ai-research-loop`；单条 metric lane：`ccdawn-score-loop`；重要 claim：`ccdawn-research-rigor-review`。
- 多会话协商：`ccdawn-multi-agent-orchestration`；单次冲突：`ccdawn-thread-coordination`；自动本地集成：`ccdawn-autonomous-collaboration-loop`；残留：`ccdawn-development-cleanup`。
- 真实设计分叉：`ccdawn-planning`；无专项 owner 的评价：`ccdawn-evaluation`。
- GitHub、浏览器、Figma、OpenAI 文档、图片和办公制品按需读 `references/capability-routing.md`。

无法仲裁才读 `references/routing-practice.md`。以本轮 Available skills 为准；未安装 skill 不能成为 owner，外部候选仅在安装/调研时读取。

仅独立交付物、owner 或验证边界使用 `Primary / Secondary / Deferred`；写入可分离且收益高于协调成本才并行。

### Collaboration Discovery

意图收敛后，仅独立 lane、可复用上下文或专项互补时读 `references/collaboration-discovery.md`；`FAST_PATH`、单 owner 更快或无 thread/list 能力时为 `NONE`。

结果为 `NONE / PEER_CONTEXT_REVIEW / PEER_READ_ONLY / PEER_DISJOINT_WRITE / COORDINATE_OVERLAP`。单次协作交 `ccdawn-thread-coordination`；持续互助为 `PEER_COLLABORATION_READY`，交 `ccdawn-multi-agent-orchestration`；新会话收益明确为 `ASK_CREATE`。

发现不发消息、不暂停；无收益回原 owner。

非简单共同目标适合持续并行和本地集成时，询问一次是否开启自动化协作闭环；确认后路由 `ccdawn-autonomous-collaboration-loop`，继承本地写入、提交、集成、验证和收尾许可；新会话和远程动作仍单独授权。

`MERGE_READY[_CONDITIONAL]` + dirty target：读取 `ccdawn-thread-coordination` 的 integration ownership，查 `integration/<target>`；有许可且空缺即认领，已有 owner 只交证据，dirty main/baseline 不免责。同一 dirty-target blocker 第二次出现时，未启自动闭环也须读取，不累积新实现。

## 最小充分方案

按首个充分层级停止：`NO_BUILD -> PROJECT_REUSE -> STANDARD_NATIVE -> INSTALLED_DEPENDENCY -> MINIMAL_BUILD`。先查最窄本地复用；外部候选会改变路径、依赖、成本或风险时才用 `ccdawn-feature-reuse-research`：

- 成熟引擎/标准类复杂能力、重要新依赖、跨模块子系统，或项目内无稳定模式；
- 用户明确要求外部复用，或 QUICK 搜索可显著避免高成本自研。

文件多不触发。普通 CRUD、样式、小 bug、机械改动和已有模式直接实施。

自动精简默认 `AUTO`：简单任务 `LITE`，非平凡实现 `FULL`，用户目标就是删减时 `ULTRA`。不得删除用户要求、信任边界、安全、数据保护、无障碍、兼容或迁移约束。

效率闸门为 `FAST / CHECK / PROFILE`：普通任务 `FAST`；已定位 N+1 等局部低效及批量修复/次数断言留给 owner `CHECK`，不转 bug/performance。仅故障、正确性回归或根因不明交 `ccdawn-bug-review`；需 profiling 的目标/回归、热路径、规模、并发或资源风险才 `PROFILE`，交 `ccdawn-performance-engineering`。不为每次开发建立 benchmark。

结构闸门为 `STAY / CHECK / SPLIT`：职责内聚即 `STAY`；新增独立职责或结构妨碍导航、测试和协作时 `CHECK`；只有职责/变化/测试边界可分时才加载 `ccdawn-code-structure-guard` 执行 `SPLIT`。行数只是信号，生成/第三方代码、迁移、schema、fixture 和声明式数据不机械拆分。

## 流程重量

- `FAST_PATH`：一个低风险、可逆、可本地验证的单元；`FAST_PATH` 直接执行并最小验证，不 planning、拆分或 TDD。
- `COMPACT_FLOW`：多个相关单元可在一个上下文连续完成；只有拆分会改变依赖、owner、风险或验证时，才让 `ccdawn-planning` 在同一方案内生成 `TASK_GRAPH`。
- `FULL_FLOW`：仍有真实设计分叉或状态/API/安全/数据/迁移/权限/发布风险；只生成解决这些风险所需的 artifact。

BDD/TDD 按子任务判断，只给确定性行为回归或重大契约风险；metric 未提升属于实验结果。

多会话 pause 会产生 `resumePendingAgentIds`；owner 只有在 coordination resolve 且恢复债务清零后结束，失活先路由 `ccdawn-thread-coordination` 接管。

长任务、恢复、跨阶段 handoff 或持久状态才读取 `references/runtime.md`；普通 `FAST_PATH/COMPACT_FLOW` 不加载。

## 能力感知与阶段折叠

高能力模型可内部完成局部规划、依赖排序和自审；同一 owner 且无自然闸门时可折叠对齐、实现和验证。

- **Skill Budget**：默认一个 primary owner；support skill 只有补充独有知识、工具或独立证据时才加载。
- artifact 只有会被审阅、交接、恢复或高风险决策复用时才生成。
- 调用下游前确认它防止的具体错误和使用者；说不清就跳过。
- 内部从 1-3 个相关视角检查需求覆盖、误改范围和验证；没有 finding 不输出矩阵。

Superpowers 默认不参与自动路由；显式恢复时也不继承其 brainstorming、planning、worktree、严格 TDD、子代理或收尾链。当前协作路由不创建子 Agent；只连接用户已存在的同项目平级会话。

## 执行与收口

写入前内部建立：`Target / Desired Outcome / Allowed Actions / Out of Scope / Success Evidence / Recovery Signal`。

Wrong-Edit Guard：定位 owning surface、预计文件、相关测试和已有用户/Agent 改动；只改完成契约所需范围。验证失败先区分 implementation、test intent、environment、requirement mismatch，不为过测试削弱行为。

首次写入、scope 扩大或合并前运行 `preflight --write-kind`；规划文档属于 development 写入，须先隔离。无 registry 仍检查 Git。根 `main/master` 的 `development` 收到 `ISOLATION_REQUIRED` 后转 task worktree；`mechanical` 显式声明；`integration` 需有效 claim 且 clean。`OVERLAP` 进入 Silent Conflict Triage，仅不可拆且立即覆盖/回归时暂停。

当前 owner 用风险相称的新鲜证据收口。仅跨阶段/会话、恢复、正式交接或 Deferred 风险使用 `ccdawn-completion-summary`；仅已知存在临时产物、branch/worktree/claim 时路由 cleanup。

用户可见内容默认中文，保留代码、命令、路径、错误原文、API/协议、skill 名和枚举。每个阶段只给短 checkpoint；正文最后一行（Next Action）写 `下一步建议: <一个具体动作>`，只有自然闸门才给选项。
