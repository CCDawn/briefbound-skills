from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from coordination_model import (
    ACTIVE_CLAIM_STATUSES,
    AGENT_STATES,
    CoordinationConflict,
    activate_claim,
    cancel_resume_obligation,
    complete_agent,
    create_claim,
    expire_resume_obligation,
    find_claim_conflicts,
    heartbeat_coordination_owner,
    load_registry,
    mark_expired_claims,
    mark_stale_coordination_owners,
    mark_stale_agents,
    mutate_registry,
    open_coordination,
    pause_agent,
    prune_registry,
    public_snapshot,
    registry_path,
    register_agent,
    release_claim,
    resolve_agent_id,
    resolve_coordination,
    respond_coordination,
    resume_agent,
    slugify,
    scopes_overlap,
    take_over_coordination,
    update_agent,
)


def print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def print_conflicts(conflicts: list[dict]) -> None:
    for item in conflicts:
        claim = item.get("claim", {})
        reasons = "; ".join(item.get("reasons", []))
        print(
            f"- {claim.get('id', '-')} [{claim.get('status', '-')}] "
            f"agent={claim.get('agentId') or claim.get('agent', '-')} "
            f"scopes={','.join(claim.get('scopes', [])) or '-'} ({reasons})"
        )


def git_write_context(project_root: Path) -> dict:
    def git(*args: str) -> str | None:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    git_dir_value = git("rev-parse", "--git-dir")
    common_dir_value = git("rev-parse", "--git-common-dir")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if git_dir_value is None or common_dir_value is None or branch is None:
        return {
            "gitRepository": False,
            "branch": "",
            "primaryWorktree": False,
            "protectedTarget": False,
            "dirty": False,
        }

    def resolve_git_path(value: str) -> Path:
        path = Path(value)
        return (project_root / path).resolve() if not path.is_absolute() else path.resolve()

    status = git("status", "--porcelain=v1", "--untracked-files=normal")
    return {
        "gitRepository": True,
        "branch": branch,
        "primaryWorktree": resolve_git_path(git_dir_value) == resolve_git_path(common_dir_value),
        "protectedTarget": branch in {"main", "master"},
        "dirty": bool(status),
    }


def command_status(project_root: Path, args: argparse.Namespace) -> int:
    registry = load_registry(project_root)
    if mark_stale_agents(registry) + mark_expired_claims(registry) + mark_stale_coordination_owners(registry):
        mutate_registry(
            project_root,
            lambda value: (
                mark_stale_agents(value)
                + mark_expired_claims(value)
                + mark_stale_coordination_owners(value)
            ),
        )
        registry = load_registry(project_root)
    payload = public_snapshot(registry) if args.public else registry
    if args.json:
        print_json(payload)
        return 0
    visible_agents = [
        item for item in registry.get("agents", []) if args.include_completed or item.get("state") != "completed"
    ]
    open_coordinations = [
        item
        for item in registry.get("coordinations", [])
        if item.get("state") != "resolved" or item.get("resumePendingAgentIds")
    ]
    active_claims = [
        item
        for item in registry.get("claims", [])
        if item.get("status") in ACTIVE_CLAIM_STATUSES | {"yielded"}
    ]
    project = registry.get("project", {})
    print(f"Project coordination: {project.get('name', project_root.name)} [{project.get('id', '-')}] rev={registry.get('revision', 0)}")
    print(f"Agents: {len(visible_agents)} | Claims: {len(active_claims)} | Open coordination: {len(open_coordinations)}")
    for agent in visible_agents:
        scopes = ",".join(agent.get("scopes", [])) or "-"
        print(
            f"- {agent.get('id')} [{agent.get('state', '-')}] branch={agent.get('branch') or '-'} "
            f"stage={agent.get('stage') or '-'} scopes={scopes} task={agent.get('task') or '-'}"
        )
        checkpoint = agent.get("lastCheckpoint") or agent.get("currentAction")
        if checkpoint:
            print(f"  checkpoint: {checkpoint}")
        if agent.get("blocker"):
            print(f"  blocker: {agent['blocker']}")
    for item in open_coordinations:
        print(
            f"- {item.get('id')} [{item.get('kind')}/{item.get('state')}] "
            f"owner={item.get('ownerAgentId')} recovery={item.get('recoveryState', '-')} "
            f"resumePending={','.join(item.get('resumePendingAgentIds', [])) or '-'} topic={item.get('topic')}"
        )
    return 0


