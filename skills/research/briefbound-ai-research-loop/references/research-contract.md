# 研究契约与证据记录

只在多轮、跨会话、高成本或需要交接时创建这些工件。简单实验保留等价信息即可，不要求生成文件。

## 最小研究契约

```text
研究问题:
成功标准:
Active baseline:
Baseline fingerprint: commit / data / config / environment
评价协议: metric / split / seeds / command
允许修改:
保护边界:
预算: time / compute / experiment count
当前最可信结论:
未决关键不确定性:
停止条件:
```

## 实验记录

使用 append-only 记录，避免覆盖失败路径：

```text
Attempt:
Parent baseline:
Hypothesis:
Mechanism:
Expected signal:
Falsification signal:
Changed surface:
Command and artifact:
Metric / uncertainty:
Decision: accept / reject / hold
Interpretation:
Reusable lesson:
Next-hypothesis signal:
```

允许把连续、同机制、同失败原因的低价值尝试压缩成一条 summary，但必须保留原始 artifact 路径。

## 外层 findings

`findings` 是综合结果，不是实验流水账：

```text
Supported:
- 已被多个独立证据支持的机制或规律

Rejected:
- 已被关键实验否证的假设族，以及适用边界

Unresolved:
- 当前证据无法区分的解释

Transferable lessons:
- 可用于下一方向、规模、数据集或实现的经验

Decision:
- CONTINUE / BRANCH / PIVOT / CONSOLIDATE / STOP

Next experiment:
- 要减少的不确定性、最小 evaluation 和 kill condition
```

## 研究回传契约

当 `briefbound-score-loop` 完成一条 lane 时，研究 owner 至少接收：

```text
Candidate:
Hypothesis outcome:
Metric evidence:
Mechanism evidence:
Confidence and caveat:
Reusable lesson:
Next-hypothesis signal:
Pivot signal:
Artifact paths:
```

metric 方向与机制证据可以不同。例如分数没有提升，但消融排除了一个关键解释，仍可能具有高研究信息价值。

## 设计参考

本流程选择性吸收以下开源项目的公开设计思想，不依赖或复制其实现：

- `karpathy/autoresearch`：固定评价器、受限编辑面、固定预算和 keep/discard 内循环。
- `Orchestra-Research/AI-Research-SKILLs`：内外双循环、findings 综合和研究严谨性检查。
- `ResearAI/DeepScientist`：baseline 复现、失败路径保留、研究记忆和人工接管。
- `microsoft/RD-Agent`：研究方向与工程执行职责分离。
- `VectorInstitute/helix`：机器可读研究契约、可编辑/只读边界和 append-only ledger。

这些来源只用于流程设计参考。实际使用时遵守各项目许可证和当前项目约束。
