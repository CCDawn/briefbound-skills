# Peer Collaboration Protocol

只在两个以上现有独立 Codex 会话形成真实协作时读取。所有消息使用同一个 `Collaboration ID` 和稳定 `Reply To`；先读已有消息，再判断是否有新增决策价值。

## COLLABORATION_PROPOSAL

```text
Type: COLLABORATION_PROPOSAL
Collaboration ID:
From Agent / Own Task:
To Agent / Own Task:
Shared Surface or Dependency:
Why Both Tasks Benefit:
Proposed Each Scope:
Evidence To Exchange:
Integration Target:
Current Integration Claim (optional):
Exit Condition:
Reply To:
```

接收方回复 `PEER_ACCEPT / PEER_ADAPT / PEER_DECLINE`。接受只代表同意协作边界，不转移原任务 owner、权限或 branch。proposal claim 已释放或过期时，迟到回复只能作为新提议的参考。

## VALUE_CHECKPOINT

只发送：

- `SHARED_CONTRACT_CHANGE`：共同接口或约束变化；
- `DEPENDENCY_READY`：对方任务依赖已可用；
- `ACTIONABLE_FINDING`：新证据会改变对方行动；
- `CORRECTION`：此前结论错误且会导致误改；
- `BLOCKED_BY_PEER_FACT`：缺少对方独有事实；
- `MERGE_READY`：自己的交付已达到约定回收条件。

消息包含 `Own Task / New Evidence / Impact On Peer / Requested Decision / Reply To`。无新增决策价值不发送；多个相关 finding 在自然 checkpoint 聚合。

## MERGE_READY

```text
Type: MERGE_READY
Collaboration ID:
Agent / Own Task:
Base / Head:
Branch / Worktree:
Changed Scope:
Dependency State:
Tests:
Known Risks:
Suggested Integration Order:
```

Integration Owner 必须用 Git 和测试重验。成功只广播一次 `INTEGRATED`；失败只通知责任 Agent 和受影响依赖方。每个 Agent 根据结果继续完成自己的原任务。

## INTEGRATION_CLAIMED

首个 `MERGE_READY` 出现且 `integration/<target-key>` 为空时，由合格 Agent 原子认领后发送一次：

```text
Type: INTEGRATION_CLAIMED
Collaboration ID:
Agent / Thread:
Target:
Queued Deliveries:
Lease / Next Checkpoint:
Reply Needed: NO
```

其他 Agent 看到有效 claim 后停止独立合并，只继续原任务或提交 `MERGE_READY`。负责人不能及时推进时发送 `INTEGRATION_HANDOFF` 并释放 claim；失活接管必须引用旧 claim、Git 现状和新 lease。完成后广播一次 `INTEGRATED`，释放 claim 并关闭关联 merge coordination。
