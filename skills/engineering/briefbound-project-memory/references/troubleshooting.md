# Troubleshooting

## Contents

- Memory scope and loading failures
- Wrong-file edits and stale HTML
- Visual mode, density, and hierarchy issues
- Lane structure and noise
- Memory-system conflicts and health checks

Read this file when the memory system feels stale, noisy, misplaced, or inconsistent.

## The wrong kind of memory is going into the system

Symptom:

- personal preferences
- generic knowledge
- contact notes
- secrets
- whole chat transcripts

Fix:

- keep `.docs/project-memory/` focused on repository state only
- move personal or global memory to another system
- delete secrets instead of preserving them
- summarize useful conclusions instead of copying transcripts

## The agent ignores existing project memory

Check:

1. `.docs/project-memory/` exists in the repository
2. `AGENTS.md` contains the injected project-memory rules when appropriate
3. the current session actually read `INDEX.md`, `memory.json`, `profile.json`, and the relevant lane before work

Fix:

- re-read the active memory files before continuing
- if the rules block is missing, re-run initialization or add the snippet intentionally

## The wrong files were edited

Rule of thumb:

- update the active lane file for task-local state
- update `memory.json` only for shared metadata and global `recentUpdates`
- do not hand-edit `overview.html` as the primary source unless the user explicitly asks for a one-off manual page

If the change touched too many files, restore discipline on the next sync instead of spreading the mistake further.

## The HTML overview is stale or missing changes

Check:

1. the relevant lane file contains the latest change
2. `memory.json` has the latest `recentUpdates` entry
3. the renderer ran after the edits

Fix:

```bash
python <skill-root>/scripts/render_overview.py <project-root>
```

If needed, re-run the full sync command for the active lane.

## The dashboard feels visually wrong for this repository

Symptoms:

- too editorial for an ops-heavy backend
- too flat or generic for a frontend product repository
- the tone feels mismatched with the kind of work being tracked

Fix:

1. Check `profile.json`
2. Set `visualMode` to a better fit:
   - `briefing`
   - `console`
   - `studio`
   - `lab`
3. Re-run the renderer

Use `visualMode` after `dashboardPreset` when the composition is already right and only the tone feels wrong.

## The dashboard is readable but feels too loose or too cramped

Symptoms:

- backend or automation repos waste vertical space
- frontend review dashboards feel too compressed
- repeated scanning is tiring because the density does not match the work style

Fix:

1. Check `profile.json`
2. Set `density` to a better fit:
   - `comfortable`
   - `balanced`
   - `compact`
3. Re-run the renderer

Use `density` after `dashboardPreset` when the composition is right but the scan rhythm is off.

## The right information is present, but the page hierarchy feels off

Symptoms:

- a high-value section is visually squeezed
- a lightweight section is taking too much width
- the dashboard reads in the wrong rhythm even though the colors and spacing feel fine

Fix:

1. Check `profile.json`
2. Edit `sectionLayouts` for the affected sections:
   - `standard`
   - `narrow`
   - `wide`
   - `full`
3. Re-run the renderer

Use `sectionLayouts` after `dashboardPreset` when the issue is page composition rather than styling.

## I changed `dashboardPreset`, but the page barely moved

Symptoms:

- the preset name changes in `profile.json`
- the rendered page still looks almost the same
- one or more lower-level fields are pinning the old behavior

Fix:

1. Check `profile.json`
2. Keep `dashboardPreset`
3. Remove any explicit keys you no longer want to pin:
   - `visualMode`
   - `density`
   - `sections`
   - `sectionLayouts`
4. Re-run the renderer

`dashboardPreset` is the base layer. Explicit fields override it on purpose.

## The lane model is getting messy

Symptoms:

- temporary lane names
- several lanes covering the same subsystem
- one lane holding unrelated work

Fix:

- use stable responsibility names such as `backend-auth` or `frontend-dashboard`
- merge overlapping lanes deliberately instead of creating near-duplicates
- keep unrelated work in separate lanes even if it happened in the same session

## The memory is noisy

Symptoms:

- long unresolved inbox
- resolved issues still clutter active views
- too many old updates in active arrays

Fix:

- fold useful inbox items into the right lane before closing the task
- move resolved or stale items into `archive/`
- keep active memory focused on current state plus near history

## This is colliding with another memory system

This skill is project-local. It should coexist with:

- chat context
- `AGENTS.md`
- any existing workspace memory files
- user-global memory systems

Do not rewrite other memory systems just because this one exists. If another system already holds a useful summary, link or restate the relevant project fact here instead of trying to merge everything.

## Quick health check

Confirm all of these:

1. `.docs/project-memory/INDEX.md` points to the active files
2. the active lane has the correct owner, focus, and latest update time
3. `recentUpdates` mentions the latest meaningful task
4. `overview.html` reflects the same state as the JSON files
5. `PROJECT_MEMORY.html` opens the overview from the project root
