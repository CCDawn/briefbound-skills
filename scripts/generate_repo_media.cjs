const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");
const sharp = require("sharp");

const repoRoot = path.resolve(__dirname, "..");
const outputDir = path.join(repoRoot, "assets");
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "briefbound-media-"));

const colors = {
  background: "#101216",
  surface: "#191c22",
  surfaceStrong: "#22262e",
  text: "#f5f7fa",
  muted: "#aab2bf",
  line: "#353b46",
  lime: "#c8ff47",
  cyan: "#4dd6c7",
  coral: "#ff7468",
};

function sharedCss(width, height) {
  return `
    * { box-sizing: border-box; }
    html, body { width: ${width}px; height: ${height}px; margin: 0; overflow: hidden; }
    body {
      background: ${colors.background};
      color: ${colors.text};
      font-family: "Microsoft YaHei", "Noto Sans SC", Arial, sans-serif;
      letter-spacing: 0;
      -webkit-font-smoothing: antialiased;
    }
    .mono { font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace; }
  `;
}

function socialPreviewHtml() {
  return `<!doctype html>
  <html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <style>
      ${sharedCss(1280, 640)}
      body { border-top: 8px solid ${colors.lime}; }
      .page { height: 632px; padding: 54px 68px 46px; display: grid; grid-template-columns: 1.55fr 1fr; gap: 58px; }
      .left { display: flex; flex-direction: column; min-width: 0; }
      .eyebrow { color: ${colors.cyan}; font-size: 21px; font-weight: 700; text-transform: uppercase; }
      h1 { margin: 44px 0 0; font-size: 64px; line-height: 1.12; font-weight: 800; }
      h1 span { color: ${colors.lime}; }
      .subtitle { margin-top: 28px; color: ${colors.muted}; font-size: 25px; line-height: 1.55; }
      .signals { margin-top: auto; display: flex; gap: 12px; flex-wrap: wrap; }
      .signal { border: 1px solid ${colors.line}; padding: 10px 15px; font-size: 17px; font-weight: 700; }
      .signal:nth-child(1) { border-color: ${colors.lime}; color: ${colors.lime}; }
      .signal:nth-child(2) { border-color: ${colors.cyan}; color: ${colors.cyan}; }
      .signal:nth-child(3) { border-color: ${colors.coral}; color: ${colors.coral}; }
      .right { border-left: 1px solid ${colors.line}; padding-left: 46px; display: flex; flex-direction: column; justify-content: center; }
      .route-label { color: ${colors.muted}; font-size: 16px; margin-bottom: 18px; }
      .route { display: grid; gap: 10px; }
      .route-step { min-height: 70px; display: grid; grid-template-columns: 44px 1fr; align-items: center; border: 1px solid ${colors.line}; background: ${colors.surface}; padding: 12px 18px; }
      .route-step strong { font-size: 20px; }
      .route-step small { display: block; color: ${colors.muted}; font-size: 14px; margin-top: 4px; }
      .index { color: ${colors.lime}; font-size: 15px; font-weight: 800; }
      .route-step.primary { background: ${colors.lime}; border-color: ${colors.lime}; color: #101216; }
      .route-step.primary .index, .route-step.primary small { color: #303713; }
      .meta { margin-top: 24px; color: ${colors.muted}; font-size: 17px; }
      .meta b { color: ${colors.text}; }
    </style>
  </head>
  <body>
    <main class="page">
      <section class="left">
        <div class="eyebrow mono">Briefbound / Agent Skills</div>
        <h1>约定内自主推进<br><span>约定变化主动商量</span></h1>
        <p class="subtitle">Bound to the brief. Free to build.</p>
        <div class="signals">
          <div class="signal">意图对齐</div>
          <div class="signal">动态路由</div>
          <div class="signal">轻量执行</div>
        </div>
      </section>
      <section class="right">
        <div class="route-label mono">BRIEFBOUND ROUTE</div>
        <div class="route">
          <div class="route-step"><div class="index mono">01</div><div><strong>用户正常表达需求</strong><small>无需记忆命令或流程</small></div></div>
          <div class="route-step primary"><div class="index mono">02</div><div><strong>Briefbound Router 理解与校准</strong><small>只讨论会改变结果的问题</small></div></div>
          <div class="route-step"><div class="index mono">03</div><div><strong>最具体 Skill 接管</strong><small>按子任务风险控制流程重量</small></div></div>
          <div class="route-step"><div class="index mono">04</div><div><strong>实施并验证结果</strong><small>用新鲜证据收口</small></div></div>
        </div>
        <div class="meta"><b>30 Skills</b> · Chinese-first · Codex & Grok</div>
      </section>
    </main>
  </body>
  </html>`;
}

