# Tailwind CSS 操作指南

仅在项目已使用 Tailwind CSS 时读取。本指南约束当前实现方式，不授权安装、升级或迁移 Tailwind。

## 写入前

1. 从 `package.json` 和锁文件确认 Tailwind 主版本及实际包管理器。
2. 读取样式入口、Tailwind 配置、构建插件、主题变量和项目已有的 class 合并工具。
3. 区分 Tailwind v3 配置模式与 v4 CSS-first 模式；不得把 v4 示例机械套到 v3，也不得仅因使用 v4 就删除仍被项目消费的配置。
4. 优先复用项目已有 token、utilities、variants 和响应式断点；不要另建平行样式体系。

## 实施规则

- 优先使用语义 utilities 和项目 token；颜色、间距、圆角、阴影等重复值进入既有主题事实源。
- Tailwind v4 中，需要生成 utilities 的设计 token 使用 `@theme`；只供普通 CSS 使用的变量留在 `:root` 或对应作用域。
- 任意值只用于真正的一次性值；重复出现或承担产品语义时提升到现有 token 体系。
- 条件 class 使用项目已有的 `cn()`、`clsx` 或等价工具；避免字符串拼接造成冲突或无效 class。
- 动态 class 必须保留可被 Tailwind 扫描到的完整字符串；不要由运行时片段拼出 utility 名。
- 优先使用框架内置的响应式、状态、容器和深色模式策略；不要为同一语义并行维护硬编码 light/dark 颜色。
- 保留项目的构建集成。除非任务明确是迁移，不擅自切换 Vite、PostCSS、CSS 入口或动画依赖。

## 验证

- 运行最接近改动的构建或样式检查，确认没有未知 utility、扫描遗漏或 CSS 顺序回归。
- 在受影响的桌面与移动视口检查布局、溢出和交互状态。
- 项目支持主题时检查 light、dark、system 及刷新后的持久化结果。
- 若修复必须升级 Tailwind、替换构建插件、删除配置或重映射全局 token，先说明证据、影响和推荐路径，等待用户确认。

## 参考来源

- Tailwind CSS theme variables: https://tailwindcss.com/docs/theme
- Tailwind CSS utility classes: https://tailwindcss.com/docs/styling-with-utility-classes
- 社区操作配方 `tailwind-theme-builder`: https://github.com/jezweb/claude-skills/blob/main/plugins/frontend/skills/tailwind-theme-builder/SKILL.md
