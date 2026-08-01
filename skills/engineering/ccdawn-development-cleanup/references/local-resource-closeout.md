# Local Resource Closeout

仅在已知 branch、worktree、claim 或 task-owned runtime 需要收尾时读取。

## Branch、worktree 与 claim

本地分支只有同时满足以下条件才可删除：目标分支已包含 tip、没有 target 之外的提交、未被任何 worktree checkout、没有 active claim、不是当前或受保护分支。只用安全删除 `git branch -d`；拒绝时保留，不升级 `-D`，也不为通过删除而切换用户正在使用的 checkout。

当前功能分支在用户授权、项目策略允许或满足同一任务 `PR_MERGED` 时可自动收尾。其他历史分支还须被当前请求或长期策略覆盖，否则只报告候选。远程分支删除必须单独授权。

worktree 只有在 clean、branch 已吸收、claim 已关闭且不再承担恢复/运行职责时才移除。不要从目标 worktree 内删除自身；从已确认的稳定 repo/worktree 操作。Windows 上先验证绝对目标位于预期 worktree 父目录，检查 junction/reparse point；只移除已确认属于该 worktree 的链接本身，不递归进入共享目标，再使用 `git worktree remove`。禁止 force 删除 dirty worktree。

claim 仅在实现确实完成或明确取消后标记 completed/released；存在 blocker 或交接时保留真实状态。需要多 Agent 裁决时路由 `ccdawn-thread-coordination`。

## 运行进程收尾

先核验本任务进程的 PID、命令、启动时间、父子进程、listener、project/worktree、data/config root 与正式停止路径。

- 只停止能证明由本任务启动或依赖的精确进程树；按端口或进程名猜测 owner、停止未知进程、刷新正式 Launcher 均为 `BLOCKED`，转 `ccdawn-thread-coordination`。
- 临时 runtime 必须已使用 task worktree、隔离 temp data/config root 和非正式端口；端口不同不等于数据隔离。发现共享正式数据时先停止本任务受影响写入并协商，不硬做清理。
- 优先使用项目 Runtime Manager、Launcher 或 owner 提供的正式 stop 命令；停止后验证 PID/children、listener 和数据 writer 均已释放，再释放相关 claim。协调方明确等待时回复 `MODEL_RUNTIME_RELEASED`。