def command_preflight(project_root: Path, args: argparse.Namespace) -> int:
    context = git_write_context(project_root)
    path = registry_path(project_root)
    registry = load_registry(project_root) if path.exists() else None
    integration_claim = None
    if registry is not None:
        mark_expired_claims(registry)
        lane_id = slugify(f"integration/{context['branch']}")
        integration_claim = next(
            (
                item
                for item in registry.get("claims", [])
                if item.get("agentId") == args.agent_id
                and item.get("laneId") == lane_id
                and item.get("status") in ACTIVE_CLAIM_STATUSES
            ),
            None,
        )

    guard = {
        **context,
        "writeKind": args.write_kind,
        "integrationClaim": bool(integration_claim),
    }
    if context["primaryWorktree"] and context["protectedTarget"]:
        if args.write_kind == "development":
            payload = {
                "state": "ISOLATION_REQUIRED",
                "registryExists": path.exists(),
                "activePeers": [],
                "overlaps": [],
                **guard,
            }
            print_json(payload) if args.json else print(
                f"ISOLATION_REQUIRED: create a task worktree before writing to {context['branch']}."
            )
            return 2
        if args.write_kind == "integration" and integration_claim is None:
            payload = {
                "state": "INTEGRATION_CLAIM_REQUIRED",
                "registryExists": path.exists(),
                "activePeers": [],
                "overlaps": [],
                **guard,
            }
            print_json(payload) if args.json else print(
                f"INTEGRATION_CLAIM_REQUIRED: claim integration/{context['branch']} before writing."
            )
            return 2
        if args.write_kind == "integration" and context["dirty"]:
            payload = {
                "state": "DIRTY_TARGET",
                "registryExists": True,
                "activePeers": [],
                "overlaps": [],
                **guard,
            }
            print_json(payload) if args.json else print(
                f"DIRTY_TARGET: clean {context['branch']} before integration."
            )
            return 2

    if not path.exists():
        payload = {
            "state": "CLEAR",
            "registryExists": False,
            "activePeers": [],
            "overlaps": [],
            **guard,
        }
        print_json(payload) if args.json else print("CLEAR: no coordination registry.")
        return 0

    assert registry is not None
    peers = [
        item
        for item in registry.get("agents", [])
        if item.get("id") != args.agent_id and item.get("state") not in {"completed", "stale"}
    ]
    ignored_claims = {
        item.get("id")
        for item in registry.get("claims", [])
        if args.agent_id and item.get("agentId") == args.agent_id
    }
    claim_overlaps = find_claim_conflicts(
        registry,
        None,
        args.scope or [],
        ignore_claim_ids=ignored_claims,
    )
    scope_overlaps = []
    for peer in peers:
        matches = sorted(
            {
                f"{requested} <-> {owned}"
                for requested in args.scope or []
                for owned in peer.get("scopes", [])
                if scopes_overlap(requested, owned)
            }
        )
        if matches:
            scope_overlaps.append(
                {"kind": "registered-scope", "agentId": peer.get("id"), "matches": matches}
            )
    overlaps = [
        {
            "kind": "claim",
            "agentId": item.get("claim", {}).get("agentId"),
            "claimId": item.get("claim", {}).get("id"),
            "reasons": item.get("reasons", []),
        }
        for item in claim_overlaps
    ] + scope_overlaps
    state = "OVERLAP" if overlaps else ("PEERS_NO_OVERLAP" if peers else "CLEAR")
    payload = {
        "state": state,
        "registryExists": True,
        "activePeers": [
            {
                "id": item.get("id"),
                "state": item.get("state"),
                "branch": item.get("branch", ""),
                "scopes": item.get("scopes", []),
                "checkpoint": item.get("lastCheckpoint") or item.get("currentAction", ""),
            }
            for item in peers
        ],
        "overlaps": overlaps,
        **guard,
    }
    print_json(payload) if args.json else print(f"{state}: peers={len(peers)} overlaps={len(overlaps)}")
    return 1 if overlaps else 0


