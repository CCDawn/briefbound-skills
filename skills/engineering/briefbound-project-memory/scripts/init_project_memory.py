from __future__ import annotations

import argparse
from pathlib import Path

from memory_model import ensure_directories, utc_now, write_json
from profile_model import (
    DASHBOARD_PRESET_CHOICES,
    DENSITY_CHOICES,
    PROJECT_TYPE_CHOICES,
    VISUAL_MODE_CHOICES,
    build_profile,
)
from render_overview import refresh_outputs


def build_memory(project_name: str, project_type: str) -> dict:
    now = utc_now()
    return {
        "project": {
            "name": project_name,
            "type": project_type,
            "root": ".",
            "memoryVersion": 2,
        },
        "summary": {
            "currentPhase": "Shared memory active",
            "health": "green",
            "focus": "See active lanes",
            "lastUpdated": now,
        },
        "progress": {
            "percent": 0,
            "status": "Memory ready",
            "milestones": [
                {
                    "title": "Shared HTML memory initialized",
                    "status": "done",
                    "note": "Created global memory shell, lanes directory, overview, and root shortcut.",
                }
            ],
        },
        "recentUpdates": [
            {
                "timestamp": now,
                "title": "Initialized shared project memory",
                "details": "Created memory.json, profile.json, overview.html, INDEX.md, inbox.json, lanes/, archive/, and PROJECT_MEMORY.html.",
            }
        ],
        "lanes": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a project memory dashboard.")
    parser.add_argument("project_root", help="Path to the target project root.")
    parser.add_argument(
        "--project-type",
        default="general",
        choices=sorted(PROJECT_TYPE_CHOICES),
        help="Project profile preset to use.",
    )
    parser.add_argument(
        "--dashboard-preset",
        default=None,
        choices=DASHBOARD_PRESET_CHOICES,
        help="Optional higher-level dashboard composition preset. Defaults by project type.",
    )
    parser.add_argument(
        "--visual-mode",
        default=None,
        choices=VISUAL_MODE_CHOICES,
        help="Optional dashboard presentation mode override.",
    )
    parser.add_argument(
        "--density",
        default=None,
        choices=DENSITY_CHOICES,
        help="Optional information density override.",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Optional display name. Defaults to the project root folder name.",
    )
    parser.add_argument(
        "--skip-agents-rules",
        action="store_true",
        help="Skip writing the Project Memory Rules block into AGENTS.md.",
    )
    return parser.parse_args()


def load_agents_snippet() -> str:
    snippet_path = Path(__file__).resolve().parents[1] / "references" / "AGENTS-snippet.md"
    text = snippet_path.read_text(encoding="utf-8")
    marker = "```md"
    start = text.find(marker)
    end = text.rfind("```")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not parse AGENTS snippet.")
    return text[start + len(marker):end].strip() + "\n"


def inject_agents_rules(project_root: Path) -> None:
    agents_path = project_root / "AGENTS.md"
    snippet = load_agents_snippet()
    content = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    if "## Project Memory Rules" in content:
        return
    separator = "\n\n" if content and not content.endswith("\n\n") else ""
    agents_path.write_text(content + separator + snippet, encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    memory_dir, _ = ensure_directories(project_root)

    project_name = args.project_name or project_root.name
    memory = build_memory(project_name, args.project_type)
    profile = build_profile(
        args.project_type,
        dashboard_preset=args.dashboard_preset,
        visual_mode=args.visual_mode,
        density=args.density,
    )

    write_json(memory_dir / "memory.json", memory)
    write_json(memory_dir / "profile.json", profile)
    write_json(memory_dir / "inbox.json", {"captures": []})
    refresh_outputs(project_root, memory, profile)
    if not args.skip_agents_rules:
        inject_agents_rules(project_root)

    print(f"Initialized project memory at {memory_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