const demoFrames = [
  {
    stage: "BRIEFBOUND / 01",
    accent: colors.lime,
    title: "一个模糊但真实的请求",
    lead: "用户不需要先写完整规格。",
    lines: ["正常说出问题", "Briefbound 判断是否需要追问"],
  },
  {
    stage: "USER / 02",
    accent: colors.coral,
    title: "“这个聊天页面有点卡，帮我优化一下。”",
    lead: "目标存在，但“卡”可能来自渲染、请求或流式更新。",
    lines: ["不直接猜测并修改", "先读取会改变判断的证据"],
  },
  {
    stage: "EVIDENCE / 03",
    accent: colors.cyan,
    title: "先查证，再提问",
    lead: "检查 SSE、active turn 和渲染投影的真实链路。",
    lines: ["排除本地可查的问题", "只保留高影响分叉"],
  },
  {
    stage: "ALIGN / 04",
    accent: colors.lime,
    title: "我理解：降低流式输出卡顿",
    lead: "保持现有交互语义，不顺带重做整个聊天架构。",
    lines: ["结果：增量输出更稳定", "非目标：视觉重设计"],
  },
  {
    stage: "DISCUSS / 05",
    accent: colors.lime,
    title: "推荐先隔离 active row 重渲染",
    lead: "原因：它直接对应已观察到的重算热点，范围最小。",
    lines: ["其他方案：先改查询层", "差异：证据较弱，返工风险更高"],
  },
  {
    stage: "USER / 06",
    accent: colors.coral,
    title: "“按推荐。”",
    lead: "用户只需确认推荐，或纠正不符合预期的一项。",
    lines: ["已对齐部分立即锁定", "不重复询问已经确认的内容"],
  },
  {
    stage: "ROUTE / 07",
    accent: colors.cyan,
    title: "自动组合最具体的 owner",
    lead: "主责：bug review；支持：UI/browser validation。",
    lines: ["Mode：COMPACT_FLOW", "不创建无必要的 worktree 或任务图"],
  },
  {
    stage: "BUILD / 08",
    accent: colors.lime,
    title: "最小充分实施",
    lead: "定位热点 → 隔离当前 turn → 运行针对性验证。",
    lines: ["只改 owning surface", "不扩张到相邻重构"],
  },
  {
    stage: "VERIFY / 09",
    accent: colors.cyan,
    title: "用可观察证据收口",
    lead: "验证 active delta 只刷新当前行，长对话不再整段重算。",
    lines: ["比较预期与实际", "检查回归与副作用"],
  },
  {
    stage: "DONE / 10",
    accent: colors.lime,
    title: "对齐 → 路由 → 实施 → 验证",
    lead: "让高能力模型发挥推理能力，只在真正需要时增加约束。",
    lines: ["github.com/CCDawn/codex-skills", "最重要入口：briefbound-router"],
  },
];

function demoFrameHtml(frame, index) {
  const progress = (index + 1) * 10;
  return `<!doctype html>
  <html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <style>
      ${sharedCss(960, 540)}
      body { border-top: 6px solid ${frame.accent}; }
      .page { height: 534px; padding: 34px 46px 32px; display: flex; flex-direction: column; }
      .header { display: flex; justify-content: space-between; align-items: center; }
      .brand { font-size: 17px; font-weight: 800; }
      .stage { color: ${frame.accent}; font-size: 15px; font-weight: 800; }
      .content { flex: 1; display: grid; grid-template-columns: 1.35fr .8fr; gap: 38px; align-items: center; }
      h1 { margin: 0; font-size: 42px; line-height: 1.25; }
      .lead { margin-top: 22px; color: ${colors.muted}; font-size: 21px; line-height: 1.6; }
      .facts { border-left: 1px solid ${colors.line}; padding-left: 30px; display: grid; gap: 14px; }
      .fact { background: ${colors.surface}; border: 1px solid ${colors.line}; padding: 17px 18px; font-size: 17px; line-height: 1.45; }
      .fact::before { content: ""; display: inline-block; width: 8px; height: 8px; margin-right: 12px; background: ${frame.accent}; }
      .footer { display: grid; grid-template-columns: 1fr auto; gap: 20px; align-items: center; }
      .track { height: 4px; background: ${colors.surfaceStrong}; }
      .progress { height: 4px; width: ${progress}%; background: ${frame.accent}; }
      .count { color: ${colors.muted}; font-size: 14px; }
    </style>
  </head>
  <body>
    <main class="page">
      <header class="header">
        <div class="brand">Briefbound Agent Skills</div>
        <div class="stage mono">${frame.stage}</div>
      </header>
      <section class="content">
        <div>
          <h1>${frame.title}</h1>
          <div class="lead">${frame.lead}</div>
        </div>
        <div class="facts">
          ${frame.lines.map((line) => `<div class="fact">${line}</div>`).join("")}
        </div>
      </section>
      <footer class="footer">
        <div class="track"><div class="progress"></div></div>
        <div class="count mono">${String(index + 1).padStart(2, "0")} / 10</div>
      </footer>
    </main>
  </body>
  </html>`;
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  }
  const browser = await chromium.launch(launchOptions);

  try {
    const socialPage = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 });
    await socialPage.setContent(socialPreviewHtml(), { waitUntil: "load" });
    await socialPage.screenshot({ path: path.join(outputDir, "social-preview.png") });
    await socialPage.close();

    const framePaths = [];
    for (let index = 0; index < demoFrames.length; index += 1) {
      const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
      await page.setContent(demoFrameHtml(demoFrames[index], index), { waitUntil: "load" });
      const framePath = path.join(tempDir, `frame-${String(index).padStart(2, "0")}.png`);
      await page.screenshot({ path: framePath });
      framePaths.push(framePath);
      await page.close();
    }

    await sharp(framePaths, { join: { animated: true } })
      .gif({
        loop: 0,
        delay: demoFrames.map(() => 2000),
        colors: 128,
        effort: 7,
        dither: 0.6,
        keepDuplicateFrames: true,
      })
      .toFile(path.join(outputDir, "briefbound-demo.gif"));

    await sharp(framePaths, { join: { across: 2, animated: false, shim: 12, background: colors.background } })
      .png()
      .toFile(path.join(tempDir, "briefbound-demo-contact.png"));

    console.log(`Generated ${path.relative(repoRoot, outputDir)}\\social-preview.png`);
    console.log(`Generated ${path.relative(repoRoot, outputDir)}\\briefbound-demo.gif`);
    console.log(`Contact sheet ${path.join(tempDir, "briefbound-demo-contact.png")}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
