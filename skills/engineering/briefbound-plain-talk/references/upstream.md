# Upstream Attribution

本技能的规则经过改编，来自以下 MIT 许可项目：

## b1rdmania/claude-plain-english-skill

- 来源：https://github.com/b1rdmania/claude-plain-english-skill
- 借鉴：AI 腔清理清单的结构（禁客套开场/收尾、禁假平衡、删堆叠限定词、句长混排、不写 diff 式叙事）与"报告改动而非贴全文"原则。
- 改编：原文面向英文成文改写（audit/rewrite/edit 三模式）与英文禁词表；本技能面向中文对话汇报，未采用其英文词表与三模式流程。

## MrGeDiao/shuorenhua

- 来源：https://github.com/MrGeDiao/shuorenhua
- 借鉴：中文判断原则——按内容判断而非词表机械替换；数字、条件、承诺、归属必须保留；引号内容按用途判断。
- 改编：原项目面向成文文档改写（README、Release Note）；本技能面向 agent 工作过程中的对话回复，并新增"默认零代码块、结论先行"条款。
