# 验证与导出

## HTML 验收

命令路径相对于 skill 根目录；输出路径用绝对路径。

```text
python scripts/self_check.py <output.html>
python scripts/verify-geometry.py <output.html>
```

前者验证无障碍和受限脚本/资源契约，后者检查标签遮挡。它们不证明图意、数值或实际排版正确。

对有对应编码的图，再运行 `scripts/verify-<kind>.py <output.html>`：`waterfall`、`sankey`、`treemap`、`polar`、`bubble`、`beeswarm`、`bump`、`slopegraph`、`ridgeline`；带 block 元数据的树运行 `verify-block-registry.py`。声明属性须与对应示例和类型 reference 一致；不得删掉属性来绕过检查。其他类型对照输入人工核验含义。

## 导出

优先使用当前可用的浏览器或本地 Playwright。先检查依赖和浏览器，不自动安装到全局。

```text
python scripts/export_diagram.py <output.html> --format both
```

支持 `--format png|svg|both`、`--scale 2` 和 `--browser-executable <path>`。生成同名 SVG/PNG，原 HTML 保留。该工具先做 HTML 自检，再打开静态最终帧，等待字体加载，将计算后的 SVG 样式内联并截图。SVG 保留文本可编辑性，目标设备缺字体时会替换；PNG 固定像素外观。脚本不覆盖既有文件，需覆盖时显式指定 `--overwrite`。

默认导出 SVG 图本身；用户要求带标题、说明卡片的完整页面时使用浏览器整页截图。每次查看最终 PNG 和单独打开的 SVG：文字、中文字体、箭头、边界、比例及长标签须可辨。不能仅凭自检退出码声称视觉验收通过。

网页字体不可用时使用明确的本地字体并重新检查；严格离线场景移除远程字体依赖。可使用 `Microsoft YaHei`、`Noto Sans CJK SC` 等实际存在且覆盖中文的字体；品牌自定义字体按许可和可用性处理。

若浏览器/Playwright 不可用，保留已生成 HTML 并说明 PNG/SVG 尚未验收，提供所缺依赖的具体信息。不得伪造图片链接或用旧截图代替本次结果。
