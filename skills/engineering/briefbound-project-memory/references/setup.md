# Setup

## Contents

- System purpose and boundaries
- First-use decisions
- Project type, dashboard preset, visual mode, and density
- Section layout review
- Initialization, first lane, and first sync

Read this file on first initialization, or when the right project-memory shape is unclear.

## What this system is

This skill creates a project-local memory system under `.docs/project-memory/`.

Use it to preserve durable repository context such as:

- subsystem status
- cross-session decisions
- blockers and follow-up threads
- technical notes worth reloading later
- recent implementation progress

This system complements chat context, `AGENTS.md`, and any built-in memory surface. It does not replace them.

## What this system is not

Do not use this skill as:

- a user-wide personal memory vault
- a contact database
- a generic knowledge base unrelated to the repository
- a place to store secrets, tokens, or credentials
- a dump of full chat transcripts

If the user wants general long-term memory outside a repository, use a different memory system.

## First-use conversation

When setup is user-facing, confirm these points briefly:

1. This memory lives inside the repository, not in a global home-directory store.
2. It will generate structured JSON plus a human-readable HTML overview.
3. It should stay focused on project state, not personal history or unrelated notes.

Initialize only when the user explicitly requests project memory or repository rules require it. Ordinary development work is not implicit permission to add this system.

## Pick the project type

Choose the closest `--project-type`:

- `frontend`: UI-heavy product or site
- `backend`: services, APIs, jobs, data systems
- `automation`: scripts, agent workflows, operational tooling
- `research`: experiments, papers, benchmark work
- `general`: mixed or unclear cases

Prefer the simplest fit. The type only tunes labels and emphasis; it should not become a taxonomy fight.

## Pick the dashboard preset

Choose the closest `--dashboard-preset` when the repository clearly leans toward one working rhythm.

Defaults:

- `general` -> `default`
- `frontend` -> `review-heavy`
- `backend` -> `ops-heavy`
- `automation` -> `ops-heavy`
- `research` -> `research-log`

Use:

- `default` for mixed or neutral repos
- `ops-heavy` for blocker-driven execution and denser operational scanning
- `review-heavy` for product, UX, and stakeholder-facing review loops
- `research-log` for experiment-first work with evidence and decisions near the top

The preset is the first adaptation hook. It sets the baseline section order, emphasis, visual mode, and density.

## Pick the visual mode

Choose a presentation mode only when the preset baseline does not fit the repository culture.

Defaults:

- `general` -> `briefing`
- `frontend` -> `studio`
- `backend` -> `console`
- `automation` -> `console`
- `research` -> `lab`

Override only when the team would benefit from a different dashboard feel.

## Pick the density

Choose how tight the dashboard should feel when the preset default is not enough.

Defaults:

- `general` -> `balanced`
- `frontend` -> `comfortable`
- `backend` -> `compact`
- `automation` -> `compact`
- `research` -> `balanced`

Use:

- `comfortable` for review-heavy or presentation-heavy repos
- `balanced` for mixed day-to-day work
- `compact` for denser operational scanning

## Review the section layout map

Use `sectionLayouts` only when a preset gets the overall rhythm mostly right but a few sections still need different width.

Use it when some sections should occupy more or less width than the default dashboard rhythm. Typical reasons:

- `recentUpdates` should stay full-width
- `issues` or `modules` should be wider in operational repos
- `summary` should stay narrow when other sections need room

Supported values:

- `standard`
- `narrow`
- `wide`
- `full`

## Initialize

Run:

```bash
python <skill-root>/scripts/init_project_memory.py <project-root> --project-type <type> --dashboard-preset <preset> --visual-mode <mode> --density <density> --skip-agents-rules
```

Then confirm:

- `.docs/project-memory/` exists
- `memory.json`, `profile.json`, `overview.html`, `INDEX.md`, and `inbox.json` exist
- `lanes/` and `archive/` exist
- `PROJECT_MEMORY.html` exists at the project root
- `profile.json` contains the intended `projectType` and `dashboardPreset`
- any explicit `visualMode` or `density` overrides appear only when intentionally pinned
- any explicit `sections` or `sectionLayouts` overrides appear only when intentionally customized

Inject the `Project Memory Rules` block into `AGENTS.md` only when the user or repository policy explicitly wants ongoing project-memory behavior; in that case, intentionally omit `--skip-agents-rules`.

## Choose the first lane

Pick a stable responsibility lane that matches the current working slice, for example:

- `frontend-dashboard`
- `backend-auth`
- `automation-release`
- `research-baseline`

Prefer ownership or subsystem language over temporary ticket names.

## First real sync

After the first meaningful task, run one real sync so the system is no longer empty:

```bash
python <skill-root>/scripts/sync_project_memory.py <project-root> --lane <lane> --focus "Initial setup" --update "What changed"
```

Setup is done when:

1. the files exist
2. the lane naming is clear
3. one real update appears in `recentUpdates`
4. `overview.html` and `PROJECT_MEMORY.html` open correctly
