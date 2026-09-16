from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import memory_model  # noqa: E402


class MemoryRootGateTests(unittest.TestCase):
    def setUp(self) -> None:
        memory_model.clear_memory_root_override()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self._projects_home_env = os.environ.get(memory_model._PROJECTS_HOME_ENV)
        os.environ[memory_model._PROJECTS_HOME_ENV] = str(self.base / "projects-home")

        def restore() -> None:
            if self._projects_home_env is None:
                os.environ.pop(memory_model._PROJECTS_HOME_ENV, None)
            else:
                os.environ[memory_model._PROJECTS_HOME_ENV] = self._projects_home_env
            memory_model.clear_memory_root_override()

        self.addCleanup(restore)

    def _write_marker(self, project_id: str, payload: dict) -> None:
        marker_dir = self.base / "projects-home" / project_id
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / memory_model.MIGRATION_MARKER_NAME).write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_explicit_memory_root_routes_writes(self) -> None:
        root = self.base / "repo"
        active = self.base / "active-memory"
        active.mkdir()
        resolved = memory_model.resolve_and_lock_memory_dir(root, str(active))
        self.assertEqual(resolved, active.resolve())
        self.assertEqual(memory_model.project_memory_dir(root), active.resolve())

    def test_unmigrated_repo_defaults_to_legacy(self) -> None:
        root = self.base / "repo"
        resolved = memory_model.resolve_and_lock_memory_dir(root)
        self.assertEqual(resolved, (root / ".docs" / "project-memory").resolve())

    def test_migrated_legacy_fails_closed(self) -> None:
        root = self.base / "repo"
        legacy = root / ".docs" / "project-memory"
        legacy.mkdir(parents=True)
        target = self.base / "active"
        target.mkdir()
        self._write_marker(
            "proj-1",
            {
                "status": "completed",
                "sources": [{"sourceRoot": str(legacy)}],
                "targetRoot": str(target),
            },
        )
        with self.assertRaises(RuntimeError):
            memory_model.resolve_and_lock_memory_dir(root)
        resolved = memory_model.resolve_and_lock_memory_dir(root, str(target))
        self.assertEqual(resolved, target.resolve())

    def test_incomplete_marker_does_not_block(self) -> None:
        root = self.base / "repo"
        self._write_marker(
            "proj-2",
            {
                "status": "in-progress",
                "sources": [{"sourceRoot": str(root / ".docs" / "project-memory")}],
            },
        )
        resolved = memory_model.resolve_and_lock_memory_dir(root)
        self.assertEqual(resolved, (root / ".docs" / "project-memory").resolve())


if __name__ == "__main__":
    unittest.main()
