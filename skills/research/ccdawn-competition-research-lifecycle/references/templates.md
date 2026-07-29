# 竞赛科研全流程模板（Competition Research Lifecycle Templates）

## 目录

- 阶段启动与项目状态
- 任务、数据和研究证据
- 假设、实验、smoke 与 proxy ranking
- Baseline、消融、论文与提交
- 并行 lane 和证据失效

当用户需要快速落一个具体 artifact 形状时，优先使用这些模板。

## 阶段启动卡

```text
当前阶段:
阶段模式:
目标:
已知输入:
未知项:
Source of truth:
Active baseline / evidence:
建议做法:
支持技能:
要产出的 artifact:
BRT gate:
- Behavior:
- Review:
- Test:
范围约束:
退出标准:
阶段决策:
下一步行动:
```

## 项目状态账本

```text
项目:
当前阶段:
当前阶段模式:
规则来源:
Active data version:
Active baseline:
Active metric:
Active evidence:
当前最好外部反馈:
已失效 evidence:
开放风险:
下一步 gate:
负责人或 lane:
更新时间:
```

## 任务定义简报

```text
项目:
竞赛或 benchmark:
主指标:
次指标:
允许使用的数据和工具:
禁止使用的数据和工具:
提交契约:
截止时间:
算力和团队约束:
已知风险:
开放问题:
Source of truth 位置:
推进决策:
```

## 数据就绪报告

```text
数据集来源:
版本标识:
Schema 概览:
Label 概览:
切分策略:
Leakage 风险:
已知质量问题:
Preprocessing 步骤:
复现性检查:
Active data version:
下游影响:
推进决策:
```

## 研究证据包

```text
目标:
来源分组:
标准化字段:
方法簇:
与 benchmark 或数据集的相关性:
可行性备注:
强证据:
弱证据或空白:
入围方法:
淘汰方法:
转化为实验假设:
```

## 实验假设包

```text
实验族:
假设:
预期信号:
所需代码或数据改动:
受控变量:
主指标:
次级检查:
失败解释:
晋级规则:
```

## 实验 Attempt 卡

```text
Attempt id:
Based-on baseline:
Data version:
Metric version:
Hypothesis:
预期提升:
已知风险:
允许改动范围:
改动变量:
固定变量:
Smoke gate:
- Smoke subset:
- Smoke budget:
- Smoke baseline:
- Smoke metric:
- Smoke result:
- Smoke decision: promote-to-full-run | reject | needs-more-evidence | skipped
运行命令:
观测指标:
外部反馈:
复现状态:
决策: promote-candidate | reject | needs-more-evidence | proposal-only
Failure reason:
Lesson:
Avoid next time:
```

## 小样本 Smoke 记录

```text
Smoke id:
目的:
Active baseline:
候选算法:
数据版本:
子集抽样规则:
样本量:
Seed:
训练预算:
评估命令:
固定参数:
变化参数:
Baseline smoke 指标:
Candidate smoke 指标:
Delta:
耗时:
峰值显存:
失败或异常:
与历史正式结果的一致性:
决策: promote-to-full-run | reject | needs-more-evidence
不能作为论文主结果的说明:
下一步:
```

## Proxy Ranking 表

```text
Ranking batch:
Active baseline:
Data version:
Smoke subset:
Smoke budget:
Metric:
候选:
改动摘要:
Proxy score:
Delta vs baseline:
Runtime:
Peak memory:
Failure:
Decision:
Reason:
Full-run priority:
```

## Baseline 运行记录

```text
Baseline 名称:
模型或方法:
数据版本:
Config 路径或摘要:
Seed:
训练流程:
验证流程:
提交检查:
观测指标:
已知问题:
Source hash 或版本标识:
晋升条件:
推进决策:
```

## 实验卡

```text
Run 名称:
日期:
父级 baseline 或 run:
假设:
改动变量:
固定变量:
Config 和 seed:
观测指标:
产出 artifacts:
解释:
是否进入 active evidence:
下一步决策:
```

## 消融与最终选择

```text
测试问题:
对比 runs:
受控因素:
主指标变化:
次指标变化:
失败案例:
解释:
被支撑的 claim:
证据边界:
最终选择决策:
```

## 论文证据映射

```text
章节或 claim:
Claim 文本:
支撑表格或图:
支撑实验或 run:
支撑引用:
已知局限:
需要修订:
状态: accepted | needs-evidence | revise | drop | stale
如果 stale，失效原因:
```

## 提交检查表

```text
提交项:
要求格式:
来源 artifact:
负责人:
复现检查:
合规或 policy 检查:
剩余风险:
状态:
```

## 并行 Lane Board

```text
epoch:
active baseline / evidence:
lane:
lane type:
hypothesis:
expected output:
allowed files or artifacts:
commands or checks:
result:
decision: promote-candidate | reject | needs-more-evidence | proposal-only
lesson:
owner:
status: active | blocked | completed | retired
```

## 证据失效记录

```text
事件:
发现时间:
触发原因:
受影响数据版本:
受影响 baseline / runs:
受影响 tables / figures:
受影响 claims:
仍然可信的 evidence:
必须重跑或重审:
恢复计划:
阶段决策: recover | stop
```
