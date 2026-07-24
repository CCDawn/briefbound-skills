# shadcn/ui 操作指南

仅在项目已使用 shadcn/ui 或存在 `components.json` 时读取。shadcn 组件是项目拥有的源码；修改前必须尊重本项目的定制和组件 API。

## 写入前

1. 读取 `components.json`、现有 `components/ui`、主题入口、工具函数和相邻消费方式。
2. 使用项目包管理器运行等价的 `shadcn@latest info --json`，确认 style、base、CSS variables、aliases、registries 和实际组件状态。
3. 先检查已安装组件，再通过 shadcn CLI 的 `docs`、`search`、`view` 查找官方或已配置 registry；不要凭记忆重写可复用 primitive。
4. 添加组件前先使用 `add --dry-run` 和 `add --diff` 检查文件、依赖及覆盖范围。未经明确授权不得覆盖现有定制文件。

## 实施规则

- 优先组合现有组件和公开 API；先用内置 `variant`、`size`、slot 与 composition，再考虑新增样式或包装层。
- 使用语义 token，如 `bg-primary`、`text-muted-foreground`；避免原始颜色和为深色模式重复硬编码颜色。
- 使用项目的 `cn()` 合并 class；布局间距优先 `gap-*`，等宽高优先 `size-*`，单行截断优先 `truncate`。
- 表单优先使用 shadcn 提供的 `FieldGroup`、`Field`、label、description 和 message 组合；错误态同时保留可见说明与正确的 `aria-invalid`。
- Button 内图标遵循组件 API；存在 `data-icon` 约定时不再手工覆盖尺寸。对话框、菜单、选择器等保留 Radix 的键盘、焦点和 portal 行为。
- Card、Dialog、Sheet、Empty、Table 等使用完整语义组合，不用无语义 `div` 模拟已有 primitive。
- 新 registry 或第三方组件可能引入依赖、样式和源码所有权；超出当前 surface 时先讨论，不静默扩大范围。

## 验证

- 添加或更新组件后检查实际 diff，确认没有意外覆盖、重复 primitive 或未批准依赖。
- 运行最近的类型、组件或构建检查，并在浏览器验证键盘路径、焦点、disabled、loading、error、空状态和目标视口。
- 同时使用 Tailwind 时继续遵守 `tailwind.md`；shadcn 示例不得覆盖项目现有 Tailwind 版本和主题事实源。
- 若 CLI 输出、项目定制与本指南冲突，以项目代码和官方当前文档为准；会改变组件 API、主题或批准界面时暂停并与用户讨论。

## 参考来源

- 官方 shadcn skill: https://github.com/shadcn-ui/ui/blob/main/skills/shadcn/SKILL.md
- shadcn CLI: https://ui.shadcn.com/docs/cli
- shadcn theming: https://ui.shadcn.com/docs/theming
