import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_briefbound_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_briefbound_skills", SCRIPT_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


class RouteReferenceTests(unittest.TestCase):
    def test_repository_name_is_not_a_skill_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skills" / "briefbound-readme-optimization"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "\n".join(
                    [
                        "参照 briefbound-skills 仓库，并交给 `briefbound-readme-optimization`。",
                        "不要路由到 briefbound-missing-skill 或 briefbound-skills-extra。",
                    ]
                ),
                encoding="utf-8",
            )

            errors: list[str] = []
            VALIDATOR.validate_briefbound_route_references(
                Path(temp_dir),
                {"briefbound-readme-optimization"},
                errors,
            )

        joined = "\n".join(errors)
        self.assertNotIn("unresolved Briefbound route 'briefbound-skills'", joined)
        self.assertNotIn("unresolved Briefbound route 'briefbound-readme-optimization'", joined)
        self.assertIn("unresolved Briefbound route 'briefbound-missing-skill'", joined)
        self.assertIn("unresolved Briefbound route 'briefbound-skills-extra'", joined)
