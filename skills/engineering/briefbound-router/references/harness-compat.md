# Harness 能力矩阵与降级

Briefbound 技能包运行在多种 agent 运行环境（Codex App、Codex CLI、ZCode、Claude Code、Cursor、Grok Build、Gemini CLI、OpenCode 等）。加载协作族技能或写入隔离规则前，先按本文件探测当前环境能力；缺失能力按表降级，不模拟协议、不发明工具名。

## 能力分级

- `C1 基础执行`：文件读写、命令执行、Git。所有 harness 默认具备；本包全部技能以 C1 为底线。
- `C2 skill 发现`：SKILL.md 目录（agentskills.io 开放格式）。由安装器装入各 harness 的 skills 目录后具备。
- `C3 子代理派发`：runtime 提供任务委派工具（如 ZCode Agent、Claude Code subagent）。只决定独立可并行工作能否派发；与平级会话协作无关，子代理不是平级会话。
- `C4 平级多会话`：同项目独立会话枚举与定向消息（如 Codex App 的 `list_threads`/`read_thread`/`send_message_to_thread`）。BRT relay 协议族（`BRT_TRUSTED_RELAY_V1`、outbox、`resumePendingAgentIds`）只在 C4 成立时生效。
- `C5 协调 registry`：`agent_coordination.py` + `briefbound/coordination/registry.json`（claim、租约、恢复债务）。需要真实多会话并行才成立。

## 判定方法

- 以本轮实际可用的工具与会话能力为准，探测一次即可，不在每个动作前重复怀疑。
- 下表只是安装参考；当前环境工具列表与表格冲突时，以工具列表为准。
- 不发明工具名；缺失即降级，不尝试用别的工具冒充原语。

## 降级规则

| 缺失能力 | 降级行为 |
| --- | --- |
| `C4` | `briefbound-thread-coordination`、`briefbound-multi-agent-orchestration`、`briefbound-autonomous-collaboration-loop` 不进入协议流程；冲突处理降级为当前 owner 单会话串行：先缩小 scope、调整顺序，共享文件在最后写入前重新拉取；不模拟 relay、outbox、接管或恢复债务。 |
| `C5` | 不使用 `agent_coordination.py`；ownership、隔离与合并判定用 Git 等价证据（分支归属、worktree 列表、clean 状态、merge-base 吸收证明）。 |
| `preflight --write-kind` | 以等价 Git 检查替代：根 `main/master` 上的 development 写入仍必须先建 task worktree；integration 仍要求目标 clean 且交付已验证。 |
| `C3` | 独立可并行工作由当前 agent 串行完成，顺序按依赖；不为并行而并行。 |

## 各 harness 安装速览

安装目标与激活块注入由 `scripts/install_codex_library.py` 的 `--agent` 参数决定：

| harness | skills 目录 | 激活块指令文件 |
| --- | --- | --- |
| Codex CLI/App | `~/.codex/skills` | `~/.codex/AGENTS.md` |
| Grok Build | `~/.grok/skills` | `~/.grok/AGENTS.md` |
| Claude Code | `~/.claude/skills` | `~/.claude/CLAUDE.md` |
| ZCode | `~/.zcode/skills`（项目级 `.agents/skills` 亦可） | `~/.zcode/AGENTS.md`（项目级 `AGENTS.md`） |
| Cursor | `~/.cursor/skills` | 项目级 `AGENTS.md`（手动放置） |
| Gemini CLI | `~/.gemini/skills` | `~/.gemini/GEMINI.md` |
| OpenCode | `~/.config/opencode/skills` | `~/.config/opencode/AGENTS.md` |

能力现状（以本机实测为准）：Codex App 具备 `C4`/`C5` 全量；其余 harness 一般只具备 `C1`–`C3`（部分提供子代理）。在这些环境中协作族技能按上表降级，Briefbound 其余 owner 技能不受影响。

## 维护规则

- 技能正文引用 `C4`/`C5` 原语时，必须处于本文件降级门槛覆盖之下（在所属 SKILL.md 显式声明门槛，或仅在协作族协议文档内出现）。
- 新增 harness 支持时同步更新本表与安装器 `--agent` 说明；安装实测后再移除“未实测”标注。
