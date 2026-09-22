# Codex 一键安装提示词

把下面任意一版提示词复制到新的 Codex 会话里，就可以让 Codex 从 GitHub 安装 Briefbound skill 包。

大多数情况用“普通版”即可。如果你希望 Codex 严格限制操作范围，只做安装相关动作，就用“强约束版”。

## 普通版

```text
请帮我一键安装 Briefbound 的 Codex skills 技能包。

仓库地址：https://github.com/CCDawn/briefbound-skills.git

要求：
1. 如果本机已有这个仓库，就进入仓库并更新到最新 main；如果没有，就 clone 到一个合适的本地目录。
2. 只安装到当前用户的 Codex live skills 目录：~/.codex/skills。
3. 不要安装到 ~/.agents/skills，避免重复 slash-command。
4. 先运行安装演练，再执行正式安装。
5. 安装后验证 live skills 是否可用。
6. 使用安装脚本默认可逆停用安装器识别的完整 Superpowers 自动发现入口集；保留原目录和内容，不要删除。
7. 允许安装器在 ~/.codex/AGENTS.md 中安装带边界标记的 Briefbound Router 激活块；保留已有规则，并确保该区段可以单独移除。
8. 如果存在旧 `ccdawn-*` live skill，先验证对应的新 `briefbound-*` 副本，再让安装器移除通过归属校验的旧副本；不要保留旧别名，也不要删除无法证明归属的目录。
9. 最后用中文汇报：仓库位置、安装目录、安装了哪些 skills、Briefbound Router 激活状态、旧副本迁移、冲突入口处理、验证是否通过、是否需要重启 Codex。
10. 重点提醒我：最重要入口是 briefbound-router；安装后用户正常说需求即可。目标清楚即行动许可，直接推进；低/中风险不确定时先声明假设再继续，只有高影响分叉（改变行为的产策决定、不可逆或用户可见面、安全、数据损失）才用一轮紧凑的建议/对齐并等待校准；只提答案会改变走向的问题，一轮集中提出。Briefbound 自身不创建子 Agent；若运行时提供委派工具，独立可并行的工作可直接派发、无需请示；平级会话协作不转移任务 owner。

如果遇到 Git、Python、网络、权限问题，只问我一个最关键的阻塞问题。
```

## 强约束版

```text
你现在负责一键安装 Briefbound Codex skills 技能包。

Repo:
https://github.com/CCDawn/briefbound-skills.git

目标:
- 安装整个 skill 包，不是只安装 briefbound-router。
- 只安装到当前用户的 Codex live skills 目录：~/.codex/skills。
- 不要安装到 ~/.agents/skills、~/.claude/skills，除非我明确要求。
- 不要修改任何用户项目代码。
- 只允许创建/更新本地 briefbound-skills 仓库、~/.codex/skills 下的安装目录，以及 ~/.codex/AGENTS.md 中带 Briefbound 边界标记的受管激活区段；不得改动该文件的其他规则。
- 安装完成后明确告诉我：briefbound-router 是最重要入口；选择它之后用户正常说需求即可，目标清楚直接推进，低/中风险不确定先声明假设再继续，只有高影响分叉才用一轮紧凑建议并等待校准；其它 skill 通常由 Briefbound Router 自动路由。
- 旧 `ccdawn-*` live skill 只能在对应的新副本验证通过且 frontmatter 归属一致后移除；不保留旧别名，不删除无法验证归属的目录。
- 可逆停用安装器识别的完整 Superpowers 入口集，只允许把对应 `SKILL.md` 重命名为 `SKILL.md.briefbound-disabled`，不得删除目录或内容。

执行步骤:
1. 识别当前系统、shell、Git、Python 是否可用。
2. 找一个合适的本地工作目录保存仓库；如果已有 briefbound-skills 仓库，进入后 git pull；如果没有，从 GitHub clone。
3. 进入仓库根目录。
4. 先运行安装演练：
   - Windows 优先用：powershell -ExecutionPolicy Bypass -File .\install.ps1 -DryRun
   - 如果不适用，Windows 用：py -3 scripts\install_codex_library.py --dry-run --process-skill-conflicts disable --router-activation install
   - macOS/Linux 用：python3 scripts/install_codex_library.py --dry-run --process-skill-conflicts disable --router-activation install
5. 正式安装到 Codex：
   - Windows 优先用：powershell -ExecutionPolicy Bypass -File .\install.ps1
   - 如果不适用，Windows 用：py -3 scripts\install_codex_library.py --agent codex --process-skill-conflicts disable --router-activation install
   - macOS/Linux 用：python3 scripts/install_codex_library.py --agent codex --process-skill-conflicts disable --router-activation install
6. 安装后验证：
   - Windows 优先用：powershell -ExecutionPolicy Bypass -File .\install.ps1 -VerifyOnly
   - 如果不适用，Windows 用：py -3 scripts\install_codex_library.py --verify-only
   - macOS/Linux 用：python3 scripts/install_codex_library.py --verify-only
   - 如果验证器缺失，要明确说明验证器缺失，但仍检查 ~/.codex/skills 下是否存在已安装 skill。
7. 最后中文汇报：
   - 仓库路径
   - 安装目标路径
   - 安装/验证命令
   - 已安装 skill 数量和关键 skill，例如 briefbound-router
   - 最重要入口：briefbound-router；选择它之后用户正常说需求即可，目标清楚直接推进，低/中风险不确定先声明假设再继续，只有高影响分叉才用一轮紧凑建议并等待校准；其它 skill 是下游能力，通常由 Briefbound Router 自动路由
   - 验证结果
   - ~/.codex/AGENTS.md 中 Briefbound Router 受管激活区段的状态，以及 `--router-activation remove` 卸载命令
   - 是否需要重启 Codex 或新开会话
   - 哪些 Superpowers 入口已被可逆停用，以及恢复命令
   - 哪些旧 skill 副本已迁移或因归属不明而保留

失败处理:
- 不要猜测成功。
- 不要跳过验证。
- 不要反复问多个问题。
- 如果 Git、Python、网络、权限或路径阻塞，只问我一个最关键的问题。
```

## 手动安装

如果你想自己执行命令，可以使用：

```powershell
git clone https://github.com/CCDawn/briefbound-skills.git
cd briefbound-skills
powershell -ExecutionPolicy Bypass -File .\install.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -VerifyOnly
```

安装后重启 Codex 或新开会话，让客户端重新加载本地 skills。建议把 `briefbound-router` 作为主入口；之后用户正常说需求即可，Briefbound Router 会自动判断是否需要路由到其它 skill。

Grok Build 使用原生目录和全局规则：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent grok -DryRun
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent grok
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent grok -VerifyOnly
grok inspect --json
```

同时使用 Codex 与 Grok 时，将 `-Agent grok` 改为 `-Agent codex-grok`，不会额外写入 Claude 或 `.agents` catalog。已有 Grok 会话不会重新加载启动时的 skill catalog，需要新开会话。

恢复被停用的 Superpowers 入口：

```powershell
py -3 scripts\install_codex_library.py --agent codex --process-skill-conflicts restore
```
