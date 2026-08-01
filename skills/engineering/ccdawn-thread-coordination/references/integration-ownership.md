# Integration Ownership

仅在出现 `MERGE_READY` 或 integration queue 时读取。

## 原子认领

所有相关 Agent 只检查一次 `lane=integration/<target-key>`：

- 用户指定 > 有效 integration claim > 首个成功原子认领者。
- 无有效 claim 时，具备目标分支权限且能开始维护队列的 Agent 应 claim，并发送一次 `INTEGRATION_CLAIMED`，包含 `Agent / Thread / Target / Queue / Lease / Next Checkpoint`。
- 已有有效 claim 时，其余 Agent只提交 branch/commit/tests/risks；不得自行等待稳定 `main`、重复 rebase/full gate 或合并。

负责人 ACK `MERGE_READY`、维护队列、串行应用交付，在最终 HEAD 运行一次完整 gate。claim 有效期间不启动新的无关实现任务。

认领的是推进义务，不要求当下即可写入 `main`。dirty checkout、等待 peer 释放或已证明无关的 baseline failure 都是队列状态，不是放弃 owner 的理由。交付已提交后，将实现 claim 转为 ready/released，由 integration claim 承担后续责任。

## Coordination Closeout Gate

收到 `INTEGRATED` 或发现目标分支已包含交付时，立即用 Git 与 registry 对账；重基交付以最终吸收的 head 为准，并记录其替代关系。代码合入不等于协调完成：integration claim 必须覆盖约定内的 post-merge gate、Launcher/runtime 验收和 dirty-scene 恢复。全部完成后才广播 `INTEGRATED`、resolve 关联 merge coordination、释放 claim，并把已结束 Agent 标记 completed；不得保留假 open、假 active 或重复集成队列。

## Dirty target 分诊

认领队列后，把阻塞文件一次分为 `SELF_OWNED / PEER_OWNED / UNOWNED / UNKNOWN`：

- `SELF_OWNED`：迁移到自己的任务交付并提交，不得把自己在根目录创建的规划或预览误报为无关阻塞。
- `PEER_OWNED`：读取 owner thread，发送一次带文件、checkpoint 和恢复动作的 `DISCUSSION_REQUEST`；双方继续非冲突工作。
- `UNOWNED`：先建立可恢复保存，再按项目权限恢复干净目标；需要破坏性清理时询问用户。
- `UNKNOWN`：保留 integration claim，做一次 owner discovery；证据仍不足时带推荐向用户对齐。

同一阻塞再次出现时必须进入本分诊；不得以“等待 main 清理”继续累积新的实现批次。阻塞恢复前由 Integration Owner 持有队列，交付者无需重复 rebase、full gate 或 Launcher 验收。

若失败能在 clean base 复现且交付没有新增失败，标记 `MERGE_READY_CONDITIONAL`；默认不接管或要求用户授权修复无关基线。强制 gate 仍阻止合入时，owner 保留队列责任，只向现有基线 owner 发一次协调并等待可行动事件；只有产品、安全、迁移或真实范围取舍才询问用户。

### 条件合入快线

hook/gate 失败分为 `CHANGE_FAILURE / BASELINE_FAILURE / ENVIRONMENT_FAILURE / POLICY_FAILURE / UNKNOWN`。窄验证通过、diff 可审、失败在 clean base 复现且不涉及高风险或强制 gate，才标记 `MERGE_READY_CONDITIONAL`。

- 环境修复只做一次 2-5 分钟 probe；无新证据即停止。
- 只跳过已证明无关的 hook；`--no-verify` 需策略或用户允许，并记录补验责任。
- 条件提交需 integration owner 补跑 gate/CI；无法提交的 diff 必须有人接管。

无法及时推进时发送 `INTEGRATION_HANDOFF` 并释放 claim，不得静默占位。只有明确释放、租约失活或 Git 已证明义务完成时，其他 Agent 才可 `takeover`。
