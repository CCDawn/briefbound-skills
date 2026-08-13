# HTML Design

## Contents

- Design stance and reusable influences
- Project-memory adaptation and anti-patterns
- Visual direction and dashboard presets
- Visual modes, density, and section layouts
- Implementation constraints

Read this file when editing `scripts/render_overview.py` or when the user explicitly wants a more polished `overview.html`.

## Design stance

Borrow the intentionality of the `frontend-design` skill, but tune it for an operational dashboard rather than a marketing page.

This dashboard should feel like:

- a durable project operations surface
- easy to scan repeatedly during real development
- distinctive enough to avoid default template energy
- restrained enough that status and decisions stay more visible than decoration

## What to borrow

Use these ideas from `frontend-design`:

- pick a clear visual direction instead of accidental defaults
- use a real typography hierarchy, not one flat system-font blob
- use a cohesive palette with a primary accent and a smaller counter-accent
- make spacing, rhythm, and information grouping feel intentional
- give the page atmosphere with subtle structure, not empty flatness

## How to adapt it for project memory

This is not a landing page. Prefer:

- dense but readable information
- predictable navigation
- lane visibility near the top
- strong section hierarchy
- repeated item styling that supports comparison
- quick re-entry for both humans and agents

Page sections should read like full-width bands or dashboard regions, not a pile of floating cards. Repeated records may still use compact cards or rows.

## Anti-patterns

Avoid:

- generic dark-slate SaaS cards everywhere
- purple-gradient-on-white startup styling
- oversized hero copy that pushes the real state below the fold
- nested cards inside cards
- decorative UI that competes with blockers, decisions, or next actions
- whimsical styling that breaks the seriousness of engineering work

## Visual direction for this skill

The default overview should feel like a calm project console:

- mixed neutral base, not one-note blue or purple
- one cool accent for navigation and emphasis
- one warm counter-accent for contrast and categorization
- compact status pills and count chips
- typography that distinguishes titles, metadata, and body copy
- subtle background structure such as fine rules or grid texture

## Dashboard presets

Expose composition families through `profile.json` as `dashboardPreset`.

Current presets:

- `default`: neutral baseline that stays close to project-type defaults
- `ops-heavy`: puts blockers, actions, and execution scanning near the front
- `review-heavy`: gives more room to progress, modules, and review-oriented sections
- `research-log`: keeps evidence, decisions, and ongoing conclusions highly visible

Prefer changing `dashboardPreset` before touching lower-level knobs. It is the highest-level adaptation hook for the page.

## Visual modes

Expose dashboard presentation style through `profile.json` as `visualMode`.

Current modes:

- `briefing`: balanced, neutral, general-purpose project review
- `console`: sharper and more operational for backend or automation work
- `studio`: slightly more editorial and product-facing for frontend-heavy projects
- `lab`: calmer, paper-adjacent, and evidence-friendly for research work

Use `visualMode` after `dashboardPreset` when the information architecture is right but the tone is wrong.

## Density

Expose information density through `profile.json` as `density`.

Current densities:

- `comfortable`: more air, better for presentation and design review
- `balanced`: default middle ground for mixed project work
- `compact`: tighter spacing for operational scanning and heavier dashboards

Use `density` to tune spacing, padding, and scan speed independently from `visualMode`.

## Section layouts

Expose section width preferences through `profile.json` as `sectionLayouts`.

Use per-section values:

- `standard`: default half-width dashboard band
- `narrow`: reduced span for compact summary-style sections
- `wide`: expanded span for heavier sections
- `full`: full-width band for sections that need uninterrupted scanning

Prefer `sectionLayouts` when the preset is close but a few sections still need different emphasis.

## Implementation constraints

Keep the renderer:

- static HTML with inline CSS
- dependency-free
- fast to regenerate
- readable without JavaScript
- robust when sections are empty

Design quality matters, but operational clarity wins every tradeoff.
