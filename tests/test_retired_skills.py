import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install_codex_library.py"
SPEC = importlib.util.spec_from_file_location("retired_installer", SCRIPT)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class RetiredSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / ".codex/skills"
        self.root.mkdir(parents=True)
        self.name = "briefbound-evaluation"
        self.path = self.root / self.name
        self.path.mkdir()
        (self.path / "SKILL.md").write_text(
            f"---\nname: {self.name}\n---\nUser-modified content\n", encoding="utf-8")
        (self.path / "notes.txt").write_text("preserve me", encoding="utf-8")

    def test_dry_run_and_verify_do_not_mutate(self):
        self.assertTrue(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-router"], dry_run=True))
        self.assertFalse(INSTALLER.manage_retired_skills([self.root], ["briefbound-router"]))
        self.assertTrue(self.path.exists())
        self.assertFalse((self.root.parent / "skill-backups").exists())

    def test_archive_preserves_custom_files_and_is_idempotent(self):
        before = (self.path / "SKILL.md").read_bytes()
        self.assertTrue(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-router"], apply=True))
        self.assertFalse(self.path.exists())
        backups = list((self.root.parent / "skill-backups").glob("*/" + self.name))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "SKILL.md").read_bytes(), before)
        self.assertEqual((backups[0] / "notes.txt").read_text(encoding="utf-8"), "preserve me")
        self.assertTrue(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-router"], apply=True))
        self.assertEqual(len(list((self.root.parent / "skill-backups").glob("*"))), 1)

    def test_unselected_replacement_leaves_old_skill(self):
        self.assertTrue(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-project-review"], apply=True))
        self.assertTrue(self.path.exists())

    def test_name_mismatch_is_not_archived(self):
        (self.path / "SKILL.md").write_text("---\nname: personal-skill\n---\n", encoding="utf-8")
        self.assertFalse(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-router"], apply=True))
        self.assertTrue(self.path.exists())

    def test_symlink_target_is_untouched(self):
        target = Path(self.temp.name) / "external"
        self.path.rename(target)
        try:
            self.path.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        self.assertFalse(INSTALLER.manage_retired_skills(
            [self.root], ["briefbound-router"], apply=True))
        self.assertTrue((target / "notes.txt").exists())
        self.assertTrue(self.path.is_symlink())


if __name__ == "__main__":
    unittest.main()
