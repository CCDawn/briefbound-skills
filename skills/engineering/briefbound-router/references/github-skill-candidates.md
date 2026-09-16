# GitHub Skill Candidates

Read this file only when Briefbound Router sees a specialized domain where a GitHub/community skill may outperform the current local fallback, or when the user asks to install/compare external skills.

## Routing rule

External candidates are install-gated:

- If the skill is installed in the current session, route to it.
- If it is not installed, use the local fallback and record the candidate as optional.
- Ask to install only when the fallback cannot produce the required output or the user explicitly wants the external skill.
- Do not route to a missing skill as the only owner.

## High ROI candidates found on GitHub

| Signal | GitHub candidate | Source | Why it matters | Local fallback |
|---|---|---|---|---|
| Frontend UI implementation | `frontend-ui-engineering` | addyosmani/agent-skills | Production UI work needs component architecture, accessibility, responsive behavior, interaction states, and visual polish instead of generic generated UI. | `briefbound-feature-reuse-research` + current project UI patterns + browser verification |
| Distinctive visual design | `frontend-design` | anthropics/skills | Strong when the task is aesthetic direction, typography, palette, layout identity, or avoiding templated frontend output. | Briefbound Router intent lock + local design system scan + browser screenshot review |
| Frontend design review | `frontend-design-review` | microsoft/skills | Useful for PR/UI review, design-system compliance, accessibility, component consistency, and responsive design checks. | `briefbound-project-review` or `briefbound-pr-review` + browser verification |
| React/Next.js performance patterns | `vercel-react-best-practices` | vercel-labs/agent-skills | Vercel-maintained React/Next guidance is more specific for data fetching, bundle, rendering, image, and component performance issues. | `briefbound-performance-engineering` + frontend owner |
| CI/GitHub Actions failures | `gh-fix-ci` | ComposioHQ/awesome-codex-skills | CI logs need check-level evidence, not generic debugging. | `briefbound-bug-review` with CI logs |
| PR review comments | `gh-address-comments` | ComposioHQ/awesome-codex-skills | Maps reviewer comments to safe accept/reject/clarify actions. | `briefbound-pr-review` feedback route |
| Sentry/production stack traces | `sentry-triage` | ComposioHQ/awesome-codex-skills | Production issues need stack-to-source mapping and privacy boundaries. | `briefbound-bug-review` + `root-cause-tracing` |
| Git-history risk scan | `codebase-recon` | ComposioHQ/awesome-codex-skills | Hotspots, bug magnets, and bus factor improve project-review focus. | `briefbound-project-review` with git history probe |
| Browser runtime verification | `browser-testing-with-devtools` | addyosmani/agent-skills | DOM, console, network, screenshot, and performance evidence reduce UI guesswork. | available browser skill or Playwright |
| Browser control with compact snapshots | `agent-browser` | vercel-labs/agent-browser | Ref-based snapshots, clicks, fills, screenshots, and batch actions are useful when MCP output is too noisy or token-heavy. | available browser skill, Chrome DevTools MCP, or Playwright |
| Chrome DevTools MCP server | `chrome-devtools-mcp` | ChromeDevTools/chrome-devtools-mcp | Official DevTools MCP gives live Chrome DOM, console, network, performance, and user-flow evidence for browser tasks. | available browser skill or Playwright |
| Security hardening | `security-and-hardening` | addyosmani/agent-skills | User input, auth, PII, webhooks, uploads, payment, and third-party APIs need threat-model evidence. | `Defense-in-Depth Validation` |
| Performance profiling | `performance-optimization`; `react-component-performance` | addyosmani/agent-skills; Dimillian/Skills | Performance work should measure before optimizing and avoid speculative complexity. | `briefbound-performance-engineering` |
| API/interface design | `api-and-interface-design` | addyosmani/agent-skills | Public contracts, module boundaries, schemas, and props create compatibility risk. | `briefbound-planning` with interface contract |
| Migration/deprecation | `deprecation-and-migration`; `codebase-migrate` | addyosmani/agent-skills; ComposioHQ/awesome-codex-skills | Removing/replacing systems requires consumer, rollout, and rollback evidence. | `briefbound-planning` with TASK_GRAPH when needed |
| Observability | `observability-and-instrumentation` | addyosmani/agent-skills | Logs, metrics, traces, and alerts should be designed with symptom and privacy boundaries. | telemetry contract inside current owner |
| Requirements/spec before coding | `spec-driven-development` | addyosmani/agent-skills | Strong for unclear feature work, significant changes, architectural decisions, or cases where a spec should become the shared source of truth. | `briefbound-router` Intent Lock + `briefbound-planning` |
| Intent interview and rough idea refinement | `interview-me`; `idea-refine` | addyosmani/agent-skills | Useful when the user has a feeling, partial solution, or rough concept and the highest ROI is extracting the real desired outcome before planning. | `briefbound-router` candidate intents/questions + `briefbound-creative-toolbox` when ideation is needed |
| Incremental multi-file implementation | `incremental-implementation` | addyosmani/agent-skills | Thin vertical slices reduce wrong edits when a change spans multiple files but does not need full BDD/TDD ceremony. | `briefbound-planning` TASK_GRAPH with SIMPLE tasks |
| High-risk self-doubt gate | `doubt-driven-development` | addyosmani/agent-skills | Production, security, unfamiliar code, or irreversible decisions need adversarial self-review before confident execution. | Briefbound review matrix + `briefbound-pr-review` or `briefbound-router` |
| Official-doc-grounded implementation | `source-driven-development` | addyosmani/agent-skills | Framework/library APIs drift; source-backed implementation reduces stale-memory bugs and gives citable decisions. | official docs/web research inside current owner |
| Project context and agent rules | `context-engineering` | addyosmani/agent-skills | Useful when agents ignore conventions, hallucinate patterns, or a project needs rules/context setup before work. | local `AGENTS.md` / standards scan + `briefbound-project-review` |
| Code quality review framework | `code-review-and-quality` | addyosmani/agent-skills | Adds a structured correctness/readability/architecture/security/performance gate for nontrivial diffs. | `briefbound-pr-review` |
| Debugging recovery workflow | `debugging-and-error-recovery` | addyosmani/agent-skills | Reproduce, localize, reduce, fix, and guard is a stronger route for messy failures than generic implementation. | `briefbound-bug-review` + `root-cause-tracing` |
| Code simplification and safe cleanup | `code-simplification`; `brooks-lint` | addyosmani/agent-skills; hyhmrright/brooks-lint | Works when code is functional but complex, decayed, overcoupled, or needs architecture/test-quality critique. | `briefbound-project-review` + `briefbound-pr-review` |
| Architecture decisions and ADRs | `documentation-and-adrs` | addyosmani/agent-skills | Public APIs, architecture decisions, and shipped features need durable context for future agents and engineers. | `briefbound-planning` + `briefbound-router` |
| Git, commits, and versioning | `git-workflow-and-versioning` | addyosmani/agent-skills | Commit boundaries, branch hygiene, and reviewable change sizes matter before push, PR, merge, or rollback. | current git tools + `briefbound-pr-review` |
| CI/CD and launch readiness | `ci-cd-and-automation`; `shipping-and-launch`; `deploy-pipeline` | addyosmani/agent-skills; ComposioHQ/awesome-codex-skills | Release, deployment, feature flags, rollback, and pipeline changes need explicit launch evidence. | `briefbound-planning` + `briefbound-router` + `briefbound-pr-review` |
| Issue and backlog triage | `issue-triage`; `linear`; `github-issue-creator` | ComposioHQ/awesome-codex-skills; microsoft/skills | Raw issues, screenshots, logs, and backlog items should become prioritized, scoped work before coding. | `briefbound-router` Intent Bundle + `briefbound-planning` |
| Spec-to-implementation from external workspace | `notion-spec-to-implementation`; `create-plan` | ComposioHQ/awesome-codex-skills | Notion specs or long notes need conversion into implementation contracts and tasks before execution. | `briefbound-planning` |
| MCP server and tool integration | `mcp-builder` | ComposioHQ/awesome-codex-skills; microsoft/skills | Building MCP servers or tool integrations has protocol, evaluation, auth, and packaging pitfalls. | `briefbound-feature-reuse-research` + `briefbound-planning` |
| Web app targeted test runs | `webapp-testing` | ComposioHQ/awesome-codex-skills | Useful when the request is to run web app tests and summarize evidence rather than inspect manually. | browser/Playwright verification + project test scripts |
| Production logs and agent traces | `datadog-logs`; `langsmith-fetch` | ComposioHQ/awesome-codex-skills | Logs and LLM traces need source-linked evidence, privacy boundaries, and digestable failure patterns. | `briefbound-bug-review` + observability fallback |
| Kaggle competition workflow | `nvidia-kaggle-skill`; `kaggle-skill` | NVIDIA/nvidia-kaggle; shepsci/kaggle-skill | Kaggle tasks need competition context, public writeups/notebooks, datasets, local reproduction, and submission workflows. | `briefbound-ai-research-loop` + `briefbound-score-loop` |
| Kaggle score stabilization | `agentic-kaggle-skill` | FrankS-IntelLab/agentic-kaggle-skill | Score stabilization, submission troubleshooting, and kernel workflows are more specific than a generic research lifecycle. | `briefbound-score-loop` |
| Kaggle technique library | `ds-skills` | wenmin-wu/ds-skills | Distilled notebook methods can provide reusable EDA, baseline, feature, validation, and ensembling patterns. | `briefbound-feature-reuse-research` + `briefbound-score-loop` |
| Empirical research skill router | `auto-empirical-research-skills` | brycewang-stanford/Auto-Empirical-Research-Skills | Large empirical pipelines benefit from a router that loads only the relevant child skill instead of a huge lifecycle prompt. | `briefbound-ai-research-loop` |
| Creative method routing | `creative-ideation` | NousResearch/hermes-agent | Best when the agent should pick one fitting ideation method instead of running every creative operator. | `briefbound-creative-toolbox` |
| Deep ideation team | `ideation_team_skill` | bladnman/ideation_team_skill | Useful only for high-value creative sessions that need multi-role debate and synthesis. | `briefbound-creative-toolbox` deep mode |
| Research creative thinking | `creative-thinking-for-research` | Orchestra-Research/AI-Research-SKILLs | Research ideation benefits from cognitive-science-backed frameworks rather than generic brainstorming. | `briefbound-creative-toolbox` |

## Installation note

When the user asks to install one of these, prefer `skill-installer` or the source repo's install command. After installation, restart Codex or open a new thread before expecting auto-trigger metadata to appear.
