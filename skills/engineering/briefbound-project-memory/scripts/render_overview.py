from __future__ import annotations

import argparse
from copy import deepcopy
from html import escape
from pathlib import Path

from memory_model import (
    aggregate_items,
    list_lanes,
    load_json,
    project_memory_dir,
    update_memory_lane_index,
    write_json,
    write_shortcut,
)
from profile_model import DASHBOARD_PRESET_LABELS, effective_profile
from coordination_model import load_registry as load_coordination_registry
from coordination_model import public_snapshot, registry_path as coordination_registry_path


SECTION_TITLES = {
    "summary": "Current Status",
    "collaboration": "Active Agents",
    "lanes": "Work Lanes",
    "progress": "Progress",
    "modules": "Modules",
    "decisions": "Key Decisions",
    "issues": "Issues",
    "todos": "Next Actions",
    "techNotes": "Technical Notes",
    "recentUpdates": "Recent Updates",
}


SECTION_DESCRIPTIONS = {
    "summary": "Shared repository state carried between sessions.",
    "collaboration": "Live project coordination without storing full conversations in repository memory.",
    "lanes": "Stable responsibility lanes keep concurrent work understandable.",
    "progress": "Milestones and completion signals keep the dashboard honest about motion.",
    "modules": "Subsystem snapshots that highlight active work and current shape.",
    "decisions": "Reasoned choices worth reloading before the next implementation pass.",
    "issues": "Risks, blockers, and investigation threads that still need attention.",
    "todos": "The next concrete actions that should pull the project forward.",
    "techNotes": "High-signal implementation details that are easy to lose in chat history.",
    "recentUpdates": "Chronological change notes for fast re-entry after time away.",
}


TYPE_SUMMARIES = {
    "general": "Project-local memory for ongoing engineering work, decisions, and execution state.",
    "frontend": "A product-surface console for tracking UX work, implementation state, and open interface risk.",
    "backend": "An operational view of services, interfaces, blockers, and implementation choices across the codebase.",
    "automation": "A flow-oriented dashboard for scripts, agents, repeatable jobs, and execution reliability.",
    "research": "A working lab notebook for experiments, evidence, blockers, and evolving project conclusions.",
}


THEME_PRESETS = {
    "briefing": {
        "--bg-top": "#f8faf7",
        "--bg-mid": "#eef2ee",
        "--bg-bottom": "#e7ece6",
        "--surface": "rgba(255, 255, 255, 0.78)",
        "--surface-strong": "#ffffff",
        "--surface-muted": "rgba(245, 247, 244, 0.92)",
        "--ink": "#17211d",
        "--muted": "#5e6c65",
        "--line": "#cfd8d1",
        "--line-strong": "#a7b5ad",
        "--accent": "#0f766e",
        "--accent-strong": "#115e59",
        "--accent-soft": "rgba(15, 118, 110, 0.12)",
        "--counter": "#a65b2e",
        "--counter-soft": "rgba(166, 91, 46, 0.12)",
        "--good": "#2d6a4f",
        "--good-soft": "rgba(45, 106, 79, 0.12)",
        "--warn": "#9a6700",
        "--warn-soft": "rgba(154, 103, 0, 0.12)",
        "--bad": "#a33a35",
        "--bad-soft": "rgba(163, 58, 53, 0.12)",
        "--shadow": "0 14px 40px rgba(23, 33, 29, 0.06)",
    },
    "studio": {
        "--bg-top": "#fbfaf8",
        "--bg-mid": "#f1f0eb",
        "--bg-bottom": "#ece9e1",
        "--surface": "rgba(255, 255, 255, 0.78)",
        "--surface-strong": "#ffffff",
        "--surface-muted": "rgba(247, 245, 240, 0.94)",
        "--ink": "#1f1d1a",
        "--muted": "#6b635c",
        "--line": "#d7cfc6",
        "--line-strong": "#b9ad9f",
        "--accent": "#a64d79",
        "--accent-strong": "#8e4067",
        "--accent-soft": "rgba(166, 77, 121, 0.12)",
        "--counter": "#0f766e",
        "--counter-soft": "rgba(15, 118, 110, 0.12)",
        "--good": "#2d6a4f",
        "--good-soft": "rgba(45, 106, 79, 0.12)",
        "--warn": "#9a6700",
        "--warn-soft": "rgba(154, 103, 0, 0.12)",
        "--bad": "#a33a35",
        "--bad-soft": "rgba(163, 58, 53, 0.12)",
        "--shadow": "0 14px 40px rgba(31, 29, 26, 0.06)",
    },
    "console": {
        "--bg-top": "#f5f8f6",
        "--bg-mid": "#ebf0ec",
        "--bg-bottom": "#e5ebe6",
        "--surface": "rgba(255, 255, 255, 0.8)",
        "--surface-strong": "#ffffff",
        "--surface-muted": "rgba(243, 246, 243, 0.95)",
        "--ink": "#15201c",
        "--muted": "#607068",
        "--line": "#cad6cf",
        "--line-strong": "#a6b7ae",
        "--accent": "#186a8a",
        "--accent-strong": "#15566f",
        "--accent-soft": "rgba(24, 106, 138, 0.12)",
        "--counter": "#5f7a18",
        "--counter-soft": "rgba(95, 122, 24, 0.12)",
        "--good": "#2d6a4f",
        "--good-soft": "rgba(45, 106, 79, 0.12)",
        "--warn": "#9a6700",
        "--warn-soft": "rgba(154, 103, 0, 0.12)",
        "--bad": "#a33a35",
        "--bad-soft": "rgba(163, 58, 53, 0.12)",
        "--shadow": "0 14px 40px rgba(21, 32, 28, 0.06)",
    },
    "lab": {
        "--bg-top": "#f7f8fa",
        "--bg-mid": "#edf0f2",
        "--bg-bottom": "#e5eaee",
        "--surface": "rgba(255, 255, 255, 0.8)",
        "--surface-strong": "#ffffff",
        "--surface-muted": "rgba(244, 246, 248, 0.95)",
        "--ink": "#18202a",
        "--muted": "#606c78",
        "--line": "#ccd5de",
        "--line-strong": "#a8b5c2",
        "--accent": "#2a6f97",
        "--accent-strong": "#245d80",
        "--accent-soft": "rgba(42, 111, 151, 0.12)",
        "--counter": "#9b4d2f",
        "--counter-soft": "rgba(155, 77, 47, 0.12)",
        "--good": "#2d6a4f",
        "--good-soft": "rgba(45, 106, 79, 0.12)",
        "--warn": "#9a6700",
        "--warn-soft": "rgba(154, 103, 0, 0.12)",
        "--bad": "#a33a35",
        "--bad-soft": "rgba(163, 58, 53, 0.12)",
        "--shadow": "0 14px 40px rgba(24, 32, 42, 0.06)",
    },
}


