# Sources

本 skill 为 Briefbound 的轻量原创整合，不在运行时加载本文件。设计时参考：

- [aj-geddes/useful-ai-prompts: profiling-optimization](https://github.com/aj-geddes/useful-ai-prompts/tree/main/skills/profiling-optimization)，MIT：渐进式 profiling 参考和 profile-before-optimize 原则。
- [tswr/engineering-mastery-plugin: performance](https://github.com/tswr/engineering-mastery-plugin/tree/main/skills/performance)，MIT：baseline、warmup、方差、代表性负载和 keep-or-revert 测量闭环。
- [static-web-server/static-web-server: performance](https://github.com/static-web-server/static-web-server/tree/master/.agents/skills/performance)，Apache-2.0：按热路径、benchmark、回归和依赖成本触发性能工作的边界设计。
- [JetBrains/skills: performance-concurrency-advisor](https://github.com/JetBrains/skills/tree/main/performance-concurrency-advisor)：仅作系统瓶颈分类的公开调研对照；未复制其文本。

适配原则：保留通用且可验证的方法，删除语言绑定、固定工具、强制全量审查和多 Agent 编排。
