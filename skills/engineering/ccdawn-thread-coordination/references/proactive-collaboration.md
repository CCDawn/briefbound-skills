# 主动协作

## 投递门禁

### Target Validity Gate

`send_message_to_thread` 前即时 `read_thread`，确认目标存在，且当前任务、owner/claim 与 scope 匹配。历史 registry 映射、Agent ID 后缀或共享旧 thread 不是投递证据；无有效 threadId 或身份不匹配时不发，目标正处理不同用户任务时留待 idle，或转当前有效 owner，不发送泛化“继续”。

### ACK Gate

ownership、conflict、discussion、merge 请求写明目标 Agent/thread/claim/scope 和 `Reply To`，并要求一次 `ACK_OWNER / NOT_OWNER / DEFER_UNTIL <checkpoint>`。无 ACK 不等于送达、同意或取消；继续非冲突工作，不定时轮询。租约失活后仅做一次状态复核，再 `takeover` 或转当前有效 Integration Owner，不改投无关 thread。

## 平级协作提议

只向相关现有会话提出能帮助双方原任务的协作。发送前用一次 claim 原子占用 `lane=collaboration/<topic-key>`，并同时加入双方 `thread/<agent-id>` 与共享 scope；不要拆成多个 claim。消息带 collaboration id，并给出 `From Agent / Own Task / To Agent / Own Task / Reply To / Shared Surface / Mutual Benefit / Expected Evidence / Exit Condition`。

双方保留各自 owner 和关键路径；接受、调整或拒绝均由对方自主决定。结束、拒绝或超时后释放 claim；超时标 stale，迟到回复不能恢复旧 agreement，只能重新提议。可选协作不 BLOCKED；简单任务、无双向收益或忙碌 Agent 不联系。

## 同行建议

相关 Agent 处理同一 surface、接口或依赖时可做 `PEER_CONTEXT_REVIEW`：只读其 task、checkpoint、diff 和已有消息。有证据支持的具体改进才发送，写明双方身份与职责、证据、影响、建议和 `Reply To`。无 finding 不发消息；不夺 owner、不暂停、不强制采纳。

### 动态消息价值闸门

消息没有固定总数上限；每次发送前必须至少满足一项：

- 新证据会改变对方的下一动作、scope、风险判断、验证或合并决定；
- 需要明确纠正自己此前会导致误改的结论；
- 缺少对方独有证据已阻塞关键路径；
- 到达双方约定的 checkpoint，需要交付结果或决策。

同一证据的改写、无变化进度、重复安全边界、非阻塞催促，以及可自行只读获得的信息不发送。关联 findings 在自然 checkpoint 按优先级聚合；高风险覆盖、数据损坏或破坏性动作风险立即发送，不等待聚合。安全边界只在首次或权限变化时声明。

消息类型保持最小集合：

- 首次可行动发现：`ADVICE_AVAILABLE`；
- 发送后出现实质独立的新证据：`ADVICE_UPDATE`；
- 旧结论错误且会影响行动：`CORRECTION`，明确被替代的结论；
- 对方独有证据阻塞关键路径：一次 `STATUS_REQUEST`，列出精确缺口和用途；
- 共享契约存在分歧：转 `DISCUSSION_REQUEST`，不继续堆叠 advice。

使用 direct message 和稳定 `Reply To` 维持同一讨论链；发送前读取已有消息并按证据、影响和请求动作去重。不要把逐步思考、每个新念头或“仍在审查”当作消息。只有审查范围确实关闭才使用 `FINAL`；关闭后发现新证据时用 `ADVICE_UPDATE` 或 `CORRECTION` 说明重开原因。

接收方回复 `ACCEPT / ADAPT / DECLINE` 及理由后关闭当前 advice lane；除非出现新的实质证据，不再追问。无回复且不阻塞关键路径时继续自身工作；阻塞时按上述 `STATUS_REQUEST`，不定时轮询。普通建议不建 coordination。
