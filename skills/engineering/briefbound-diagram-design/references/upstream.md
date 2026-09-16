# 上游来源与同步

- 来源：https://github.com/cathrynlavery/diagram-design
- 固定快照：`ce9344c52cb9be811de187bf2a6d58c712c9c9fe`，manifest 版本 `2.6.23`，2026-09-15 调研版本。
- MIT 原文保存在本 skill 的 `LICENSE`；图标等第三方许可保存在 `third-party-licenses.md`。
- `upstream-manifest.json` 逐文件记录来源、原始 SHA-256 与适配后 SHA-256。

## 选择范围

保留类型/语义/尺寸参考、三种静态模板及可编辑 HTML 示例、图标、三种导入器、输出自检和相关几何/定量检查器。示例用于按类型参考和回归；不一次加载所有示例。品牌流程改写为任务内副本，避免修改安装目录或全局 profile。

不复制上游 GitHub 发布流程、marketplace、commands/prompts、doctor、旧导出/profile 流程、截图目录、画廊 index、维护历史和仓库级发布门禁。Briefbound 管理入口、安装、路由和文档。

## 本地适配

上游路径 `skills/diagram-design/` 改为本 skill 根目录；长 reference 增加目录。原 SKILL 的设计段落提取为 `design-spec.md`；入口、品牌默认行为、导出工具和路由由 Briefbound 维护。品牌初始化等原参考只提供按需知识，不能覆盖本入口的授权边界。上游文档提到未包含的维护脚本和旧宿主 slash command 时，不将其当作本包运行入口。

类型 reference 中对 `scripts/test-*.py` 的提及记录上游如何验证规则；本包运行时只执行实际随包提供的 `scripts/verify-*.py`、`self_check.py` 和 `export_diagram.py`。

## 后续更新

先只读比较当前固定 commit 与候选 commit，再按 manifest 的文件范围更新；核对接口/引用和许可变化，更新原始及适配后的哈希。保留 Briefbound 中文入口和任务边界，不执行上游自动发布，不在每次制图时联网同步。

运行本仓库 `tests/test_diagram_design.py`、包验证和安装测试；导入夹具、自检反例、模板与定量编码须通过。最后生成并查看真实中文 HTML、SVG、PNG，记录浏览器与字体。哈希或静态门禁通过不能替代图意和视觉验证。
