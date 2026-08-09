import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "install_codex_library.py"
SPEC = importlib.util.spec_from_file_location("install_codex_library", SCRIPT_PATH)
INSTALLER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INSTALLER)


class BrtActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.agents_path = self.home / ".codex" / "AGENTS.md"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_install_preserves_existing_rules_and_is_idempotent(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        self.agents_path.write_text("# Existing\n\n- keep me\n", encoding="utf-8")

        self.assertTrue(INSTALLER.install_brt_activation(self.agents_path))
        first = self.agents_path.read_text(encoding="utf-8")
        self.assertIn("# Existing", first)
        self.assertIn("- keep me", first)
        self.assertEqual(first.count(INSTALLER.BRT_ACTIVATION_START), 1)
        self.assertFalse(INSTALLER.install_brt_activation(self.agents_path))
        self.assertEqual(first, self.agents_path.read_text(encoding="utf-8"))

    def test_activation_blocks_broad_work_when_intent_is_uncertain(self) -> None:
        block = INSTALLER.BRT_ACTIVATION_BLOCK
        self.assertIn("Before the first tool call", block)
        self.assertIn("Desired Result", block)
        self.assertIn("MISSING_CONTEXT", block)
        self.assertIn("PRODUCT_FORK", block)
        self.assertIn("wait for calibration", block)
        self.assertIn("stop affected writes and realign", block)
        self.assertIn("most specific owner", block)
        self.assertIn("project `preflight`", block)
        self.assertIn("primary `main/master`", block)
        self.assertIn("active claim and clean target", block)
        self.assertIn("ccdawn-performance-engineering", block)
        self.assertIn("ccdawn-code-structure-guard", block)
        self.assertIn("subagent roles", block)
        self.assertIn("reasonix_executor", block)
        self.assertIn("bounded peer discovery", block)
        self.assertIn("ccdawn-multi-agent-orchestration", block)
        self.assertIn("ccdawn-autonomous-collaboration-loop", block)
        self.assertIn("remote actions remain separately authorized", block)
        self.assertIn("MERGE_READY", block)
        self.assertIn("remote branch deletion", block)
        self.assertIn("Do not auto-load generic frameworks", block)
        self.assertIn("Chinese-first", block)

    def test_activation_defers_downstream_owner_until_calibrated(self) -> None:
        block = INSTALLER.BRT_ACTIVATION_BLOCK

        self.assertIn("ALIGNMENT_PENDING", block)
        self.assertIn("do not load a downstream implementation or planning owner", block)
        self.assertIn("CALIBRATED", block)
        self.assertIn("recompute the owner", block)

    def test_remove_deletes_only_managed_block(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        original = "# Existing\n\nKeep this rule.\n\n"
        self.agents_path.write_text(original, encoding="utf-8")
        INSTALLER.install_brt_activation(self.agents_path)

        self.assertTrue(INSTALLER.remove_brt_activation(self.agents_path))
        result = self.agents_path.read_text(encoding="utf-8")
        self.assertEqual(result, original)
        self.assertFalse(INSTALLER.remove_brt_activation(self.agents_path))

    def test_malformed_markers_fail_closed(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        self.agents_path.write_text(
            f"# Existing\n{INSTALLER.BRT_ACTIVATION_START}\n",
            encoding="utf-8",
        )

        self.assertEqual(INSTALLER.brt_activation_state(self.agents_path), "conflict")
        with self.assertRaises(SystemExit):
            INSTALLER.install_brt_activation(self.agents_path)
        with self.assertRaises(SystemExit):
            INSTALLER.remove_brt_activation(self.agents_path)

    def test_dry_run_does_not_create_agents_file(self) -> None:
        INSTALLER.manage_brt_activation(self.home, "install", dry_run=True)
        self.assertFalse(self.agents_path.exists())

    def test_install_preserves_crlf_style(self) -> None:
        self.agents_path.parent.mkdir(parents=True)
        with self.agents_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("# Existing\r\n\r\n- keep me\r\n")

        INSTALLER.install_brt_activation(self.agents_path)
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

        INSTALLER.manage_selected_brt_activations(self.home, roots, "install")

        self.assertEqual(INSTALLER.brt_activation_state(self.home / ".codex" / "AGENTS.md"), "active")
        self.assertEqual(INSTALLER.brt_activation_state(self.home / ".grok" / "AGENTS.md"), "active")

    def test_verify_installed_grok_skill_copy(self) -> None:
        skill_dir = self.home / ".grok" / "skills" / "ccdawn-brt"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ccdawn-brt\ndescription: test\n---\n\n# Test\n",
            encoding="utf-8",
        )

        verified = INSTALLER.verify_installed_skill_copies(
            [self.home / ".grok" / "skills"],
            ["ccdawn-brt"],
        )

        self.assertEqual(verified, [skill_dir])


if __name__ == "__main__":
    unittest.main()
