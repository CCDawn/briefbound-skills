# Briefbound Agent Skills

[![Release](https://img.shields.io/github/v/release/CCDawn/codex-skills?display_name=tag)](https://github.com/CCDawn/codex-skills/releases)
[![Validate](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/CCDawn/codex-skills)](LICENSE)
[![Skills](https://img.shields.io/badge/skills-30-2f81f7)](#skill-catalog)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-1f883d)](https://agentskills.io/)
[![skills.sh](https://skills.sh/b/CCDawn/codex-skills)](https://skills.sh/CCDawn/codex-skills)

**Bound to the brief. Free to build.**

Briefbound is a Chinese-first collection of 30 Agent Skills for Codex and Grok Build, covering intent alignment, dynamic routing, peer collaboration and opt-in autonomous closure across existing threads, lightweight development, code-structure guards, performance engineering, cleanup, code review, UI design, and AI research workflows.

- Users describe the task normally. They do not need to invoke `briefbound-router` or memorize a workflow.
- [`briefbound-router`](skills/engineering/briefbound-router/SKILL.md) proceeds immediately when intent is clear. When discussion is needed, it leads with the result, uses plain language, and explains only complex concepts that affect a decision or action.
- Simple work stays simple. Durable plans, embedded task graphs, and compact TDD appear only when the risk justifies them.

**English** | [简体中文](README.md)

## Briefbound Router in 20 Seconds

![Briefbound Router moving from intent alignment to routing, implementation, and verification](assets/briefbound-demo.gif)

This is an illustrative workflow: the user describes the task normally; Briefbound Router inspects available context, discusses only decisions that change the result, and hands the aligned task to the most specific skill. User-facing updates stay focused on the conclusion, supporting evidence, and next action rather than internal routing enums or process ledgers. After alignment, Briefbound Router can discover useful same-project peer threads.

## Quick Start

Preview the main entry skill:

```bash
gh skill preview CCDawn/codex-skills briefbound-router
```

List or install the skills with the Agent Skills CLI:

```bash
npx skills add CCDawn/codex-skills --list
npx skills add CCDawn/codex-skills --skill '*' -g -a codex -y
```

This installs the skill files but does not modify global `AGENTS.md`. Use the repository installer below when you want Briefbound Router to activate automatically from ordinary requests.

For Briefbound's full installation policy, including dry-run, live-copy validation, and reversible conflict handling:

```powershell
git clone https://github.com/CCDawn/codex-skills.git
Set-Location codex-skills
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Install only for Grok Build, or keep Codex and Grok synchronized without extra catalogs:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent grok
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent codex-grok
```

```bash
git clone https://github.com/CCDawn/codex-skills.git
cd codex-skills
sh ./install.sh
```

The repository installer targets `~/.codex/skills` by default and avoids a duplicate `.agents` catalog. The `grok` target uses `~/.grok/skills`; `codex-grok` maintains only those two runtimes. A reversible Briefbound Router activation block is installed in each selected runtime's `AGENTS.md`, preserving existing rules.

When upgrading, the installer validates each new `briefbound-*` live copy before removing its verified `ccdawn-*` predecessor and migrates the old activation block in place. Legacy names are not retained as aliases; a same-named directory that fails the frontmatter ownership check is reported and left untouched.

The wrapper scripts install the activation by default. Direct Python usage is conservative and reports its state unless explicitly requested:

```powershell
py -3 scripts\install_codex_library.py --agent codex --router-activation install
py -3 scripts\install_codex_library.py --agent codex --router-activation remove
py -3 scripts\install_codex_library.py --agent grok --router-activation install
py -3 scripts\install_codex_library.py --agent grok --router-activation remove
```

Run `py -3 scripts\run_briefbound_routing_eval.py` after installation for a low-cost, read-only live routing smoke check.

## What Makes It Different

| Problem | Briefbound approach |
| --- | --- |
| The request is incomplete | Inspect available evidence, then discuss only decisions that change the result |
| Agent updates are dense with jargon | Lead with the result, use plain language, and explain a complex term only when it affects the user's decision or action |
| Many skills exist but routing is manual | Briefbound Router selects the most specific owner and can combine multiple intents |
| Installed GitHub, browser, Figma, or artifact tools are ignored | Briefbound Router routes to currently available capabilities while Briefbound retains intent and acceptance ownership |
| Small changes trigger heavyweight process | Scale workflow weight per subtask and prefer direct implementation plus verification |
| New features may introduce inefficient code | Check obvious inefficiency silently; measure only real hot paths, regressions, or performance targets |
| Development keeps producing giant source files | Apply a `STAY/CHECK/SPLIT` gate to touched hand-written code and split only around durable responsibility boundaries |
| Reviews stop after listing findings | Build a dependency-aware action queue and continue within the agreed boundary |
| Multiple Codex threads develop in one project | Briefbound Router connects useful peer threads so each keeps its own task while negotiating shared contracts, dependencies, and integration |
| Multi-thread work stalls after a conflict | One opt-in enables a recoverable loop that resumes paused peers and verifies integration into local `main` |
| Finished features leave temporary files and stale branches | Clean only known attributable residue or resources covered by an explicit cleanup request |
| Research experiments get treated like software tests | Separate research, score loops, rigor review, and deterministic software TDD |
| Score optimization keeps tuning nearby parameters | Freeze a comparable protocol, then switch deliberately among exploiting positive signals, exploring different mechanisms, and diagnosing uncertainty; prune hopeless candidates early |
| Creative output looks polished but generic | Route by creative phase, use one method by default, reject obvious ideas, and return a few concrete mechanisms with failure modes and first steps |

## Featured Skills

- [`briefbound-router`](skills/engineering/briefbound-router/SKILL.md): intent inference, plain-language alignment, routing, and workflow-weight control.
- [`briefbound-autonomous-collaboration-loop`](skills/engineering/briefbound-autonomous-collaboration-loop/SKILL.md): one opt-in drives peer completion, conflict recovery, verified local-main integration, and cleanup without repeated gates.
- [`briefbound-multi-agent-orchestration`](skills/engineering/briefbound-multi-agent-orchestration/SKILL.md): low-noise peer negotiation across existing same-project threads; it creates no subagents and transfers no task ownership.
- [`briefbound-thread-coordination`](skills/engineering/briefbound-thread-coordination/SKILL.md): shared progress, conflict, discussion, pause/resume, and fast-merge coordination for same-project agents.
- [`briefbound-development-cleanup`](skills/engineering/briefbound-development-cleanup/SKILL.md): post-development residue and safe merged local branch, worktree, and claim cleanup.
- [`briefbound-bug-review`](skills/engineering/briefbound-bug-review/SKILL.md): evidence-driven diagnosis, bounded repair, and verification.
- [`briefbound-performance-engineering`](skills/engineering/briefbound-performance-engineering/SKILL.md): measured bottleneck diagnosis and minimal optimization only for real performance targets, regressions, or hot paths.
- [`briefbound-code-structure-guard`](skills/engineering/briefbound-code-structure-guard/SKILL.md): lightweight protection against multi-responsibility giant files without mechanical line-count splitting.
- [`briefbound-pr-review`](skills/engineering/briefbound-pr-review/SKILL.md): risk-ranked PR and diff review with merge-readiness evidence.
- [`briefbound-ui-design`](skills/engineering/briefbound-ui-design/SKILL.md): UI/UX direction with an isolated interactive preview before high-impact production changes.
- [`briefbound-visual-design`](skills/engineering/briefbound-visual-design/SKILL.md): context-aware brand and visual direction with preview approval before implementation.
- [`briefbound-frontend-engineering`](skills/engineering/briefbound-frontend-engineering/SKILL.md): production implementation of approved or explicitly preview-exempt UI contracts.
- [`briefbound-ui-review`](skills/engineering/briefbound-ui-review/SKILL.md): findings-first review of existing interfaces or isolated previews without replacing user approval.
- [`briefbound-design-system`](skills/engineering/briefbound-design-system/SKILL.md): shared token, theme, component API, variant, and Figma-to-code governance.
- [`briefbound-ai-research-loop`](skills/research/briefbound-ai-research-loop/SKILL.md): baseline reproduction, hypotheses, experiments, ablations, and research synthesis.
- [`briefbound-score-loop`](skills/competition/briefbound-score-loop/SKILL.md): adaptive candidate search under a frozen comparison protocol, with early pruning and evidence-based baseline replacement.
- [`briefbound-huawei-nslb-score-loop`](skills/competition/briefbound-huawei-nslb-score-loop/SKILL.md): live-state Huawei NSLB adapter for solver search, packaging, workers, and online-score calibration when needed.
- [`briefbound-creative-toolbox`](skills/creative/briefbound-creative-toolbox/SKILL.md): phase-routed ideation that defaults to one method and returns a few specific, testable ideas with honest failure modes.
- [`briefbound-feature-reuse-research`](skills/engineering/briefbound-feature-reuse-research/SKILL.md): reuse research for complex feature decisions.

## Skill Catalog

### Engineering

- [`briefbound-router`](skills/engineering/briefbound-router/SKILL.md)
- [`briefbound-autonomous-collaboration-loop`](skills/engineering/briefbound-autonomous-collaboration-loop/SKILL.md)
- [`briefbound-multi-agent-orchestration`](skills/engineering/briefbound-multi-agent-orchestration/SKILL.md)
- [`briefbound-thread-coordination`](skills/engineering/briefbound-thread-coordination/SKILL.md)
- [`briefbound-development-cleanup`](skills/engineering/briefbound-development-cleanup/SKILL.md)
- [`briefbound-bug-review`](skills/engineering/briefbound-bug-review/SKILL.md)
- [`briefbound-pr-review`](skills/engineering/briefbound-pr-review/SKILL.md)
- [`briefbound-project-review`](skills/engineering/briefbound-project-review/SKILL.md)
- [`briefbound-performance-engineering`](skills/engineering/briefbound-performance-engineering/SKILL.md)
- [`briefbound-code-structure-guard`](skills/engineering/briefbound-code-structure-guard/SKILL.md)
- [`briefbound-ui-design`](skills/engineering/briefbound-ui-design/SKILL.md)
- [`briefbound-visual-design`](skills/engineering/briefbound-visual-design/SKILL.md)
- [`briefbound-frontend-engineering`](skills/engineering/briefbound-frontend-engineering/SKILL.md)
- [`briefbound-ui-review`](skills/engineering/briefbound-ui-review/SKILL.md)
- [`briefbound-design-system`](skills/engineering/briefbound-design-system/SKILL.md)
- [`briefbound-feature-reuse-research`](skills/engineering/briefbound-feature-reuse-research/SKILL.md)
- [`briefbound-planning`](skills/engineering/briefbound-planning/SKILL.md)
- [`briefbound-bdd-tdd-development`](skills/engineering/briefbound-bdd-tdd-development/SKILL.md)
- [`briefbound-completion-summary`](skills/engineering/briefbound-completion-summary/SKILL.md)
- [`briefbound-simplification-review`](skills/engineering/briefbound-simplification-review/SKILL.md)
- [`briefbound-simplification-audit`](skills/engineering/briefbound-simplification-audit/SKILL.md)
- [`briefbound-evaluation`](skills/engineering/briefbound-evaluation/SKILL.md)
- [`briefbound-goal-loop`](skills/engineering/briefbound-goal-loop/SKILL.md)
- [`briefbound-project-memory`](skills/engineering/briefbound-project-memory/SKILL.md)

### AI Research and Competition

- [`briefbound-ai-research-loop`](skills/research/briefbound-ai-research-loop/SKILL.md)
- [`briefbound-research-rigor-review`](skills/research/briefbound-research-rigor-review/SKILL.md)
- [`briefbound-competition-research-lifecycle`](skills/research/briefbound-competition-research-lifecycle/SKILL.md)
- [`briefbound-score-loop`](skills/competition/briefbound-score-loop/SKILL.md)
- [`briefbound-huawei-nslb-score-loop`](skills/competition/briefbound-huawei-nslb-score-loop/SKILL.md)

### Creativity

- [`briefbound-creative-toolbox`](skills/creative/briefbound-creative-toolbox/SKILL.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for package rules and validation requirements. The repository is available under the [MIT License](LICENSE).
