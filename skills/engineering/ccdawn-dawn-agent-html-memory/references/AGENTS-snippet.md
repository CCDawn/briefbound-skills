# Project Memory Rules

仅在用户或仓库维护者明确选择项目 memory 后，才把下面的 block 加入目标仓库 `AGENTS.md`。它让 agent 在确有跨会话价值时使用 memory，不要求每个任务读写或创建 claim。

```md
## Project Memory Rules

- `.docs/project-memory/` 是跨会话项目状态的辅助事实面；只在其内容会改变当前判断，或需要持久化决策、blocker、handoff 时读取或更新。
- 读取时先看 `.docs/project-memory/INDEX.md` 和当前职责相关 lane；不要默认加载全部历史。
- 普通单会话实现、机械小改、简单问答和一次性审查不要求 memory sync。
- 首次写入前运行 `agent_coordination.py <project-root> preflight --write-kind <development|mechanical|integration>`；根 `main/master` 普通开发必须进入 task worktree，集成必须持有对应 claim 且目标 clean。出现第二个 Agent 或 registry 已存在时再注册任务并维护 scope。
- LIVE registry 位于 Git common dir 或本机 Codex coordination 目录，不进入 Git；`.docs/project-memory` 只保存已确认决策、里程碑、blocker 和合并结果。
- claim 保持最小 scope。暂停时让出 claim，恢复时重新检查；并行期间只有协调者将确定内容同步到项目 memory，避免多个 worktree 同时改记忆文件。
- 更新只记录 durable delta：已验证状态、关键决策、blocker、跨会话技术事实和正式下一步；不要写完整对话或过程旁白。
- 写入后运行 `sync_project_memory.py` 或 `render_overview.py`，并验证 lane、`INDEX.md`、`overview.html` 和 `PROJECT_MEMORY.html` 一致。
- 不存在 `.docs/project-memory/` 时不要自动初始化，除非用户明确授权或项目规则要求。
```
