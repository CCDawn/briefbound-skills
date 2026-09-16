from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from coordination_model import (  # noqa: E402
    CoordinationConflict,
    cancel_resume_obligation,
    complete_agent,
    coordination_root,
    create_claim,
    ensure_registry_shape,
    load_registry,
    mark_stale_coordination_owners,
    mutate_registry,
    open_coordination,
    pause_agent,
    public_snapshot,
    prune_registry,
    register_agent,
    release_claim,
    resolve_coordination,
    respond_coordination,
    resume_agent,
    slugify,
    take_over_coordination,
    update_agent,
)


def run_git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_coordination(
    project: Path,
    codex_home: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "agent_coordination.py"), str(project), *args],
        check=check,
        capture_output=True,
        text=True,
        env=environment,
    )


def run_script(name: str, project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / name), str(project), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def run_sync(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_script("sync_project_memory.py", project, *args, check=check)


def run_render(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_script("render_overview.py", project, *args, check=check)


def run_capture(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_script("capture_note.py", project, *args, check=check)


def init_memory_root(seed: Path) -> Path:
    seed.mkdir()
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "init_project_memory.py"),
            str(seed),
            "--skip-agents-rules",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return seed / ".docs" / "project-memory"


def lane_fixture(lane_id: str, issues: list[dict]) -> dict:
    return {
        "id": lane_id,
        "title": lane_id.replace("-", " ").title(),
        "owner": "shared-session",
        "focus": "",
        "phase": "Active",
        "health": "green",
        "lastUpdated": "2026-08-17T00:00:00Z",
        "modules": [],
        "decisions": [],
        "issues": issues,
        "todos": [],
        "techNotes": [],
        "recentUpdates": [],
    }


def lane_bytes(external_root: Path, lane_id: str) -> bytes:
    return (external_root / "lanes" / f"{lane_id}.json").read_bytes()


class AgentCoordinationTests(unittest.TestCase):
    def test_implicit_agent_id_does_not_add_a_second_agent_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()

            joined = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "agent-root-source-search-brief-production",
                    "--thread-id",
                    "thread-source-search",
                    "--task",
                    "Implement source search brief",
                    "--json",
                ).stdout
            )
            claimed = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "claim",
                    "--lane",
                    "challenge-cup-frontend",
                    "--scope",
                    "web/src/routes/TeamsRoute.tsx",
                    "--agent",
                    "agent-root-source-search-brief-production",
                    "--task",
                    "Implement source search brief",
                    "--json",
                ).stdout
            )["claim"]

            self.assertEqual("agent-root-source-search-brief-production", joined["id"])
            self.assertEqual(joined["id"], claimed["agentId"])

    def test_join_reuses_the_active_agent_identity_for_the_same_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()

            first = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "Source search brief owner",
                    "--agent-id",
                    "agent-root-source-search-brief-production",
                    "--thread-id",
                    "thread-source-search",
                    "--task",
                    "Implement source search brief",
                    "--json",
                ).stdout
            )
            second = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "Codex source search brief production",
                    "--thread-id",
                    "thread-source-search",
                    "--task",
                    "Continue source search brief",
                    "--json",
                ).stdout
            )
            explicit_alias = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "Another label for the same task",
                    "--agent-id",
                    "agent-source-search-alias",
                    "--thread-id",
                    "thread-source-search",
                    "--task",
                    "Continue source search brief",
                    "--json",
                ).stdout
            )
            registry = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "status",
                    "--include-completed",
                    "--json",
                ).stdout
            )

            self.assertEqual(first["id"], second["id"])
            self.assertEqual(first["id"], explicit_alias["id"])
            self.assertEqual(
                [first["id"]],
                [item["id"] for item in registry["agents"]],
            )

    def test_parallel_root_labels_get_distinct_thread_bound_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()

            first = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "/root",
                    "--thread-id",
                    "thread-top-level-a",
                    "--task",
                    "First top-level task",
                    "--json",
                ).stdout
            )
            second = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    "/root",
                    "--thread-id",
                    "thread-top-level-b",
                    "--task",
                    "Second top-level task",
                    "--json",
                ).stdout
            )
            registry = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "status",
                    "--include-completed",
                    "--json",
                ).stdout
            )

            self.assertNotEqual(first["id"], second["id"])
            self.assertTrue(second["id"].startswith("agent-thread-"))
            self.assertEqual(
                {
                    "thread-top-level-a": first["id"],
                    "thread-top-level-b": second["id"],
                },
                {item["threadId"]: item["id"] for item in registry["agents"]},
            )

    def test_explicit_agent_identity_cannot_be_rebound_to_another_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()

            run_coordination(
                project,
                codex_home,
                "join",
                "--agent",
                "/root",
                "--agent-id",
                "agent-root-legacy",
                "--thread-id",
                "thread-top-level-a",
                "--task",
                "First top-level task",
            )
            rebound = run_coordination(
                project,
                codex_home,
                "join",
                "--agent",
                "/root",
                "--agent-id",
                "agent-root-legacy",
                "--thread-id",
                "thread-top-level-b",
                "--task",
                "Second top-level task",
                check=False,
            )

            self.assertNotEqual(0, rebound.returncode)
            self.assertIn("already bound to thread", rebound.stderr)

    def test_update_completed_closes_owned_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()

            run_coordination(
                project,
                codex_home,
                "join",
                "--agent",
                "Agent A",
                "--agent-id",
                "agent-a",
                "--task",
                "Frontend task",
            )
            claim = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "claim",
                    "--lane",
                    "frontend",
                    "--scope",
                    "web/src",
                    "--agent-id",
                    "agent-a",
                    "--task",
                    "Frontend task",
                    "--json",
                ).stdout
            )["claim"]

            run_coordination(
                project,
                codex_home,
                "update",
                "--agent-id",
                "agent-a",
                "--state",
                "completed",
                "--last-checkpoint",
                "Merged and verified",
            )
            registry = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "status",
                    "--include-completed",
                    "--json",
                ).stdout
            )
            stored_claim = next(item for item in registry["claims"] if item["id"] == claim["id"])

            self.assertEqual("completed", stored_claim["status"])
            self.assertEqual("completed", registry["agents"][0]["state"])

    def test_preflight_blocks_development_on_primary_main_but_allows_linked_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            worker = Path(temp) / "worker"
            codex_home = Path(temp) / "codex-home"
            root.mkdir()
            run_git("init", "-b", "main", cwd=root)
            (root / "README.md").write_text("baseline\n", encoding="utf-8")
            run_git("add", "README.md", cwd=root)
            run_git(
                "-c",
                "user.name=Briefbound Test",
                "-c",
                "user.email=briefbound@example.invalid",
                "commit",
                "-m",
                "baseline",
                cwd=root,
            )
            run_git("worktree", "add", "-b", "worker", str(worker), cwd=root)

            blocked = run_coordination(
                root,
                codex_home,
                "preflight",
                "--agent-id",
                "agent-a",
                "--scope",
                "src",
                "--json",
                check=False,
            )
            self.assertEqual(2, blocked.returncode)
            blocked_payload = json.loads(blocked.stdout)
            self.assertEqual("ISOLATION_REQUIRED", blocked_payload["state"])
            self.assertTrue(blocked_payload["primaryWorktree"])
            self.assertEqual("main", blocked_payload["branch"])

            allowed = json.loads(
                run_coordination(
                    worker,
                    codex_home,
                    "preflight",
                    "--agent-id",
                    "agent-a",
                    "--scope",
                    "src",
                    "--json",
                ).stdout
            )
            self.assertEqual("CLEAR", allowed["state"])
            self.assertFalse(allowed["primaryWorktree"])

    def test_preflight_allows_explicit_mechanical_write_on_primary_main(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            root.mkdir()
            run_git("init", "-b", "main", cwd=root)

            payload = json.loads(
                run_coordination(
                    root,
                    codex_home,
                    "preflight",
                    "--agent-id",
                    "agent-a",
                    "--scope",
                    "README.md",
                    "--write-kind",
                    "mechanical",
                    "--json",
                ).stdout
            )

            self.assertEqual("CLEAR", payload["state"])
            self.assertEqual("mechanical", payload["writeKind"])

    def test_preflight_requires_integration_claim_and_clean_primary_main(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            root.mkdir()
            run_git("init", "-b", "main", cwd=root)
            (root / "README.md").write_text("baseline\n", encoding="utf-8")
            run_git("add", "README.md", cwd=root)
            run_git(
                "-c",
                "user.name=Briefbound Test",
                "-c",
                "user.email=briefbound@example.invalid",
                "commit",
                "-m",
                "baseline",
                cwd=root,
            )

            missing = run_coordination(
                root,
                codex_home,
                "preflight",
                "--agent-id",
                "agent-a",
                "--write-kind",
                "integration",
                "--json",
                check=False,
            )
            self.assertEqual(2, missing.returncode)
            self.assertEqual("INTEGRATION_CLAIM_REQUIRED", json.loads(missing.stdout)["state"])

            run_coordination(
                root,
                codex_home,
                "join",
                "--agent",
                "Agent A",
                "--agent-id",
                "agent-a",
                "--task",
                "integrate main",
                "--branch",
                "main",
                "--worktree",
                str(root),
                "--json",
            )
            run_coordination(
                root,
                codex_home,
                "claim",
                "--lane",
                "integration/main",
                "--agent-id",
                "agent-a",
                "--task",
                "integrate main",
                "--json",
            )

            allowed = json.loads(
                run_coordination(
                    root,
                    codex_home,
                    "preflight",
                    "--agent-id",
                    "agent-a",
                    "--write-kind",
                    "integration",
                    "--json",
                ).stdout
            )
            self.assertEqual("CLEAR", allowed["state"])
            self.assertTrue(allowed["integrationClaim"])

            (root / "README.md").write_text("dirty\n", encoding="utf-8")
            dirty = run_coordination(
                root,
                codex_home,
                "preflight",
                "--agent-id",
                "agent-a",
                "--write-kind",
                "integration",
                "--json",
                check=False,
            )
            self.assertEqual(2, dirty.returncode)
            self.assertEqual("DIRTY_TARGET", json.loads(dirty.stdout)["state"])

    def test_cli_preflight_is_silent_without_registry_and_routes_only_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()
            clear = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "preflight",
                    "--agent-id",
                    "agent-a",
                    "--scope",
                    "core/api",
                    "--json",
                ).stdout
            )
            self.assertEqual("CLEAR", clear["state"])
            self.assertFalse(clear["registryExists"])
            self.assertFalse(coordination_root(project, codex_home=codex_home).exists())

            for agent_id, scope in (("agent-a", "core/api"), ("agent-b", "web/src")):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--task",
                    "parallel work",
                    "--scope",
                    scope,
                    "--json",
                )
            no_overlap = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "preflight",
                    "--agent-id",
                    "agent-a",
                    "--scope",
                    "core/api",
                    "--json",
                ).stdout
            )
            self.assertEqual("PEERS_NO_OVERLAP", no_overlap["state"])
            self.assertEqual("agent-b", no_overlap["activePeers"][0]["id"])

            overlap_result = run_coordination(
                project,
                codex_home,
                "preflight",
                "--agent-id",
                "agent-a",
                "--scope",
                "web/src/components",
                "--json",
                check=False,
            )
            self.assertEqual(1, overlap_result.returncode)
            overlap = json.loads(overlap_result.stdout)
            self.assertEqual("OVERLAP", overlap["state"])
            self.assertEqual("agent-b", overlap["overlaps"][0]["agentId"])

    def test_git_worktrees_share_one_coordination_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            worktree = Path(temp) / "worker"
            root.mkdir()
            run_git("init", cwd=root)
            run_git("config", "user.email", "test@example.com", cwd=root)
            run_git("config", "user.name", "Test User", cwd=root)
            (root / "README.md").write_text("test\n", encoding="utf-8")
            run_git("add", "README.md", cwd=root)
            run_git("commit", "-m", "init", cwd=root)
            run_git("worktree", "add", "-b", "worker", str(worktree), cwd=root)

            self.assertEqual(coordination_root(root), coordination_root(worktree))

    def test_existing_legacy_coordination_registry_keeps_active_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            run_git("init", cwd=project)
            common_dir = Path(run_git("rev-parse", "--git-common-dir", cwd=project))
            if not common_dir.is_absolute():
                common_dir = (project / common_dir).resolve()
            legacy_root = common_dir / "ccdawn" / "coordination"
            legacy_root.mkdir(parents=True)
            (legacy_root / "registry.json").write_text("{}", encoding="utf-8")

            self.assertEqual(coordination_root(project), legacy_root)

    def test_cli_worktree_conflict_pause_resume_completion_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            worktree_a = Path(temp) / "agent-a"
            worktree_b = Path(temp) / "agent-b"
            codex_home = Path(temp) / "codex-home"
            root.mkdir()
            run_git("init", "-b", "main", cwd=root)
            run_git("config", "user.email", "test@example.com", cwd=root)
            run_git("config", "user.name", "Test User", cwd=root)
            (root / "shared").mkdir()
            (root / "shared" / "router.ts").write_text("export const route = 'base';\n", encoding="utf-8")
            run_git("add", "shared/router.ts", cwd=root)
            run_git("commit", "-m", "init", cwd=root)
            run_git("worktree", "add", "-b", "agent-a", str(worktree_a), cwd=root)
            run_git("worktree", "add", "-b", "agent-b", str(worktree_b), cwd=root)

            for project, agent_id, branch in (
                (worktree_a, "agent-a", "agent-a"),
                (worktree_b, "agent-b", "agent-b"),
            ):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--thread-id",
                    f"thread-{agent_id}",
                    "--task",
                    "shared router work",
                    "--branch",
                    branch,
                    "--worktree",
                    str(project),
                    "--scope",
                    "shared/router.ts",
                    "--json",
                )

            claim_b = json.loads(
                run_coordination(
                    worktree_b,
                    codex_home,
                    "claim",
                    "--lane",
                    "router-b",
                    "--scope",
                    "shared/router.ts",
                    "--agent-id",
                    "agent-b",
                    "--task",
                    "extend router",
                    "--json",
                ).stdout
            )["claim"]
            blocked_claim = run_coordination(
                worktree_a,
                codex_home,
                "claim",
                "--lane",
                "router-a",
                "--scope",
                "shared/router.ts",
                "--agent-id",
                "agent-a",
                "--task",
                "repair router",
                "--json",
                check=False,
            )
            self.assertEqual(1, blocked_claim.returncode)

            coordination = json.loads(
                run_coordination(
                    worktree_a,
                    codex_home,
                    "open",
                    "--kind",
                    "conflict",
                    "--owner-agent-id",
                    "agent-a",
                    "--participant",
                    "agent-b",
                    "--topic",
                    "shared router overlap",
                    "--surface",
                    "shared/router.ts",
                    "--json",
                ).stdout
            )
            coordination_id = coordination["id"]
            run_coordination(
                worktree_b,
                codex_home,
                "pause",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--reason",
                "yield shared router",
                "--json",
            )
            claim_a = json.loads(
                run_coordination(
                    worktree_a,
                    codex_home,
                    "claim",
                    "--lane",
                    "router-a",
                    "--scope",
                    "shared/router.ts",
                    "--agent-id",
                    "agent-a",
                    "--task",
                    "repair router",
                    "--json",
                ).stdout
            )["claim"]
            run_coordination(
                worktree_a,
                codex_home,
                "resolve",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-a",
                "--decision",
                "repair verified",
                "--reason",
                "release repair claim before resume",
                "--json",
            )

            early_complete = run_coordination(
                worktree_a,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--json",
                check=False,
            )
            self.assertEqual(1, early_complete.returncode)
            early_resume = run_coordination(
                worktree_b,
                codex_home,
                "resume",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--json",
                check=False,
            )
            self.assertEqual(1, early_resume.returncode)

            run_coordination(
                worktree_a,
                codex_home,
                "release",
                "--claim-id",
                claim_a["id"],
                "--status",
                "completed",
                "--reason",
                "repair verified",
                "--json",
            )
            run_coordination(
                worktree_b,
                codex_home,
                "resume",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--json",
            )
            run_coordination(
                worktree_a,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--summary",
                "repair and resume closed",
                "--json",
            )

            registry = json.loads(
                run_coordination(worktree_a, codex_home, "status", "--json").stdout
            )
            agents = {item["id"]: item for item in registry["agents"]}
            claims = {item["id"]: item for item in registry["claims"]}
            closed = next(item for item in registry["coordinations"] if item["id"] == coordination_id)
            self.assertEqual("completed", agents["agent-a"]["state"])
            self.assertEqual("active", agents["agent-b"]["state"])
            self.assertEqual("active", claims[claim_b["id"]]["status"])
            self.assertEqual([], closed["resumePendingAgentIds"])
            self.assertEqual("closed", closed["recoveryState"])

    def test_cli_stale_owner_takeover_inherits_resume_debt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            worktree_b = Path(temp) / "agent-b"
            worktree_c = Path(temp) / "agent-c"
            codex_home = Path(temp) / "codex-home"
            root.mkdir()
            run_git("init", "-b", "main", cwd=root)
            run_git("config", "user.email", "test@example.com", cwd=root)
            run_git("config", "user.name", "Test User", cwd=root)
            (root / "shared.txt").write_text("base\n", encoding="utf-8")
            run_git("add", "shared.txt", cwd=root)
            run_git("commit", "-m", "init", cwd=root)
            run_git("worktree", "add", "-b", "agent-b", str(worktree_b), cwd=root)
            run_git("worktree", "add", "-b", "agent-c", str(worktree_c), cwd=root)

            for project, agent_id in (
                (root, "agent-a"),
                (worktree_b, "agent-b"),
                (worktree_c, "agent-c"),
            ):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--thread-id",
                    f"thread-{agent_id}",
                    "--task",
                    "shared work",
                    "--branch",
                    "main" if agent_id == "agent-a" else agent_id,
                    "--worktree",
                    str(project),
                    "--scope",
                    "shared.txt",
                    "--json",
                )

            run_coordination(
                worktree_b,
                codex_home,
                "claim",
                "--lane",
                "shared-b",
                "--scope",
                "shared.txt",
                "--agent-id",
                "agent-b",
                "--task",
                "edit shared file",
                "--json",
            )
            coordination = json.loads(
                run_coordination(
                    root,
                    codex_home,
                    "open",
                    "--kind",
                    "conflict",
                    "--owner-agent-id",
                    "agent-a",
                    "--participant",
                    "agent-b",
                    "--topic",
                    "owner may stop during conflict",
                    "--surface",
                    "shared.txt",
                    "--json",
                ).stdout
            )
            coordination_id = coordination["id"]
            run_coordination(
                worktree_b,
                codex_home,
                "pause",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--reason",
                "yield for owner repair",
                "--json",
            )
            run_coordination(
                root,
                codex_home,
                "update",
                "--agent-id",
                "agent-a",
                "--state",
                "stale",
                "--current-action",
                "owner session stopped",
                "--json",
            )

            status = json.loads(run_coordination(worktree_c, codex_home, "status", "--json").stdout)
            stale = next(item for item in status["coordinations"] if item["id"] == coordination_id)
            self.assertEqual("owner-stale", stale["recoveryState"])
            taken_over = json.loads(
                run_coordination(
                    worktree_c,
                    codex_home,
                    "takeover",
                    "--coordination-id",
                    coordination_id,
                    "--agent-id",
                    "agent-c",
                    "--reason",
                    "agent-a stopped before conflict recovery",
                    "--json",
                ).stdout
            )
            self.assertEqual("agent-c", taken_over["ownerAgentId"])
            self.assertEqual(["agent-b"], taken_over["resumePendingAgentIds"])

            run_coordination(
                worktree_c,
                codex_home,
                "resolve",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-c",
                "--decision",
                "no conflicting write remains",
                "--reason",
                "takeover audit completed",
                "--json",
            )
            early_complete = run_coordination(
                worktree_c,
                codex_home,
                "complete",
                "--agent-id",
                "agent-c",
                "--json",
                check=False,
            )
            self.assertEqual(1, early_complete.returncode)
            run_coordination(
                worktree_b,
                codex_home,
                "resume",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--json",
            )
            run_coordination(
                worktree_c,
                codex_home,
                "complete",
                "--agent-id",
                "agent-c",
                "--summary",
                "takeover and resume closed",
                "--json",
            )

            registry = json.loads(
                run_coordination(worktree_c, codex_home, "status", "--json").stdout
            )
            agents = {item["id"]: item for item in registry["agents"]}
            closed = next(item for item in registry["coordinations"] if item["id"] == coordination_id)
            self.assertEqual("completed", agents["agent-c"]["state"])
            self.assertEqual("active", agents["agent-b"]["state"])
            self.assertEqual("agent-c", closed["ownerAgentId"])
            self.assertEqual("agent-a", closed["ownerHistory"][0]["agentId"])
            self.assertEqual([], closed["resumePendingAgentIds"])
            self.assertEqual("closed", closed["recoveryState"])

    def test_cli_partial_resume_keeps_remaining_debt_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()
            for agent_id in ("agent-a", "agent-b", "agent-c"):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--thread-id",
                    f"thread-{agent_id}",
                    "--task",
                    "shared coordination",
                    "--json",
                )

            coordination = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "open",
                    "--kind",
                    "conflict",
                    "--owner-agent-id",
                    "agent-a",
                    "--participant",
                    "agent-b",
                    "--participant",
                    "agent-c",
                    "--topic",
                    "pause two participants",
                    "--surface",
                    "shared",
                    "--json",
                ).stdout
            )
            coordination_id = coordination["id"]
            for agent_id in ("agent-b", "agent-c"):
                run_coordination(
                    project,
                    codex_home,
                    "pause",
                    "--agent-id",
                    agent_id,
                    "--coordination-id",
                    coordination_id,
                    "--reason",
                    "yield shared scope",
                    "--json",
                )

            registry = json.loads(run_coordination(project, codex_home, "status", "--json").stdout)
            current = next(item for item in registry["coordinations"] if item["id"] == coordination_id)
            self.assertEqual(["agent-b", "agent-c"], current["resumePendingAgentIds"])
            run_coordination(
                project,
                codex_home,
                "resolve",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-a",
                "--decision",
                "shared conflict resolved",
                "--reason",
                "both participants may resume",
                "--json",
            )
            run_coordination(
                project,
                codex_home,
                "resume",
                "--agent-id",
                "agent-b",
                "--coordination-id",
                coordination_id,
                "--json",
            )

            partial = json.loads(run_coordination(project, codex_home, "status", "--json").stdout)
            partial_coordination = next(
                item for item in partial["coordinations"] if item["id"] == coordination_id
            )
            self.assertEqual(["agent-c"], partial_coordination["resumePendingAgentIds"])
            self.assertEqual("resume-pending", partial_coordination["recoveryState"])
            blocked_complete = run_coordination(
                project,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--json",
                check=False,
            )
            self.assertEqual(1, blocked_complete.returncode)

            run_coordination(
                project,
                codex_home,
                "resume",
                "--agent-id",
                "agent-c",
                "--coordination-id",
                coordination_id,
                "--json",
            )
            run_coordination(
                project,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--summary",
                "all resume debts cleared",
                "--json",
            )
            final = json.loads(run_coordination(project, codex_home, "status", "--json").stdout)
            final_coordination = next(
                item for item in final["coordinations"] if item["id"] == coordination_id
            )
            final_agents = {item["id"]: item for item in final["agents"]}
            self.assertEqual([], final_coordination["resumePendingAgentIds"])
            self.assertEqual("closed", final_coordination["recoveryState"])
            self.assertEqual("active", final_agents["agent-b"]["state"])
            self.assertEqual("active", final_agents["agent-c"]["state"])
            self.assertEqual("completed", final_agents["agent-a"]["state"])

    def test_cli_cancel_one_resume_debt_preserves_other_participants(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()
            for agent_id in ("agent-a", "agent-b", "agent-c"):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--task",
                    "shared coordination",
                    "--json",
                )
            for agent_id in ("agent-b", "agent-c"):
                run_coordination(
                    project,
                    codex_home,
                    "claim",
                    "--lane",
                    f"lane-{agent_id}",
                    "--scope",
                    f"scope/{agent_id}",
                    "--agent-id",
                    agent_id,
                    "--task",
                    f"work for {agent_id}",
                    "--json",
                )

            coordination = json.loads(
                run_coordination(
                    project,
                    codex_home,
                    "open",
                    "--kind",
                    "conflict",
                    "--owner-agent-id",
                    "agent-a",
                    "--participant",
                    "agent-b",
                    "--participant",
                    "agent-c",
                    "--topic",
                    "cancel one paused task",
                    "--json",
                ).stdout
            )
            coordination_id = coordination["id"]
            for agent_id in ("agent-b", "agent-c"):
                run_coordination(
                    project,
                    codex_home,
                    "pause",
                    "--agent-id",
                    agent_id,
                    "--coordination-id",
                    coordination_id,
                    "--reason",
                    "await owner decision",
                    "--json",
                )
            run_coordination(
                project,
                codex_home,
                "resolve",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-a",
                "--decision",
                "cancel B and resume C",
                "--reason",
                "user archived only B task",
                "--json",
            )
            unauthorized_cancel = run_coordination(
                project,
                codex_home,
                "cancel-resume",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-a",
                "--target-agent-id",
                "agent-b",
                "--reason",
                "agent-b did not respond",
                "--json",
                check=False,
            )
            self.assertEqual(1, unauthorized_cancel.returncode)
            before_cancel = json.loads(
                run_coordination(project, codex_home, "status", "--json").stdout
            )
            before_coordination = next(
                item for item in before_cancel["coordinations"] if item["id"] == coordination_id
            )
            self.assertEqual(
                ["agent-b", "agent-c"], before_coordination["resumePendingAgentIds"]
            )

            run_coordination(
                project,
                codex_home,
                "cancel-resume",
                "--coordination-id",
                coordination_id,
                "--agent-id",
                "agent-a",
                "--target-agent-id",
                "agent-b",
                "--reason",
                "user explicitly cancelled and archived B task",
                "--confirmed-by-user",
                "--json",
            )

            partial = json.loads(run_coordination(project, codex_home, "status", "--json").stdout)
            agents = {item["id"]: item for item in partial["agents"]}
            claims = {item["agentId"]: item for item in partial["claims"]}
            current = next(item for item in partial["coordinations"] if item["id"] == coordination_id)
            self.assertEqual("completed", agents["agent-b"]["state"])
            self.assertEqual("released", claims["agent-b"]["status"])
            self.assertEqual("paused", agents["agent-c"]["state"])
            self.assertEqual("yielded", claims["agent-c"]["status"])
            self.assertEqual(["agent-c"], current["resumePendingAgentIds"])
            self.assertEqual("resume-pending", current["recoveryState"])
            blocked_complete = run_coordination(
                project,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--json",
                check=False,
            )
            self.assertEqual(1, blocked_complete.returncode)

            run_coordination(
                project,
                codex_home,
                "resume",
                "--agent-id",
                "agent-c",
                "--coordination-id",
                coordination_id,
                "--json",
            )
            run_coordination(
                project,
                codex_home,
                "complete",
                "--agent-id",
                "agent-a",
                "--summary",
                "cancelled B and resumed C",
                "--json",
            )
            final = json.loads(run_coordination(project, codex_home, "status", "--json").stdout)
            final_coordination = next(
                item for item in final["coordinations"] if item["id"] == coordination_id
            )
            self.assertEqual([], final_coordination["resumePendingAgentIds"])
            self.assertEqual("closed", final_coordination["recoveryState"])

    def test_concurrent_agent_registration_keeps_every_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            codex_home = Path(temp) / "codex-home"

            def join(index: int) -> None:
                mutate_registry(
                    project,
                    lambda registry: register_agent(
                        registry,
                        agent_id=f"agent-{index}",
                        label=f"Agent {index}",
                        task=f"Task {index}",
                        scopes=[f"scope/{index}"],
                    ),
                    codex_home=codex_home,
                )

            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(join, range(12)))

            registry = load_registry(project, codex_home=codex_home)
            self.assertEqual(12, len(registry["agents"]))
            self.assertEqual(12, registry["revision"])

    def test_concurrent_integration_claim_has_one_owner_then_allows_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            codex_home = Path(temp) / "codex-home"

            for agent_id in ("agent-a", "agent-b"):
                run_coordination(
                    project,
                    codex_home,
                    "join",
                    "--agent",
                    agent_id,
                    "--agent-id",
                    agent_id,
                    "--task",
                    "Integrate merge-ready delivery",
                    "--scope",
                    "target/main",
                    "--json",
                )

            def claim(agent_id: str) -> subprocess.CompletedProcess[str]:
                return run_coordination(
                    project,
                    codex_home,
                    "claim",
                    "--lane",
                    "integration/main",
                    "--scope",
                    "target/main",
                    "--agent-id",
                    agent_id,
                    "--task",
                    "Own local main integration",
                    "--json",
                    check=False,
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(claim, ("agent-a", "agent-b")))

            winners = [result for result in results if result.returncode == 0]
            blocked = [result for result in results if result.returncode != 0]
            self.assertEqual(1, len(winners))
            self.assertEqual(1, len(blocked))

            winning_claim = json.loads(winners[0].stdout)["claim"]
            winner_id = winning_claim["agentId"]
            next_owner_id = "agent-b" if winner_id == "agent-a" else "agent-a"

            run_coordination(
                project,
                codex_home,
                "release",
                "--claim-id",
                winning_claim["id"],
                "--status",
                "released",
                "--reason",
                "Explicit integration handoff",
                "--json",
            )
            replacement = json.loads(claim(next_owner_id).stdout)["claim"]
            self.assertEqual(next_owner_id, replacement["agentId"])

    def test_pause_yields_claim_and_resume_rechecks_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            codex_home = Path(temp) / "codex-home"

            def setup(registry: dict) -> None:
                register_agent(registry, "agent-a", "Agent A", task="Integrator")
                register_agent(registry, "agent-b", "Agent B", task="Frontend")
                create_claim(registry, "agent-b", "ui", ["web/src"], "Frontend work")
                open_coordination(
                    registry,
                    kind="conflict",
                    owner_agent_id="agent-a",
                    participants=["agent-a", "agent-b"],
                    topic="Resolve overlapping UI changes",
                    surfaces=["web/src"],
                )

            mutate_registry(project, setup, codex_home=codex_home)
            registry = load_registry(project, codex_home=codex_home)
            coordination_id = registry["coordinations"][0]["id"]

            mutate_registry(
                project,
                lambda value: pause_agent(value, "agent-b", coordination_id, "Yield UI scope"),
                codex_home=codex_home,
            )
            mutate_registry(
                project,
                lambda value: create_claim(value, "agent-a", "ui", ["web/src"], "Conflict repair"),
                codex_home=codex_home,
            )
            mutate_registry(
                project,
                lambda value: resolve_coordination(
                    value,
                    coordination_id,
                    "agent-a",
                    "Conflict repair verified",
                    "Resume after the repair claim is released",
                ),
                codex_home=codex_home,
            )

            with self.assertRaises(CoordinationConflict):
                mutate_registry(
                    project,
                    lambda value: resume_agent(value, "agent-b", coordination_id),
                    codex_home=codex_home,
                )

            registry = load_registry(project, codex_home=codex_home)
            active_claim = next(item for item in registry["claims"] if item["agentId"] == "agent-a")
            mutate_registry(
                project,
                lambda value: release_claim(value, active_claim["id"], "completed"),
                codex_home=codex_home,
            )
            mutate_registry(
                project,
                lambda value: resume_agent(value, "agent-b", coordination_id),
                codex_home=codex_home,
            )

            registry = load_registry(project, codex_home=codex_home)
            agent_b = next(item for item in registry["agents"] if item["id"] == "agent-b")
            claim_b = next(item for item in registry["claims"] if item["agentId"] == "agent-b")
            coordination = registry["coordinations"][0]
            self.assertEqual("active", agent_b["state"])
            self.assertEqual("active", claim_b["status"])
            self.assertEqual([], coordination["resumePendingAgentIds"])
            self.assertEqual("closed", coordination["recoveryState"])

    def test_join_or_update_cannot_bypass_paused_resume_check(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        coordination = open_coordination(
            registry,
            kind="conflict",
            owner_agent_id="agent-a",
            participants=["agent-a"],
            topic="Pause for shared scope",
        )
        pause_agent(registry, "agent-a", coordination["id"], "Wait for integration")

        refreshed = register_agent(registry, "agent-a", "Agent A", task="Same task")
        self.assertEqual("paused", refreshed["state"])
        with self.assertRaises(CoordinationConflict):
            register_agent(registry, "agent-a", "Agent A", state="active")
        with self.assertRaises(CoordinationConflict):
            update_agent(registry, "agent-a", state="active")

    def test_resume_requires_resolved_coordination(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        coordination = open_coordination(
            registry,
            kind="conflict",
            owner_agent_id="agent-a",
            participants=["agent-b"],
            topic="Shared file conflict",
        )
        pause_agent(registry, "agent-b", coordination["id"], "Wait for owner repair")

        with self.assertRaisesRegex(CoordinationConflict, "before coordination is resolved"):
            resume_agent(registry, "agent-b", coordination["id"])

    def test_owner_cannot_complete_until_resume_debt_is_cleared(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        coordination = open_coordination(
            registry,
            kind="conflict",
            owner_agent_id="agent-a",
            participants=["agent-b"],
            topic="Shared file conflict",
        )

        with self.assertRaisesRegex(CoordinationConflict, "open coordination"):
            complete_agent(registry, "agent-a")

        pause_agent(registry, "agent-b", coordination["id"], "Wait for owner repair")
        resolve_coordination(
            registry,
            coordination["id"],
            "agent-a",
            "Repair complete",
            "Target may resume",
        )
        self.assertEqual(["agent-b"], coordination["resumePendingAgentIds"])

        with self.assertRaisesRegex(CoordinationConflict, "resume debt"):
            complete_agent(registry, "agent-a")

        resume_agent(registry, "agent-b", coordination["id"])
        completed = complete_agent(registry, "agent-a", "Conflict and resume handshake complete")
        self.assertEqual("completed", completed["state"])

    def test_stale_owner_coordination_can_be_taken_over(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        coordination = open_coordination(
            registry,
            kind="conflict",
            owner_agent_id="agent-a",
            participants=["agent-a"],
            topic="Owner stopped during conflict repair",
        )

        with self.assertRaisesRegex(CoordinationConflict, "explicit force"):
            take_over_coordination(
                registry,
                coordination["id"],
                "agent-b",
                "Premature takeover",
            )

        coordination["ownerLeaseUntil"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.assertEqual(1, mark_stale_coordination_owners(registry))
        recovered = take_over_coordination(
            registry,
            coordination["id"],
            "agent-b",
            "Original owner stopped before resolving the conflict",
        )

        self.assertEqual("agent-b", recovered["ownerAgentId"])
        self.assertIn("agent-b", recovered["participants"])
        self.assertEqual("agent-a", recovered["ownerHistory"][0]["agentId"])
        self.assertEqual("active", recovered["recoveryState"])

    def test_explicit_cancellation_clears_resume_debt(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        create_claim(registry, "agent-b", "ui", ["web/src"], "Frontend work")
        coordination = open_coordination(
            registry,
            kind="conflict",
            owner_agent_id="agent-a",
            participants=["agent-b"],
            topic="Cancel obsolete frontend task",
        )
        pause_agent(registry, "agent-b", coordination["id"], "Await decision")
        resolve_coordination(registry, coordination["id"], "agent-a", "Cancel task", "User archived it")

        with self.assertRaisesRegex(CoordinationConflict, "explicit user cancellation"):
            cancel_resume_obligation(
                registry,
                coordination["id"],
                "agent-a",
                "agent-b",
                "Agent did not respond",
            )

        cancel_resume_obligation(
            registry,
            coordination["id"],
            "agent-a",
            "agent-b",
            "User explicitly cancelled and archived the task",
            confirmed_by_user=True,
        )

        agent_b = next(item for item in registry["agents"] if item["id"] == "agent-b")
        claim_b = next(item for item in registry["claims"] if item["agentId"] == "agent-b")
        self.assertEqual("completed", agent_b["state"])
        self.assertEqual("released", claim_b["status"])
        self.assertEqual([], coordination["resumePendingAgentIds"])
        self.assertEqual("closed", coordination["recoveryState"])

    def test_legacy_registry_backfills_resume_debt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            registry = {
                "schemaVersion": 1,
                "agents": [
                    {
                        "id": "agent-b",
                        "state": "paused",
                        "coordinationId": "coord-legacy",
                    }
                ],
                "claims": [],
                "coordinations": [
                    {
                        "id": "coord-legacy",
                        "kind": "conflict",
                        "state": "resolved",
                        "ownerAgentId": "agent-a",
                    }
                ],
                "recentEvents": [],
            }

            ensure_registry_shape(registry, project)

            coordination = registry["coordinations"][0]
            self.assertEqual(2, registry["schemaVersion"])
            self.assertEqual(["agent-b"], coordination["resumePendingAgentIds"])
            self.assertEqual("resume-pending", coordination["recoveryState"])

    def test_legacy_open_coordination_uses_existing_timestamp_for_owner_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            old_timestamp = (
                datetime.now(timezone.utc) - timedelta(minutes=31)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            registry = {
                "schemaVersion": 1,
                "agents": [{"id": "agent-a", "state": "active"}],
                "claims": [],
                "coordinations": [
                    {
                        "id": "coord-legacy-open",
                        "kind": "conflict",
                        "state": "open",
                        "ownerAgentId": "agent-a",
                        "updatedAt": old_timestamp,
                    }
                ],
                "recentEvents": [],
            }

            ensure_registry_shape(registry, project)

            self.assertEqual(1, mark_stale_coordination_owners(registry))
            self.assertEqual("owner-stale", registry["coordinations"][0]["recoveryState"])

    def test_reclaim_by_same_agent_is_idempotent(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        first = create_claim(registry, "agent-a", "api", ["core/api"], "Build API")
        second = create_claim(registry, "agent-a", "api", ["core/api"], "Build API")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, len(registry["claims"]))

    def test_collaboration_claim_atomically_reserves_peer_and_topic(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        first = create_claim(
            registry,
            "agent-a",
            "collaboration/auth-contract",
            ["thread/agent-reviewer", "shared/auth-contract"],
            "Coordinate auth contract",
        )

        with self.assertRaises(CoordinationConflict):
            create_claim(
                registry,
                "agent-b",
                "collaboration/duplicate-auth-contract",
                ["thread/agent-reviewer", "shared/auth-contract"],
                "Duplicate collaboration proposal",
            )

        release_claim(registry, first["id"], "released", "Peer declined")
        replacement = create_claim(
            registry,
            "agent-b",
            "collaboration/new-auth-contract",
            ["thread/agent-reviewer", "shared/auth-contract"],
            "New collaboration proposal",
        )
        self.assertEqual("agent-b", replacement["agentId"])

    def test_expired_claim_does_not_block_new_owner(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        expired = create_claim(registry, "agent-a", "api", ["core/api"], "Old API work")
        expired["expiresAt"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        current = create_claim(registry, "agent-b", "api", ["core/api"], "Current API work")

        self.assertEqual("agent-b", current["agentId"])
        self.assertEqual("expired", expired["status"])

    def test_repository_scope_blocks_every_nested_scope(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        create_claim(registry, "agent-a", "whole-project", ["repo"], "Repository migration")

        with self.assertRaises(CoordinationConflict):
            create_claim(registry, "agent-b", "ui", ["web/src"], "Frontend work")

    def test_non_ascii_labels_get_stable_distinct_ids(self) -> None:
        self.assertEqual(slugify("前端 Agent"), slugify("前端 Agent"))
        self.assertNotEqual(slugify("前端"), slugify("后端"))

    def test_prune_removes_closed_claim_history(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        closed = create_claim(registry, "agent-a", "api", ["core/api"], "Finished API")
        release_claim(registry, closed["id"], "completed")

        prune_registry(registry)

        self.assertEqual([], registry["claims"])

    def test_discussion_keeps_positions_and_one_decision(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        coordination = open_coordination(
            registry,
            kind="discussion",
            owner_agent_id="agent-a",
            participants=["agent-a", "agent-b"],
            topic="Fast merge order",
            surfaces=["core", "web"],
        )
        respond_coordination(
            registry,
            coordination["id"],
            "agent-b",
            "position",
            "Merge shared contract before UI",
            ["UI depends on the contract"],
        )
        resolve_coordination(
            registry,
            coordination["id"],
            "agent-a",
            "Merge core first, then UI",
            "Dependency order accepted",
        )

        self.assertEqual("resolved", coordination["state"])
        self.assertEqual(1, len(coordination["responses"]))
        self.assertEqual("Merge core first, then UI", coordination["decision"])

    def test_only_participants_respond_and_only_owner_resolves(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(registry, "agent-a", "Agent A")
        register_agent(registry, "agent-b", "Agent B")
        register_agent(registry, "agent-c", "Agent C")
        coordination = open_coordination(
            registry,
            kind="discussion",
            owner_agent_id="agent-a",
            participants=["agent-a", "agent-b"],
            topic="Choose merge order",
        )

        with self.assertRaises(CoordinationConflict):
            respond_coordination(registry, coordination["id"], "agent-c", "position", "Uninvited", [])
        with self.assertRaises(CoordinationConflict):
            resolve_coordination(registry, coordination["id"], "agent-b", "Decision", "Not owner")

    def test_legacy_claims_migrate_without_deleting_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            memory_dir = project / ".docs" / "project-memory"
            memory_dir.mkdir(parents=True)
            legacy_path = memory_dir / "agent-claims.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "claims": [
                            {
                                "id": "claim-old",
                                "laneId": "api",
                                "agent": "legacy-agent",
                                "task": "Legacy task",
                                "status": "active",
                                "scopes": ["core/api"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            registry = load_registry(project, codex_home=Path(temp) / "codex-home")

            self.assertEqual("claim-old", registry["claims"][0]["id"])
            self.assertEqual("legacy-agent", registry["agents"][0]["label"])
            self.assertTrue(legacy_path.exists())
            self.assertIn("agent-claims.json", registry["migration"]["source"])

    def test_public_snapshot_redacts_thread_and_absolute_worktree(self) -> None:
        registry: dict = {"agents": [], "claims": [], "coordinations": [], "recentEvents": []}
        register_agent(
            registry,
            "agent-a",
            "Agent A",
            thread_id="thread-secret",
            worktree="C:/secret/worktree",
            task="Visible task",
        )

        snapshot = public_snapshot(registry)
        encoded = json.dumps(snapshot)
        self.assertNotIn("thread-secret", encoded)
        self.assertNotIn("C:/secret/worktree", encoded)
        self.assertIn("Visible task", encoded)

    def test_resolved_coordination_syncs_decision_and_redacted_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            codex_home = Path(temp) / "codex-home"
            project.mkdir()
            environment = dict(os.environ)
            environment["CODEX_HOME"] = str(codex_home)
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "init_project_memory.py"),
                    str(project),
                    "--project-type",
                    "general",
                    "--dashboard-preset",
                    "default",
                    "--skip-agents-rules",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            def setup(registry: dict) -> str:
                register_agent(
                    registry,
                    "agent-a",
                    "Agent A",
                    thread_id="thread-secret",
                    worktree="C:/secret/worktree",
                    task="Integrate branches",
                    stage="merging",
                )
                coordination = open_coordination(
                    registry,
                    kind="merge",
                    owner_agent_id="agent-a",
                    participants=["agent-a"],
                    topic="Merge API before UI",
                    surfaces=["core/api", "web/src"],
                    target_branch="main",
                )
                resolve_coordination(
                    registry,
                    coordination["id"],
                    "agent-a",
                    "Merge API first, then UI",
                    "UI consumes the new contract",
                )
                return coordination["id"]

            coordination_id = mutate_registry(project, setup, codex_home=codex_home)
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "sync_project_memory.py"),
                    str(project),
                    "--lane",
                    "integration",
                    "--coordination-id",
                    coordination_id,
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            lane = json.loads(
                (project / ".docs" / "project-memory" / "lanes" / "integration.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(coordination_id, lane["decisions"][0]["coordinationId"])
            dashboard = (project / ".docs" / "project-memory" / "overview.html").read_text(encoding="utf-8")
            index = (project / ".docs" / "project-memory" / "INDEX.md").read_text(encoding="utf-8")
            self.assertIn("Active Agents", dashboard)
            self.assertIn("Agent A", dashboard)
            self.assertIn("Active agents: 1", index)
            self.assertNotIn("thread-secret", dashboard)
            self.assertNotIn("C:/secret/worktree", dashboard)

    def test_explicit_memory_root_sync_updates_summary_resolves_issue_and_keeps_legacy_tree_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            external_root = init_memory_root(Path(temp) / "seed")
            project = Path(temp) / "project"
            project.mkdir()
            lane_path = external_root / "lanes" / "backend.json"
            lane_path.write_text(
                json.dumps(
                    lane_fixture(
                        "backend",
                        [
                            {"title": "Fix auth bug", "status": "open", "severity": "high"},
                            {"title": "Fix auth bug", "status": "resolved"},
                            {"title": "Other issue", "status": "open"},
                        ],
                    )
                ),
                encoding="utf-8",
            )

            result = run_sync(
                project,
                "--memory-root",
                str(external_root),
                "--lane",
                "backend",
                "--focus",
                "external hardening",
                "--summary-phase",
                "Hardening",
                "--summary-focus",
                "External root sync",
                "--summary-health",
                "yellow",
                "--update",
                "hardened external sync",
                "--resolve-issue",
                "Fix auth bug",
                "--resolve-note",
                "root cause fixed",
            )
            self.assertEqual(0, result.returncode, result.stderr)

            lane = json.loads(lane_path.read_text(encoding="utf-8"))
            self.assertEqual("external hardening", lane["focus"])
            self.assertEqual(
                [],
                [item for item in lane["issues"] if item["title"] == "Fix auth bug" and item["status"] == "open"],
            )
            updated = next(
                item
                for item in lane["issues"]
                if item["title"] == "Fix auth bug" and item["status"] == "resolved" and item.get("resolvedAt")
            )
            self.assertEqual("root cause fixed", updated["resolution"])
            self.assertEqual("open", next(item for item in lane["issues"] if item["title"] == "Other issue")["status"])

            memory = json.loads((external_root / "memory.json").read_text(encoding="utf-8"))
            self.assertEqual("Hardening", memory["summary"]["currentPhase"])
            self.assertEqual("External root sync", memory["summary"]["focus"])
            self.assertEqual("yellow", memory["summary"]["health"])
            self.assertTrue((external_root / "INDEX.md").exists())
            self.assertTrue((external_root / "overview.html").exists())
            external_index = (external_root / "INDEX.md").read_text(encoding="utf-8")
            external_overview = (external_root / "overview.html").read_text(encoding="utf-8")
            self.assertNotIn(".docs/project-memory", external_index)
            self.assertNotIn("../../PROJECT_MEMORY.html", external_index)
            self.assertNotIn(".docs/project-memory", external_overview)
            self.assertNotIn(
                "Open <code>PROJECT_MEMORY.html</code> from the project root for the stable shortcut.",
                external_overview,
            )
            self.assertFalse((project / ".docs").exists())
            self.assertFalse((project / "PROJECT_MEMORY.html").exists())

    def test_explicit_memory_root_missing_or_uninitialized_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            missing = Path(temp) / "missing-root"

            result = run_sync(project, "--memory-root", str(missing), "--lane", "backend", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Memory root does not exist", result.stderr)
            self.assertFalse(missing.exists())
            self.assertFalse((project / ".docs").exists())

            partial = Path(temp) / "partial-root"
            partial.mkdir()
            (partial / "memory.json").write_text("{}", encoding="utf-8")
            result = run_sync(project, "--memory-root", str(partial), "--lane", "backend", check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("not initialized", result.stderr)
            self.assertFalse((partial / "inbox.json").exists())
            self.assertFalse((partial / "lanes").exists())
            self.assertFalse((project / ".docs").exists())

    def test_explicit_memory_root_zero_or_duplicate_issue_matches_fail_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            external_root = init_memory_root(Path(temp) / "seed")
            project = Path(temp) / "project"
            project.mkdir()
            lane_path = external_root / "lanes" / "backend.json"

            def snapshot() -> dict[str, bytes]:
                return {
                    "lane": lane_bytes(external_root, "backend"),
                    "memory": (external_root / "memory.json").read_bytes(),
                    "inbox": (external_root / "inbox.json").read_bytes(),
                    "index": (external_root / "INDEX.md").read_bytes(),
                    "overview": (external_root / "overview.html").read_bytes(),
                }

            lane_path.write_text(
                json.dumps(lane_fixture("backend", [{"title": "Auth bug", "status": "open"}])),
                encoding="utf-8",
            )
            archive_dir = external_root / "archive"
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            before = snapshot()
            zero = run_sync(
                project,
                "--memory-root",
                str(external_root),
                "--lane",
                "backend",
                "--resolve-issue",
                "Missing title",
                check=False,
            )
            self.assertNotEqual(0, zero.returncode)
            self.assertIn("exactly one", zero.stderr)
            self.assertFalse(archive_dir.exists())
            self.assertEqual(before, snapshot())

            lane_path.write_text(
                json.dumps(
                    lane_fixture(
                        "backend",
                        [
                            {"title": "Auth bug", "status": "open"},
                            {"title": "Auth bug", "status": "open"},
                        ],
                    )
                ),
                encoding="utf-8",
            )
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            before = snapshot()
            duplicate = run_sync(
                project,
                "--memory-root",
                str(external_root),
                "--lane",
                "backend",
                "--resolve-issue",
                "Auth bug",
                check=False,
            )
            self.assertNotEqual(0, duplicate.returncode)
            self.assertIn("exactly one", duplicate.stderr)
            self.assertFalse(archive_dir.exists())
            self.assertEqual(before, snapshot())

    def test_explicit_memory_root_capture_and_render_write_only_external_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            external_root = init_memory_root(Path(temp) / "seed")
            project = Path(temp) / "project"
            project.mkdir()

            captured = run_capture(
                project,
                "--memory-root",
                str(external_root),
                "--title",
                "Auth breadcrumb",
                "--details",
                "token rotation needed",
            )
            self.assertEqual(0, captured.returncode, captured.stderr)
            inbox = json.loads((external_root / "inbox.json").read_text(encoding="utf-8"))
            self.assertEqual("Auth breadcrumb", inbox["captures"][0]["title"])
            self.assertFalse((project / ".docs").exists())

            rendered = run_render(project, "--memory-root", str(external_root))
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertTrue((external_root / "INDEX.md").exists())
            self.assertTrue((external_root / "overview.html").exists())
            external_index = (external_root / "INDEX.md").read_text(encoding="utf-8")
            external_overview = (external_root / "overview.html").read_text(encoding="utf-8")
            self.assertNotIn(".docs/project-memory", external_index)
            self.assertNotIn("../../PROJECT_MEMORY.html", external_index)
            self.assertNotIn(".docs/project-memory", external_overview)
            self.assertNotIn(
                "Open <code>PROJECT_MEMORY.html</code> from the project root for the stable shortcut.",
                external_overview,
            )
            self.assertFalse((project / ".docs").exists())
            self.assertFalse((project / "PROJECT_MEMORY.html").exists())

    def test_init_refuses_to_overwrite_initialized_memory_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            first = run_script("init_project_memory.py", project, "--skip-agents-rules")
            self.assertEqual(0, first.returncode, first.stderr)
            memory_path = project / ".docs" / "project-memory" / "memory.json"
            inbox_path = project / ".docs" / "project-memory" / "inbox.json"
            captured = run_capture(project, "--title", "Keep me", "--details", "precious breadcrumb")
            self.assertEqual(0, captured.returncode, captured.stderr)
            memory_before = memory_path.read_bytes()

            refused = run_script("init_project_memory.py", project, "--skip-agents-rules", check=False)
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("already initialized", refused.stderr)
            self.assertIn("--force", refused.stderr)
            self.assertEqual(memory_before, memory_path.read_bytes())
            inbox = json.loads(inbox_path.read_text(encoding="utf-8"))
            self.assertEqual("Keep me", inbox["captures"][0]["title"])

    def test_init_force_overwrites_memory_and_resets_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            run_script("init_project_memory.py", project, "--skip-agents-rules")
            run_capture(project, "--title", "Wipe me", "--details", "stale breadcrumb")

            forced = run_script("init_project_memory.py", project, "--skip-agents-rules", "--force")
            self.assertEqual(0, forced.returncode, forced.stderr)
            memory_dir = project / ".docs" / "project-memory"
            inbox = json.loads((memory_dir / "inbox.json").read_text(encoding="utf-8"))
            self.assertEqual([], inbox["captures"])
            memory = json.loads((memory_dir / "memory.json").read_text(encoding="utf-8"))
            self.assertEqual("Initialized shared project memory", memory["recentUpdates"][0]["title"])


if __name__ == "__main__":
    unittest.main()
