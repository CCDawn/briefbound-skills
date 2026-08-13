# UI Preview Approval

前端结果尚未确认时，用隔离的可交互网页让用户在正式实现前预审。预览是自然闸门，不是最终验收，也不扩大生产写入许可。

## 判定

写前端前先选择一个状态：

- `PREVIEW_REQUIRED`：新增页面；信息架构、布局、交互、响应式策略或视觉方向变化；跨组件 UI 改造；存在多个有实质差异的结果；或用户尚未确认最终界面。
- `PREVIEW_SKIPPED`：文案、明确的小样式/溢出修复、已有模式下的机械改动，或用户已批准具体设计稿/预览且实现不改变结果。

只把“代码容易改”当成跳过理由无效。跳过时内部保留一行依据，不生成仪式性报告。

## Owner

- 信息架构、任务流、交互和响应式结果由 `briefbound-ui-design` 生成预览。
- 品牌、字体、色彩、构图、图像、图标和动效方向由 `briefbound-visual-design` 生成预览。
- `briefbound-ui-review` 只读检查预览，输出 `READY_FOR_USER_APPROVAL` 或 `REVISE_RECOMMENDED`；它不能代表用户批准。
- `briefbound-frontend-engineering` 只消费 `APPROVED` 或有依据的 `PREVIEW_SKIPPED` 契约。缺批准证据且命中触发条件时，回到对应设计 owner。

## 隔离预览

优先复用项目技术栈和现有组件，在已有 Storybook/example/preview surface 或任务级临时目录中制作可交互网页。批准前不得修改正式 UI owning surface、生产 route 或共享设计事实源来充当预览。

预览至少包含：

- 可访问的本地 URL；无法启动项目时才降级为独立 HTML/CSS/JS 网页。
- 主要桌面视口、相关移动视口和会改变判断的关键状态。
- 代表性真实文案与安全的确定性 mock 数据。
- 一组能快速比较结果的截图；截图不能替代网页交互。
- 已模拟、未连接或尚未验证的行为说明。

预览禁止使用生产 secret、真实写接口、不可逆操作或线上发布。外部部署属于独立 `REMOTE_WRITE`，没有授权时只提供本地预览。

## 状态与闸门

```text
PREVIEW_REQUIRED
  -> PREVIEW_READY
  -> WAITING_USER_REVIEW
  -> APPROVED | REVISE | ABANDON
```

- `APPROVED` 必须来自用户明确批准或等价表达；沉默、UI Review 通过、测试通过和 Agent 判断都不能代替用户批准。
- `REVISE` 只迭代隔离预览，更新 URL/截图和变化摘要，再回到 `WAITING_USER_REVIEW`。
- `ABANDON` 停止该方向，不修改正式 surface。
- `APPROVED` 后沿已确认契约连续实施，不重复询问是否开始；正式实现仍需测试、浏览器主路径、状态、视口和 console 验收。

预览在正式实现验证前保留；完成后作为已知开发残留清理，除非用户要求保留为 Storybook/example 或设计资产。

## 预审输出

```text
预览已就绪:
- 状态: WAITING_USER_REVIEW
- 预览网页: <local URL>
- 代表截图: <desktop/mobile>
- 覆盖: <主路径、状态与视口>
- 模拟/未验证: <真实缺口>
- 正式代码: 尚未修改
请回复: APPROVED / REVISE <反馈> / ABANDON
```
