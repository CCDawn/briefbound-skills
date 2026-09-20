# 技能包变更锚点清单

按变更类型勾选；每项完成后跑一次校验器比反复肉眼核对更可靠。

## 新增技能

1. `skills/<bucket>/<skill-name>/SKILL.md`：frontmatter（name / 英文 description / license MIT）+ 目标 + 任务契约 + 统一调用契约 + 激活闸门 + 核心机制 + 输出。
2. `agents/openai.yaml`：display_name、short_description、default_prompt（`$skill-name`）。
3. 按需 `references/*.md`：长清单与示例放参考文件，SKILL.md 只留契约与闸门。
4. router `SKILL.md`：owner 清单加紧凑提及；先压缩既有行，净增量不进 profile 上限。
5. `references/routing-practice.md`：仲裁表加一行；同样先压缩腾位。
6. `.claude-plugin/plugin.json`：skills 数组加路径。
7. 桶 `README.md`（如 `skills/engineering/README.md`）加一行英文简介。
8. `README.zh-CN.md`：精选 Skill 行、完整 skill 目录条目（名称 + 两行说明）、结构树行、徽章 `skills-N`、首段数量文案。
9. `cp README.zh-CN.md README.md`（双份必须逐字节一致）。
10. `README.en.md`：curated 行、完整目录行、徽章、数量文案。
11. `tests/routing_cases.json`：该技能 ≥1 条 primary 用例；进入 ≥1 条其他用例 forbidden。
12. 校验器 `scripts/validate_briefbound_skills.py`：`TOKEN_BUDGETS`（实测 + ~150）、写型技能进 `DIRECT_WRITE_OWNERS`、安全敏感技能加专项 marker 块。

## 修改技能

- 只动语义时：确认 pinned markers 未破坏，跑校验器。
- 改触发/排除语义时：同步 router 提及、routing-practice 行、README 描述与用例 prompt。
- 改 Route Out 指向时：确认目标技能已打包（校验器会查未解析路由）。

## 删除技能

1. 确认语义去向：合并进 router references 或由相邻 owner 承接。
2. 清理锚点：同新增清单的 4–11 项反向操作；徽章与数量文案同步减少。
3. 用例重定向：以它为 primary 的用例改 primary（通常 router）；forbidden 列表里的死名字清除，但每条用例 forbidden 保持非空。
4. 校验器：删 TOKEN_BUDGETS 条目与专项检查块；route_regressions/契约块里对它的引用一并清理。
5. `git rm -r` 技能目录。
6. 手动删除已安装副本：`~/.codex/skills`、`~/.zcode/skills`、`~/.claude/skills`、`~/.cursor/skills` 等目录下的同名目录——安装器只做复制，不会删除消失的技能。

## 验证与交付

1. `python3 scripts/validate_briefbound_skills.py --repo-root .` → 退出码 0，技能数与徽章一致。
2. `python3 -m py_compile scripts/install_codex_library.py scripts/validate_briefbound_skills.py`。
3. `python3 scripts/install_codex_library.py --agent <目标>` 刷新安装并核对目录数量。
4. 提交信息说明技能定位、边界与锚点同步范围；推送后用 head_sha 查 CI。

## 预算速查（上游基线，改动前重测）

- router `SKILL.md` ≈ 2800 上限；alignment profile（+output-forms）3600、maximum profile（+routing-practice+runtime）7200，均贴线。
- `routing-practice.md` 2650、`runtime.md` 1800、`output-forms.md` 900、`collaboration-discovery.md` 900、`capability-routing.md` 1500、`ui-preview-approval.md` 1600。
- 估算公式：CJK 字符 + round(拉丁词数 × 1.3) + 标点 ÷ 3。
