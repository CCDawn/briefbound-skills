# Briefbound Router Capability Routing

只在请求主要依赖专用工具、外部服务或文件制品时读取。以下 owner 必须先出现在本轮 Available skills；缺失时使用表中 fallback，不为普通任务临时安装插件。

## 路由表

| 用户目标 | Preferred owner（可用时） | 角色与 fallback |
|---|---|---|
| GitHub 仓库、issue、PR 元信息与一般分诊 | `github:github` | primary；缺失时用 `gh`/git 做最窄读取 |
| 处理 PR review comments | `github:gh-address-comments` | primary；不要退化成重新做整份 PR review |
| GitHub Actions/PR checks 失败 | `github:gh-fix-ci` | primary，`briefbound-bug-review` 仅承接已定位的代码缺陷 |
| 提交、push、创建 draft PR | `github:yeet` | primary；远程写入仍遵守授权和 scope；随后由 Briefbound Router 执行 `Post-PR Closeout Gate` |
| 操作或检查 in-app Browser | `browser:control-in-app-browser` | 工具 owner；UI/bug owner 保留行为判断与最终结论 |
| OpenAI API、Codex、ChatGPT 使用与最新官方说明 | `openai-docs` | primary；只采用官方来源 |
| 生成或编辑位图资产 | `imagegen` | primary；UI/Visual owner 提供用途和验收边界 |
| Figma 通用读写 | `figma:figma-use` | 每次 `use_figma` 前置；按任务叠加下面一个最具体 Figma skill |
| 代码页面生成 Figma 设计 | `figma:figma-generate-design` | 与 `figma:figma-use` 配合，不路由普通前端实现 |
| Figma 设计系统/组件库 | `figma:figma-generate-library` | Design System 判断契约，Figma skill 执行制品写入 |
| Figma 图表、FigJam、Slides、motion、SwiftUI | 对应 `figma:*` 专项 | 只选当前动作需要的一个专项，不加载整套 Figma skills |
| 创建/编辑 Word 文档 | `documents:documents` | primary，遵循渲染验证 |
| PDF 阅读、生成或版面检查 | `pdf:pdf` | primary，视觉版面必须渲染验证 |
| Excel/CSV/独立表格制品 | `spreadsheets:Spreadsheets` | primary；已打开 Excel 会话用 `spreadsheets:excel-live-control` |
| PowerPoint/Slides 演示文稿 | `presentations:Presentations` | primary |
| `.openai/hosting.json` 项目或 Sites 建站 | `sites:sites-building` | primary；发布随后使用 `sites:sites-hosting` |
| 明确要求操作 Windows 应用 | `computer-use:computer-use` | 工具 owner；可用 CLI/API 时优先更稳定的专用能力 |

## 组合规则

- 专项工具拥有“如何操作”，Briefbound owner 拥有“做什么、范围、判断和验收”。同一动作只设一个 primary；工具只是支撑时不重复输出第二份流程。
- PR + UI 运行验证：`briefbound-pr-review` primary，Browser/UI Review 最多一个 support。CI 修复请求则 `github:gh-fix-ci` primary。
- UI 设计并实现仍由 UI/Visual owner 贯穿；Browser、Figma、Imagegen 是按需能力，不产生新阶段。
- 文件制品请求直接命中对应 artifact owner，不先进入 Planning；只有内容、结构或高风险取舍仍未对齐时才回 Briefbound Router。
- 多动作请求按依赖动态组合，例如“修 CI 后 push 并开 PR”依次使用 CI owner、当前代码 owner、发布 owner，不同时加载全部 skill。
- 用户已明确说“修复/处理/实现”时，诊断完成后可在原 scope 内直接实施；专项 owner 的“先检查再修复”是执行顺序，不是再次索要许可。`push`、发布、破坏性操作、权限或范围扩大仍是独立授权边界。
- Preferred owner 不可用时说明能力缺口并使用最低充分 fallback；需要安装指定插件时才进入安装流程。

## 无专项 skill 的软件任务

后端/API、数据库查询与普通 schema 修改、CLI、构建配置、依赖更新、常规测试、容器和一般部署脚本默认由当前代码 owner 直接完成，不因“技能包没有同名 skill”而进入 Planning 或安装新工具。出现真实设计分叉/迁移/发布风险才用 Planning；已有故障用 Bug Review；整仓健康审计用 Project Review；外部复用会改变架构时才用 Feature Reuse Research。

性能症状有明确对象时归 Bug Review；整仓性能结构审计归 Project Review。安全、权限、数据删除和生产发布不靠通用包装 skill 降低风险，沿当前最具体 owner 执行，并保留 Briefbound Router 的授权、迁移和验证闸门。
