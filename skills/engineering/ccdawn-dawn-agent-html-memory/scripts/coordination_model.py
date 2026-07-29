from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


ACTIVE_CLAIM_STATUSES = {"ready", "active"}
FINAL_CLAIM_STATUSES = {"released", "completed", "blocked", "expired"}
AGENT_STATES = {
    "active",
    "waiting",
    "paused",
    "blocked",
    "reviewing",
    "merge-ready",
    "merging",
    "completed",
    "stale",
}
COORDINATION_KINDS = {"conflict", "discussion", "merge"}
COORDINATION_OWNER_TTL_MINUTES = 30
MAX_RECENT_EVENTS = 50


class CoordinationConflict(RuntimeError):
    def __init__(self, message: str, conflicts: list[dict] | None = None):
        super().__init__(message)
        self.conflicts = conflicts or []


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def future_utc(minutes: int) -> str:
    value = datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", collapsed).strip("-")
    if normalized:
        return normalized
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:8]
    return f"id-{digest}"


def canonical_agent_id(label: str) -> str:
    normalized = slugify(label)
    return normalized if normalized.startswith("agent-") else f"agent-{normalized}"


def resolve_agent_id(
    registry: dict,
    requested_agent_id: str | None,
    label: str,
    *,
    thread_id: str = "",
) -> str:
    if thread_id:
        active_matches = [
            item
            for item in registry.get("agents", [])
            if item.get("threadId") == thread_id
            and item.get("state") not in {"completed", "stale"}
        ]
        if len(active_matches) == 1:
            return str(active_matches[0]["id"])
        if len(active_matches) > 1:
            preferred = requested_agent_id or canonical_agent_id(label)
            exact = [item for item in active_matches if item.get("id") == preferred]
            if len(exact) == 1:
                return str(exact[0]["id"])
            raise CoordinationConflict(
                f"Thread {thread_id} already has multiple active Agent identities; pass --agent-id explicitly.",
                [
                    {
                        "kind": "duplicate-thread-agent",
                        "threadId": thread_id,
                        "agentIds": [str(item.get("id") or "") for item in active_matches],
                    }
                ],
            )
    return requested_agent_id or canonical_agent_id(label)


def _git_common_dir(project_root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    value = Path(result.stdout.strip())
    if not value.is_absolute():
        value = project_root / value
    return value.resolve()


def project_identity(project_root: Path) -> tuple[str, Path | None]:
    root = project_root.resolve()
    common_dir = _git_common_dir(root)
    seed = str(common_dir or root).casefold()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], common_dir


def coordination_root(project_root: Path, codex_home: Path | None = None) -> Path:
    project_id, common_dir = project_identity(project_root)
    if common_dir is not None:
        return common_dir / "ccdawn" / "coordination"
    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home.expanduser().resolve() / "project-coordination" / project_id


def registry_path(project_root: Path, codex_home: Path | None = None) -> Path:
    return coordination_root(project_root, codex_home) / "registry.json"


def lock_path(project_root: Path, codex_home: Path | None = None) -> Path:
    return coordination_root(project_root, codex_home) / ".registry.lock"


def legacy_registry_path(project_root: Path) -> Path:
    return project_root.resolve() / ".docs" / "project-memory" / "agent-claims.json"


def default_registry(project_root: Path) -> dict:
    project_id, common_dir = project_identity(project_root)
    return {
        "schemaVersion": 2,
        "revision": 0,
        "project": {
            "id": project_id,
            "name": project_root.resolve().name,
            "root": str(project_root.resolve()),
            "gitCommonDir": str(common_dir) if common_dir else "",
        },
        "agents": [],
        "claims": [],
        "coordinations": [],
        "recentEvents": [],
        "updatedAt": utc_now(),
    }


