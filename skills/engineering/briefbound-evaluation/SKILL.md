---
name: briefbound-evaluation
description: Use when Briefbound workflow needs a Chinese-first evaluation adapter and no more specific existing skill already owns the review, debugging, PR, planning, feedback, verification, or goal task.
license: MIT
---

# Briefbound Evaluation

## 目标

评价方案、流程、skill、输出质量、合理性、灵活性或下一步价值。只在没有更具体 owner 时使用；不重复 PR、项目、bug、复用研究或 planning 流程。

## Briefbound task contract

- Context Boundary: 被评价对象、用户标准、证据来源、允许动作和已排除的专项 owner。
- Output Contract: 简洁判断、1-3 个会改变行动的依据或建议和 Route Out。
- Allowed Action: 只读评价；用户要求优化时路由最具体执行 owner，不在评价过程中顺手修改。
- Success Evidence: 判断绑定具体对象、证据、影响和可验证下一步。
- Stop Condition: 对象/目标不明、存在更具体 owner、关键证据缺失、实施越界或高风险取舍未确认。
- Route Out: 更具体 owner、`briefbound-router`、`briefbound-planning`、FAST_PATH、`briefbound-completion-summary` 或 BLOCKED。

## 统一调用契约

- 只处理 Briefbound task contract 范围；不匹配时回 `briefbound-router` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文；保留技术字面量；只报结论、证据、风险和产出；Route Out 仅以 Briefbound task contract 为准，末行写 `下一步建议: <一个具体动作>`。

## 评价方法

1. 先内部确认没有更具体 owner；无需向用户输出“复用检查”。
2. 只选会改变结论或下一动作的维度；证据已足够时停止，不固定遍历完整质量清单。
3. 每个判断给最短证据、影响和最小有效改进，不用“更完善/更灵活”等空话。
4. 最多给 3 个建议，按依赖、ROI 和误改风险排序；其余只在用户要求完整审计时展开。
5. 用户已要求“继续/优化/修复”时，立即路由最具体执行 owner，并沿已授权范围连续推进；评价 skill 本身不再复制执行流程。

内部可以多视角自审，但没有 finding 不展示矩阵，也不输出固定角色、严重度体系或 `SAFE_DIRECT/PLAN_THEN_EXECUTE` 分类。

## 输出

```text
评估结论: GOOD / ACCEPTABLE_WITH_RISK / NEEDS_CHANGE / BLOCKED
关键依据: <只保留会改变结论的证据>
建议（0-3 项）:
1. <最小动作>；原因；完成条件
剩余风险: ...
下一步建议: <一个具体动作>
```

评价对象不清时回 Briefbound Router 对齐；评价变成项目/PR/bug/复用专项时立即 Route Out，不在本 skill 扩写对应流程。
