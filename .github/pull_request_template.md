## 变更目标

<!-- 说明这个 PR 要解决的用户问题和可观察结果。 -->

## 变更范围

<!-- 列出修改的 Skill、脚本或文档，以及明确不包含的范围。 -->

## 验证证据

<!-- 填写实际运行的命令和结果。不要只写“测试通过”。 -->

- [ ] `python scripts/validate_briefbound_skills.py --warnings-as-errors`
- [ ] `python scripts/install_codex_library.py --dry-run`
- [ ] 如修改 Skill 行为，已检查 live copy 或提供前向验证证据

## 路由与兼容性

- [ ] Skill 名称、目录和 `agents/openai.yaml` 保持一致
- [ ] 没有新增强制阶段或让简单任务升级为重流程
- [ ] 用户可见输出默认中文，代码、命令和协议原文保持原样