def ensure_registry_shape(registry: dict, project_root: Path) -> dict:
    baseline = default_registry(project_root)
    for key, value in baseline.items():
        registry.setdefault(key, deepcopy(value))
    registry["schemaVersion"] = max(2, int(registry.get("schemaVersion") or 1))
    registry.setdefault("agents", [])
    registry.setdefault("claims", [])
    registry.setdefault("coordinations", [])
    registry.setdefault("recentEvents", [])
    for coordination in registry["coordinations"]:
        coordination.setdefault("pausedAgentIds", [])
        coordination.setdefault("resumedAgentIds", [])
        coordination.setdefault("cancelledResumeAgents", [])
        coordination.setdefault("ownerHistory", [])
        if coordination.get("state") == "open":
            if not coordination.get("ownerLeaseUntil"):
                lease_base = (
                    parse_utc(coordination.get("updatedAt"))
                    or parse_utc(coordination.get("createdAt"))
                    or datetime.now(timezone.utc) - timedelta(minutes=COORDINATION_OWNER_TTL_MINUTES + 1)
                )
                coordination["ownerLeaseUntil"] = (
                    lease_base + timedelta(minutes=COORDINATION_OWNER_TTL_MINUTES)
                ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            coordination.setdefault("resumePendingAgentIds", [])
            coordination.setdefault("recoveryState", "active")
            continue
        paused_agent_ids = [
            item.get("id")
            for item in registry["agents"]
            if item.get("state") == "paused" and item.get("coordinationId") == coordination.get("id")
        ]
        coordination.setdefault("resumePendingAgentIds", paused_agent_ids)
        coordination.setdefault(
            "recoveryState",
            "resume-pending" if coordination["resumePendingAgentIds"] else "closed",
        )
    return registry


def _legacy_agent_id(label: str) -> str:
    return canonical_agent_id(label)


def migrate_legacy_claims(registry: dict, project_root: Path) -> dict:
    source = legacy_registry_path(project_root)
    if registry.get("claims") or not source.exists():
        return registry
    try:
        legacy = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return registry
    claims = legacy.get("claims", [])
    if not isinstance(claims, list) or not claims:
        return registry

    agents_by_id = {item.get("id"): item for item in registry.get("agents", [])}
    now = utc_now()
    for original in claims:
        claim = deepcopy(original)
        label = str(claim.get("agent") or "legacy-agent")
        agent_id = str(claim.get("agentId") or _legacy_agent_id(label))
        claim["agentId"] = agent_id
        claim.setdefault("createdAt", now)
        claim.setdefault("updatedAt", now)
        claim.setdefault("expiresAt", future_utc(240))
        registry["claims"].append(claim)
        if agent_id not in agents_by_id:
            agent = {
                "id": agent_id,
                "label": label,
                "task": str(claim.get("task") or "Migrated work"),
                "state": "active" if claim.get("status") in ACTIVE_CLAIM_STATUSES else "stale",
                "stage": "migrated",
                "currentAction": "",
                "lastCheckpoint": "",
                "nextCheckpoint": "",
                "blocker": "",
                "branch": "",
                "worktree": "",
                "threadId": "",
                "scopes": list(claim.get("scopes") or []),
                "baseCommit": "",
                "headCommit": "",
                "createdAt": now,
                "updatedAt": now,
                "leaseUntil": claim.get("expiresAt") or future_utc(240),
            }
            registry["agents"].append(agent)
            agents_by_id[agent_id] = agent
    registry["migration"] = {"source": str(source), "migratedAt": now}
    return registry


def load_registry(project_root: Path, codex_home: Path | None = None) -> dict:
    path = registry_path(project_root, codex_home)
    if path.exists():
        registry = json.loads(path.read_text(encoding="utf-8"))
    else:
        registry = default_registry(project_root)
    ensure_registry_shape(registry, project_root)
    return migrate_legacy_claims(registry, project_root)


def write_registry(project_root: Path, registry: dict, codex_home: Path | None = None) -> None:
    path = registry_path(project_root, codex_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    payload = json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class RegistryLock:
    def __init__(self, path: Path, timeout_seconds: float = 10.0, stale_seconds: float = 60.0):
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self.acquired = False

    def __enter__(self) -> "RegistryLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(f"{os.getpid()} {time.time()}\n")
                self.acquired = True
                return self
            except (FileExistsError, PermissionError) as exc:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale_seconds:
                        try:
                            self.path.unlink(missing_ok=True)
                            continue
                        except PermissionError:
                            pass
                except FileNotFoundError:
                    continue
                except PermissionError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Could not inspect coordination registry lock: {self.path}") from exc
                    time.sleep(0.02)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Could not acquire coordination registry lock: {self.path}") from exc
                time.sleep(0.02)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


def mutate_registry(
    project_root: Path,
    mutator: Callable[[dict], Any],
    codex_home: Path | None = None,
) -> Any:
    with RegistryLock(lock_path(project_root, codex_home)):
        registry = load_registry(project_root, codex_home)
        result = mutator(registry)
        registry["revision"] = int(registry.get("revision", 0)) + 1
        registry["updatedAt"] = utc_now()
        registry["recentEvents"] = list(registry.get("recentEvents", []))[:MAX_RECENT_EVENTS]
        write_registry(project_root, registry, codex_home)
        return result


def add_event(registry: dict, kind: str, agent_id: str, summary: str, coordination_id: str = "") -> dict:
    event = {
        "id": f"event-{uuid4().hex[:12]}",
        "kind": kind,
        "agentId": agent_id,
        "summary": summary,
        "coordinationId": coordination_id,
        "timestamp": utc_now(),
    }
    registry.setdefault("recentEvents", []).insert(0, event)
    del registry["recentEvents"][MAX_RECENT_EVENTS:]
    return event


def find_agent(registry: dict, agent_id: str) -> dict:
    agent = next((item for item in registry.get("agents", []) if item.get("id") == agent_id), None)
    if agent is None:
        raise KeyError(f"Agent not found: {agent_id}")
    return agent


def register_agent(
    registry: dict,
    agent_id: str,
    label: str,
    *,
    thread_id: str = "",
    task: str = "",
    state: str | None = None,
    stage: str = "starting",
    current_action: str = "",
    last_checkpoint: str = "",
    next_checkpoint: str = "",
    blocker: str = "",
    branch: str = "",
    worktree: str = "",
    scopes: list[str] | None = None,
    base_commit: str = "",
    head_commit: str = "",
    ttl_minutes: int = 240,
) -> dict:
    if state is not None and state not in AGENT_STATES:
        raise ValueError(f"Unsupported agent state: {state}")
    now = utc_now()
    existing = next((item for item in registry.setdefault("agents", []) if item.get("id") == agent_id), None)
    if existing is not None and existing.get("state") == "paused" and state not in {None, "paused"}:
        raise CoordinationConflict("Paused agents must use resume so yielded scopes are rechecked.")
    effective_state = state or (existing.get("state") if existing else "active")
    agent = existing or {"id": agent_id, "createdAt": now}
    agent.update(
        {
            "label": label,
            "threadId": thread_id or agent.get("threadId", ""),
            "task": task or agent.get("task", ""),
            "state": effective_state,
            "stage": stage or agent.get("stage", ""),
            "currentAction": current_action or agent.get("currentAction", ""),
            "lastCheckpoint": last_checkpoint or agent.get("lastCheckpoint", ""),
            "nextCheckpoint": next_checkpoint or agent.get("nextCheckpoint", ""),
            "blocker": blocker or agent.get("blocker", ""),
            "branch": branch or agent.get("branch", ""),
            "worktree": worktree or agent.get("worktree", ""),
            "scopes": list(scopes) if scopes is not None else list(agent.get("scopes", [])),
            "baseCommit": base_commit or agent.get("baseCommit", ""),
            "headCommit": head_commit or agent.get("headCommit", ""),
            "updatedAt": now,
            "leaseUntil": future_utc(ttl_minutes),
        }
    )
    if existing is None:
        registry["agents"].append(agent)
    add_event(registry, "agent-joined" if existing is None else "agent-updated", agent_id, task or stage)
    return agent


def update_agent(registry: dict, agent_id: str, **changes: Any) -> dict:
    agent = find_agent(registry, agent_id)
    if agent.get("state") == "paused" and changes.get("state") not in {None, "paused"}:
        raise CoordinationConflict("Paused agents must use resume so yielded scopes are rechecked.")
    mapping = {
        "state": "state",
        "task": "task",
        "stage": "stage",
        "current_action": "currentAction",
        "last_checkpoint": "lastCheckpoint",
        "next_checkpoint": "nextCheckpoint",
        "blocker": "blocker",
        "branch": "branch",
        "worktree": "worktree",
        "scopes": "scopes",
        "base_commit": "baseCommit",
        "head_commit": "headCommit",
        "thread_id": "threadId",
    }
    for source, target in mapping.items():
        if source in changes and changes[source] is not None:
            if source == "state" and changes[source] not in AGENT_STATES:
                raise ValueError(f"Unsupported agent state: {changes[source]}")
            value = changes[source]
            agent[target] = list(value) if source == "scopes" else value
    agent["updatedAt"] = utc_now()
    agent["leaseUntil"] = future_utc(int(changes.get("ttl_minutes") or 240))
    add_event(registry, "agent-progress", agent_id, agent.get("currentAction") or agent.get("stage") or agent.get("task", ""))
    return agent


def normalize_scope(value: str) -> str:
    scope = value.replace("\\", "/").strip().strip("/").lower()
    return re.sub(r"/{2,}", "/", scope)


def is_repository_scope(value: str) -> bool:
    return normalize_scope(value) in {"*", ".", "repo", "repository", "project", "project-root"}


def scopes_overlap(left: str, right: str) -> bool:
    left_scope = normalize_scope(left)
    right_scope = normalize_scope(right)
    if not left_scope or not right_scope:
        return False
    if is_repository_scope(left_scope) or is_repository_scope(right_scope):
        return True
    return (
        left_scope == right_scope
        or left_scope.startswith(right_scope + "/")
        or right_scope.startswith(left_scope + "/")
    )


def find_claim_conflicts(
    registry: dict,
    lane_id: str | None,
    scopes: list[str],
    *,
    ignore_claim_ids: set[str] | None = None,
) -> list[dict]:
    mark_expired_claims(registry)
    ignored = ignore_claim_ids or set()
    conflicts = []
    for claim in registry.get("claims", []):
        if claim.get("id") in ignored or claim.get("status") not in ACTIVE_CLAIM_STATUSES:
            continue
        reasons = []
        if lane_id and claim.get("laneId") == lane_id:
            reasons.append(f"lane overlap: {lane_id}")
        for requested in scopes:
            for claimed in claim.get("scopes", []):
                if scopes_overlap(requested, claimed):
                    reasons.append(f"scope overlap: {requested} <-> {claimed}")
        if reasons:
            conflicts.append({"claim": claim, "reasons": sorted(set(reasons))})
    return conflicts


def mark_expired_claims(registry: dict) -> int:
    now = datetime.now(timezone.utc)
    changed = 0
    for claim in registry.get("claims", []):
        if claim.get("status") not in ACTIVE_CLAIM_STATUSES:
            continue
        expires_at = parse_utc(claim.get("expiresAt"))
        if expires_at is not None and expires_at < now:
            claim["status"] = "expired"
            claim["updatedAt"] = utc_now()
            changed += 1
    return changed


def create_claim(
    registry: dict,
    agent_id: str,
    lane_id: str,
    scopes: list[str],
    task: str,
    *,
    status: str = "active",
    ttl_minutes: int = 240,
    note: str = "",
    force: bool = False,
) -> dict:
    if status not in ACTIVE_CLAIM_STATUSES:
        raise ValueError(f"Unsupported active claim status: {status}")
    find_agent(registry, agent_id)
    normalized = [normalize_scope(item) for item in scopes if normalize_scope(item)] or [normalize_scope(lane_id)]
    normalized_lane = slugify(lane_id)
    mark_expired_claims(registry)
    reusable = next(
        (
            item
            for item in registry.get("claims", [])
            if item.get("agentId") == agent_id
            and item.get("laneId") == normalized_lane
            and item.get("status") in ACTIVE_CLAIM_STATUSES
        ),
        None,
    )
    ignored = {reusable.get("id")} if reusable else set()
    conflicts = find_claim_conflicts(registry, normalized_lane, normalized, ignore_claim_ids=ignored)
    if conflicts and not force:
        raise CoordinationConflict("Requested work overlaps an active claim.", conflicts)
    if reusable is not None:
        reusable.update(
            {
                "task": task,
                "status": status,
                "scopes": list(dict.fromkeys([*reusable.get("scopes", []), *normalized])),
                "updatedAt": utc_now(),
                "expiresAt": future_utc(ttl_minutes),
                "notes": note or reusable.get("notes", ""),
            }
        )
        add_event(registry, "claim-refreshed", agent_id, task)
        return reusable
    now = utc_now()
    claim = {
        "id": f"claim-{uuid4().hex[:12]}",
        "laneId": normalized_lane,
        "agentId": agent_id,
        "agent": next((item.get("label") for item in registry.get("agents", []) if item.get("id") == agent_id), agent_id),
        "task": task,
        "status": status,
        "scopes": normalized,
        "createdAt": now,
        "updatedAt": now,
        "expiresAt": future_utc(ttl_minutes),
        "notes": note,
    }
    registry.setdefault("claims", []).insert(0, claim)
    add_event(registry, "claim-created", agent_id, task)
    return claim


def release_claim(registry: dict, claim_id: str, status: str = "released", reason: str = "") -> dict:
    if status not in FINAL_CLAIM_STATUSES - {"expired"}:
        raise ValueError(f"Unsupported final claim status: {status}")
    claim = next((item for item in registry.get("claims", []) if item.get("id") == claim_id), None)
    if claim is None:
        raise KeyError(f"Claim not found: {claim_id}")
    claim["status"] = status
    claim["updatedAt"] = utc_now()
    if reason:
        claim["releaseReason"] = reason
    add_event(registry, "claim-released", str(claim.get("agentId") or ""), reason or status)
    return claim


def activate_claim(registry: dict, claim_id: str, force: bool = False) -> dict:
    claim = next((item for item in registry.get("claims", []) if item.get("id") == claim_id), None)
    if claim is None:
        raise KeyError(f"Claim not found: {claim_id}")
    conflicts = find_claim_conflicts(
        registry,
        claim.get("laneId"),
        list(claim.get("scopes", [])),
        ignore_claim_ids={claim_id},
    )
    if conflicts and not force:
        raise CoordinationConflict("Activating this claim would overlap active work.", conflicts)
    claim["status"] = "active"
    claim["updatedAt"] = utc_now()
    claim.pop("coordinationId", None)
    add_event(registry, "claim-activated", str(claim.get("agentId") or ""), claim.get("task", ""))
    return claim


def complete_agent(registry: dict, agent_id: str, summary: str = "") -> dict:
    agent = find_agent(registry, agent_id)
    if agent.get("state") == "paused":
        raise CoordinationConflict("Paused agents must resume or be explicitly cancelled before completion.")
    owned_open = [
        item
        for item in registry.get("coordinations", [])
        if item.get("ownerAgentId") == agent_id and item.get("state") == "open"
    ]
    resume_debts = [
        item
        for item in registry.get("coordinations", [])
        if item.get("ownerAgentId") == agent_id and item.get("resumePendingAgentIds")
    ]
    if owned_open or resume_debts:
        coordination_ids = [item.get("id", "") for item in [*owned_open, *resume_debts]]
        raise CoordinationConflict(
            "Agent still owns open coordination or unresolved resume debt: "
            + ", ".join(dict.fromkeys(coordination_ids))
        )
    agent.update(
        {
            "state": "completed",
            "currentAction": "",
            "lastCheckpoint": summary or agent.get("lastCheckpoint", ""),
            "nextCheckpoint": "",
            "blocker": "",
            "updatedAt": utc_now(),
        }
    )
    for claim in registry.get("claims", []):
        if claim.get("agentId") == agent_id and claim.get("status") in ACTIVE_CLAIM_STATUSES | {"yielded"}:
            claim["status"] = "completed"
            claim["updatedAt"] = utc_now()
    add_event(registry, "agent-completed", agent_id, summary or agent.get("task", ""))
    return agent


def prune_registry(registry: dict) -> dict:
    mark_expired_claims(registry)
    registry["claims"] = [
        item
        for item in registry.get("claims", [])
        if item.get("status") in ACTIVE_CLAIM_STATUSES | {"yielded", "blocked"}
    ]
    live_items = [
        item
        for item in registry.get("coordinations", [])
        if item.get("state") != "resolved" or item.get("resumePendingAgentIds")
    ]
    settled = [
        item
        for item in registry.get("coordinations", [])
        if item.get("state") == "resolved" and not item.get("resumePendingAgentIds")
    ][:20]
    registry["coordinations"] = live_items + settled
    registry["agents"] = [
        item
        for item in registry.get("agents", [])
        if item.get("state") not in {"completed", "stale"}
        or any(event.get("agentId") == item.get("id") for event in registry.get("recentEvents", [])[:20])
    ]
    return registry


def open_coordination(
    registry: dict,
    *,
    kind: str,
    owner_agent_id: str,
    participants: list[str],
    topic: str,
    surfaces: list[str] | None = None,
    summary: str = "",
    target_branch: str = "",
    owner_ttl_minutes: int = COORDINATION_OWNER_TTL_MINUTES,
) -> dict:
    if kind not in COORDINATION_KINDS:
        raise ValueError(f"Unsupported coordination kind: {kind}")
    find_agent(registry, owner_agent_id)
    normalized_participants = list(dict.fromkeys([owner_agent_id, *participants]))
    for participant in normalized_participants:
        find_agent(registry, participant)
    now = utc_now()
    coordination = {
        "id": f"coord-{uuid4().hex[:12]}",
        "kind": kind,
        "state": "open",
        "ownerAgentId": owner_agent_id,
        "participants": normalized_participants,
        "topic": topic,
        "surfaces": [normalize_scope(item) for item in surfaces or []],
        "summary": summary,
        "targetBranch": target_branch,
        "responses": [],
        "decision": "",
        "decisionReason": "",
        "ownerLeaseUntil": future_utc(owner_ttl_minutes),
        "recoveryState": "active",
        "pausedAgentIds": [],
        "resumePendingAgentIds": [],
        "resumedAgentIds": [],
        "cancelledResumeAgents": [],
        "ownerHistory": [],
        "createdAt": now,
        "updatedAt": now,
    }
    registry.setdefault("coordinations", []).insert(0, coordination)
    add_event(registry, f"{kind}-opened", owner_agent_id, topic, coordination["id"])
    return coordination


def find_coordination(registry: dict, coordination_id: str) -> dict:
    coordination = next(
        (item for item in registry.get("coordinations", []) if item.get("id") == coordination_id),
        None,
    )
    if coordination is None:
        raise KeyError(f"Coordination not found: {coordination_id}")
    return coordination


def respond_coordination(
    registry: dict,
    coordination_id: str,
    agent_id: str,
    status: str,
    summary: str,
    evidence: list[str] | None = None,
) -> dict:
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("state") != "open":
        raise CoordinationConflict(f"Coordination is not open: {coordination_id}")
    if agent_id not in coordination.get("participants", []):
        raise CoordinationConflict(f"Agent is not a participant in {coordination_id}: {agent_id}")
    find_agent(registry, agent_id)
    response = next((item for item in coordination.setdefault("responses", []) if item.get("agentId") == agent_id), None)
    payload = {
        "agentId": agent_id,
        "status": status,
        "summary": summary,
        "evidence": list(evidence or []),
        "updatedAt": utc_now(),
    }
    if response is None:
        coordination["responses"].append(payload)
        response = payload
    else:
        response.update(payload)
    coordination["updatedAt"] = utc_now()
    if coordination.get("ownerAgentId") == agent_id:
        coordination["ownerLeaseUntil"] = future_utc(COORDINATION_OWNER_TTL_MINUTES)
        coordination["recoveryState"] = "active"
    add_event(registry, "coordination-response", agent_id, summary, coordination_id)
    return response


def heartbeat_coordination_owner(
    registry: dict,
    coordination_id: str,
    agent_id: str,
    summary: str = "",
    ttl_minutes: int = COORDINATION_OWNER_TTL_MINUTES,
) -> dict:
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("state") != "open":
        raise CoordinationConflict(f"Coordination is not open: {coordination_id}")
    if coordination.get("ownerAgentId") != agent_id:
        raise CoordinationConflict(f"Only the coordination owner can heartbeat {coordination_id}.")
    find_agent(registry, agent_id)
    coordination["ownerLeaseUntil"] = future_utc(ttl_minutes)
    coordination["recoveryState"] = "active"
    coordination["updatedAt"] = utc_now()
    if summary:
        coordination["summary"] = summary
    add_event(registry, "coordination-heartbeat", agent_id, summary or "Owner lease refreshed", coordination_id)
    return coordination


def take_over_coordination(
    registry: dict,
    coordination_id: str,
    new_owner_agent_id: str,
    reason: str,
    *,
    force: bool = False,
    ttl_minutes: int = COORDINATION_OWNER_TTL_MINUTES,
) -> dict:
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("state") != "open":
        raise CoordinationConflict(f"Only open coordination can be taken over: {coordination_id}")
    new_owner = find_agent(registry, new_owner_agent_id)
    previous_owner_id = str(coordination.get("ownerAgentId") or "")
    if previous_owner_id == new_owner_agent_id:
        return heartbeat_coordination_owner(
            registry,
            coordination_id,
            new_owner_agent_id,
            reason,
            ttl_minutes,
        )

    previous_owner = next(
        (item for item in registry.get("agents", []) if item.get("id") == previous_owner_id),
        None,
    )
    lease_until = parse_utc(coordination.get("ownerLeaseUntil"))
    owner_unavailable = (
        previous_owner is None
        or previous_owner.get("state") in {"completed", "stale"}
        or coordination.get("recoveryState") == "owner-stale"
        or (lease_until is not None and lease_until < datetime.now(timezone.utc))
    )
    if not owner_unavailable and not force:
        raise CoordinationConflict(
            f"Coordination owner is still active; explicit force is required to take over {coordination_id}."
        )

    now = utc_now()
    coordination.setdefault("ownerHistory", []).append(
        {
            "agentId": previous_owner_id,
            "replacedAt": now,
            "reason": reason,
            "forced": bool(force and not owner_unavailable),
        }
    )
    coordination["ownerAgentId"] = new_owner_agent_id
    coordination["participants"] = list(
        dict.fromkeys([*coordination.get("participants", []), new_owner_agent_id])
    )
    coordination["ownerLeaseUntil"] = future_utc(ttl_minutes)
    coordination["recoveryState"] = "active"
    coordination["recoveredAt"] = now
    coordination["updatedAt"] = now
    new_owner["leaseUntil"] = future_utc(max(ttl_minutes, COORDINATION_OWNER_TTL_MINUTES))
    new_owner["updatedAt"] = now
    add_event(registry, "coordination-taken-over", new_owner_agent_id, reason, coordination_id)
    return coordination


def resolve_coordination(
    registry: dict,
    coordination_id: str,
    agent_id: str,
    decision: str,
    reason: str,
) -> dict:
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("ownerAgentId") != agent_id:
        raise CoordinationConflict(f"Only the coordination owner can resolve {coordination_id}.")
    if coordination.get("state") == "resolved":
        if coordination.get("decision") == decision:
            return coordination
        raise CoordinationConflict(f"Coordination already has a different decision: {coordination_id}")
    paused_agent_ids = [
        item.get("id")
        for item in registry.get("agents", [])
        if item.get("state") == "paused" and item.get("coordinationId") == coordination_id
    ]
    resume_pending = list(
        dict.fromkeys([*coordination.get("resumePendingAgentIds", []), *paused_agent_ids])
    )
    coordination.update(
        {
            "state": "resolved",
            "decision": decision,
            "decisionReason": reason,
            "resolvedBy": agent_id,
            "updatedAt": utc_now(),
            "resolvedAt": utc_now(),
            "resumePendingAgentIds": resume_pending,
            "recoveryState": "resume-pending" if resume_pending else "closed",
        }
    )
    if not resume_pending:
        coordination["closedAt"] = utc_now()
    add_event(registry, "coordination-resolved", agent_id, decision, coordination_id)
    return coordination


def mark_coordination_synced(registry: dict, coordination_id: str, lane_id: str) -> dict:
    coordination = find_coordination(registry, coordination_id)
    coordination["memorySyncedAt"] = utc_now()
    coordination["memoryLaneId"] = lane_id
    coordination["updatedAt"] = utc_now()
    add_event(
        registry,
        "coordination-memory-synced",
        str(coordination.get("ownerAgentId") or ""),
        f"Synced to lane {lane_id}",
        coordination_id,
    )
    return coordination


def pause_agent(registry: dict, agent_id: str, coordination_id: str, reason: str) -> dict:
    agent = find_agent(registry, agent_id)
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("state") != "open":
        raise CoordinationConflict(f"Cannot pause an agent for resolved coordination: {coordination_id}")
    if agent_id not in coordination.get("participants", []):
        raise CoordinationConflict(f"Agent is not a participant in {coordination_id}: {agent_id}")
    agent.update(
        {
            "state": "paused",
            "blocker": reason,
            "coordinationId": coordination_id,
            "updatedAt": utc_now(),
        }
    )
    for claim in registry.get("claims", []):
        if claim.get("agentId") == agent_id and claim.get("status") in ACTIVE_CLAIM_STATUSES:
            claim["status"] = "yielded"
            claim["coordinationId"] = coordination_id
            claim["updatedAt"] = utc_now()
    coordination["pausedAgentIds"] = list(
        dict.fromkeys([*coordination.get("pausedAgentIds", []), agent_id])
    )
    coordination["resumePendingAgentIds"] = list(
        dict.fromkeys([*coordination.get("resumePendingAgentIds", []), agent_id])
    )
    coordination["ownerLeaseUntil"] = future_utc(COORDINATION_OWNER_TTL_MINUTES)
    coordination["updatedAt"] = utc_now()
    add_event(registry, "agent-paused", agent_id, reason, coordination_id)
    return agent


def resume_agent(registry: dict, agent_id: str, coordination_id: str) -> dict:
    agent = find_agent(registry, agent_id)
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("state") != "resolved":
        raise CoordinationConflict(f"Cannot resume before coordination is resolved: {coordination_id}")
    if agent_id not in coordination.get("resumePendingAgentIds", []):
        raise CoordinationConflict(f"Agent has no resume obligation in {coordination_id}: {agent_id}")
    yielded = [
        claim
        for claim in registry.get("claims", [])
        if claim.get("agentId") == agent_id
        and claim.get("status") == "yielded"
        and claim.get("coordinationId") == coordination_id
    ]
    conflicts = []
    for claim in yielded:
        conflicts.extend(
            find_claim_conflicts(
                registry,
                claim.get("laneId"),
                list(claim.get("scopes", [])),
                ignore_claim_ids={claim.get("id")},
            )
        )
    if conflicts:
        raise CoordinationConflict("Cannot resume while overlapping work remains active.", conflicts)
    for claim in yielded:
        claim["status"] = "active"
        claim["updatedAt"] = utc_now()
        claim.pop("coordinationId", None)
    agent.update(
        {
            "state": "active",
            "blocker": "",
            "coordinationId": "",
            "updatedAt": utc_now(),
            "leaseUntil": future_utc(240),
        }
    )
    coordination["resumePendingAgentIds"] = [
        item for item in coordination.get("resumePendingAgentIds", []) if item != agent_id
    ]
    coordination["resumedAgentIds"] = list(
        dict.fromkeys([*coordination.get("resumedAgentIds", []), agent_id])
    )
    coordination["updatedAt"] = utc_now()
    if coordination["resumePendingAgentIds"]:
        coordination["recoveryState"] = "resume-pending"
    else:
        coordination["recoveryState"] = "closed"
        coordination["closedAt"] = utc_now()
    add_event(registry, "agent-resumed", agent_id, "Resumed after conflict recheck", coordination_id)
    return agent


def cancel_resume_obligation(
    registry: dict,
    coordination_id: str,
    owner_agent_id: str,
    target_agent_id: str,
    reason: str,
    *,
    confirmed_by_user: bool = False,
) -> dict:
    if not confirmed_by_user:
        raise CoordinationConflict(
            "Cancelling resume debt requires explicit user cancellation or archival confirmation."
        )
    coordination = find_coordination(registry, coordination_id)
    if coordination.get("ownerAgentId") != owner_agent_id:
        raise CoordinationConflict(f"Only the coordination owner can cancel resume debt in {coordination_id}.")
    if coordination.get("state") != "resolved":
        raise CoordinationConflict(f"Resolve coordination before cancelling resume debt: {coordination_id}")
    if target_agent_id not in coordination.get("resumePendingAgentIds", []):
        raise CoordinationConflict(f"Agent has no resume obligation in {coordination_id}: {target_agent_id}")

    target = find_agent(registry, target_agent_id)
    now = utc_now()
    coordination["resumePendingAgentIds"] = [
        item for item in coordination.get("resumePendingAgentIds", []) if item != target_agent_id
    ]
    coordination.setdefault("cancelledResumeAgents", []).append(
        {
            "agentId": target_agent_id,
            "reason": reason,
            "confirmedByUser": True,
            "cancelledAt": now,
        }
    )
    coordination["updatedAt"] = now
    target.update(
        {
            "state": "completed",
            "coordinationId": "",
            "currentAction": "",
            "nextCheckpoint": "",
            "blocker": reason,
            "updatedAt": now,
        }
    )
    for claim in registry.get("claims", []):
        if (
            claim.get("agentId") == target_agent_id
            and claim.get("status") == "yielded"
            and claim.get("coordinationId") == coordination_id
        ):
            claim["status"] = "released"
            claim["releaseReason"] = reason
            claim["updatedAt"] = now
    if coordination["resumePendingAgentIds"]:
        coordination["recoveryState"] = "resume-pending"
    else:
        coordination["recoveryState"] = "closed"
        coordination["closedAt"] = now
    add_event(registry, "resume-obligation-cancelled", owner_agent_id, reason, coordination_id)
    return coordination


def mark_stale_agents(registry: dict) -> int:
    now = datetime.now(timezone.utc)
    changed = 0
    for agent in registry.get("agents", []):
        if agent.get("state") in {"completed", "stale"}:
            continue
        lease_until = parse_utc(agent.get("leaseUntil"))
        if lease_until is not None and lease_until < now:
            agent["state"] = "stale"
            agent["updatedAt"] = utc_now()
            changed += 1
    return changed


def mark_stale_coordination_owners(registry: dict) -> int:
    now = datetime.now(timezone.utc)
    changed = 0
    agents = {item.get("id"): item for item in registry.get("agents", [])}
    for coordination in registry.get("coordinations", []):
        if coordination.get("state") != "open" or coordination.get("recoveryState") == "owner-stale":
            continue
        owner = agents.get(coordination.get("ownerAgentId"))
        lease_until = parse_utc(coordination.get("ownerLeaseUntil"))
        unavailable = (
            owner is None
            or owner.get("state") in {"completed", "stale"}
            or (lease_until is not None and lease_until < now)
        )
        if unavailable:
            coordination["recoveryState"] = "owner-stale"
            coordination["ownerStaleAt"] = utc_now()
            coordination["updatedAt"] = utc_now()
            add_event(
                registry,
                "coordination-owner-stale",
                str(coordination.get("ownerAgentId") or ""),
                "Coordination requires takeover before work can continue",
                str(coordination.get("id") or ""),
            )
            changed += 1
    return changed


def public_snapshot(registry: dict) -> dict:
    snapshot = {
        "schemaVersion": registry.get("schemaVersion", 1),
        "revision": registry.get("revision", 0),
        "project": {
            "id": registry.get("project", {}).get("id", ""),
            "name": registry.get("project", {}).get("name", ""),
        },
        "agents": [],
        "claims": deepcopy(registry.get("claims", [])),
        "coordinations": deepcopy(registry.get("coordinations", [])),
        "recentEvents": deepcopy(registry.get("recentEvents", []))[:20],
        "updatedAt": registry.get("updatedAt", ""),
    }
    for original in registry.get("agents", []):
        agent = {key: deepcopy(value) for key, value in original.items() if key not in {"threadId", "worktree"}}
        snapshot["agents"].append(agent)
    return snapshot