VISUAL_MODE_LABELS = {
    "briefing": "Briefing",
    "console": "Console",
    "studio": "Studio",
    "lab": "Lab",
}


DENSITY_PRESETS = {
    "comfortable": {
        "--page-pad-top": "40px",
        "--page-pad-side": "28px",
        "--page-pad-bottom": "88px",
        "--masthead-gap": "30px",
        "--metric-min-height": "104px",
        "--metric-pad-y": "18px",
        "--metric-pad-x": "18px",
        "--grid-row-gap": "34px",
        "--grid-col-gap": "22px",
        "--band-pad-top": "24px",
        "--section-head-margin": "18px",
        "--key-grid-gap-y": "16px",
        "--key-grid-gap-x": "20px",
        "--card-gap": "12px",
        "--record-pad-y": "16px",
        "--record-pad-x": "18px",
        "--lane-pad": "18px",
        "--count-box-pad-y": "12px",
        "--count-box-pad-x": "12px",
        "--hero-focus-width": "440px",
        "--body-copy-size": "15px",
        "--meta-copy-size": "13px",
    },
    "balanced": {
        "--page-pad-top": "32px",
        "--page-pad-side": "24px",
        "--page-pad-bottom": "72px",
        "--masthead-gap": "24px",
        "--metric-min-height": "92px",
        "--metric-pad-y": "14px",
        "--metric-pad-x": "16px",
        "--grid-row-gap": "28px",
        "--grid-col-gap": "20px",
        "--band-pad-top": "20px",
        "--section-head-margin": "16px",
        "--key-grid-gap-y": "12px",
        "--key-grid-gap-x": "18px",
        "--card-gap": "10px",
        "--record-pad-y": "14px",
        "--record-pad-x": "16px",
        "--lane-pad": "16px",
        "--count-box-pad-y": "10px",
        "--count-box-pad-x": "12px",
        "--hero-focus-width": "420px",
        "--body-copy-size": "14px",
        "--meta-copy-size": "12px",
    },
    "compact": {
        "--page-pad-top": "24px",
        "--page-pad-side": "20px",
        "--page-pad-bottom": "56px",
        "--masthead-gap": "18px",
        "--metric-min-height": "82px",
        "--metric-pad-y": "12px",
        "--metric-pad-x": "14px",
        "--grid-row-gap": "22px",
        "--grid-col-gap": "16px",
        "--band-pad-top": "16px",
        "--section-head-margin": "12px",
        "--key-grid-gap-y": "10px",
        "--key-grid-gap-x": "14px",
        "--card-gap": "8px",
        "--record-pad-y": "12px",
        "--record-pad-x": "14px",
        "--lane-pad": "14px",
        "--count-box-pad-y": "8px",
        "--count-box-pad-x": "10px",
        "--hero-focus-width": "380px",
        "--body-copy-size": "13px",
        "--meta-copy-size": "11px",
    },
}


