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
        self.assertIn("before the first tool call", block)
        self.assertIn("MUST NOT start a broad repository scan", block)
        self.assertIn("grouped high-impact questions", block)
        self.assertIn("Desired Result", block)
        self.assertIn("Continuation Health Check", block)
        self.assertIn("MISSING_CONTEXT", block)
        self.assertIn("PRODUCT_FORK", block)
        self.assertIn("existing same-project peer threads", block)
        self.assertIn("ccdawn-multi-agent-orchestration", block)
        self.assertIn("ccdawn-autonomous-collaboration-loop", block)
        self.assertIn("ask once whether to enable", block)
        self.assertIn("without stage-by-stage prompts", block)
        self.assertIn("remote push/PR/publish still require separate permission", block)
        self.assertIn("FAST / CHECK / PROFILE", block)
        self.assertIn("already-located N+1 or local inefficiency", block)
        self.assertIn("deterministic query/count assertion", block)
        self.assertIn("failing WindowsApps alias", block)
        self.assertIn("do not cycle equivalent aliases", block)
        self.assertIn("Planning artifacts are development writes", block)
        self.assertIn("observed failure, correctness regression, or unresolved root cause", block)
        self.assertIn("ccdawn-performance-engineering", block)
        self.assertIn("Do not benchmark routine changes", block)
        self.assertIn("Discovery sends no messages", block)
        self.assertIn("never creates subagents", block)
        self.assertIn("keeps ownership of its own task", block)
        self.assertIn("integration/<target-key>", block)
        self.assertIn("proactively claim the queue", block)
        self.assertIn("baseline failures or a dirty main", block)
        self.assertIn("load `ccdawn-thread-coordination`", block)
        self.assertIn("SELF_OWNED / PEER_OWNED / UNOWNED / UNKNOWN", block)
        self.assertIn("must not load `ccdawn-autonomous-collaboration-loop`", block)
        self.assertIn("must not continue accumulating implementation batches", block)
        self.assertIn("do not independently chase main", block)
        self.assertIn("read the live local `SKILL.md`", block)
        self.assertIn("Do not auto-load generic process frameworks", block)

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
