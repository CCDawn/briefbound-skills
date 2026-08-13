# Briefbound Router Long-Task Runtime

只用于跨会话恢复、跨 owner/stage、真实 blocker、长任务 handoff 或必须持久化的 Deferred 风险。普通 FAST_PATH 和单上下文 COMPACT_FLOW 不读取、不建账本。

## 最小状态

```text
Current Stage: ALIGNING / PLANNING / EXECUTING / VERIFYING / BLOCKED / COMPLETED
Intent: 可观察结果
Owner: 当前最具体 owner
Active Item: 当前推进单元
Decisions: 只记会影响后续行动的决定
Evidence: 最新验证
Deferred/Risks: 未决项及触发条件
Next Action: 下一可执行动作
```

这是当前任务的对话内临时状态，不自动写文件、Memory 或 dashboard。只在 handoff、恢复、blocker、风险决策或证据可能丢失时更新；不要保存完整对话、命令日志、内部推理或每个小步骤。确需跨会话持久化时，把最小 durable delta 交给 Project Memory，不复制两份账本。

## 持续推进

- 用户已授权实现/修复/优化时，相关步骤默认连续执行；完成一个 task 不构成用户闸门。
- `继续/确认/按推荐` 从 `Active Item` 续接，不重读无关文件，不重开对齐或规划。
- 仅在意图变化、范围扩大、不可安全恢复的失败、权限/破坏性/迁移/发布动作、跨 owner 冲突或真实取舍时暂停。
- 状态汇报只给新结果、证据、风险和下一动作，不复述全部历史。

## 计划与任务

只有方案会被审阅、交接或防止真实设计错误时进入 planning。只有独立交付物、owner、依赖 artifact、风险 gate、并行 lane 或不同验证契约存在时拆分。

```text
Task: 可观察产出
Boundary: owning files/surface
Dependency: 无或前置 artifact
Mode: SIMPLE / BDD_TDD / EXPERIMENT
Verification: 完成证据
Stop: 自然闸门
```

同机制机械修改合并为一个单元。测试、文档和配置并入其服务的功能任务。实验 lane 由 score/research owner 管理，不切成 RED/GREEN 小任务。

## 执行循环

每个实现单元内部完成：

1. 重验 owning surface、保护边界和现有改动。
2. 实现当前最小结果，不扩 scope。
3. 运行风险相称的最窄有效验证。
4. 对比 expected/actual，分类失败来源。
5. 契约内可恢复就修复并重验；否则进入自然闸门。
6. 当前项通过后自动进入下一个已授权项。

BDD/TDD 只用于预期行为确定且回归风险显著的子任务。已知失败测试可作为 RED；普通配置、样式、机械迁移或实验结果只需适当验证。

## 多会话与接管

跨会话状态以 live coordination registry 为准，代码/Git 为实现事实源。共享写入前确认 claim；冲突遵循 `briefbound-thread-coordination`。

- pause 必须有 `PAUSED` 回执并产生恢复债务。
- coordination owner 跨 checkpoint 时 heartbeat。
- owner stale/退出后由注册 Agent takeover，继承修复和恢复义务。
- resolve 后主动通知 paused Agent；`resumePendingAgentIds` 清零才闭环。
- 没有真实并行时不创建 worktree、claim 或 coordination。

## 验证与完成

证据必须与声明匹配：测试通过需最新命令和结果；UI 行为需运行时/浏览器证据；merge readiness 需 diff/PR 与 checks；实验提升需 baseline/candidate/protocol 一致。

当前 owner 可以完成 FAST_PATH 或有界 COMPACT_FLOW，条件是：

- 意图和 critical work 已满足；
- 新鲜验证通过；
- 无 unresolved blocker 或未披露副作用；
- 未越过保护边界；
- 已知产生的临时产物或 Git/claim 生命周期已处理，或集成前明确 `DEFERRED_INTEGRATION`；没有已知候选不运行专项清理。

只有跨阶段综合、恢复、正式交接或持久风险才使用 `briefbound-completion-summary`。PR/diff 的 `MERGE_READY` 由 `briefbound-pr-review` 判断。集成后不得继续用 `DEFERRED_INTEGRATION` 收口。

## 阻塞输出

```text
BLOCKED
- 原因与受影响项
- 已保留现场/证据
- 可行恢复路径
- 需要用户提供的一个不可约输入（如有）
```

难、慢或验证失败本身不是 BLOCKED；仍能在当前契约内安全推进时继续。