DENSITY_LABELS = {
    "comfortable": "Comfortable",
    "balanced": "Balanced",
    "compact": "Compact",
}


def project_counts(memory: dict, lanes: list[dict]) -> dict:
    modules = aggregate_items(memory, lanes, "modules")
    issues = aggregate_items(memory, lanes, "issues")
    decisions = aggregate_items(memory, lanes, "decisions")
    todos = aggregate_items(memory, lanes, "todos")
    updates = aggregate_items(memory, lanes, "recentUpdates")
    return {
        "modules": len(modules),
        "open_issues": len([item for item in issues if item.get("status") != "resolved"]),
        "decisions": len(decisions),
        "open_todos": len([item for item in todos if item.get("status") != "done"]),
        "updates": len(updates),
        "lanes": len(lanes),
    }


def render_index(memory: dict, profile: dict, lanes: list[dict]) -> str:
    resolved_profile = effective_profile(profile)
    project = memory.get("project", {})
    summary = memory.get("summary", {})
    counts = project_counts(memory, lanes)
    collaboration = memory.get("_coordination", {})
    active_agents = len(
        [item for item in collaboration.get("agents", []) if item.get("state") not in {"completed", "stale"}]
    )
    open_coordination = len(
        [item for item in collaboration.get("coordinations", []) if item.get("state") != "resolved"]
    )
    return f"""# Project Memory Index

## Overview

- Project: {project.get("name", "Unknown")}
- Type: {project.get("type", resolved_profile.get("projectType", "general"))}
- Dashboard preset: {DASHBOARD_PRESET_LABELS.get(resolved_profile.get("dashboardPreset", "default"), "Default")}
- Visual mode: {VISUAL_MODE_LABELS.get(resolved_profile.get("visualMode", "briefing"), "Briefing")}
- Density: {DENSITY_LABELS.get(resolved_profile.get("density", "balanced"), "Balanced")}
- Last updated: {summary.get("lastUpdated", "Unknown")}
- Work lanes: {counts["lanes"]}
- Active agents: {active_agents}
- Open coordination: {open_coordination}

## Files

- [overview.html](./overview.html)
- [memory.json](./memory.json)
- [profile.json](./profile.json)
- [inbox.json](./inbox.json)
- [lanes/](./lanes/)
- [archive/](./archive/)
- [../../PROJECT_MEMORY.html](../../PROJECT_MEMORY.html)

## Active Counts

| Section | Count |
|---|---:|
| Work lanes | {counts["lanes"]} |
| Modules | {counts["modules"]} |
| Open issues | {counts["open_issues"]} |
| Decisions | {counts["decisions"]} |
| Open todos | {counts["open_todos"]} |
| Recent updates | {counts["updates"]} |

## Focus

- Current phase: {summary.get("currentPhase", "Shared memory active")}
- Current focus: {summary.get("focus", "See active lanes")}
- Health: {summary.get("health", "green")}
"""


def label_for(section: str, profile: dict) -> str:
    return profile.get("labels", {}).get(section, SECTION_TITLES.get(section, section))


def theme_for(profile: dict) -> dict:
    visual_mode = str(profile.get("visualMode", "briefing"))
    return THEME_PRESETS.get(visual_mode, THEME_PRESETS["briefing"])


def section_note(section: str) -> str:
    return SECTION_DESCRIPTIONS.get(section, "")


def band_class(layout_name: str) -> str:
    return f"band {layout_name}" if layout_name in {"narrow", "wide", "full"} else "band"


