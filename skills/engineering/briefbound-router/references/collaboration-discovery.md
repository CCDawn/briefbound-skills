# Collaboration Discovery

只在需求已收敛、功能 owner 已选定、本轮原生 thread/list 能力可用，且现有同项目独立会话可能互助时读取。能力不可用时返回 `NONE`，不得伪造或创建候选。发现目的是判断平级协作价值，不是启动协调。

## 有界发现

1. 使用本轮原生 thread/list 能力查找同一项目的活跃对话；registry 已存在时读取 Agent、scope、branch/worktree 和 checkpoint，不为发现初始化 memory 或 registry。
2. 只读最多 3 个最相关候选，确认真实任务、进度、有效 thread id、互补价值和重叠风险；路径或名称相似不等于同项目。
3. 比较对各自任务的帮助、重复工作消除、冲突/返工降低与消息/协调/合并成本。候选忙碌、过期、共享同一小文件或协作会拖慢任一关键任务时排除。

## 决策

- `NONE`：无正收益候选，原 owner 静默继续。
- `PEER_CONTEXT_REVIEW`：同行上下文能改善当前判断，交 thread coordination 做一次只读建议。
- `PEER_READ_ONLY`：双方交换独立只读证据能帮助各自任务，交 thread coordination 提议协作。
- `COORDINATE_OVERLAP`：只有重叠、讨论或恢复需求，交 thread coordination。
- `PEER_DISJOINT_WRITE -> PEER_COLLABORATION_READY`：至少两个现有会话各有原任务，存在明确依赖或共同集成面，写入可分离且整体收益高于协商成本，交 multi-agent orchestration。
- `ASK_CREATE`：无现有候选但新增会话有明确收益；向用户询问一次，未授权则当前 owner 继续。

发现时不得发送消息、claim、创建会话或暂停其他 Agent。不得把现有会话视为可派发的 worker；路由后只能提出平级协作。
