---
name: briefbound-completion-summary
description: Use when completed work needs formal cross-stage or cross-session synthesis, resumed-task closure, durable handoff evidence, deferred-risk accounting, or an independent PR/release evidence package that the current owner's concise final response cannot represent.
license: MIT
---

# Briefbound Completion Summary

## 目标

把跨会话、跨 owner 或正式交接所需的现有证据压成一份可恢复的结论。普通 FAST_PATH 和有界 COMPACT_FLOW 由当前 owner 验证后直接汇报，不单独加载本 skill。

## Briefbound task contract

- Context Boundary: 已确认需求、跨阶段产物、最新验证、未决风险、保护边界和交接对象。
- Output Contract: `COMPLETE / PARTIAL / BLOCKED`、需求覆盖、新鲜证据、未决风险和一个恢复/交付动作。
- Allowed Action: 只读取、验证和压缩现有证据；不补功能、不重新审查整个项目、不提交、推送、合并或发布。
- Success Evidence: 每个完成 claim 都由匹配的新鲜命令、日志、截图、diff 或结构检查支撑。
- Stop Condition: 关键工作未完成、证据不足、保护边界越界、需要新范围或高风险授权。
- Route Out: 原 owner、`briefbound-bug-review`、`briefbound-planning`、`briefbound-pr-review`、提交/PR 准备、`briefbound-router` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文，完成只报状态、产出、证据和剩余风险；代码、命令、路径、错误原文、API/协议、skill 名和枚举保留原样；Route Out 仅以 Briefbound task contract 为准；有自然闸门（需用户裁决、批准或被外部阻塞）时末行 `下一步建议: <一个具体动作>`，否则声明继续已授权工作。

## 进入闸门

只在当前 owner 的简短完成说明无法承载以下任一价值时进入：

- 跨会话恢复或多个 owner/stage 的证据需要合并；
- 正式交接、审计或持久化 Deferred 风险；
- 用户明确要求完整完成报告；
- PR/发布前需要独立证据包，且不属于 PR diff 审阅本身。

单一 owner、单一上下文、验证已通过的普通实现直接收口。缺工作回原 owner，未知根因回 Bug Review，方案边界错误回 Planning/Briefbound Router；不要用总结包装半成品。

## 证据压缩

1. 从原需求提取必须满足的结果，不复述过程。
2. 只读取能证明完成、未完成或风险的最新证据；已有可靠证据不重复运行昂贵全量检查。
3. 对照 expected/actual、保护边界和 blocker，得到 `COMPLETE / PARTIAL / BLOCKED`。
4. 合并重复日志和阶段汇报，每个 claim 保留最短可追溯证据。
5. 只记录会影响恢复、交付或决策的风险；无持久状态需求时不生成 Ledger。

`COMPLETE` 表示目标已满足、新鲜验证通过、没有未解决 blocker；`PARTIAL` 表示有可恢复缺口；`BLOCKED` 表示继续需要新输入、权限或高风险决策。清理状态不是正式总结的固定前置条件；只有已知存在真实残留时才路由 Cleanup。

## 输出

```text
完成结论: COMPLETE / PARTIAL / BLOCKED
- 需求覆盖: <已满足；未满足/不做>
- 关键证据: <claim -> 最新证据>
- 保护边界与剩余风险: <仅真实项>
- 交付/恢复动作: <一个动作>
下一步建议: <有自然闸门时的一个具体动作；无闸门则声明继续已授权工作>
```

只有跨会话恢复确实依赖持久状态时，追加最小 handoff：`Owner / Completed / Evidence / Deferred / Next Action`。不输出固定 Completion Gate、Review Matrix、完整 Task Graph、命令流水账或阶段菜单。