def normalize_percent(value: object) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def tone_class(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "neutral"
    if any(bit in text for bit in ("blocked", "critical", "error", "failed", "red")):
        return "bad"
    if any(bit in text for bit in ("warn", "warning", "yellow", "risk", "pending", "hold")):
        return "warn"
    if any(bit in text for bit in ("done", "resolved", "healthy", "green", "complete", "ready", "active")):
        return "good"
    return "neutral"


def pill(text: object, tone: str | None = None) -> str:
    label = str(text or "Unknown").strip() or "Unknown"
    return f'<span class="pill {escape(tone or tone_class(label))}">{escape(label)}</span>'


def tag(label: str, value: object, *, tone: str = "neutral") -> str:
    return f'<span class="tag {escape(tone)}">{escape(label)}: {escape(str(value))}</span>'


def html_page(title: str, body: str, theme: dict, density_tokens: dict) -> str:
    theme_vars = "\n".join(f"      {name}: {value};" for name, value in theme.items())
    density_vars = "\n".join(f"      {name}: {value};" for name, value in density_tokens.items())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
{theme_vars}
{density_vars}
    }}
    * {{
      box-sizing: border-box;
    }}
    html {{
      color-scheme: light;
    }}
    body {{
      margin: 0;
      font-family: "Aptos", "Segoe UI Variable Text", "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg-mid) 42%, var(--bg-bottom) 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(rgba(23, 33, 29, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(23, 33, 29, 0.035) 1px, transparent 1px);
      background-size: 32px 32px;
      opacity: 0.28;
    }}
    .page {{
      position: relative;
      max-width: 1420px;
      margin: 0 auto;
      padding: var(--page-pad-top) var(--page-pad-side) var(--page-pad-bottom);
      font-size: var(--body-copy-size);
    }}
    .masthead {{
      display: grid;
      gap: var(--masthead-gap);
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line-strong);
    }}
    .masthead-top {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-end;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 12px 0;
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .eyebrow::before {{
      content: "";
      width: 20px;
      height: 1px;
      background: var(--accent);
    }}
    .title-block h1 {{
      margin: 0;
      font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", sans-serif;
      font-size: clamp(34px, 5vw, 62px);
      line-height: 0.95;
      letter-spacing: 0;
    }}
    .title-block p {{
      margin: 12px 0 0 0;
      max-width: 66ch;
      color: var(--muted);
      line-height: 1.55;
    }}
    .hero-focus {{
      width: min(var(--hero-focus-width), 100%);
      padding-left: 18px;
      border-left: 2px solid var(--line);
    }}
    .hero-focus strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .hero-focus span {{
      display: block;
      margin-top: 10px;
      font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", sans-serif;
      font-size: 21px;
      line-height: 1.2;
    }}
    .hero-focus p {{
      margin: 10px 0 0 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }}
    .metric {{
      min-height: var(--metric-min-height);
      padding: var(--metric-pad-y) var(--metric-pad-x);
      background: var(--surface);
      border-right: 1px solid var(--line);
      box-shadow: var(--shadow);
    }}
    .metric:last-child {{
      border-right: none;
    }}
    .metric-label {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .metric-value {{
      display: block;
      margin-top: 12px;
      font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", sans-serif;
      font-size: 30px;
      line-height: 1;
    }}
    .metric-note {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: var(--meta-copy-size);
      line-height: 1.4;
    }}
    .dashboard-grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: var(--grid-row-gap) var(--grid-col-gap);
      margin-top: 34px;
    }}
    .band {{
      grid-column: span 6;
      padding-top: var(--band-pad-top);
      border-top: 1px solid var(--line-strong);
    }}
    .band.full {{
      grid-column: 1 / -1;
    }}
    .band.narrow {{
      grid-column: span 4;
    }}
    .band.wide {{
      grid-column: span 8;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      margin-bottom: var(--section-head-margin);
    }}
    .section-head h2 {{
      margin: 0;
      font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", sans-serif;
      font-size: 22px;
      line-height: 1.1;
    }}
    .section-note {{
      margin: 7px 0 0 0;
      max-width: 62ch;
      color: var(--muted);
      line-height: 1.5;
    }}
    .section-meta {{
      color: var(--muted);
      font-size: var(--meta-copy-size);
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      text-align: right;
    }}
    .muted {{
      color: var(--muted);
    }}
    .key-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: var(--key-grid-gap-y) var(--key-grid-gap-x);
    }}
    .kv {{
      min-width: 0;
      padding-bottom: 12px;
      border-bottom: 1px dashed var(--line);
    }}
    .kv strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .kv span {{
      display: block;
      margin-top: 6px;
      line-height: 1.45;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 28px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.75);
      color: var(--ink);
      font-size: 12px;
      font-weight: 700;
      line-height: 1;
      white-space: nowrap;
    }}
    .pill.good {{
      color: var(--good);
      border-color: rgba(45, 106, 79, 0.26);
      background: var(--good-soft);
    }}
    .pill.warn {{
      color: var(--warn);
      border-color: rgba(154, 103, 0, 0.26);
      background: var(--warn-soft);
    }}
    .pill.bad {{
      color: var(--bad);
      border-color: rgba(163, 58, 53, 0.26);
      background: var(--bad-soft);
    }}
    .pill.neutral {{
      color: var(--accent-strong);
      border-color: rgba(15, 118, 110, 0.22);
      background: var(--accent-soft);
    }}
    .progress-bar {{
      height: 12px;
      margin-top: 14px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(23, 33, 29, 0.08);
    }}
    .progress-bar span {{
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent) 0%, var(--counter) 100%);
    }}
    .lane-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 12px;
    }}
    .lane-card {{
      padding: var(--lane-pad);
      border: 1px solid var(--line);
      border-radius: 6px;
      background: linear-gradient(180deg, var(--surface-strong) 0%, var(--surface-muted) 100%);
      box-shadow: var(--shadow);
    }}
    .lane-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .lane-top h3 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.3;
    }}
    .lane-kicker {{
      display: inline-block;
      margin-bottom: 8px;
      color: var(--counter);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .lane-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
      color: var(--muted);
      font-size: var(--meta-copy-size);
      line-height: 1.4;
    }}
    .lane-focus {{
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px dashed var(--line);
      line-height: 1.55;
    }}
    .count-row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 14px;
    }}
    .count-box {{
      min-width: 0;
      padding: var(--count-box-pad-y) var(--count-box-pad-x);
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.66);
    }}
    .count-box strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .count-box span {{
      display: block;
      margin-top: 7px;
      font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", "Trebuchet MS", sans-serif;
      font-size: 22px;
      line-height: 1;
    }}
    .records {{
      display: grid;
      gap: var(--card-gap);
    }}
    .record {{
      padding: var(--record-pad-y) var(--record-pad-x);
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }}
    .record-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .record h3 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
    }}
    .record-tags,
    .related-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: var(--meta-copy-size);
      line-height: 1;
      white-space: nowrap;
    }}
    .tag.good {{
      color: var(--good);
      background: var(--good-soft);
    }}
    .tag.warn {{
      color: var(--warn);
      background: var(--warn-soft);
    }}
    .tag.bad {{
      color: var(--bad);
      background: var(--bad-soft);
    }}
    .tag.neutral {{
      color: var(--accent-strong);
      background: var(--accent-soft);
    }}
    .record-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px 14px;
    }}
    .record-grid div {{
      min-width: 0;
    }}
    .record-grid strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .record-grid span {{
      display: block;
      margin-top: 5px;
      line-height: 1.5;
      word-break: break-word;
    }}
    .related-tags {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed var(--line);
    }}
    .footer {{
      margin-top: 36px;
      padding-top: 18px;
      border-top: 1px solid var(--line-strong);
      color: var(--muted);
      font-size: var(--meta-copy-size);
      line-height: 1.5;
    }}
    @media (max-width: 980px) {{
      .band,
      .band.full,
      .band.narrow,
      .band.wide {{
        grid-column: 1 / -1;
      }}
      .hero-focus {{
        width: 100%;
        padding-left: 0;
        padding-top: 14px;
        border-left: none;
        border-top: 1px solid var(--line);
      }}
      .metric {{
        border-right: none;
        border-bottom: 1px solid var(--line);
      }}
      .metrics {{
        border-bottom: none;
      }}
      .count-row {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    {body}
  </main>
</body>
</html>
"""


def render_summary(memory: dict, *, title: str = "Current Status", layout_name: str = "narrow") -> str:
    summary = memory.get("summary", {})
    health = summary.get("health", "green")
    rows = [
        ("Phase", escape(summary.get("currentPhase", "Shared memory active"))),
        ("Focus", escape(summary.get("focus", "See active lanes"))),
        ("Health", pill(health)),
        ("Last Updated", escape(summary.get("lastUpdated", "Unknown"))),
    ]
    content = "".join(
        f'<div class="kv"><strong>{escape(label)}</strong><span>{value}</span></div>' for label, value in rows
    )
    return f"""
    <section class="{band_class(layout_name)}">
      <div class="section-head">
        <div>
          <h2>{escape(title)}</h2>
          <p class="section-note">{escape(section_note("summary"))}</p>
        </div>
        <div class="section-meta">Shared state</div>
      </div>
      <div class="key-grid">{content}</div>
    </section>
    """


def render_progress(memory: dict, *, title: str = "Progress", layout_name: str = "wide") -> str:
    progress = memory.get("progress", {})
    percent = normalize_percent(progress.get("percent", 0))
    status = progress.get("status", "Unknown")
    milestones = progress.get("milestones", [])
    milestone_items = []
    for item in milestones:
        note = item.get("note")
        details = [
            f'<div><strong>Status</strong><span>{pill(item.get("status", "Unknown"))}</span></div>'
        ]
        if note:
            details.append(f'<div><strong>Note</strong><span>{escape(str(note))}</span></div>')
        milestone_items.append(
            f"""
            <article class="record">
              <div class="record-head">
                <h3>{escape(item.get("title", "Milestone"))}</h3>
                <div class="record-tags">{pill(item.get("status", "Unknown"))}</div>
              </div>
              <div class="record-grid">{''.join(details)}</div>
            </article>
            """
        )
    milestones_html = "".join(milestone_items) or '<p class="muted">No milestones recorded.</p>'
    return f"""
    <section class="{band_class(layout_name)}">
      <div class="section-head">
        <div>
          <h2>{escape(title)}</h2>
          <p class="section-note">{escape(section_note("progress"))}</p>
        </div>
        <div class="section-meta">{percent}% complete</div>
      </div>
      <div class="key-grid">
        <div class="kv"><strong>Status</strong><span>{escape(str(status))}</span></div>
        <div class="kv"><strong>Completion</strong><span>{percent}%</span></div>
      </div>
      <div class="progress-bar"><span style="width: {percent}%"></span></div>
      <div class="records" style="margin-top: 14px;">{milestones_html}</div>
    </section>
    """


def render_lanes(memory: dict, *, title: str = "Work Lanes", layout_name: str = "full") -> str:
    lanes = memory.get("lanes", [])
    if not lanes:
        return f"""
        <section class="{band_class(layout_name)}">
          <div class="section-head">
            <div>
              <h2>{escape(title)}</h2>
              <p class="section-note">{escape(section_note("lanes"))}</p>
            </div>
            <div class="section-meta">No lanes yet</div>
          </div>
          <p class="muted">No work lanes recorded yet.</p>
        </section>
        """
    cards = []
    for lane in lanes:
        health = lane.get("health", "green")
        cards.append(
            f"""
            <article class="lane-card">
              <div class="lane-top">
                <div>
                  <span class="lane-kicker">Lane {escape(lane.get("id", ""))}</span>
                  <h3>{escape(lane.get("title", "Untitled Lane"))}</h3>
                </div>
                {pill(health)}
              </div>
              <div class="lane-meta">
                <span>Owner: {escape(lane.get("owner", "shared-session"))}</span>
                <span>Phase: {escape(lane.get("phase", "Active"))}</span>
                <span>Updated: {escape(lane.get("lastUpdated", ""))}</span>
              </div>
              <div class="lane-focus">
                <strong>Focus</strong>
                <div>{escape(lane.get("focus", "")) or "Unspecified"}</div>
              </div>
              <div class="count-row">
                <div class="count-box">
                  <strong>Open Todos</strong>
                  <span>{lane.get("openTodos", 0)}</span>
                </div>
                <div class="count-box">
                  <strong>Open Issues</strong>
                  <span>{lane.get("openIssues", 0)}</span>
                </div>
                <div class="count-box">
                  <strong>Updates</strong>
                  <span>{lane.get("updates", 0)}</span>
                </div>
              </div>
            </article>
            """
        )
    return f"""
    <section class="{band_class(layout_name)}">
      <div class="section-head">
        <div>
          <h2>{escape(title)}</h2>
          <p class="section-note">{escape(section_note("lanes"))}</p>
        </div>
        <div class="section-meta">{len(lanes)} lanes</div>
      </div>
      <div class="lane-grid">{''.join(cards)}</div>
    </section>
    """


def render_collaboration(memory: dict, *, title: str = "Active Agents", layout_name: str = "full") -> str:
    collaboration = memory.get("_coordination", {})
    agents = [item for item in collaboration.get("agents", []) if item.get("state") != "completed"]
    open_items = [item for item in collaboration.get("coordinations", []) if item.get("state") != "resolved"]
    if not agents and not open_items:
        return ""

    cards = []
    for agent in agents:
        scopes = ", ".join(agent.get("scopes", [])) or "Unclaimed"
        checkpoint = agent.get("lastCheckpoint") or agent.get("currentAction") or "No checkpoint published"
        blocker = agent.get("blocker") or "None"
        cards.append(
            f"""
            <article class="lane-card">
              <div class="lane-top">
                <div>
                  <span class="lane-kicker">{escape(agent.get("id", "agent"))}</span>
                  <h3>{escape(agent.get("label", "Agent"))}</h3>
                </div>
                {pill(agent.get("state", "unknown"))}
              </div>
              <div class="lane-meta">
                <span>Branch: {escape(agent.get("branch") or "-")}</span>
                <span>Stage: {escape(agent.get("stage") or "-")}</span>
                <span>Updated: {escape(agent.get("updatedAt") or "-")}</span>
              </div>
              <div class="lane-focus"><strong>Task</strong><div>{escape(agent.get("task") or "Unspecified")}</div></div>
              <div class="record-grid">
                <div><strong>Scopes</strong><span>{escape(scopes)}</span></div>
                <div><strong>Checkpoint</strong><span>{escape(checkpoint)}</span></div>
                <div><strong>Blocker</strong><span>{escape(blocker)}</span></div>
              </div>
            </article>
            """
        )

    coordination_html = ""
    if open_items:
        coordination_html = '<div class="records" style="margin-top: 14px;">' + "".join(
            f"""
            <article class="record">
              <div class="record-head">
                <h3>{escape(item.get("topic") or "Coordination")}</h3>
                <div class="record-tags">{pill(item.get("kind", "coordination"))}</div>
              </div>
              <div class="record-grid">
                <div><strong>Owner</strong><span>{escape(item.get("ownerAgentId") or "-")}</span></div>
                <div><strong>Participants</strong><span>{escape(", ".join(item.get("participants", [])) or "-")}</span></div>
                <div><strong>Surfaces</strong><span>{escape(", ".join(item.get("surfaces", [])) or "-")}</span></div>
              </div>
            </article>
            """
            for item in open_items
        ) + "</div>"

    return f"""
    <section class="{band_class(layout_name)}">
      <div class="section-head">
        <div>
          <h2>{escape(title)}</h2>
          <p class="section-note">{escape(section_note("collaboration"))}</p>
        </div>
        <div class="section-meta">{len(agents)} agents / {len(open_items)} open</div>
      </div>
      <div class="lane-grid">{''.join(cards)}</div>
      {coordination_html}
    </section>
    """


def render_named_items(items: list[dict], empty_text: str, fields: list[tuple[str, str]]) -> str:
    if not items:
        return f'<p class="muted">{escape(empty_text)}</p>'
    rendered = []
    for item in items:
        title = escape(item.get("title") or item.get("name") or "Untitled")
        tags = []
        if item.get("laneTitle"):
            tags.append(tag("Lane", item.get("laneTitle"), tone="neutral"))
        if item.get("status"):
            tags.append(pill(item.get("status")))
        if item.get("severity"):
            tags.append(tag("Severity", item.get("severity"), tone=tone_class(item.get("severity"))))

        details = []
        for key, label in fields:
            if key in {"status", "severity"} and item.get(key):
                continue
            value = item.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value_text = ", ".join(str(part) for part in value)
            else:
                value_text = str(value)
            details.append(f'<div><strong>{escape(label)}</strong><span>{escape(value_text)}</span></div>')
        if not details:
            details.append('<div><strong>Details</strong><span class="muted">No extra details recorded.</span></div>')

        related_tags = []
        for key, label in [
            ("relatedModules", "Modules"),
            ("relatedIssues", "Issues"),
            ("relatedDecisions", "Decisions"),
            ("relatedFiles", "Files"),
        ]:
            value = item.get(key)
            if not value:
                continue
            if isinstance(value, list):
                for entry in value:
                    related_tags.append(tag(label, entry))
            else:
                related_tags.append(tag(label, value))
        related_html = f'<div class="related-tags">{"".join(related_tags)}</div>' if related_tags else ""
        rendered.append(
            f"""
            <article class="record">
              <div class="record-head">
                <h3>{title}</h3>
                <div class="record-tags">{''.join(tags)}</div>
              </div>
              <div class="record-grid">{''.join(details)}</div>
              {related_html}
            </article>
            """
        )
    return "".join(rendered)


def section_meta(section: str, items: list[dict]) -> str:
    if section == "issues":
        open_items = len([item for item in items if item.get("status") != "resolved"])
        return f"{open_items} open / {len(items)} total"
    if section == "todos":
        open_items = len([item for item in items if item.get("status") != "done"])
        return f"{open_items} open / {len(items)} total"
    return f"{len(items)} entries"


def render_section(section: str, memory: dict, profile: dict, lanes: list[dict], section_layouts: dict[str, str]) -> str:
    title = label_for(section, profile)
    layout_name = section_layouts.get(section, "standard")
    if section == "summary":
        return render_summary(memory, title=title, layout_name=layout_name)
    if section == "collaboration":
        return render_collaboration(memory, title=title, layout_name=layout_name)
    if section == "lanes":
        return render_lanes(memory, title=title, layout_name=layout_name)
    if section == "progress":
        return render_progress(memory, title=title, layout_name=layout_name)

    mapping = {
        "modules": ("No modules recorded.", [("status", "Status"), ("summary", "Summary"), ("notes", "Notes")]),
        "decisions": ("No decisions recorded.", [("context", "Context"), ("decision", "Decision"), ("impact", "Impact")]),
        "issues": ("No issues recorded.", [("status", "Status"), ("severity", "Severity"), ("impact", "Impact"), ("nextStep", "Next Step")]),
        "todos": ("No todos recorded.", [("status", "Status"), ("owner", "Owner"), ("notes", "Notes")]),
        "techNotes": ("No technical notes recorded.", [("body", "Note")]),
        "recentUpdates": ("No updates recorded.", [("timestamp", "Time"), ("details", "Details")]),
    }
    empty_text, fields = mapping[section]
    items = aggregate_items(memory, lanes, section)
    content = render_named_items(items, empty_text, fields)
    layout_attr = f" {layout_name}" if layout_name in {"narrow", "wide", "full"} else ""
    return f"""
    <section class="band{layout_attr}">
      <div class="section-head">
        <div>
          <h2>{escape(title)}</h2>
          <p class="section-note">{escape(section_note(section))}</p>
        </div>
        <div class="section-meta">{escape(section_meta(section, items))}</div>
      </div>
      <div class="records">{content}</div>
    </section>
    """


def render_metric(label: str, value: object, note: str) -> str:
    return f"""
    <div class="metric">
      <span class="metric-label">{escape(label)}</span>
      <span class="metric-value">{escape(str(value))}</span>
      <span class="metric-note">{escape(note)}</span>
    </div>
    """


def render_html(memory: dict, profile: dict, lanes: list[dict]) -> str:
    resolved_profile = effective_profile(profile)
    project = memory.get("project", {})
    summary = memory.get("summary", {})
    counts = project_counts(memory, lanes)
    title = project.get("name", "Project Memory")
    project_type = project.get("type", resolved_profile.get("projectType", "general"))
    dashboard_preset = resolved_profile.get("dashboardPreset", "default")
    visual_mode = resolved_profile.get("visualMode", "briefing")
    density = resolved_profile.get("density", "balanced")
    section_layouts = resolved_profile.get("sectionLayouts", {})
    theme = theme_for(resolved_profile)
    density_tokens = DENSITY_PRESETS.get(density, DENSITY_PRESETS["balanced"])
    focus = summary.get("focus", "See active lanes")
    phase = summary.get("currentPhase", "Shared memory active")
    updated = summary.get("lastUpdated", "Unknown")
    headline = TYPE_SUMMARIES.get(project_type, TYPE_SUMMARIES["general"])
    health = str(summary.get("health", "green"))
    hero = f"""
    <header class="masthead">
      <div class="masthead-top">
        <div class="title-block">
          <div class="eyebrow">Project Memory Dashboard</div>
          <h1>{escape(title)}</h1>
          <p>{escape(headline)}</p>
        </div>
        <div class="hero-focus">
          <strong>Current focus</strong>
          <span>{escape(str(focus))}</span>
          <p>Phase: {escape(str(phase))}<br>Last updated: {escape(str(updated))}<br>Memory version: {escape(str(project.get("memoryVersion", 1)))}</p>
        </div>
      </div>
        <div class="metrics">
        {render_metric("Project Type", str(project_type).title(), "Profile-driven section ordering and labels.")}
        {render_metric("Dashboard Preset", DASHBOARD_PRESET_LABELS.get(dashboard_preset, str(dashboard_preset).title()), "High-level composition preset for section order and emphasis.")}
        {render_metric("Visual Mode", VISUAL_MODE_LABELS.get(visual_mode, visual_mode.title()), "Named presentation style for the static dashboard.")}
        {render_metric("Density", DENSITY_LABELS.get(density, density.title()), "Information spacing and visual compression for repeated use.")}
        {render_metric("Health", health.title(), "A fast signal for the state of current execution.")}
        {render_metric("Shared Lanes", counts["lanes"], "Stable responsibility slices for multi-session work.")}
        {render_metric("Open Issues", counts["open_issues"], "Active blockers and investigation threads.")}
        {render_metric("Open Todos", counts["open_todos"], "Concrete next actions still in play.")}
        {render_metric("Recent Updates", counts["updates"], "Chronological re-entry trail for the project.")}
      </div>
    </header>
    """

    preferred = resolved_profile.get("sections", list(SECTION_TITLES))
    ordered_sections = []
    leading_sections = ["summary"]
    if memory.get("_coordination"):
        leading_sections.append("collaboration")
    leading_sections.extend(["progress", "lanes"])
    for section in leading_sections:
        if section not in ordered_sections:
            ordered_sections.append(section)
    for section in preferred:
        if section in SECTION_TITLES and section not in ordered_sections:
            ordered_sections.append(section)

    body_sections = "".join(render_section(section, memory, resolved_profile, lanes, section_layouts) for section in ordered_sections)
    footer = """
    <div class="footer">
      Generated from <code>.docs/project-memory/memory.json</code>, <code>profile.json</code>, and per-lane JSON files.
      Open <code>PROJECT_MEMORY.html</code> from the project root for the stable shortcut.
    </div>
    """
    return html_page(title, hero + f'<div class="dashboard-grid">{body_sections}</div>' + footer, theme, density_tokens)


def refresh_outputs(project_root: Path, memory: dict | None = None, profile: dict | None = None) -> tuple[dict, dict, list[dict]]:
    memory_dir = project_memory_dir(project_root)
    memory = memory or load_json(memory_dir / "memory.json")
    profile = profile or load_json(memory_dir / "profile.json")
    lanes = list_lanes(project_root)
    update_memory_lane_index(memory, lanes)
    render_memory = deepcopy(memory)
    if coordination_registry_path(project_root).exists():
        render_memory["_coordination"] = public_snapshot(load_coordination_registry(project_root))
    (memory_dir / "overview.html").write_text(render_html(render_memory, profile, lanes), encoding="utf-8")
    (memory_dir / "INDEX.md").write_text(render_index(render_memory, profile, lanes), encoding="utf-8")
    write_shortcut(project_root, memory.get("project", {}).get("name", project_root.name))
    return memory, profile, lanes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the static overview HTML for a project memory dashboard.")
    parser.add_argument("project_root", help="Path to the target project root.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    memory_dir = project_memory_dir(project_root)
    memory, _, _ = refresh_outputs(project_root)
    write_json(memory_dir / "memory.json", memory)
    print(f"Rendered {memory_dir / 'overview.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
