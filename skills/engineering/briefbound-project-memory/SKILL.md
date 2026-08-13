---
name: briefbound-project-memory
description: Use when the user or project rules explicitly request project-local memory/dashboard initialization or updates, or when an existing `.docs/project-memory/` is needed for cross-session recovery, durable decisions, blockers, parallel-agent coordination, or formal handoff; do not auto-initialize or sync it for ordinary development.
license: MIT
---

# Briefbound Project Memory

## 目标

按需维护 `.docs/project-memory/` 和 HTML 总览，并为同项目 Agent 提供不入 Git 的 live coordination registry。memory 只保存会改变未来行动的事实；普通开发不自动初始化、同步或渲染。

## Briefbound task contract

- Context Boundary: 目标仓库、现有 memory、live registry、项目规则和需持久化的事实。
- Output Contract: READ/INIT/SYNC 结果、持久 delta、渲染/registry 验证和 Route Out。
- Allowed Action: 只操作 memory/dashboard 与协调工具；不修改业务代码或伪造 claim、进度和验证。
- Success Evidence: 来源可追溯，delta 写入正确 lane，索引/HTML/registry 一致且不覆盖并行改动。
- Stop Condition: 用户/规则未要求、事实源不明、ownership 冲突、脚本缺失、渲染失败或写入会覆盖他人状态。
- Route Out: 原任务 owner、`briefbound-autonomous-collaboration-loop`、`briefbound-thread-coordination`、`briefbound-completion-summary`、`briefbound-router` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文；保留技术字面量；只报产出、证据与风险；Route Out 仅以 Briefbound task contract 为准，末行写 `下一步建议: <一个具体动作>`。

## 激活与模式

仅在以下任一成立时使用：用户/项目规则明确要求；已有 memory 是恢复所需事实源；跨会话决定/blocker/handoff 必须持久化；真实多 Agent 协作需要 registry。

- `READ`：只读 `INDEX.md`、`profile.json` 和会改变判断的 lane，不加载全部历史。
- `INIT`：用户/规则要求且目录不存在时初始化。
- `SYNC`：只写本轮 durable delta，不记录完整对话、旁白或普通测试日志。

现有 `.docs/project-memory` 存在时先读规则和索引；无目录且未触发 INIT 时直接返回原 owner。

Memory 不接管执行循环。自动闭环由 `briefbound-autonomous-collaboration-loop` 持有，memory 只提供可恢复状态载体；当前动作和短期续接留在 Briefbound runtime。只有已确认决定、跨会话 blocker、正式 handoff 或会改变未来行动的验证结论才写入，不为每个 task、测试或 checkpoint 重写并渲染。

## 事实与结构

- 代码/Git/运行结果是实现事实源；memory 是恢复与决策投影，不能覆盖源事实。
- `lanes/*.json` 按稳定职责保存状态、决定、问题和 next step；`memory.json` 只保留全局事实。
- `INDEX.md` 与 `overview.html` 是投影，不作为 claim 或运行状态权威。
- 绝对 worktree、thread id、secret 和敏感日志不进入 tracked dashboard。

首次初始化才读取 `references/setup.md`，运行 `init_project_memory.py`。已有结构使用 `sync_project_memory.py`、`capture_note.py` 和 `render_overview.py`；参数以脚本 `--help` 为准。`capture_note.py` 仅保存仍需调查的高价值线索。

## 并行协作

存在真实并行或 registry 已存在时使用 `agent_coordination.py <project-root> status/join/update/claim/open/respond/resolve/pause/resume/complete`。

live registry 位于 `<git-common-dir>/briefbound/coordination/registry.json`；非 Git 项目回退 `~/.codex/project-coordination/<project-id>/registry.json`。它跨 worktree 共享、不入 Git，并使用文件锁、revision 和原子替换。

只 claim 最小 scope。pause 让出 claim，resolve 形成 `resumePendingAgentIds`；owner 失活由 `takeover` 接管，恢复重查重叠，明确取消/归档才可 `cancel-resume --confirmed-by-user`。open coordination 或恢复债务阻止 complete。`agent_work_guard.py` 仅为兼容入口。

并行 worker 不直接同步 tracked memory；coordinator 在决定解决后写一次：

```powershell
py -3 <skill-root>\scripts\sync_project_memory.py <project-root> --lane <lane> --coordination-id <id>
```

## 验证

写入后确认：durable delta 位于正确 lane；`INDEX.md` 计数/链接一致；HTML 可打开且已脱敏；无关 lane、历史和并行改动未覆盖。结构/渲染异常才读 `references/troubleshooting.md`，用户要求视觉调整才读 `references/html-design.md`。

事实不足或工具缺失时报告 BLOCKED，不手改 JSON/HTML 伪造状态。
