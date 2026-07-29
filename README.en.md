# CCDawn Codex Skills

[![Release](https://img.shields.io/github/v/release/CCDawn/codex-skills?display_name=tag)](https://github.com/CCDawn/codex-skills/releases)
[![Validate](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/CCDawn/codex-skills/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/CCDawn/codex-skills)](LICENSE)
[![Skills](https://img.shields.io/badge/skills-30-2f81f7)](#skill-catalog)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-1f883d)](https://agentskills.io/)
[![skills.sh](https://skills.sh/b/CCDawn/codex-skills)](https://skills.sh/CCDawn/codex-skills)

**Let Codex understand what you mean before deciding how to work.**

CCDawn is a Chinese-first collection of 30 Agent Skills for Codex and Grok Build, covering intent alignment, dynamic routing, peer collaboration and opt-in autonomous closure across existing threads, lightweight development, code-structure guards, performance engineering, cleanup, code review, UI design, and AI research workflows.

- Users describe the task normally. They do not need to invoke `/brt` or memorize a workflow.
- [`ccdawn-brt`](skills/engineering/ccdawn-brt/SKILL.md) proceeds immediately when intent is clear and starts a focused discussion only when ambiguity could materially change the result.
- Simple work stays simple. Durable plans, embedded task graphs, and compact TDD appear only when the risk justifies them.

**English** | [简体中文](README.md)

## BRT in 20 Seconds

![BRT moving from intent alignment to routing, implementation, and verification](assets/brt-demo.gif)

This is an illustrative workflow: the user describes the task normally; BRT inspects available context, discusses only decisions that change the result, and hands the aligned task to the most specific skill. After alignment, it can discover existing same-project peer threads when mutual help would reduce duplicate work, conflict, or integration rework.

## Quick Start

Preview the main entry skill:

```bash
gh skill preview CCDawn/codex-skills ccdawn-brt
```

List or install the skills with the Agent Skills CLI:

```bash
npx skills add CCDawn/codex-skills --list
npx skills add CCDawn/codex-skills --skill '*' -g -a codex -y
```

This installs the skill files but does not modify global `AGENTS.md`. Use the repository installer below when you want BRT to activate automatically from ordinary requests.

For CCDawn's full installation policy, including dry-run, live-copy validation, and reversible conflict handling:

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

The repository installer targets `~/.codex/skills` by default and avoids a duplicate `.agents` catalog. The `grok` target uses `~/.grok/skills`; `codex-grok` maintains only those two runtimes. A reversible BRT activation block is installed in each selected runtime's `AGENTS.md`, preserving existing rules.

The wrapper scripts install the activation by default. Direct Python usage is conservative and reports its state unless explicitly requested:

```powershell
py -3 scripts\install_codex_library.py --agent codex --brt-activation install
py -3 scripts\install_codex_library.py --agent codex --brt-activation remove
py -3 scripts\install_codex_library.py --agent grok --brt-activation install
py -3 scripts\install_codex_library.py --agent grok --brt-activation remove
```

Run `py -3 scripts\run_brt_routing_eval.py` after installation for a low-cost, read-only live routing smoke check.

## What Makes It Different

| Problem | CCDawn approach |
| --- | --- |
| The request is incomplete | Inspect available evidence, then discuss only decisions that change the result |
| Many skills exist but routing is manual | BRT selects the most specific owner and can combine multiple intents |
| Installed GitHub, browser, Figma, or artifact tools are ignored | BRT routes to currently available capabilities while CCDawn retains intent and acceptance ownership |
| Small changes trigger heavyweight process | Scale workflow weight per subtask and prefer direct implementation plus verification |
| New features may introduce inefficient code | Check obvious inefficiency silently; measure only real hot paths, regressions, or performance targets |
| Development keeps producing giant source files | Apply a `STAY/CHECK/SPLIT` gate to touched hand-written code and split only around durable responsibility boundaries |
| Reviews stop after listing findings | Build a dependency-aware action queue and continue within the agreed boundary |
| Multiple Codex threads develop in one project | BRT connects useful peer threads so each keeps its own task while negotiating shared contracts, dependencies, and integration |
| Multi-thread work stalls after a conflict | One opt-in enables a recoverable loop that resumes paused peers and verifies integration into local `main` |
| Finished features leave temporary files and stale branches | Clean only known attributable residue or resources covered by an explicit cleanup request |
| Research experiments get treated like software tests | Separate research, score loops, rigor review, and deterministic software TDD |

## Featured Skills

- [`ccdawn-brt`](skills/engineering/ccdawn-brt/SKILL.md): intent inference, collaborative alignment, routing, and workflow-weight control.
- [`ccdawn-autonomous-collaboration-loop`](skills/engineering/ccdawn-autonomous-collaboration-loop/SKILL.md): one opt-in drives peer completion, conflict recovery, verified local-main integration, and cleanup without repeated gates.
- [`ccdawn-multi-agent-orchestration`](skills/engineering/ccdawn-multi-agent-orchestration/SKILL.md): low-noise peer negotiation across existing same-project threads; it creates no subagents and transfers no task ownership.
- [`ccdawn-thread-coordination`](skills/engineering/ccdawn-thread-coordination/SKILL.md): shared progress, conflict, discussion, pause/resume, and fast-merge coordination for same-project agents.
- [`ccdawn-development-cleanup`](skills/engineering/ccdawn-development-cleanup/SKILL.md): post-development residue and safe merged local branch, worktree, and claim cleanup.
- [`ccdawn-bug-review`](skills/engineering/ccdawn-bug-review/SKILL.md): evidence-driven diagnosis, bounded repair, and verification.
- [`ccdawn-performance-engineering`](skills/engineering/ccdawn-performance-engineering/SKILL.md): measured bottleneck diagnosis and minimal optimization only for real performance targets, regressions, or hot paths.
- [`ccdawn-code-structure-guard`](skills/engineering/ccdawn-code-structure-guard/SKILL.md): lightweight protection against multi-responsibility giant files without mechanical line-count splitting.
- [`ccdawn-pr-review`](skills/engineering/ccdawn-pr-review/SKILL.md): risk-ranked PR and diff review with merge-readiness evidence.
- [`ccdawn-ui-design`](skills/engineering/ccdawn-ui-design/SKILL.md): UI/UX direction with an isolated interactive preview before high-impact production changes.
- [`ccdawn-visual-design`](skills/engineering/ccdawn-visual-design/SKILL.md): context-aware brand and visual direction with preview approval before implementation.
- [`ccdawn-frontend-engineering`](skills/engineering/ccdawn-frontend-engineering/SKILL.md): production implementation of approved or explicitly preview-exempt UI contracts.
- [`ccdawn-ui-review`](skills/engineering/ccdawn-ui-review/SKILL.md): findings-first review of existing interfaces or isolated previews without replacing user approval.
- [`ccdawn-design-system`](skills/engineering/ccdawn-design-system/SKILL.md): shared token, theme, component API, variant, and Figma-to-code governance.
- [`ccdawn-ai-research-loop`](skills/research/ccdawn-ai-research-loop/SKILL.md): baseline reproduction, hypotheses, experiments, ablations, and research synthesis.
- [`ccdawn-feature-reuse-research`](skills/engineering/ccdawn-feature-reuse-research/SKILL.md): reuse research for complex feature decisions.

## Skill Catalog

### Engineering

- [`ccdawn-brt`](skills/engineering/ccdawn-brt/SKILL.md)
- [`ccdawn-autonomous-collaboration-loop`](skills/engineering/ccdawn-autonomous-collaboration-loop/SKILL.md)
- [`ccdawn-multi-agent-orchestration`](skills/engineering/ccdawn-multi-agent-orchestration/SKILL.md)
- [`ccdawn-thread-coordination`](skills/engineering/ccdawn-thread-coordination/SKILL.md)
- [`ccdawn-development-cleanup`](skills/engineering/ccdawn-development-cleanup/SKILL.md)
- [`ccdawn-bug-review`](skills/engineering/ccdawn-bug-review/SKILL.md)
- [`ccdawn-pr-review`](skills/engineering/ccdawn-pr-review/SKILL.md)
- [`ccdawn-project-review`](skills/engineering/ccdawn-project-review/SKILL.md)
- [`ccdawn-performance-engineering`](skills/engineering/ccdawn-performance-engineering/SKILL.md)
- [`ccdawn-code-structure-guard`](skills/engineering/ccdawn-code-structure-guard/SKILL.md)
- [`ccdawn-ui-design`](skills/engineering/ccdawn-ui-design/SKILL.md)
- [`ccdawn-visual-design`](skills/engineering/ccdawn-visual-design/SKILL.md)
- [`ccdawn-frontend-engineering`](skills/engineering/ccdawn-frontend-engineering/SKILL.md)
- [`ccdawn-ui-review`](skills/engineering/ccdawn-ui-review/SKILL.md)
- [`ccdawn-design-system`](skills/engineering/ccdawn-design-system/SKILL.md)
- [`ccdawn-feature-reuse-research`](skills/engineering/ccdawn-feature-reuse-research/SKILL.md)
- [`ccdawn-planning`](skills/engineering/ccdawn-planning/SKILL.md)
- [`ccdawn-bdd-tdd-development`](skills/engineering/ccdawn-bdd-tdd-development/SKILL.md)
- [`ccdawn-completion-summary`](skills/engineering/ccdawn-completion-summary/SKILL.md)
- [`ccdawn-simplification-review`](skills/engineering/ccdawn-simplification-review/SKILL.md)
- [`ccdawn-simplification-audit`](skills/engineering/ccdawn-simplification-audit/SKILL.md)
- [`ccdawn-evaluation`](skills/engineering/ccdawn-evaluation/SKILL.md)
- [`ccdawn-goal-loop`](skills/engineering/ccdawn-goal-loop/SKILL.md)
- [`ccdawn-dawn-agent-html-memory`](skills/engineering/ccdawn-dawn-agent-html-memory/SKILL.md)

### AI Research and Competition

- [`ccdawn-ai-research-loop`](skills/research/ccdawn-ai-research-loop/SKILL.md)
- [`ccdawn-research-rigor-review`](skills/research/ccdawn-research-rigor-review/SKILL.md)
- [`ccdawn-competition-research-lifecycle`](skills/research/ccdawn-competition-research-lifecycle/SKILL.md)
- [`ccdawn-score-loop`](skills/competition/ccdawn-score-loop/SKILL.md)
- [`ccdawn-huawei-nslb-score-loop`](skills/competition/ccdawn-huawei-nslb-score-loop/SKILL.md)

### Creativity

- [`ccdawn-creative-toolbox`](skills/creative/ccdawn-creative-toolbox/SKILL.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for package rules and validation requirements. The repository is available under the [MIT License](LICENSE).
