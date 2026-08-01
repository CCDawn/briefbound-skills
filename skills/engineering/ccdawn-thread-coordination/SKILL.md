---
name: ccdawn-thread-coordination
description: "Use when existing independent Codex App threads in one project need peer advice, target/ACK validation, file or runtime-process ownership and shared data-root arbitration, conflict recovery, discussion, merge coordination, status exchange, or native-thread handoff without creating subagents."
license: MIT
---

# CCDawn Thread Coordination

## 目标

以 registry/thread 协调 scope、冲突和合并；Git 为事实源。

## BRT interface

- Context Boundary: 项目/thread/branch/worktree/scope/claim/coordination，以及共享 runtime 的 PID、listener、data root 和 owner。
- Output Contract: ownership、决定、验证、恢复债务。
- Allowed Action: 使用 `read_thread`、`send_message_to_thread`、只读进程探针与 `agent_coordination.py`；不停止未知 owner 进程，创建/归档或远程 Git 需授权。
- Success Evidence: registry revision、thread 回执、Git/测试及协调闭环。
- Stop Condition: thread 不明、owner 争议、暂停未确认、状态漂移或未授权。
- Route Out: 原 owner、`ccdawn-autonomous-collaboration-loop`、`ccdawn-multi-agent-orchestration`、`ccdawn-pr-review`、`ccdawn-development-cleanup`、`ccdawn-dawn-agent-html-memory`、`ccdawn-brt` 或 BLOCKED。

## 统一调用契约

- 只处理 BRT interface；不匹配时回具体 owner。
- 用户可见内容默认中文；只报产出、证据和风险；Route Out 仅以 BRT interface 为准；末行写 `下一步建议: <一个具体动作>`。

## 接入与所有权

`preflight` 传 `--write-kind development|mechanical|integration`：根 `main/master` 开发返回 `ISOLATION_REQUIRED`，集成需 claim + clean；其余按 `CLEAR/PEERS_NO_OVERLAP` 或 `OVERLAP` 分诊，只 claim 最小 scope。

owner 顺序：用户指定 > 有效 claim/registry > 更早 owner。非 owner 停止自身冲突写入，不要求既有 owner 暂停；争议面只读。

文件/集成 owner 分开。`MERGE_READY` 时读 `references/integration-ownership.md`，按 claim 认领或退回交付者。

共享进程、listener 或 data root 冲突时，读取 `references/proactive-collaboration.md` 的“运行进程归属”；端口不同不等于数据隔离。确认 owner 后，运行中仲裁仍由本 skill 负责，已知本任务进程的安全停止与释放转 `ccdawn-development-cleanup`。

## 主动协作

消息投递或协作时读 `references/proactive-collaboration.md`，不转移 owner。

skill 只提供协调原语。持续互助交 `ccdawn-multi-agent-orchestration`；自动闭环由 `ccdawn-autonomous-collaboration-loop` 驱动并继承恢复债务。不得建立主从关系。

新会话有收益才询问是否创建；未授权不创建，也不停止当前工作。

## 冲突恢复

Silent Conflict Triage 核验 claim、真实写入和替代工作；优先 `SELF_NARROWED / CONTINUE_NON_CONFLICTING / WAIT_SILENTLY`。

需共同决定时为 `DISCUSSION_REQUIRED`：复用 open coordination，否则发送含双方身份、原任务和 `Reply To` 的 `DISCUSSION_REQUEST`。各方回复 position；Coordination Owner 汇总 proposal，ACK 回复其 thread；收齐后 `resolve` 并广播 final，final 不索要回复。期间继续各自安全工作。

继续执行会立即覆盖/回归、无法拆分且协商不能避免时才为 `PAUSE_REQUIRED`：升级 conflict，发送一次 `CONFLICT_PAUSE_REQUEST`。`PAUSE_REQUEST` 不等于 `PAUSED`，确认前不写冲突面。

修复后 `resolve` 并主动发送 `CONFLICT_RESOLVED`；对方重读状态，`resume` 后回复 `RESUMED`。不要随后调用 registry `respond --status RESUMED`。

三门禁：`Target Validity Gate` 与 `ACK Gate` 读主动协作参考；`Coordination Closeout Gate` 读集成责任参考。失败不发、不接管或不关闭。

`main` 推进、合入排队或 gate 可能 stale 不属于 `PAUSE_REQUIRED`。Peer 完成聚焦验证并返回 `MERGE_READY`，由有效 integration claim 的 owner 串行应用交付；不要求 peer 等稳定窗口或重复 full gate。只有集成失败需要其独有判断时才唤醒原 owner。

pause 产生 `resumePendingAgentIds`；债务清零才能 `complete`：

- `open` 默认 30 分钟租约；跨 checkpoint 用 `heartbeat`，不高频轮询。
- `status` 标记 `owner-stale`；注册 Agent 用 `takeover` 并继承恢复义务。健康 owner 仅由用户改派。
- 任务明确取消/归档才可 `cancel-resume --confirmed-by-user`；无回复不等于取消，不得自行设置确认标记。

## 讨论与合并

讨论优先于暂停；同一 participants + surface 存在则复用，不重复发送。

各 Agent 返回 `MERGE_READY`（branch/base/head/scopes/dependency/tests/risks）。Integration Owner 用 Git 重验；无重叠成组，共享面串行，全部进入目标分支后只跑一次完整 gate。失败通知责任方，成功广播并释放 integration claim、关闭关联 merge coordination。standalone 不自动 push、发布或清理。

条件合入快线及失败分类读取 `references/integration-ownership.md`。

影响未来行动的决定才执行 `sync_project_memory.py --coordination-id <id>`；普通并行会话不写 tracked memory。

## 完成

未收到 `PAUSED` 为 BLOCKED；已修复未恢复为 PARTIAL；送达未恢复为 `DELIVERED_AWAITING_RESUME`。`RESUMED` 后闭环；merge 需目标分支含提交且验证通过。
