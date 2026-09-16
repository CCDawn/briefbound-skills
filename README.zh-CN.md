# Briefbound Agent Skills

[![Release](https://img.shields.io/github/v/release/CCDawn/codex-skills?display_name=tag)](https://github.com/CCDawn/codex-skills/releases)
[![Validate](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/CCDawn/codex-skills)](LICENSE)
[![Skills](https://img.shields.io/badge/skills-32-2f81f7)](#完整-skill-目录)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-1f883d)](https://agentskills.io/)
[![skills.sh](https://skills.sh/b/CCDawn/codex-skills)](https://skills.sh/CCDawn/codex-skills)

**Bound to the brief. Free to build.**

**约定内自主推进，约定变化主动商量。**

32 个中文优先 Agent Skills，支持 Codex 与 Grok Build，覆盖意图对齐、动态路由、多会话平级协作与自动闭环、轻量开发、代码结构守卫、性能工程、开发清理、代码审查、UI 设计和 AI 研究工作流。

- 用户正常说需求即可，不需要主动调用 `briefbound-router` 或记忆流程命令。
- [`briefbound-router`](skills/engineering/briefbound-router/SKILL.md) 会在意图明确时直接推进；低/中风险不确定时先声明假设再继续，只有高影响分叉才用一轮紧凑的建议/对齐并等待校准；讨论时先说结果、使用通俗中文，并只解释会影响判断或操作的复杂概念。
- 简单任务直接实现和验证；只有真实风险存在时才升级到规划、内嵌任务图或紧凑 TDD。

[English](README.en.md) | **简体中文**

## 20 秒看懂 Briefbound Router

![Briefbound Router 从意图对齐到自动路由、实施与验证的演示](assets/briefbound-demo.gif)

这是一个流程示例：用户只需正常表达需求；Briefbound Router 会先查证可用上下文，只讨论会改变结果的问题，然后把已对齐的任务交给最具体的 Skill。用户看到的是简短结论、必要依据和下一步，而不是内部路由枚举或流程账本。

## 快速体验

先预览最重要的入口 Skill：

```powershell
gh skill preview CCDawn/codex-skills briefbound-router
```

使用 Agent Skills CLI 查看或安装：

```powershell
npx skills add CCDawn/codex-skills --list
npx skills add CCDawn/codex-skills --skill '*' -g -a codex -y
```

这会安装 skill 文件，但不会修改全局 `AGENTS.md`。需要“正常说需求即可自动进入 Briefbound Router”的默认激活能力时，使用下面的仓库安装器。

需要 Briefbound 完整安装策略，包括安装演练、live copy 验证和可逆处理冲突入口时，使用仓库安装器：

```powershell
git clone https://github.com/CCDawn/codex-skills.git
Set-Location codex-skills
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

只安装到 Grok Build，或同时维护 Codex 与 Grok：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent grok
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent codex-grok
```

macOS/Linux：

```bash
git clone https://github.com/CCDawn/codex-skills.git
cd codex-skills
sh ./install.sh
```

默认只安装到 `~/.codex/skills/<briefbound-skill-name>`，不会同时写入 `~/.agents/skills` 造成重复入口。选择 `grok` 时安装到 `~/.grok/skills`；选择 `codex-grok` 时只维护这两个运行时。安装器会在对应的 `AGENTS.md` 中维护可逆的轻量 Briefbound Router 激活块，让普通需求自动进入路由，并保留已有全局规则。高级选项见[安装细节](#安装细节)。

## 为什么使用 Briefbound

| 常见问题 | Briefbound 的处理方式 |
| --- | --- |
| 用户没有写完整规格 | 先读取可查证上下文，再讨论真正会改变结果的问题 |
| Agent 汇报术语多、难评估 | 先说结果，默认使用通俗短句；复杂概念只有影响决定时才主动解释 |
| Skill 很多但不会自动选 | Briefbound Router 选择最具体 owner，并可动态组合多个意图 |
| 已安装 GitHub、浏览器、Figma 或文档工具却不会用 | Briefbound Router 按当前可用能力直接路由，Briefbound owner 只保留目标与验收 |
| 简单修改被流程拖慢 | 按子任务风险控制重量，默认优先直接实现和验证 |
| 高影响前端改动难以提前评估 | 先制作隔离的可交互预览网页，用户批准后再修改正式页面；明确小修可跳过 |
| 新功能可能引入低效代码 | 普通功能静默检查明显低效；只有真实热路径或指标问题才测量和优化 |
| 开发不断堆出巨型单文件 | 对本轮手写源码使用 `STAY/CHECK/SPLIT`；只有职责边界可分时才做最小拆分 |
| 审查只给结论、不继续推进 | 形成按依赖排序的行动队列，在边界内连续处理 |
| 多个 Codex 会话同时开发 | Briefbound Router 对齐后发现可互助的平级会话，让各自完成任务并协商共享边界与集成 |
| 多会话冲突后链路容易停住 | 用户确认一次后，自动协作闭环可接管失活协调、恢复暂停任务并验证合入本地 `main` |
| 功能完成后残留临时文件和旧分支 | 仅在已知产生残留或用户要求时清理有归属证据的本地资源 |
| AI 研究和普通开发混用流程 | 分离研究实验、评分循环、严谨性审查和软件 TDD |
| 评分优化只会重复调相邻参数 | 固定可比协议后，在利用正向信号、探索不同机制和诊断不确定性之间主动切换，并尽早淘汰无望候选 |
| 创意输出模板很完整但想法普通 | 按创意阶段默认只选一个方法，先过滤显而易见的答案，再给少量具体机制、失败方式和可执行第一步 |

## 精选 Skill

- [`briefbound-router`](skills/engineering/briefbound-router/SKILL.md)：默认适配层，负责意图理解、通俗对齐、路由和流程重量控制。
- [`briefbound-autonomous-collaboration-loop`](skills/engineering/briefbound-autonomous-collaboration-loop/SKILL.md)：用户确认一次后，持续驱动现有会话完成各自任务、恢复冲突并验证合入本地 `main`。
- [`briefbound-multi-agent-orchestration`](skills/engineering/briefbound-multi-agent-orchestration/SKILL.md)：连接同项目现有平级会话，让各 Agent 保留原任务，通过低噪声协商减少重复、冲突和集成返工。
- [`briefbound-thread-coordination`](skills/engineering/briefbound-thread-coordination/SKILL.md)：共享同项目 Agent 进度，协调冲突、讨论、暂停恢复与快速合并。
- [`briefbound-development-cleanup`](skills/engineering/briefbound-development-cleanup/SKILL.md)：清理开发残留，并安全收尾已合并本地分支、worktree 和 claim。
- [`briefbound-bug-review`](skills/engineering/briefbound-bug-review/SKILL.md)：从症状和失败证据定位根因，完成有界修复与验证。
- [`briefbound-performance-engineering`](skills/engineering/briefbound-performance-engineering/SKILL.md)：只在性能目标、回归或关键热路径需要测量时定位瓶颈并验证最小优化。
- [`briefbound-code-structure-guard`](skills/engineering/briefbound-code-structure-guard/SKILL.md)：在开发中识别多职责巨型文件，只在维护收益明确时执行最小拆分。
- [`briefbound-pr-review`](skills/engineering/briefbound-pr-review/SKILL.md)：按风险排序审查 PR、diff、分支和合并准备度。
- [`briefbound-ui-design`](skills/engineering/briefbound-ui-design/SKILL.md)：处理 UI/UX、响应式和无障碍；高影响结果先制作隔离网页供用户预审。
- [`briefbound-visual-design`](skills/engineering/briefbound-visual-design/SKILL.md)：建立品牌与视觉方向，并在正式落地前提供可交互预览。
- [`briefbound-ui-review`](skills/engineering/briefbound-ui-review/SKILL.md)：审查已有界面或隔离预览，输出 findings 与预审建议，但不替用户批准。
- [`briefbound-design-system`](skills/engineering/briefbound-design-system/SKILL.md)：治理跨组件 token、主题、variants、共享组件和 Figma/code 一致性。
- [`briefbound-frontend-engineering`](skills/engineering/briefbound-frontend-engineering/SKILL.md)：消费已批准或明确跳过预览的界面契约，实施生产代码并做运行时验证。
- [`briefbound-ai-research-loop`](skills/research/briefbound-ai-research-loop/SKILL.md)：复现 baseline，推进假设、实验、消融与研究方向收敛。
- [`briefbound-score-loop`](skills/competition/briefbound-score-loop/SKILL.md)：固定比较协议后主动选择利用、探索或诊断候选，用早停和代表性评价决定是否替换当前最好方案。
- [`briefbound-huawei-nslb-score-loop`](skills/competition/briefbound-huawei-nslb-score-loop/SKILL.md)：从当前 NSLB 项目读取 baseline、hash 和线上反馈，按需调用 solver 搜索、打包与校准工具。
- [`briefbound-creative-toolbox`](skills/creative/briefbound-creative-toolbox/SKILL.md)：按生成、扩展、选择、解卡、颠覆、精炼、整理或命名阶段选择一个方法，输出少量可尝试的非套路方案。
- [`briefbound-feature-reuse-research`](skills/engineering/briefbound-feature-reuse-research/SKILL.md)：为复杂功能评估项目内外可复用方案。

## 懒人安装

不想手动 clone、找目录或运行命令时，把下面的提示词直接发给 Codex。

<details>
<summary>展开一键安装提示词</summary>

```text
请帮我一键安装 Briefbound 的 Codex skills 技能包。

仓库地址：https://github.com/CCDawn/codex-skills.git

要求：
1. 如果本机已有这个仓库，就进入仓库并更新到最新 main；如果没有，就 clone 到一个合适的本地目录。
2. 只安装到当前用户的 Codex live skills 目录：~/.codex/skills。
3. 不要安装到 ~/.agents/skills，避免重复 slash-command。
4. 先运行安装演练，再执行正式安装。
5. 安装后验证 live skills 是否可用。
6. 使用安装脚本默认可逆停用安装器识别的完整 Superpowers 自动发现入口集，保留原目录和内容，不要删除。
7. 允许安装器在 ~/.codex/AGENTS.md 中安装受管的 Briefbound Router 激活块；必须保留用户已有规则，并确保可单独卸载。
8. 最后用中文汇报：仓库位置、安装目录、安装了哪些 skills、Briefbound Router 激活状态、冲突入口处理、验证是否通过、是否需要重启 Codex。
9. 重点提醒我：最重要入口是 briefbound-router；用户正常说需求即可。目标清楚即行动许可，直接推进；低/中风险不确定时先声明假设再继续，只有高影响分叉（改变行为的产策决定、不可逆或用户可见面、安全、数据损失）才用一轮紧凑的建议/对齐并等待校准。只提答案会改变走向的问题，一轮集中提出；意图和范围清楚时零提问也合法。复杂术语只在影响判断或操作时解释。Briefbound 自身不创建子 Agent；若运行时提供委派工具，独立可并行的工作可直接派发、无需请示，琐碎或单一 owner 的工作留在当前会话；平级会话协作不转移任务 owner。需要持续自动开发、冲突恢复和本地 main 集成时，Briefbound Router 只询问一次是否开启 briefbound-autonomous-collaboration-loop。

如果遇到 Git、Python、网络、权限问题，只问我一个最关键的阻塞问题。
```

</details>

需要更严格限制写入范围时，用[强约束版安装提示词](INSTALL_PROMPTS.md#强约束版)。

## 完整 Skill 目录

### 工程流程

- **`briefbound-router`**
  Briefbound 最重要入口 skill。目标清楚即行动许可，直接推进；低/中风险不确定时先声明假设再继续，只有高影响分叉才用一轮紧凑的建议/对齐并等待校准。只提答案会改变走向的问题。复杂术语只在必要时解释。

- **`briefbound-autonomous-collaboration-loop`**
  用户明确开启后，持续协调同项目现有会话完成各自任务，普通冲突自动协商，最大冲突只暂停重叠面，并由可接管的 owner 恢复任务、验证合入本地 `main` 和安全收尾。

- **`briefbound-multi-agent-orchestration`**
  Briefbound Router 对齐并发现双向协作价值后的多会话协议。它协调现有平级会话而不转移任务 owner；各平级 Agent 继续完成自己的原任务，只协商共享契约、依赖、冲突和集成责任。

- **`briefbound-thread-coordination`**
  同一项目多会话协调 owner。用跨 worktree 的 live registry 共享任务、scope 和 checkpoint；通过收敛讨论、暂停握手和 merge order 减少冲突与回归。

- **`briefbound-development-cleanup`**
  只在已知产生临时残留、branch/worktree/claim，或用户明确要求时加载；安全清理可证明无用且已吸收的开发噪音。

- **`briefbound-ui-design`**
  UI/UX 专项 owner，负责信息层级、交互状态、响应式和无障碍；高影响结果先交付隔离预览并等待用户批准，机械前端小改可明确跳过。

- **`briefbound-visual-design`**
  视觉方向 owner，根据产品、品牌和受众决定字体、色彩、构图、图像、图标和动效语言，并在正式落地前提供隔离网页预审。

- **`briefbound-ui-review`**
  已有界面与隔离预览审查 owner，以真实用户任务和浏览器证据给出 findings 及预审建议；只有用户可以批准预览。

- **`briefbound-design-system`**
  设计系统治理 owner，只处理跨消费者的 token、主题、组件 API、variants、Figma/code 映射和渐进迁移。

- **`briefbound-frontend-engineering`**
  前端生产实现 owner，只消费用户已批准或有依据跳过预览的界面契约，负责组件、状态、响应式和无障碍实现，并使用真实浏览器证据收口。

- **`briefbound-diagram-design`**
  结构化图解 owner：把架构、流程、时序、ER/UML、定量数据做成可编辑的 HTML/SVG/PNG，支持 Mermaid、draw.io、Excalidraw 导入；报告内配图以 support 身份参与，不抢内容 owner。

- **`briefbound-feature-reuse-research`**
  只在复用候选会实质改变复杂功能的架构、依赖或实现范围时调研现有项目、库、标准、示例和项目内模块。

- **`briefbound-planning`**
  只在真实设计分叉、高风险顺序或跨边界交接需要可复用方案时触发；存在独立 owner、依赖或验证边界时在同一方案内生成最小任务图，否则由当前 owner 直接实施。

- **`briefbound-bdd-tdd-development`**
  仅对预期已明确的新行为或高风险实现契约使用紧凑 TDD；未知根因和 bug 修复仍由 Bug Review 全程持有。

- **`briefbound-completion-summary`**
  只为跨阶段/会话恢复、正式交接或独立证据包生成紧凑总结；普通实现由当前 owner 直接收口，不生成固定账本。

- **`briefbound-pr-review`**
  PR 审阅阶段 skill，用来把 PR、分支、提交范围或本地 diff 对照已确认需求、任务证据、回归风险和合并准备度进行审查。

- **`briefbound-project-review`**
  项目审查 skill，用来审查整个仓库、架构、技术债、测试缺口、可维护性、接手状态和项目健康。

- **`briefbound-project-dissection`**
  项目拆解教学：从真实数据结构和入口追到业务结果，解释设计取舍与失效边界，并给出阅读路线；不做风险优先的项目审查。

- **`briefbound-simplification-review`**
  当前 diff 的精简审查 skill，用来寻找可删除代码、原生/标准库替代、无效抽象和不必要依赖；不替代正确性审查。

- **`briefbound-simplification-audit`**
  整仓或子系统精简审计 skill，用来形成证据化复杂度 findings 和按风险排序的精简队列。

- **`briefbound-bug-review`**
  紧凑 bug owner，直接完成证据收集、根因定位、最小修复和验证；必要 RED/GREEN 作为内部测试锚点，不再切换 TDD owner。

- **`briefbound-performance-engineering`**
  只承接 `PROFILE`：以代表性负载建立 baseline、定位主要瓶颈、实施一个最小优化并同负载复测；普通功能留在当前 owner 的 `FAST/CHECK`，不强制 benchmark。

- **`briefbound-code-structure-guard`**
  对本轮手写源码执行 `STAY/CHECK/SPLIT` 结构闸门；行数只触发检查，只有职责、变化或测试边界可分时才拆分。

- **`briefbound-evaluation`**
  Briefbound 评估适配器，只在没有更具体的 review、debug、planning、verification、feedback 或 goal skill 承接时使用。

- **`briefbound-project-memory`**
  按用户或项目选择维护跨会话决策、blocker 和正式 handoff；不接管当前执行循环，也不逐 task 同步或渲染。

- **`briefbound-goal-loop`**
  只处理用户明确要求的开放式持续迭代策略；普通有限任务和“继续完成”仍由当前 owner 连续执行。

### 研究流程

- **`briefbound-ai-research-loop`**
  AI 研究工程主流程，负责 baseline 复现、可证伪假设、最小实验、多轮 findings 综合，以及继续、分支、转向或停止决策。

- **`briefbound-research-rigor-review`**
  重要 baseline、反直觉结果和论文级结论晋升前的轻量严谨性审查；普通实验 lane 不强制触发。

- **`briefbound-competition-research-lifecycle`**
  只在请求跨越多个竞赛/benchmark 阶段时协调规则、数据、baseline、claim 和提交依赖；具体工作交给当前最具体 owner，不强制逐阶段 gate 或并行 lane。

### 竞赛与评分

- **`briefbound-score-loop`**
  围绕固定评价协议主动选择候选：利用已有正向信号、探索不同机制或先诊断不确定性；用早停筛选和代表性评价决定是否替换当前最好方案。

- **`briefbound-huawei-nslb-score-loop`**
  Huawei Algorithm Challenge 37 NSLB 的轻量适配层。它从当前项目读取 baseline、hash 和线上反馈，按需调用 solver 搜索、worker、打包与校准工具，不使用写死的旧最佳记录。

### 创意工具

- **`briefbound-creative-toolbox`**
  先判断用户是在生成、扩展、选择、解卡、颠覆、精炼、整理还是命名，再默认只用一个最合适的方法，产出少量具体候选、真实失败方式和可执行第一步。

## 统一管理格式

已发布 skill 统一使用这个目录形状：

```text
skills/<bucket>/<briefbound-skill-name>/
  SKILL.md
  agents/openai.yaml        # 可选，但推荐用于 Codex 斜杠指令 metadata
  references/               # 可选，用于参考资料、模板、ledger 或 schema
  scripts/                  # 可选，用于 skill 自带辅助工具
```

规则：

- `skill-name` 必须和 `SKILL.md` 里的 `name` 字段一致。
- 每次 catalog 变化，都同步更新 `README.md`、`README.zh-CN.md`、对应 bucket 的 `README.md`，以及 `.claude-plugin/plugin.json`。
- 正式安装到 `~/.codex/skills/<briefbound-skill-name>` 时，优先运行 `install.ps1` / `install.sh`，或直接调用 Python 安装器，使用真实目录复制。
- 除非你明确想要重复斜杠条目，否则不要把同一个 skill 同时安装到 `~/.codex/skills` 和 `~/.agents/skills`。

## 仓库结构

```text
.claude-plugin/
  plugin.json
AGENTS.md
CLAUDE.md
INSTALL_PROMPTS.md
install.ps1
install.sh
skills/
  competition/
    README.md
    briefbound-score-loop/
    briefbound-huawei-nslb-score-loop/
  creative/
    README.md
    briefbound-creative-toolbox/
  engineering/
    README.md
    briefbound-project-memory/
    briefbound-autonomous-collaboration-loop/
    briefbound-multi-agent-orchestration/
    briefbound-thread-coordination/
    briefbound-development-cleanup/
    briefbound-router/
    briefbound-ui-design/
    briefbound-visual-design/
    briefbound-ui-review/
    briefbound-design-system/
    briefbound-frontend-engineering/
    briefbound-diagram-design/
    briefbound-feature-reuse-research/
    briefbound-planning/
    briefbound-bdd-tdd-development/
    briefbound-completion-summary/
    briefbound-pr-review/
    briefbound-project-review/
    briefbound-project-dissection/
    briefbound-simplification-review/
    briefbound-simplification-audit/
    briefbound-bug-review/
    briefbound-performance-engineering/
    briefbound-code-structure-guard/
    briefbound-evaluation/
    briefbound-goal-loop/
  research/
    README.md
    briefbound-ai-research-loop/
    briefbound-research-rigor-review/
    briefbound-competition-research-lifecycle/
scripts/
  install_codex_library.py
```

## 安装细节

也可以直接调用 Python 安装器。Windows PowerShell 推荐用 `py -3`；macOS/Linux 推荐用 `python3`。

```powershell
py -3 scripts\install_codex_library.py
```

安装器会先运行 Briefbound package validator，再把已发布 skill 复制成真实目录，检查目录名是否和 `SKILL.md` 的 `name` 字段一致，并在本机存在 Codex `quick_validate.py` 时校验 live skill。`install.ps1` 和 `install.sh` 默认使用 `--process-skill-conflicts disable`，并在 `~/.codex/AGENTS.md` 安装带边界标记的轻量 Briefbound Router 激活块。重复安装只更新受管区段，不覆盖已有规则。

从旧版升级时，安装器先验证新的 `briefbound-*` 副本，再删除能通过 frontmatter 归属校验的对应 `ccdawn-*` live 目录，并把旧激活块原位迁移为 Briefbound Router。旧名称不作为别名保留；无法证明归属的同名目录只报告，不自动删除。

直接调用 Python 安装器时，Briefbound Router 激活默认为只报告状态；显式安装或移除：

```powershell
py -3 scripts\install_codex_library.py --agent codex --router-activation install
py -3 scripts\install_codex_library.py --agent codex --router-activation remove
py -3 scripts\install_codex_library.py --agent grok --router-activation install
py -3 scripts\install_codex_library.py --agent grok --router-activation remove
```

移除激活块不会删除 skills，也不会改动 `AGENTS.md` 中的其他内容。

恢复这些入口：

```powershell
py -3 scripts\install_codex_library.py --agent codex --process-skill-conflicts restore
```

直接调用 Python 安装器时，流程冲突和 Briefbound Router 激活默认都只警告；要获得与仓库快捷脚本相同的行为，显式加 `--process-skill-conflicts disable --router-activation install`。需要单独使用某个 Superpowers skill 时，可先恢复全部入口，再手动保留所需入口；恢复不会改变 Briefbound skills。

只演练安装计划，不改文件：

```powershell
py -3 scripts\install_codex_library.py --dry-run
```

列出当前仓库可安装的 skills：

```powershell
py -3 scripts\install_codex_library.py --list
```

只验证已经安装到 Codex live 目录的副本，不重新安装：

```powershell
py -3 scripts\install_codex_library.py --verify-only
```

只安装部分 skill：

```powershell
py -3 scripts\install_codex_library.py --skill briefbound-router --skill briefbound-project-memory
```

安装目标选项：

```powershell
py -3 scripts\install_codex_library.py --agent codex         # 默认 live Codex 目标
py -3 scripts\install_codex_library.py --agent grok          # Grok Build 原生目标
py -3 scripts\install_codex_library.py --agent codex-grok    # 只同步 Codex 与 Grok
py -3 scripts\install_codex_library.py --agent agents        # 可选本地 catalog 副本
py -3 scripts\install_codex_library.py --agent claude        # 可选 Claude 全局副本
py -3 scripts\install_codex_library.py --agent codex-agents  # Codex 加 .agents
py -3 scripts\install_codex_library.py --agent all           # 所有支持目标
```

只有在明确需要重复入口时，才把同一个 skill 同时安装到 `.codex/skills` 和 `.agents/skills`。

## 斜杠指令排查

如果斜杠条目缺失或重复，先按这个顺序排查，不要先改提示词或随手改目录名：

1. 先看 `~/.codex/skills/<briefbound-skill-name>` 里的 live 安装副本，不要只看仓库副本。
2. 检查是否还存在额外的 `~/.agents/skills/<briefbound-skill-name>` 副本；同一个 skill 两边都装时，Codex 里可能出现重复条目。
3. 检查 live 安装副本里的 `agents/openai.yaml`，并保持它和本仓库里已经验证可用的最小 `interface:` 结构一致。
4. 如果当前激活且受信任的工作区就是这个仓库，也要检查 `.claude-plugin/plugin.json`，因为仓库本地 manifest 也可能影响可见条目。
5. 修改 metadata 后先重启 Codex，再在新线程里验证，不要在旧线程里直接下结论。

## 可选的开发捷径

如果只是临时开发调试，仍然可以把 skills 链接到 `~/.claude/skills`。

macOS/Linux：

```bash
bash scripts/link-skills.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\link-skills.ps1
```

不要把这条链接流程当成这个仓库的正式发布/安装方式。

仓库里的元数据索引在这里：

```text
.claude-plugin/plugin.json
```

真正的 skills 内容在这里：

```text
skills/
```

安装或更新 live skill 后，重启客户端，让它重新加载本地 skills。

## 开发

- [贡献指南](CONTRIBUTING.md)
- [MIT 许可证](LICENSE)

安装后可运行一条低成本、只读的真实 Codex 路由回归：

```powershell
py -3 scripts\run_briefbound_routing_eval.py
```

默认只检查模糊需求是否先进入 Briefbound Router 对齐且不做全仓扫描；`--all` 才运行完整专项路由样本。

Grok Build 安装后可用 `grok inspect --json` 确认 `briefbound-router` 的 source 指向 `~/.grok/skills/briefbound-router/SKILL.md`，并在新 Grok 会话中加载 `~/.grok/AGENTS.md`。

## 使用方式

安装后建议把 `briefbound-router` 作为主入口。用户不需要记固定口令或主动声明流程，正常说需求即可，例如：

- `修一下这个登录 bug`
- `帮我审这个 PR`
- `先审查一下这个项目结构`
- `我要加一个复杂编辑器功能`
- `这个 benchmark 分数退化了，帮我分析并继续优化`
- `连续几个相邻参数都没提升，换一种搜索方向继续优化`
- `这个产品点子太普通，给我三个机制真正不同、今天能试的方向`
- `帮我把这个目标拆成可验证的执行计划`
- `帮我给这个仓库初始化项目记忆`
- `另一个会话也在改这些文件，协调一下并在完成后通知它恢复`

Briefbound Router 会根据意图置信度控制交流成本：

- 需求明确：直接执行或路由，不为了展示流程而追问。
- 需求存在多种合理解释：先读取可查证的上下文；低/中风险不确定时声明假设后继续，只有会改变走向的高影响分叉才用一条消息集中提出并等待校准。
- 讨论时 agent 会用通俗话说明它理解的结果、判断依据和具体建议；用户可以回复 `按建议`、`按推荐`，也可以只指出需要修改的编号。
- 简单结果不套模板；复杂术语只有在影响用户判断或操作时才用一句话解释。
- 信息足够后立即继续，不重复确认已经对齐的内容；只有缺少不可替代输入时才单独询问阻塞问题。
- 对齐后的非简单项目任务会在原生 thread 能力可用时静默发现同项目会话；只有双方原任务都能受益或全局冲突/返工会降低时才建立平级协作。

例如输入 `优化一下这个页面，但我还不确定应该优先改视觉还是操作流程`，Briefbound Router 应先结合现有页面形成判断，再与用户讨论目标结果、改动范围和验收方式，而不是直接改代码或只路由到 UI skill。

这个仓库按本地 skill library 维护。