def command_join(project_root: Path, args: argparse.Namespace) -> int:
    agent = mutate_registry(
        project_root,
        lambda registry: register_agent(
            registry,
            resolve_agent_id(
                registry,
                args.agent_id,
                args.agent,
                thread_id=args.thread_id,
            ),
            args.agent,
            thread_id=args.thread_id,
            task=args.task,
            state=args.state,
            stage=args.stage,
            current_action=args.current_action,
            branch=args.branch,
            worktree=args.worktree,
            scopes=args.scope,
            base_commit=args.base_commit,
            head_commit=args.head_commit,
            ttl_minutes=args.ttl_minutes,
        ),
    )
    if args.json:
        print_json(agent)
    else:
        print(f"Registered {agent['id']} [{agent['state']}] for {agent.get('task') or 'current project work'}.")
    return 0


def command_update(project_root: Path, args: argparse.Namespace) -> int:
    changes = {
        "state": args.state,
        "task": args.task,
        "stage": args.stage,
        "current_action": args.current_action,
        "last_checkpoint": args.last_checkpoint,
        "next_checkpoint": args.next_checkpoint,
        "blocker": "" if args.clear_blocker else args.blocker,
        "branch": args.branch,
        "worktree": args.worktree,
        "scopes": args.scope,
        "base_commit": args.base_commit,
        "head_commit": args.head_commit,
        "thread_id": args.thread_id,
        "ttl_minutes": args.ttl_minutes,
    }
    def apply_update(registry: dict) -> dict:
        if args.state != "completed":
            return update_agent(registry, args.agent_id, **changes)
        non_state_changes = {
            key: value
            for key, value in changes.items()
            if key != "state" and value is not None
        }
        if non_state_changes:
            update_agent(registry, args.agent_id, **non_state_changes)
        summary = args.last_checkpoint or args.current_action or args.task or ""
        return complete_agent(registry, args.agent_id, summary)

    agent = mutate_registry(project_root, apply_update)
    if args.json:
        print_json(agent)
    else:
        print(f"Updated {agent['id']} [{agent['state']}] stage={agent.get('stage') or '-'}.")
    return 0


def command_check(project_root: Path, args: argparse.Namespace) -> int:
    registry = load_registry(project_root)
    conflicts = find_claim_conflicts(registry, slugify(args.lane) if args.lane else None, args.scope or [])
    if args.json:
        print_json({"ok": not conflicts, "conflicts": conflicts})
    elif conflicts:
        print("Blocked: active work overlaps requested scope.")
        print_conflicts(conflicts)
    else:
        print("No overlapping active claims.")
    return 1 if conflicts else 0


def command_claim(project_root: Path, args: argparse.Namespace) -> int:
    def create(registry: dict) -> dict:
        agent_id = resolve_agent_id(
            registry,
            args.agent_id,
            args.agent,
            thread_id=args.thread_id,
        )
        if not any(item.get("id") == agent_id for item in registry.get("agents", [])):
            register_agent(
                registry,
                agent_id,
                args.agent,
                thread_id=args.thread_id,
                task=args.task,
                scopes=args.scope,
            )
        return create_claim(
            registry,
            agent_id,
            args.lane,
            args.scope or [args.lane],
            args.task,
            status=args.status,
            ttl_minutes=args.ttl_minutes,
            note=args.note,
            force=args.force,
        )

    try:
        claim = mutate_registry(project_root, create)
    except CoordinationConflict as exc:
        if args.json:
            print_json({"ok": False, "conflicts": exc.conflicts})
        else:
            print(f"Blocked: {exc}")
            print_conflicts(exc.conflicts)
        return 1
    if args.json:
        print_json({"ok": True, "claim": claim, "forced": args.force})
    else:
        print(f"Created {claim['id']} [{claim['status']}] for {claim['laneId']}.")
    return 0


def command_activate(project_root: Path, args: argparse.Namespace) -> int:
    try:
        claim = mutate_registry(project_root, lambda registry: activate_claim(registry, args.claim_id, args.force))
    except CoordinationConflict as exc:
        if args.json:
            print_json({"ok": False, "conflicts": exc.conflicts})
        else:
            print(f"Blocked: {exc}")
            print_conflicts(exc.conflicts)
        return 1
    if args.json:
        print_json({"ok": True, "claim": claim})
    else:
        print(f"Activated {claim['id']}.")
    return 0


def command_release(project_root: Path, args: argparse.Namespace) -> int:
    claim = mutate_registry(
        project_root,
        lambda registry: release_claim(registry, args.claim_id, args.status, args.reason),
    )
    if args.json:
        print_json({"ok": True, "claim": claim})
    else:
        print(f"Marked {claim['id']} as {claim['status']}.")
    return 0


