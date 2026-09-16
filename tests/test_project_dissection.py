import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/engineering/briefbound-project-dissection"
SCRIPT = SKILL / "scripts/scan_repo.py"
spec = importlib.util.spec_from_file_location("dissection_scan", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class DissectionScanTests(unittest.TestCase):
    def test_line_counts_empty_and_terminal_newline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.py"
            for content, expected in [("", 0), ("x", 1), ("x\n", 1), ("x\ny", 2)]:
                path.write_text(content, encoding="utf-8")
                self.assertEqual(scan.count_lines(path), expected)

    def test_scan_outputs_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "repo"
            root.mkdir()
            files = {
                "main.py": "print('中文')\n",
                ".env": "TOKEN=do-not-disclose\n",
                "node_modules/noise.js": "noise\n" * 20,
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            out = Path(folder) / "facts"
            subprocess.run([sys.executable, str(SCRIPT), str(root), "--out", str(out)],
                           check=True, capture_output=True)
            facts = json.loads((out / "facts.json").read_text(encoding="utf-8"))
            self.assertEqual(facts["size"]["total_code_lines"], 1)
            self.assertIn(".env", facts["sensitive_files"])
            self.assertNotIn("do-not-disclose", (out / "facts.json").read_text(encoding="utf-8"))
            self.assertFalse((root / ".project-dissection").exists())
            for name, content in files.items():
                self.assertEqual((root / name).read_text(encoding="utf-8"), content)

    def test_stdout_does_not_write_and_limit_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for i in range(3):
                (root / f"file{i}.py").write_text("pass\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(root), "--stdout", "--max-files", "1"],
                check=True, capture_output=True, encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertTrue(result.stdout)
            self.assertFalse((root / ".project-dissection").exists())
            out = root / "facts"
            subprocess.run([sys.executable, str(SCRIPT), str(root), "--out", str(out),
                            "--max-files", "1"], check=True, capture_output=True)
            facts = json.loads((out / "facts.json").read_text(encoding="utf-8"))
            self.assertTrue(facts["scan"]["truncated"])
            self.assertEqual(facts["scan"]["files_scanned"], 1)


if __name__ == "__main__":
    unittest.main()
