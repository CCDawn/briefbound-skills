# Huawei NSLB Project Profile

只在需要项目专用命令、并行 worker、打包或线上反馈时读取。默认入口是 `../SKILL.md`。

## 目录

- 当前事实源、工具定位与状态检查
- 候选、命令、worker、gate 与线上反馈

## 1. 当前事实源

项目必须包含 `src/Solution.cpp`。优先使用项目当前存在的事实源，不假设路径一定存在：

- baseline id、source hash 与本地评价协议；
- `docs/optimization-ledger.json`；
- `docs/online-offline-weights.json`；
- `docs/search-graph.json`；
- `docs/submission-map.json`；
- `docs/attempt-cards/` 与 `docs/failed_diffs/`；
- `.docs/project-memory/`；
- 本 skill 的 `mutation_space.json`。

skill 不保存“当前线上最佳”的固定副本。若这些来源互相矛盾，先报告不可比状态，不凭最近聊天或文件时间猜测。

## 2. 工具定位

```powershell
$project = if ($env:CCDawn_HUAWEI_NSLB_ROOT) {
  (Resolve-Path -LiteralPath $env:CCDawn_HUAWEI_NSLB_ROOT).Path
} else {
  (git rev-parse --show-toplevel 2>$null)
}
if (-not $project -or -not (Test-Path -LiteralPath (Join-Path $project "src\Solution.cpp"))) {
  throw "请通过 --project、CCDawn_HUAWEI_NSLB_ROOT 或当前仓库提供 Huawei NSLB 项目根目录。"
}
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$tool = Join-Path $codexHome "skills\ccdawn-huawei-nslb-score-loop\scripts\score_loop_tools.py"
python $tool --help
```

若 `python` 命中 WindowsApps alias，先使用 Codex bundled Python。执行任何写入型子命令前先看该子命令 `--help`；含 `--write` 的命令默认先预览。

## 3. 最小状态检查

```powershell
python $tool status --project $project
python $tool doctor --project $project --min-score 0
python $tool drift --project $project
```

`status` 用于当前 baseline/online 状态，`doctor` 检查运行条件，`drift` 判断源码是否偏离已登记 baseline。任何失败都先区分项目状态、环境问题和真实代码错误。

## 4. 候选生成

每个候选至少包含：

```json
{
  "laneId": "short-id",
  "targetComponent": "solver component or diagnostic surface",
  "searchMode": "EXPLOIT | EXPLORE | DIAGNOSE",
  "mechanism": "one causal change",
  "intendedMetric": "primary metric or diagnostic signal",
  "smallestDecisiveEvaluation": "case, trace, or narrow suite",
  "killCondition": "regression, flat signal, timeout, or illegal output",
  "expectedDiffSurface": ["src/Solution.cpp"],
  "recoveryArtifact": "diff and child_result.json"
}
```

选择规则：

- 用 `index` 或 `check` 排除同 baseline、同 family、同机制和同方向的重复候选。
- `EXPLOIT` 只在已有可复现正向信号时邻近搜索。
- 平台期用 `suggest-lanes`、`idea-board` 或 `epoch-board` 选择机制差异，而不是换名字重复旧尝试。
- `DIAGNOSE` 可以只产出 case、trace 或 scorer 报告，但必须回答一个明确问题。
- `mutation_space.json` 很大时只读所选 family；不要为选一个候选把全部历史塞进上下文。

## 5. 命令路由

只读状态与重复检查：

```text
status, doctor, drift, index, check, audit-skill
```

单候选与结果判断：

```text
gate-decision, validate-child, rank-children, learn-from-children,
archive-attempt, attempt-card, failed-diffs, search-graph
```

候选与 epoch：

```text
suggest-lanes, idea-board, epoch-board, prepare-epoch, run-epoch,
dispatch-epoch, collect-epoch, close-epoch, pool-update,
phase-transition, pool-retire
```

数据/代理评价：

```text
dataset-status, dataset-suggest, dataset-validate, dataset-promote
```

线上反馈与打包：

```text
register-submission, online-feedback, online-update, init-weights,
reweight-mutations, restore-online-best
```

不要因为子命令存在就自动使用。`restore-online-best`、带 `--write` 的更新、提交注册和 baseline 变更属于状态写入，需要精确目标、preflight/claim 与现有授权。

## 6. Worker 契约

并行 lane 必须提供唯一 workspace、baseline hash、allowed files、首个筛选、kill condition 和结果路径。worker 不读取或修改 main project 的共享 ledger。

最小 `child_result.json`：

```json
{
  "laneId": "",
  "status": "complete | pruned | failed | blocked",
  "baselineHash": "",
  "candidateHash": "",
  "mechanism": "",
  "commands": [],
  "metrics": {},
  "constraintsPassed": true,
  "smallestDecisiveResult": "",
  "diffArtifact": "",
  "recommendation": "PROMOTE | REJECT | HOLD | BLOCKED"
}
```

父 owner 必须重新验证候选与当前 baseline 仍可比较；worker 的 recommendation 不是最终替换决定。

## 7. Parent Gate

- `PROMOTE`：主指标达到有效提升，合法性与资源边界通过，代表性验证支持。
- `REJECT`：可比较但未过线，或副作用越界。
- `HOLD`：方向有价值，但需要一个已明确的补充验证。
- `BLOCKED`：baseline、协议、结果或提交对应关系不可信。

组合多个好 diff 前要重新建立一个组合 candidate；不能把多个 worker 的单独改善相加后直接晋升。

## 8. 线上反馈与打包

- zip 用短名，例如 `sub053.zip`；长元数据放项目已有 submission map。
- 线上反馈必须能唯一对应 package、candidate hash 和 baseline。
- 线上严格改善才更新 online best；中性/下降只更新校准证据。
- 本地代理测试只负责筛选。若它与线上多次反向，优先进入 `DIAGNOSE`，不要继续盲目 `EXPLOIT`。

## 9. 收口

普通 QUICK 只报告结论、比较证据和下一候选。只有跨会话恢复、线上反馈、可复用失败或项目规则要求时，才更新 ledger、attempt card、search graph 或 project memory。
