from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


LANE_SECTIONS = ("modules", "decisions", "issues", "todos", "techNotes", "recentUpdates")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return deepcopy(default) if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project_memory_dir(project_root: Path) -> Path:
    return project_root / ".docs" / "project-memory"


def lanes_dir(project_root: Path) -> Path:
    return project_memory_dir(project_root) / "lanes"


def ensure_directories(project_root: Path) -> tuple[Path, Path]:
    memory_dir = project_memory_dir(project_root)
    memory_dir.mkdir(parents=True, exist_ok=True)
    lane_dir = memory_dir / "lanes"
    lane_dir.mkdir(exist_ok=True)
    (memory_dir / "archive").mkdir(exist_ok=True)
    return memory_dir, lane_dir


def slugify_lane(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    collapsed = re.sub(r"-{2,}", "-", collapsed).strip("-")
    return collapsed or "general-work"


def titleize_lane(lane_id: str) -> str:
    return lane_id.replace("-", " ").title()


def lane_path(project_root: Path, lane_id: str) -> Path:
    return lanes_dir(project_root) / f"{lane_id}.json"


def default_lane(lane_id: str, title: str | None = None, owner: str | None = None, focus: str | None = None) -> dict:
    now = utc_now()
    lane = {
        "id": lane_id,
        "title": title or titleize_lane(lane_id),
        "owner": owner or "shared-session",
        "focus": focus or "",
        "phase": "Active",
        "health": "green",
        "lastUpdated": now,
        "modules": [],
        "decisions": [],
        "issues": [],
        "todos": [],
        "techNotes": [],
        "recentUpdates": [],
    }
    return lane


def load_lane(project_root: Path, lane_id: str) -> dict:
    path = lane_path(project_root, lane_id)
    return load_json(path, default_lane(lane_id))


def save_lane(project_root: Path, lane: dict) -> None:
    write_json(lane_path(project_root, lane["id"]), lane)


def list_lanes(project_root: Path) -> list[dict]:
    lane_dir = lanes_dir(project_root)
    if not lane_dir.exists():
        return []
    lanes = []
    for path in sorted(lane_dir.glob("*.json")):
        lane = load_json(path)
        lane.setdefault("id", path.stem)
        lane.setdefault("title", titleize_lane(path.stem))
        lane.setdefault("owner", "shared-session")
        lane.setdefault("focus", "")
        lane.setdefault("phase", "Active")
        lane.setdefault("health", "green")
        lane.setdefault("lastUpdated", "")
        for section in LANE_SECTIONS:
            lane.setdefault(section, [])
        lanes.append(lane)
    lanes.sort(key=lambda item: item.get("lastUpdated", ""), reverse=True)
    return lanes


def ensure_lane(project_root: Path, lane_id: str, title: str | None = None, owner: str | None = None, focus: str | None = None) -> dict:
    lane = load_lane(project_root, lane_id)
    lane["id"] = lane_id
    lane.setdefault("title", title or titleize_lane(lane_id))
    if title:
        lane["title"] = title
    if owner:
        lane["owner"] = owner
    lane.setdefault("owner", "shared-session")
    if focus:
        lane["focus"] = focus
    lane.setdefault("focus", "")
    lane.setdefault("phase", "Active")
    lane.setdefault("health", "green")
    lane.setdefault("lastUpdated", utc_now())
    for section in LANE_SECTIONS:
        lane.setdefault(section, [])
    return lane


def aggregate_items(memory: dict, lanes: list[dict], section: str) -> list[dict]:
    items = []
    if section in memory and isinstance(memory.get(section), list):
        items.extend(memory.get(section, []))
    for lane in lanes:
        for item in lane.get(section, []):
            lane_item = dict(item)
            lane_item.setdefault("laneId", lane.get("id"))
            lane_item.setdefault("laneTitle", lane.get("title"))
            items.append(lane_item)
    if section == "recentUpdates":
        deduped = []
        seen = set()
        for item in items:
            key = (
                item.get("timestamp", ""),
                item.get("title", ""),
                item.get("laneId", ""),
                item.get("details", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        items = deduped
        items.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return items


def summarize_lane(lane: dict) -> dict:
    return {
        "id": lane.get("id", ""),
        "title": lane.get("title", titleize_lane(lane.get("id", ""))),
        "owner": lane.get("owner", "shared-session"),
        "focus": lane.get("focus", ""),
        "phase": lane.get("phase", "Active"),
        "health": lane.get("health", "green"),
        "lastUpdated": lane.get("lastUpdated", ""),
        "openIssues": len([item for item in lane.get("issues", []) if item.get("status") != "resolved"]),
        "openTodos": len([item for item in lane.get("todos", []) if item.get("status") != "done"]),
        "updates": len(lane.get("recentUpdates", [])),
    }


def update_memory_lane_index(memory: dict, lanes: list[dict]) -> dict:
    memory["lanes"] = [summarize_lane(lane) for lane in lanes]
    summary = memory.setdefault("summary", {})
    timestamps = [summary.get("lastUpdated", "")]
    timestamps.extend(item.get("lastUpdated", "") for item in lanes if item.get("lastUpdated"))
    if timestamps:
        summary["lastUpdated"] = max(timestamps)
    return memory


def build_shortcut_html(project_name: str) -> str:
    safe_name = project_name or "Project Memory"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=.docs/project-memory/overview.html">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_name} Memory</title>
</head>
<body>
  <p>Open <a href=".docs/project-memory/overview.html">project memory overview</a>.</p>
</body>
</html>
"""


def write_shortcut(project_root: Path, project_name: str) -> None:
    shortcut_path = project_root / "PROJECT_MEMORY.html"
    shortcut_path.write_text(build_shortcut_html(project_name), encoding="utf-8")
