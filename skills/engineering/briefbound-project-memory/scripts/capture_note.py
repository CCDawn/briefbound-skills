from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {"captures": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def csv_or_none(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture a quick project-memory note into inbox.json.")
    parser.add_argument("project_root", help="Path to the target project root.")
    parser.add_argument("--title", required=True, help="Short title for the captured note.")
    parser.add_argument("--details", required=True, help="The raw finding, observation, or breadcrumb to record.")
    parser.add_argument("--lane", default=None, help="Optional responsibility lane hint, such as backend-auth.")
    parser.add_argument("--modules", default=None, help="Comma-separated related modules.")
    parser.add_argument("--issues", default=None, help="Comma-separated related issues.")
    parser.add_argument("--decisions", default=None, help="Comma-separated related decisions.")
    parser.add_argument("--files", default=None, help="Comma-separated related files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    inbox_path = project_root / ".docs" / "project-memory" / "inbox.json"
    inbox = load_json(inbox_path)
    capture = {
        "timestamp": utc_now(),
        "title": args.title,
        "details": args.details,
    }
    if args.lane:
        capture["laneId"] = args.lane
    mappings = {
        "relatedModules": csv_or_none(args.modules),
        "relatedIssues": csv_or_none(args.issues),
        "relatedDecisions": csv_or_none(args.decisions),
        "relatedFiles": csv_or_none(args.files),
    }
    for key, value in mappings.items():
        if value:
            capture[key] = value
    inbox.setdefault("captures", []).insert(0, capture)
    write_json(inbox_path, inbox)
    print(f"Captured note in {inbox_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
