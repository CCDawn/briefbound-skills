---
name: briefbound-simplification-audit
description: Use when the user explicitly requests a repository/subsystem simplification audit, dependency-bloat review, or ranked removal plan, or when concrete evidence makes structural complexity the primary investigation; do not substitute it for ordinary project health review.
license: MIT
---

# Briefbound 精简审计

## 目标

只读审计仓库或子系统中的可移除复杂度，形成按价值和风险排序的精简队列。它补充项目健康审查，不替代 `briefbound-project-review`。

## Briefbound task contract

- Context Boundary: 仓库/子系统范围、入口与依赖、已知架构约束、生成代码/第三方代码排除范围。
- Output Contract: 证据化复杂度 findings、保留项、精简候选队列和后续 owner。
- Allowed Action: 只读；不修改文件、不卸载依赖、不移动分支、不改 index。
- Success Evidence: 每个候选都有路径/引用/依赖或调用证据，并说明收益、风险和验证要求。
- Stop Condition: 审计范围不明、缺少源码/依赖证据、建议涉及行为或架构取舍、或问题主要属于正确性/安全/性能。
- Route Out: `briefbound-project-review`、`briefbound-performance-engineering`、`briefbound-planning`、对应开发 owner、`briefbound-router` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文，完成只报状态、产出、证据和剩余风险；代码、命令、路径、错误原文、API/协议、skill 名和枚举保留原样；Route Out 仅以 Briefbound task contract 为准，末行写 `下一步建议: <一个具体动作>`。

## 审计规则

1. 先定位入口、依赖清单和高变更/高耦合区域，不为“全面”盲扫全仓。
2. 重点检查：重复依赖、标准库/平台已有能力、单实现接口、单产品工厂、只转发的 wrapper、废弃 flag/config、并存的 legacy 路径、重复事实源和跨文件样板。
3. 排除生成代码、vendored/third-party 代码、迁移期间明确保留的兼容层，以及安全、无障碍、数据恢复和真实平台适配约束。
4. 每项区分“确认可删”“需 probe”“架构取舍”；证据不足不能写成确定结论。
5. 正确性、测试、安全和总体健康交 `briefbound-project-review`；需实测的性能问题交 `briefbound-performance-engineering`；实施方案交 `briefbound-planning`。

优先级：`P1 高收益`、`P2 中收益`、`P3 低收益`、`需证据`。

## 输出

```text
精简审计:
- 结论: LEAN / OPPORTUNITIES_FOUND / NEEDS_EVIDENCE / BLOCKED
- 范围与排除项: ...

Findings:
- P1/P2/P3/需证据: [位置] 复杂度来源；证据；最小替代；收益；风险。

保留项:
- 必须存在的复杂度及原因。

精简队列:
- 1. ... [SAFE_DIRECT / PLAN_THEN_EXECUTE / DEFERRED / BLOCKED]；验证条件...

组合路由:
- 项目健康/正确性/安全 -> briefbound-project-review
- 性能测量 -> briefbound-performance-engineering
- 多项结构调整 -> briefbound-planning

下一步建议: <一个具体动作>
```

只在可复现计数后报告精确净减行数或依赖数，不拿外部 benchmark 冒充当前仓库收益。

本 skill 的复杂度视角借鉴 [Ponytail](https://github.com/DietrichGebert/ponytail)（MIT），并按 Briefbound 的中文输出、证据和 owner 契约重新组织。
