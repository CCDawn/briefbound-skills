from __future__ import annotations

import argparse
from pathlib import Path

from coordination_model import (
    find_agent,
    find_coordination,
    load_registry,
    mark_coordination_synced,
    mutate_registry,
)

from memory_model import (
    ensure_directories,
    ensure_lane,
    load_json,
    load_lane,
    save_lane,
    slugify_lane,
    titleize_lane,
    utc_now,
    write_json,
)
from render_overview import refresh_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync project memory after meaningful development work.")
    parser.add_argument("project_root", help="Path to the target project root.")
    parser.add_argument("--lane", default=None, help="Stable lane id for the responsibility area, such as backend-auth.")
    parser.add_argument("--lane-title", default=None, help="Optional human-readable lane title.")
    parser.add_argument("--owner", default=None, help="Optional current session or owner label.")
    parser.add_argument("--focus", default=None, help="Current lane focus.")
    parser.add_argument("--phase", default=None, help="Current lane phase.")
    parser.add_argument("--health", default=None, choices=["green", "yellow", "red"], help="Current lane health.")
    parser.add_argument("--update", default=None, help="Short recent update summary for this task.")
    parser.add_argument("--capture-title", default=None, help="Optional inbox capture title to promote.")
    parser.add_argument("--promote-captures", action="store_true", help="Promote all inbox captures into the current lane and clear inbox.")
    parser.add_argument(
        "--coordination-id",
        default=None,
        help="Promote one resolved conflict, discussion, or merge decision into durable project memory.",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Promote one agent's current checkpoint into durable project memory.",
    )
    return parser.parse_args()


def promote_capture_to_update(capture: dict, lane: dict) -> dict:
    timestamp = capture.get("timestamp") or utc_now()
    title = capture.get("title") or "Promoted inbox capture"
    details = capture.get("details") or capture.get("body") or ""
    promoted = {
        "timestamp": timestamp,
        "title": title,
        "details": details,
        "laneId": lane["id"],
        "laneTitle": lane["title"],
    }
    for key in ("relatedModules", "relatedIssues", "relatedDecisions", "relatedFiles"):
        if capture.get(key):
            promoted[key] = capture[key]
    return promoted


def resolve_lane_id(args: argparse.Namespace) -> str:
    seed = args.lane or args.focus or args.update or "general-work"
    return slugify_lane(seed)


def sync_memory(project_root: Path, args: argparse.Namespace) -> None:
    ensure_directories(project_root)
    memory_dir = project_root / ".docs" / "project-memory"
    memory_path = memory_dir / "memory.json"
    profile_path = memory_dir / "profile.json"
    inbox_path = memory_dir / "inbox.json"

    memory = load_json(memory_path)
    profile = load_json(profile_path)
    inbox = load_json(inbox_path, {"captures": []})

    lane_id = resolve_lane_id(args)
    lane_title = args.lane_title or (titleize_lane(lane_id) if args.lane or args.focus or args.update else "General Work")
    lane = ensure_lane(project_root, lane_id, title=lane_title, owner=args.owner, focus=args.focus)
    if (project_root / ".docs" / "project-memory" / "lanes" / f"{lane_id}.json").exists():
        lane = load_lane(project_root, lane_id)
        lane = ensure_lane(project_root, lane_id, title=lane_title, owner=args.owner, focus=args.focus)

    now = utc_now()
    lane["lastUpdated"] = now
    if args.owner:
        lane["owner"] = args.owner
    if args.focus:
        lane["focus"] = args.focus
    if args.phase:
        lane["phase"] = args.phase
    if args.health:
        lane["health"] = args.health

    registry = None
    coordination = None
    agent = None
    if args.coordination_id or args.agent_id:
        registry = load_registry(project_root)
    if args.coordination_id:
        coordination = find_coordination(registry, args.coordination_id)
        if coordination.get("state") != "resolved":
            raise SystemExit(f"Coordination is not resolved: {args.coordination_id}")
    if args.agent_id:
        agent = find_agent(registry, args.agent_id)

    recent_updates = lane.setdefault("recentUpdates", [])
    global_recent = memory.setdefault("recentUpdates", [])
    if args.update:
        lane_update = {
            "timestamp": now,
            "title": args.update,
            "details": args.update,
            "laneId": lane["id"],
            "laneTitle": lane["title"],
        }
        recent_updates.insert(0, lane_update)
        global_recent.insert(
            0,
            {
                "timestamp": now,
                "title": args.update,
                "details": args.update,
                "laneId": lane["id"],
                "laneTitle": lane["title"],
            },
        )

    if coordination is not None and not any(
        item.get("coordinationId") == args.coordination_id for item in lane.setdefault("decisions", [])
    ):
        durable_decision = {
            "timestamp": coordination.get("resolvedAt") or utc_now(),
            "title": coordination.get("topic") or "Coordination decision",
            "context": coordination.get("summary") or coordination.get("kind", "coordination"),
            "decision": coordination.get("decision") or "Resolved",
            "impact": coordination.get("decisionReason") or "Shared agent coordination updated",
            "coordinationId": args.coordination_id,
            "participants": coordination.get("participants", []),
        }
        lane["decisions"].insert(0, durable_decision)
        update = {
            "timestamp": durable_decision["timestamp"],
            "title": f"Coordination resolved: {durable_decision['title']}",
            "details": durable_decision["decision"],
            "coordinationId": args.coordination_id,
            "laneId": lane["id"],
            "laneTitle": lane["title"],
        }
        recent_updates.insert(0, update)
        global_recent.insert(0, dict(update))

    if agent is not None:
        checkpoint_key = "|".join(
            [
                str(agent.get("id") or ""),
                str(agent.get("state") or ""),
                str(agent.get("lastCheckpoint") or agent.get("currentAction") or ""),
                str(agent.get("headCommit") or ""),
            ]
        )
        if not any(item.get("agentCheckpointKey") == checkpoint_key for item in recent_updates):
            update = {
                "timestamp": agent.get("updatedAt") or utc_now(),
                "title": f"Agent checkpoint: {agent.get('label') or agent.get('id')}",
                "details": agent.get("lastCheckpoint")
                or agent.get("currentAction")
                or agent.get("task")
                or agent.get("state"),
                "agentId": agent.get("id"),
                "agentState": agent.get("state"),
                "agentCheckpointKey": checkpoint_key,
                "laneId": lane["id"],
                "laneTitle": lane["title"],
            }
            recent_updates.insert(0, update)
            global_recent.insert(0, dict(update))

    captures = inbox.get("captures", [])
    remaining_captures = []
    for capture in captures:
        should_promote = args.promote_captures or (
            args.capture_title is not None and capture.get("title") == args.capture_title
        )
        if should_promote:
            promoted = promote_capture_to_update(capture, lane)
            recent_updates.insert(0, promoted)
            global_recent.insert(0, promoted)
        else:
            remaining_captures.append(capture)

    inbox["captures"] = remaining_captures
    save_lane(project_root, lane)
    memory.setdefault("summary", {})
    refresh_outputs(project_root, memory, profile)
    write_json(memory_path, memory)
    write_json(inbox_path, inbox)
    if coordination is not None:
        mutate_registry(
            project_root,
            lambda value: mark_coordination_synced(value, args.coordination_id, lane["id"]),
        )


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    sync_memory(project_root, args)
    print(f"Synced project memory at {project_root / '.docs' / 'project-memory'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
