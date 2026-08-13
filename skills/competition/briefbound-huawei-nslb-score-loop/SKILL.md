---
name: briefbound-huawei-nslb-score-loop
description: "Use when a Huawei Algorithm Challenge 37 NSLB workspace needs live status, adaptive solver search, comparable evaluation, packaging, or online-score feedback; it is a thin project adapter over briefbound-score-loop."
license: MIT
---

# Huawei NSLB Score Loop

## 目标

这是 `briefbound-score-loop` 的 Huawei NSLB 适配层，补充项目识别、工具命令、solver 约束和线上反馈；候选搜索、淘汰和替换仍用通用 score loop。

不得把 skill 内的旧分数、hash 或聊天记忆当成当前事实。最好方案、源码 hash、活跃运行和提交映射须从项目现场读取。

## Briefbound task contract

- Context Boundary: 项目根目录、当前 baseline/hash、评价协议、solver 写入面、工具状态和线上反馈。
- Output Contract: 当前状态、下一候选、可比证据、替换决定、提交包或恢复结果。
- Allowed Action: 只在项目授权范围内运行命令和修改隔离 workspace；不静默改主 baseline、ledger、提交映射或线上最佳记录。
- Success Evidence: 当前命令输出、source hash、candidate diff/config、可复现指标、`child_result.json`、gate 或短名提交包。
- Stop Condition: source drift 未解释、协议不可比、共享事实源写冲突、child result 无效、提交包无效、线上反馈归属不清或用户暂停。
- Route Out: `briefbound-score-loop`、项目工具、`briefbound-bug-review`、online feedback wait、项目 memory 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract；Route Out 仅以 Briefbound task contract 为准。
- 用户可见内容默认中文，先说状态、原因和下一步，不先列 ledger、epoch 或内部枚举。
- 首次出现代理测试时解释：它是用于快速淘汰候选的小测试，不能代替正式分数。
- 只有复杂问题需要时才展开 hash、worker、校准或搜索图；末行写 `下一步建议: <一个具体动作>`。

## Live-State Gate

从 `--project`、`BRIEFBOUND_HUAWEI_NSLB_ROOT` 或当前仓库解析根目录，确认 `src/Solution.cpp`，再定位工具。检查 `status`、`doctor`、`drift`，读取已有 baseline、ledger、online feedback 和 package map；缺失就说明，不新造事实源。协议或 baseline 漂移时先恢复可比性。

工具入口和完整命令分组见 `references/huawei-nslb-profile.md`。

## 自适应搜索

根据当前证据选择一个方向：

- 有稳定正向机制：`EXPLOIT`，只改一个邻近变量。
- 连续候选重复或停滞：`EXPLORE`，从 `mutation_space.json` 选择机制不同的 family。
- 本地与线上关系不清、失败原因不明：`DIAGNOSE`，先构造区分性 case/trace，不急着改 solver。

候选写清 component、单一机制、预期指标、`smallestDecisiveEvaluation`、kill condition 和恢复产物。先查重，再跑合法性/编译和最小筛选；无晋升可能就淘汰。

## 工作重量

- `QUICK`：单候选、单 workspace；无需 epoch、worker pool、attempt card 或 memory 更新。
- `STANDARD`：多轮可比候选；复用项目当前 ledger/search history 记录必要结果。
- `FULL`：真正独立的并行 lanes、昂贵验证、提交包或线上反馈；才启用 epoch/worker/校准工具。

旧 ledger、search graph、attempt cards 和 failed diffs 是可选事实源，不是每轮流程。

## Worker rule

并行收益明确时才创建 worker。worker 只改隔离 workspace，main project 只读；通常只改 `src/Solution.cpp` 的一个机制。先核对 baseline hash，再编译和最小筛选；命中 kill condition 后保留 diff、指标和原因并停止。完成前写有效 `child_result.json`，不能自行替换共享 baseline 或线上最佳。

## 线上反馈与提交

本地结果和线上分数分别记录。线上严格改善且对应唯一提交包时才更新线上最佳；中性或下降只调整搜索权重，不抹掉本地证据。

zip 用短名如 `sub053.zip`；完整元数据写入已有 submission map。恢复 baseline、写 ledger、注册提交或更新权重继承项目 preflight、claim 和用户授权。

## 完成

```text
结论: <替换 / 淘汰 / 继续观察 / 暂时无法比较>
当前依据: <baseline/hash、主指标、硬约束和线上反馈>
产物: <diff、child_result、提交包或记录；没有则省略>
下一步建议: <一个具体动作>
```

仅在跨会话恢复或项目规则要求时更新 `competition-huawei-nslb` memory；普通 QUICK 不为留痕而写 memory。
