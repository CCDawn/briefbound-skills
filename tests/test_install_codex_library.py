import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "install_codex_library.py"
SPEC = importlib.util.spec_from_file_location("install_codex_library", SCRIPT_PATH)
INSTALLER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INSTALLER)


class RouterActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.agents_path = self.home / ".codex" / "AGENTS.md"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_install_preserves_existing_rules_and_is_idempotent(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        self.agents_path.write_text("# Existing\n\n- keep me\n", encoding="utf-8")

        self.assertTrue(INSTALLER.install_router_activation(self.agents_path))
        first = self.agents_path.read_text(encoding="utf-8")
        self.assertIn("# Existing", first)
        self.assertIn("- keep me", first)
        self.assertEqual(first.count(INSTALLER.ROUTER_ACTIVATION_START), 1)
        self.assertFalse(INSTALLER.install_router_activation(self.agents_path))
        self.assertEqual(first, self.agents_path.read_text(encoding="utf-8"))

    def test_install_migrates_legacy_activation_block_in_place(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        self.agents_path.write_text(
            "# Existing\n\n"
            f"{INSTALLER.LEGACY_ROUTER_ACTIVATION_START}\nold rules\n"
            f"{INSTALLER.LEGACY_ROUTER_ACTIVATION_END}\n",
            encoding="utf-8",
        )

        self.assertEqual(INSTALLER.router_activation_state(self.agents_path), "legacy")
        self.assertTrue(INSTALLER.install_router_activation(self.agents_path))
        migrated = self.agents_path.read_text(encoding="utf-8")
        self.assertIn("# Existing", migrated)
        self.assertIn(INSTALLER.ROUTER_ACTIVATION_START, migrated)
        self.assertNotIn(INSTALLER.LEGACY_ROUTER_ACTIVATION_START, migrated)
        self.assertEqual(INSTALLER.router_activation_state(self.agents_path), "active")

    def test_activation_block_pins_unified_entry_rules(self) -> None:
        block = INSTALLER.ROUTER_ACTIVATION_BLOCK
        self.assertIn("permission to act", block)
        self.assertIn("state the assumption and continue", block)
        self.assertIn("high-impact fork", block)
        self.assertIn("Zero questions", block)
        self.assertIn("creates no subagents", block)
        self.assertIn("dispatch independent, parallelizable work directly without asking", block)
        self.assertIn("never invent tool names", block)
        self.assertIn("load `briefbound-router` and follow its gates", block)
        self.assertIn("Chinese-first", block)
        self.assertIn("briefbound-plain-talk", block)
        self.assertIn("lead with the answer", block)
        self.assertIn("no code dumps in replies", block)
        self.assertIn("`file:line`", block)
        self.assertIn("unexplained enums", block)
        calibration_lines = [
            line for line in block.splitlines() if "wait for calibration" in line
        ]
        self.assertEqual(len(calibration_lines), 1)
        self.assertIn("high-impact fork", calibration_lines[0])
        self.assertLessEqual(len(block.strip().splitlines()), 14)

    def test_activation_block_excludes_retired_routing_tools_and_prompts(self) -> None:
        block = INSTALLER.ROUTER_ACTIVATION_BLOCK
        for banned in ("reasonix_executor", "delegate_task", "opencode", "proactively ask", "2-4"):
            self.assertNotIn(banned, block)

    def test_activation_defers_cross_skill_gates_to_router(self) -> None:
        block = INSTALLER.ROUTER_ACTIVATION_BLOCK

        self.assertIn("For cross-skill routing", block)
        self.assertIn("briefbound-router", block)
        self.assertIn("follow its gates", block)
        self.assertIn("If the runtime provides delegation tools", block)
        self.assertIn("never block work on a delegation decision", block)

    def test_remove_deletes_only_managed_block(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        original = "# Existing\n\nKeep this rule.\n\n"
        self.agents_path.write_text(original, encoding="utf-8")
        INSTALLER.install_router_activation(self.agents_path)

        self.assertTrue(INSTALLER.remove_router_activation(self.agents_path))
        result = self.agents_path.read_text(encoding="utf-8")
        self.assertEqual(result, original)
        self.assertFalse(INSTALLER.remove_router_activation(self.agents_path))

    def test_malformed_markers_fail_closed(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        self.agents_path.write_text(
            f"# Existing\n{INSTALLER.ROUTER_ACTIVATION_START}\n",
            encoding="utf-8",
        )

        self.assertEqual(INSTALLER.router_activation_state(self.agents_path), "conflict")
        with self.assertRaises(SystemExit):
            INSTALLER.install_router_activation(self.agents_path)
        with self.assertRaises(SystemExit):
            INSTALLER.remove_router_activation(self.agents_path)

    def test_dry_run_does_not_create_agents_file(self) -> None:
        INSTALLER.manage_router_activation(self.home, "install", dry_run=True)
        self.assertFalse(self.agents_path.exists())

    def test_install_preserves_crlf_style(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        with self.agents_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("# Existing\r\n\r\n- keep me\r\n")

        INSTALLER.install_router_activation(self.agents_path)
        with self.agents_path.open("r", encoding="utf-8", newline="") as handle:
            result = handle.read()
        self.assertIn("# Existing\r\n", result)
        self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_grok_target_uses_native_skill_root(self) -> None:
        roots = INSTALLER.destination_roots(self.home, "grok")

        self.assertEqual(roots, [self.home / ".grok" / "skills"])
        self.assertTrue(INSTALLER.targets_grok(self.home, roots))
        self.assertFalse(INSTALLER.targets_codex(self.home, roots))

    def test_codex_grok_target_avoids_extra_catalogs(self) -> None:
        roots = INSTALLER.destination_roots(self.home, "codex-grok")

        self.assertEqual(
            roots,
            [self.home / ".codex" / "skills", self.home / ".grok" / "skills"],
        )

    def test_selected_activation_manages_codex_and_grok_rules(self) -> None:
        roots = INSTALLER.destination_roots(self.home, "all")

        INSTALLER.manage_selected_router_activations(self.home, roots, "install")

        self.assertEqual(INSTALLER.router_activation_state(self.home / ".codex" / "AGENTS.md"), "active")
        self.assertEqual(INSTALLER.router_activation_state(self.home / ".grok" / "AGENTS.md"), "active")

    def test_verify_installed_grok_skill_copy(self) -> None:
        skill_dir = self.home / ".grok" / "skills" / "briefbound-router"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: briefbound-router\ndescription: test\n---\n\n# Test\n",
            encoding="utf-8",
        )

        verified = INSTALLER.verify_installed_skill_copies(
            [self.home / ".grok" / "skills"],
            ["briefbound-router"],
        )

        self.assertEqual(verified, [skill_dir])

    def test_live_validator_forces_utf8_on_windows(self) -> None:
        validator = INSTALLER.codex_validator_path(self.home)
        validator.parent.mkdir(parents=True)
        validator.write_text("# validator", encoding="utf-8")
        installed_skill = self.home / ".codex" / "skills" / "briefbound-router"

        with mock.patch.object(INSTALLER.subprocess, "run") as run:
            validated = INSTALLER.validate_installed_codex_skills(self.home, [installed_skill])

        self.assertEqual(validated, [installed_skill])
        run.assert_called_once()
        validation_env = run.call_args.kwargs["env"]
        self.assertEqual(validation_env["PYTHONUTF8"], "1")
        self.assertEqual(validation_env["PYTHONIOENCODING"], "utf-8")

    def test_legacy_skill_cleanup_requires_matching_frontmatter(self) -> None:
        root = self.home / ".codex" / "skills"
        verified_legacy = root / "ccdawn-brt"
        verified_legacy.mkdir(parents=True)
        (verified_legacy / "SKILL.md").write_text(
            "---\nname: ccdawn-brt\ndescription: legacy\n---\n",
            encoding="utf-8",
        )
        unverified_legacy = root / "ccdawn-project-review"
        unverified_legacy.mkdir(parents=True)
        (unverified_legacy / "SKILL.md").write_text(
            "---\nname: custom-project-review\ndescription: custom\n---\n",
            encoding="utf-8",
        )

        INSTALLER.manage_legacy_skill_copies(
            [root],
            ["briefbound-router", "briefbound-project-review"],
            remove=True,
        )

        self.assertFalse(verified_legacy.exists())
        self.assertTrue(unverified_legacy.exists())

    def test_legacy_alias_link_is_removed_without_touching_new_skill(self) -> None:
        root = self.home / ".codex" / "skills"
        new_skill = root / "briefbound-router"
        new_skill.mkdir(parents=True)
        (new_skill / "SKILL.md").write_text(
            "---\nname: briefbound-router\ndescription: current\n---\n",
            encoding="utf-8",
        )
        legacy_alias = root / "ccdawn-brt"
        try:
            legacy_alias.symlink_to(new_skill, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")

        INSTALLER.manage_legacy_skill_copies(
            [root],
            ["briefbound-router"],
            remove=True,
        )

        self.assertFalse(legacy_alias.exists())
        self.assertTrue((new_skill / "SKILL.md").exists())

    def test_disable_migrates_legacy_superpowers_marker(self) -> None:
        skill_dir = self.home / ".codex" / "skills" / "using-superpowers"
        skill_dir.mkdir(parents=True)
        legacy_disabled = skill_dir / INSTALLER.LEGACY_DISABLED_SKILL_FILENAME
        legacy_disabled.write_text("legacy", encoding="utf-8")

        states = dict(INSTALLER.process_skill_conflict_state(self.home))
        self.assertEqual(states["using-superpowers"], "legacy-disabled")

        INSTALLER.manage_process_skill_conflicts(self.home, "disable")

        self.assertFalse(legacy_disabled.exists())
        self.assertTrue((skill_dir / INSTALLER.DISABLED_SKILL_FILENAME).exists())


if __name__ == "__main__":
    unittest.main()