def command_pause(project_root: Path, args: argparse.Namespace) -> int:
    agent = mutate_registry(
        project_root,
        lambda registry: pause_agent(registry, args.agent_id, args.coordination_id, args.reason),
    )
    if args.json:
        print_json(agent)
    else:
        print(f"Paused {agent['id']} at a safe checkpoint; its claims are yielded.")
    return 0


def command_resume(project_root: Path, args: argparse.Namespace) -> int:
    try:
        agent = mutate_registry(
            project_root,
            lambda registry: resume_agent(registry, args.agent_id, args.coordination_id),
        )
    except CoordinationConflict as exc:
        if args.json:
            print_json({"ok": False, "conflicts": exc.conflicts})
        else:
            print(f"Blocked: {exc}")
            print_conflicts(exc.conflicts)
        return 1
    if args.json:
        print_json(agent)
    else:
        print(f"Resumed {agent['id']} after overlap recheck.")
    return 0


def command_open(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: open_coordination(
            registry,
            kind=args.kind,
            owner_agent_id=args.owner_agent_id,
            participants=args.participant,
            topic=args.topic,
            surfaces=args.surface,
            summary=args.summary,
            target_branch=args.target_branch,
            owner_ttl_minutes=args.owner_ttl_minutes,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"Opened {coordination['id']} [{coordination['kind']}] {coordination['topic']}.")
    return 0


def command_respond(project_root: Path, args: argparse.Namespace) -> int:
    response = mutate_registry(
        project_root,
        lambda registry: respond_coordination(
            registry,
            args.coordination_id,
            args.agent_id,
            args.status,
            args.summary,
            args.evidence,
        ),
    )
    if args.json:
        print_json(response)
    else:
        print(f"Recorded {args.agent_id} response [{response['status']}].")
    return 0


def command_resolve(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: resolve_coordination(
            registry,
            args.coordination_id,
            args.agent_id,
            args.decision,
            args.reason,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"Resolved {coordination['id']}: {coordination['decision']}")
    return 0


def command_heartbeat(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: heartbeat_coordination_owner(
            registry,
            args.coordination_id,
            args.agent_id,
            args.summary,
            args.ttl_minutes,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"Refreshed owner lease for {coordination['id']} until {coordination['ownerLeaseUntil']}.")
    return 0


def command_takeover(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: take_over_coordination(
            registry,
            args.coordination_id,
            args.agent_id,
            args.reason,
            force=args.force,
            ttl_minutes=args.ttl_minutes,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"{args.agent_id} now owns {coordination['id']}; recovery work may continue.")
    return 0


def command_cancel_resume(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: cancel_resume_obligation(
            registry,
            args.coordination_id,
            args.agent_id,
            args.target_agent_id,
            args.reason,
            confirmed_by_user=args.confirmed_by_user,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"Cancelled resume debt for {args.target_agent_id} in {coordination['id']}.")
    return 0


def command_expire_resume(project_root: Path, args: argparse.Namespace) -> int:
    coordination = mutate_registry(
        project_root,
        lambda registry: expire_resume_obligation(
            registry,
            args.coordination_id,
            args.agent_id,
            args.target_agent_id,
            args.evidence,
        ),
    )
    if args.json:
        print_json(coordination)
    else:
        print(f"Expired resume debt for stale {args.target_agent_id} in {coordination['id']}.")
    return 0


def command_complete(project_root: Path, args: argparse.Namespace) -> int:
    agent = mutate_registry(project_root, lambda registry: complete_agent(registry, args.agent_id, args.summary))
    if args.json:
        print_json(agent)
    else:
        print(f"Completed {agent['id']}; active claims closed.")
    return 0


def command_prune(project_root: Path, args: argparse.Namespace) -> int:
    mutate_registry(project_root, prune_registry)
    registry = load_registry(project_root)
    if args.json:
        print_json(public_snapshot(registry))
    else:
        print(
            f"Pruned coordination registry; agents={len(registry['agents'])} "
            f"claims={len(registry['claims'])} coordinations={len(registry['coordinations'])}."
        )
    return 0


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coordinate project-local Codex agents and work claims.")
    parser.add_argument("project_root", help="Target project or worktree root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show current agents, claims, and open coordination.")
    status.add_argument("--public", action="store_true", help="Redact thread ids and absolute worktree paths.")
    status.add_argument("--include-completed", action="store_true")
    status.add_argument("--include-expired", action="store_true", help="Compatibility flag; expired claims remain excluded.")
    add_json_flag(status)

    preflight = subparsers.add_parser("preflight", help="Check worktree isolation and scope overlap before writing.")
    preflight.add_argument("--agent-id", default="")
    preflight.add_argument("--scope", action="append", default=[])
    preflight.add_argument(
        "--write-kind",
        choices=["development", "mechanical", "integration"],
        default="development",
    )
    add_json_flag(preflight)

    join = subparsers.add_parser("join", help="Register or refresh an agent in this project.")
    join.add_argument("--agent", required=True, help="Human-readable agent label.")
    join.add_argument("--agent-id", default=None)
    join.add_argument("--thread-id", default="")
    join.add_argument("--task", default="")
    join.add_argument("--state", choices=sorted(AGENT_STATES), default=None)
    join.add_argument("--stage", default="starting")
    join.add_argument("--current-action", default="")
    join.add_argument("--branch", default="")
    join.add_argument("--worktree", default="")
    join.add_argument("--scope", action="append", default=[])
    join.add_argument("--base-commit", default="")
    join.add_argument("--head-commit", default="")
    join.add_argument("--ttl-minutes", type=int, default=240)
    add_json_flag(join)

    update = subparsers.add_parser("update", help="Publish a meaningful progress or state transition.")
    update.add_argument("--agent-id", required=True)
    update.add_argument("--state", choices=sorted(AGENT_STATES), default=None)
    update.add_argument("--task", default=None)
    update.add_argument("--stage", default=None)
    update.add_argument("--current-action", default=None)
    update.add_argument("--last-checkpoint", default=None)
    update.add_argument("--next-checkpoint", default=None)
    update.add_argument("--blocker", default=None)
    update.add_argument("--clear-blocker", action="store_true")
    update.add_argument("--branch", default=None)
    update.add_argument("--worktree", default=None)
    update.add_argument("--scope", action="append", default=None)
    update.add_argument("--base-commit", default=None)
    update.add_argument("--head-commit", default=None)
    update.add_argument("--thread-id", default=None)
    update.add_argument("--ttl-minutes", type=int, default=240)
    add_json_flag(update)

    check = subparsers.add_parser("check", help="Check whether a lane or scope overlaps active work.")
    check.add_argument("--lane", default=None)
    check.add_argument("--scope", action="append", default=[])
    add_json_flag(check)

    claim = subparsers.add_parser("claim", help="Claim a lane and scope when no active overlap exists.")
    claim.add_argument("--lane", required=True)
    claim.add_argument("--scope", action="append", default=[])
    claim.add_argument("--agent", default="codex-session")
    claim.add_argument("--agent-id", default=None)
    claim.add_argument("--thread-id", default="")
    claim.add_argument("--task", required=True)
    claim.add_argument("--status", choices=sorted(ACTIVE_CLAIM_STATUSES), default="active")
    claim.add_argument("--ttl-minutes", type=int, default=240)
    claim.add_argument("--note", default="")
    claim.add_argument("--force", action="store_true")
    add_json_flag(claim)

    activate = subparsers.add_parser("activate", help="Activate a ready or yielded claim after overlap checks.")
    activate.add_argument("--claim-id", required=True)
    activate.add_argument("--force", action="store_true")
    add_json_flag(activate)

    release = subparsers.add_parser("release", help="Release or close a claim.")
    release.add_argument("--claim-id", required=True)
    release.add_argument("--status", choices=["released", "completed", "blocked"], default="released")
    release.add_argument("--reason", default="")
    add_json_flag(release)

    pause = subparsers.add_parser("pause", help="Pause an agent and yield its active claims.")
    pause.add_argument("--agent-id", required=True)
    pause.add_argument("--coordination-id", required=True)
    pause.add_argument("--reason", required=True)
    add_json_flag(pause)

    resume = subparsers.add_parser("resume", help="Resume an agent after rechecking yielded scopes.")
    resume.add_argument("--agent-id", required=True)
    resume.add_argument("--coordination-id", required=True)
    add_json_flag(resume)

    open_parser = subparsers.add_parser("open", help="Open a conflict, discussion, or merge coordination item.")
    open_parser.add_argument("--kind", choices=["conflict", "discussion", "merge"], required=True)
    open_parser.add_argument("--owner-agent-id", required=True)
    open_parser.add_argument("--participant", action="append", required=True)
    open_parser.add_argument("--topic", required=True)
    open_parser.add_argument("--surface", action="append", default=[])
    open_parser.add_argument("--summary", default="")
    open_parser.add_argument("--target-branch", default="")
    open_parser.add_argument("--owner-ttl-minutes", type=int, default=30)
    add_json_flag(open_parser)

    respond = subparsers.add_parser("respond", help="Record one agent position or readiness response.")
    respond.add_argument("--coordination-id", required=True)
    respond.add_argument("--agent-id", required=True)
    respond.add_argument("--status", required=True)
    respond.add_argument("--summary", required=True)
    respond.add_argument("--evidence", action="append", default=[])
    add_json_flag(respond)

    resolve = subparsers.add_parser("resolve", help="Resolve a coordination item with one shared decision.")
    resolve.add_argument("--coordination-id", required=True)
    resolve.add_argument("--agent-id", required=True)
    resolve.add_argument("--decision", required=True)
    resolve.add_argument("--reason", required=True)
    add_json_flag(resolve)

    heartbeat = subparsers.add_parser("heartbeat", help="Refresh an open coordination owner's recovery lease.")
    heartbeat.add_argument("--coordination-id", required=True)
    heartbeat.add_argument("--agent-id", required=True)
    heartbeat.add_argument("--summary", default="")
    heartbeat.add_argument("--ttl-minutes", type=int, default=30)
    add_json_flag(heartbeat)

    takeover = subparsers.add_parser("takeover", help="Adopt an open coordination whose owner stopped.")
    takeover.add_argument("--coordination-id", required=True)
    takeover.add_argument("--agent-id", required=True)
    takeover.add_argument("--reason", required=True)
    takeover.add_argument("--ttl-minutes", type=int, default=30)
    takeover.add_argument("--force", action="store_true")
    add_json_flag(takeover)

    cancel_resume = subparsers.add_parser(
        "cancel-resume",
        help="Close one resume debt after the paused task was explicitly cancelled or archived.",
    )
    cancel_resume.add_argument("--coordination-id", required=True)
    cancel_resume.add_argument("--agent-id", required=True, help="Current coordination owner.")
    cancel_resume.add_argument("--target-agent-id", required=True)
    cancel_resume.add_argument("--reason", required=True)
    cancel_resume.add_argument(
        "--confirmed-by-user",
        action="store_true",
        help="Confirm that the user explicitly cancelled or archived the paused task.",
    )
    add_json_flag(cancel_resume)

    expire_resume = subparsers.add_parser(
        "expire-resume",
        help="Close one stale resume debt after fresh thread transport evidence.",
    )
    expire_resume.add_argument("--coordination-id", required=True)
    expire_resume.add_argument("--agent-id", required=True, help="Current coordination owner.")
    expire_resume.add_argument("--target-agent-id", required=True)
    expire_resume.add_argument(
        "--evidence",
        required=True,
        help="Fresh list/read evidence that the stale peer cannot resume safely.",
    )
    add_json_flag(expire_resume)

    complete = subparsers.add_parser("complete", help="Mark an agent complete and close its claims.")
    complete.add_argument("--agent-id", required=True)
    complete.add_argument("--summary", default="")
    add_json_flag(complete)

    prune = subparsers.add_parser("prune", help="Prune inactive coordination history while preserving live state.")
    add_json_flag(prune)
    return parser.parse_args()


COMMANDS = {
    "status": command_status,
    "preflight": command_preflight,
    "join": command_join,
    "update": command_update,
    "check": command_check,
    "claim": command_claim,
    "activate": command_activate,
    "release": command_release,
    "pause": command_pause,
    "resume": command_resume,
    "open": command_open,
    "respond": command_respond,
    "resolve": command_resolve,
    "heartbeat": command_heartbeat,
    "takeover": command_takeover,
    "cancel-resume": command_cancel_resume,
    "expire-resume": command_expire_resume,
    "complete": command_complete,
    "prune": command_prune,
}


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    try:
        return COMMANDS[args.command](project_root, args)
    except (CoordinationConflict, KeyError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
