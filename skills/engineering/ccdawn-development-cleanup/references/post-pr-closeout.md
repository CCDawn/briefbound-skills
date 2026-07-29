# Post-PR Closeout

只在同一任务已创建或更新 PR，且 branch/worktree/claim 生命周期仍需收口时读取。

先记录并核验 `PR URL / base / published head / local branch / worktree / claim`：

- `PR_OPEN`：输出 `DEFERRED_INTEGRATION`；published head 无待处理写入时关闭/release 实现 claim，保留 branch/worktree 和恢复证据，并以合并为下次触发条件。后续 review 修复重新认领写 scope；没有监控授权时不后台等待，也不声称 `CLEAN`。
- `PR_MERGED`：刷新远程状态并验证 base 包含 published head；关闭无待处理写入的同任务 claim，从稳定 checkout 移除 clean worktree，再用 `git branch -d` 删除已吸收本地分支。目标未安全同步或任一门槛不满足时保留并报告。
- `PR_CLOSED_UNMERGED`：输出 `KEEP`，保留未吸收 branch/worktree 与提交；只有用户明确放弃且满足普通删除门槛时另行清理。

“完成开发到 PR”的请求继承合并后的同任务安全本地收尾许可。它不授权远程分支删除；仓库既有自动删除策略除外。
