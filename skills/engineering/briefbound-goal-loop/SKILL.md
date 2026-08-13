---
name: briefbound-goal-loop
description: Use when the user explicitly requests an open-ended, persistent iteration policy with evidence-based next-step selection and stop conditions, and no domain-specific research, score, development, or coordination owner already controls the loop.
license: MIT
---

# Briefbound Goal Loop

## 目标

为明确要求持续迭代的开放目标提供轻量控制策略。它不替代 Briefbound Router 对齐、专项 owner、Planning 或 Project Memory，也不用于普通有限任务。

## Briefbound task contract

- Context Boundary: 已对齐目标、不可破坏约束、可用范围、当前证据和停止条件。
- Output Contract: 当前最有价值动作、最新证据、`ADVANCE / ITERATE / STOP / BLOCKED` 和下一动作。
- Allowed Action: 在用户授权和约束内执行最小高信息动作；不因本 skill 自动扩大工具、写入或远程权限。
- Success Evidence: 当前动作产生能改变完成判断或下一选择的可检查证据。
- Stop Condition: 目标达成、约束将被突破、没有高价值动作、连续尝试无新证据、缺输入/权限或用户暂停。
- Route Out: 最具体专项 owner、继续当前 loop、`briefbound-router` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文，完成只报状态、产出、证据和剩余风险；代码、命令、路径、错误原文、API/协议、skill 名和枚举保留原样；Route Out 仅以 Briefbound task contract 为准，末行写 `下一步建议: <一个具体动作>`。

## 激活闸门

必须同时满足：用户明确要求持续/反复迭代；终点不能预先拆成有限任务；每轮需要根据证据选择下一动作；没有更具体 owner。普通“继续”“优化到完成”、有限实现、已知 task graph、实验/score/research loop 和多 Agent 协调均不触发。

## 最小循环

1. 首轮只确认 `Goal / Evidence / Constraints / Stop`；Briefbound Router 已提供的内容直接继承，不重复询问或展示合同。
2. 选择最小且最可能产生新证据的动作，执行并验证。
3. 根据证据判断：推进目标用 `ADVANCE`，修正方法用 `ITERATE`，目标已达成或继续无价值用 `STOP`，缺不可约输入/权限用 `BLOCKED`。
4. 已授权且未触发停止条件时连续迭代，不在每轮询问是否继续。

Goal Loop 是控制策略，不是状态存储。对话内续接使用 Briefbound runtime；只有用户/项目已启用跨会话 memory 且当前决定值得持久化时，才由 `briefbound-project-memory` 写一次 durable delta。不得逐轮生成 ledger、dashboard、完整尝试历史或重复 goal contract。

需要校准正常推进、边界澄清或阻塞停止行为时，读取 `references/examples.md`。

## 输出

普通轮次只给：`本轮结果 / 新证据 / 决策 / 下一动作`。只有 `BLOCKED` 才补已尝试的关键路径和一个不可约问题；只有用户明确要求正式交接时才路由 Completion Summary。

下一步建议: <一个具体动作>
