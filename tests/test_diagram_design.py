import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "creative" / "briefbound-diagram-design"


class DiagramDesignTests(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SKILL / "scripts" / name), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )

    def test_vendored_manifest_matches_files(self) -> None:
        payload = json.loads((SKILL / "references" / "upstream-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["repository"], "https://github.com/cathrynlavery/diagram-design")
        self.assertEqual(payload["commit"], "ce9344c52cb9be811de187bf2a6d58c712c9c9fe")
        self.assertGreaterEqual(len(payload["files"]), 200)
        for entry in payload["files"]:
            path = SKILL / entry["destination"]
            self.assertTrue(path.is_file(), entry["destination"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"], entry["destination"])

    def test_default_output_language_is_chinese(self) -> None:
        instructions = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("用户可见内容默认中文", instructions)

    def test_report_routing_has_positive_and_negative_diagram_cases(self) -> None:
        cases = {
            case["id"]: case
            for case in json.loads((ROOT / "tests" / "routing_cases.json").read_text(encoding="utf-8"))
        }
        proactive = cases["proactive-project-report-diagram"]
        self.assertEqual(proactive["primary"], "briefbound-project-review")
        self.assertEqual(proactive["support"], ["briefbound-diagram-design"])
        for case_id in ("short-status-without-diagram", "project-report-explicitly-no-image"):
            self.assertEqual(cases[case_id]["support"], [])
            self.assertIn("briefbound-diagram-design", cases[case_id]["forbidden_primary"])

    def test_local_markdown_links_resolve(self) -> None:
        missing = []
        for markdown in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
            for target in re.findall(r"\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
                path_text = target.split("#", 1)[0]
                if not path_text or "://" in path_text or path_text.startswith("mailto:"):
                    continue
                if not (markdown.parent / path_text).resolve().exists():
                    missing.append(f"{markdown.name}: {target}")
        self.assertEqual(missing, [])

    def test_shipped_example_passes_output_self_check(self) -> None:
        result = self.run_script("self_check.py", str(SKILL / "assets" / "example-architecture.html"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_mermaid_input_is_parsed_as_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="briefbound-diagram-") as tmp:
            source = Path(tmp) / "flow.mmd"
            source.write_text("flowchart LR\nA[Client] --> B[API]\n", encoding="utf-8")
            result = self.run_script("mermaid_extract.py", str(source), "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        parsed = json.loads(result.stdout)
        diagram = parsed["diagrams"][0]
        self.assertEqual({node["label"] for node in diagram["nodes"]}, {"Client", "API"})
        self.assertEqual(len(diagram["edges"]), 1)

    def test_executable_mermaid_directive_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="briefbound-diagram-") as tmp:
            source = Path(tmp) / "unsafe.mmd"
            source.write_text("flowchart LR\nA --> B\nclick A https://example.com\n", encoding="utf-8")
            result = self.run_script("mermaid_extract.py", str(source), "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        parsed = json.loads(result.stdout)
        self.assertNotIn("example.com", json.dumps(parsed))


if __name__ == "__main__":
    unittest.main()
