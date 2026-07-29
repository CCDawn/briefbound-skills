---
name: ccdawn-ui-design
description: Use when a CCDawn task needs a new or revised UI/UX direction, information architecture, interaction model, responsive behavior, accessibility decision, or implementable interface contract; do not use for review-only findings, production implementation of an accepted contract, backend work, or mechanical frontend edits.
license: MIT
---

# CCDawn UI Design

## 目标

作为 UI/UX 专项 owner，把用户目标转成可实施、可渲染验证的界面契约。先尊重现有产品和设计系统；只有真实设计分叉会影响结果时才向用户对齐，不把普通前端修改升级成设计流程。

## BRT interface

- Context Boundary: 用户目标、目标页面/组件、现有设计系统、相邻界面、实现技术栈和可运行环境。
- Output Contract: 可实施的界面契约；命中预览闸门时先交付隔离预览 URL、代表截图、覆盖状态和用户批准状态。
- Allowed Action: 在 BRT 授权范围内检查 UI surface；`PREVIEW_REQUIRED` 时只写隔离预览，收到用户 `APPROVED` 后才可修改正式 UI owning surface；不顺带重做品牌、后端协议或无关页面。
- Success Evidence: 预览阶段为可访问网页、桌面/移动截图、关键状态与模拟边界；正式阶段为浏览器截图、DOM/布局、目标视口和交互状态检查。
- Stop Condition: `WAITING_USER_REVIEW`、用户要求 `REVISE/ABANDON`、目标 surface 不明、品牌/设计系统冲突、应用不可运行且代码证据不足，或修改将越过授权边界。
- Route Out: 品牌表达成为主要未知量时转 `ccdawn-visual-design`；只交付方案或需要独立实施 handoff 时转 `ccdawn-frontend-engineering`；已有界面审查转 `ccdawn-ui-review`；跨组件事实源治理转 `ccdawn-design-system`；复杂外部复用决策转 `ccdawn-feature-reuse-research`；验证后的真实残留转 `ccdawn-development-cleanup`；PR 正确性审查转 `ccdawn-pr-review`；阻塞则回 `ccdawn-brt`。

## 统一调用契约

- 只处理 BRT interface 范围；不匹配时回 `ccdawn-brt` 或更具体 owner，复合任务不吞其他 owner。
- 用户可见内容默认中文，完成只报状态、产出、证据和剩余风险；代码、命令、路径、错误原文、API/协议、skill 名和枚举保留原样；Route Out 仅以 BRT interface 为准，末行写 `下一步建议: <一个具体动作>`。

## 触发强度

- `FAST_PATH`：既有模式下的文案、小样式、状态或响应式修复。记录 `PREVIEW_SKIPPED` 依据，直接修改并做目标验证。
- `COMPACT_FLOW`：新增页面/组件或多个相关交互状态。界面结果未批准时先制作隔离预览并等待用户预审。
- `FULL_FLOW`：跨页面信息架构、设计系统、品牌重构、复杂编辑器或高影响可访问性改造。只保留会改变决策的方案和闸门。

默认 0 个问题。用户只说“更好看/更现代”时，先结合产品类型、现有界面和主要任务给出推荐方向；仅当不同方向会显著改变布局、交互或品牌结果时，集中给出 2-3 个具体选项，并标出推荐和代价。

## 单 owner 贯穿

用户同时要求设计并实现时，本 owner 贯穿预览、批准后的正式实施和浏览器验证，不再二次加载 Frontend Engineering。`WAITING_USER_REVIEW` 是必须暂停的自然闸门，不因已有一般实现许可而跳过。只有用户只要设计方案、需要跨会话/独立 owner 交接，或实现范围超出当前授权时才 Route Out。视觉细节和现有 token 使用是本任务内部决策；只有品牌语言或共享事实源成为主要问题时才切换专项 owner。

## 预览批准闸门

继承 BRT 的 `PREVIEW_REQUIRED / PREVIEW_SKIPPED`：

- `PREVIEW_REQUIRED`：新增页面，或信息架构、布局、交互、响应式结果、跨组件 UI 结果尚未获用户确认。
- `PREVIEW_SKIPPED`：文案、明确小修、既有模式机械改动，或已有用户批准的具体设计/预览。
- 预览优先复用项目技术栈、组件和安全 mock 数据，放入已有 preview/example surface 或任务级临时目录；不得先改正式 route、生产组件或真实写接口。
- 必须提供可访问的本地网页、主要桌面/移动截图、关键状态和模拟/未验证说明。项目无法运行时才降级为独立 HTML/CSS/JS 网页。
- 交付后进入 `WAITING_USER_REVIEW`，请用户回复 `APPROVED / REVISE <反馈> / ABANDON`。沉默、测试通过或 Agent/UI Review 判断都不构成批准。
- `REVISE` 只迭代预览；`APPROVED` 后按已确认契约连续修改正式 surface；`ABANDON` 不落地该方向。

## 界面契约

实施或审查前，内部确认最少必要信息：

- 用户与任务：谁在什么场景下，需要看懂、比较、输入或完成什么。
- Surface 与主路径：首屏、主操作、返回/取消，以及 loading、empty、error、disabled、success 等关键状态。
- 信息层级：什么必须先被看到，哪些内容需要扫描、对比、编辑或信任。
- 交互模型：控件类型、反馈、键鼠/触控、破坏性动作与恢复方式。
- 视觉约束：现有 token、组件库、品牌、密度、字体、颜色、图标、动效和图像资产。
- 响应式边界：目标视口、固定格式元素、换行、溢出、最小尺寸和移动端降级。
- 验证面：需要打开的 route、状态和视口。

简单任务不输出完整契约；只把会影响实现或验收的部分说给用户。

## 设计判断

- 先匹配产品目的：运营工具应安静、紧凑、便于扫描；展示或品牌页面可以更强调图像、节奏和动效。
- 先复用相邻页面、组件和 token，再引入新的视觉语言。HeroUI 等库提供 primitives，不自动成为产品设计系统。
- 用合适的原生控件表达选择、模式、数值和危险操作；不要用大量文本按钮或说明文案代替清楚的交互。
- 稳定布局尺寸，覆盖长文本、空数据、错误、加载、选中、焦点、禁用和窄屏；不允许重叠、跳动、裁切或不可达操作。
- 保证语义结构、键盘可达、可见焦点、对比度、目标尺寸和非颜色提示。
- 避免嵌套卡片、装饰性堆叠、单一色调、紧凑面板中的超大字号，以及与产品目标无关的视觉炫技。

## 实施与验证

1. 读取 owning component、样式/token 和相邻页面，确定现有约定。
2. 选择满足用户任务的最小界面方向；复杂复用决策才做外部调研。
3. 命中 `PREVIEW_REQUIRED` 时先完成隔离网页并等待批准；批准前不进入正式实现。
4. 收到 `APPROVED` 或有依据的 `PREVIEW_SKIPPED` 后，在授权 surface 内实施，保持原有数据和行为契约。
5. 可运行时必须用浏览器验证目标路由，至少覆盖主要桌面视口和相关移动视口；检查 console、溢出、交互反馈和关键状态。
6. 画布、3D、图片或动效是核心时，补充像素非空、构图、资源加载或运动证据。

代码检查只能证明结构，不能替代可运行 UI 的视觉证据。浏览器不可用时，明确说明未验证项，不声称“视觉已完成”。

用户可见正文末尾保留：`下一步建议: <一个具体动作>`。
