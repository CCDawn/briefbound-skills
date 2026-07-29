import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_brt_routing_eval.py"
SPEC = importlib.util.spec_from_file_location("run_brt_routing_eval", SCRIPT_PATH)
ROUTING_EVAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ROUTING_EVAL)


class RoutingEvalTests(unittest.TestCase):
    def test_parse_events_counts_unique_commands_and_skill_reads(self) -> None:
        stream = "\n".join(
            [
                'warning that is not JSON',
                '{"type":"item.started","item":{"id":"cmd-1","type":"command_execution","command":"Get-Content C:\\\\Users\\\\me\\\\.codex\\\\skills\\\\ccdawn-brt\\\\SKILL.md"}}',
                '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution","command":"Get-Content C:\\\\Users\\\\me\\\\.codex\\\\skills\\\\ccdawn-brt\\\\SKILL.md","exit_code":0,"status":"completed"}}',
                '{"type":"item.completed","item":{"id":"msg-1","type":"agent_message","text":"当前理解与建议"}}',
            ]
        )

        events, skill_reads, last_message = ROUTING_EVAL.parse_events(stream)

        self.assertEqual(len(events), 3)
        self.assertEqual(skill_reads, ["ccdawn-brt"])
        self.assertEqual(last_message, "当前理解与建议")

    def test_parse_events_accepts_codex_double_escaped_windows_paths(self) -> None:
        stream = (
            '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution",'
            '"command":"Get-Content C:\\\\\\\\Users\\\\\\\\me\\\\\\\\.codex\\\\\\\\skills'
            '\\\\\\\\ccdawn-project-review\\\\\\\\SKILL.md","exit_code":0,'
            '"status":"completed"}}'
        )

        _, skill_reads, _ = ROUTING_EVAL.parse_events(stream)

        self.assertEqual(skill_reads, ["ccdawn-project-review"])

    def test_parse_events_does_not_count_failed_skill_read(self) -> None:
        stream = "\n".join(
            [
                '{"type":"item.started","item":{"id":"cmd-1","type":"command_execution",'
                '"command":"Get-Content C:\\\\Users\\\\me\\\\.codex\\\\skills\\\\ccdawn-brt\\\\SKILL.md"}}',
                '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution",'
                '"command":"Get-Content C:\\\\Users\\\\me\\\\.codex\\\\skills\\\\ccdawn-brt\\\\SKILL.md",'
                '"exit_code":-1,"status":"failed"}}',
            ]
        )

        _, skill_reads, _ = ROUTING_EVAL.parse_events(stream)

        self.assertEqual(skill_reads, [])

    def test_find_codex_cli_prefers_explicit_environment_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "codex.exe"
            executable.touch()
            with mock.patch.dict(os.environ, {"CODEX_CLI_PATH": str(executable)}):
                self.assertEqual(ROUTING_EVAL.find_codex_cli(), executable)

    def test_evaluate_response_enforces_structural_alignment_contract(self) -> None:
        case = {
            "expected_final_any": ["当前理解"],
            "expected_final_all": ["行为差异", "错判影响"],
            "forbidden_final_any": ["已经修改"],
            "forbidden_delegation_phrases": ["请提供页面路径"],
            "min_questions": 1,
            "max_questions": 2,
            "require_recommendation": True,
            "require_wrong_decision_impact": True,
            "require_wait_for_calibration": True,
        }
        final_message = (
            "当前理解：为已选成员增加低风险批量操作。\n"
            "请确认：\n"
            "1. 仅支持停用。推荐：是；行为差异：不会批量删除；错判影响：可能误删。\n"
            "请回复“按推荐”或纠正。"
        )

        self.assertEqual(ROUTING_EVAL.evaluate_final_response(case, final_message), [])

    def test_evaluate_response_reports_missing_alignment_structure(self) -> None:
        case = {
            "expected_final_any": [],
            "expected_final_all": ["行为差异"],
            "forbidden_final_any": [],
            "forbidden_delegation_phrases": ["请选择一个明确目标"],
            "min_questions": 1,
            "max_questions": 2,
            "require_recommendation": True,
            "require_wrong_decision_impact": True,
            "require_wait_for_calibration": True,
        }

        failures = ROUTING_EVAL.evaluate_final_response(
            case,
            "请选择一个明确目标，我就开始处理。",
        )

        self.assertTrue(any("lacks required terms" in failure for failure in failures))
        self.assertTrue(any("question count" in failure for failure in failures))
        self.assertTrue(any("recommendation" in failure for failure in failures))
        self.assertTrue(any("wrong-decision impact" in failure for failure in failures))
        self.assertTrue(any("calibration wait" in failure for failure in failures))
        self.assertTrue(any("delegation phrases" in failure for failure in failures))

    def test_evaluate_response_accepts_equivalent_wrong_decision_heading(self) -> None:
        case = {
            "expected_final_any": [],
            "forbidden_final_any": [],
            "require_wrong_decision_impact": True,
        }

        self.assertEqual(
            ROUTING_EVAL.evaluate_final_response(case, "错误决策影响：可能造成误删。"),
            [],
        )
        self.assertEqual(
            ROUTING_EVAL.evaluate_final_response(case, "选错影响：可能造成误删。"),
            [],
        )

    def test_evaluate_response_counts_grouped_calibration_as_one_question(self) -> None:
        case = {
            "expected_final_any": [],
            "forbidden_final_any": [],
            "min_questions": 1,
            "max_questions": 4,
            "require_wait_for_calibration": True,
        }
        final_message = (
            "推荐先做结构审查。\n"
            "1. 检查目录。\n"
            "2. 检查安装脚本。\n"
            "如果同意，回复 **“按推荐”**，或改成速度优先。"
        )

        self.assertEqual(ROUTING_EVAL.evaluate_final_response(case, final_message), [])

    @mock.patch.object(ROUTING_EVAL.os, "name", "nt")
    def test_child_environment_filters_windowsapps_powershell(self) -> None:
        source = {
            "PATH": (
                r"C:\Tools;"
                r"C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.4.0_x64__8wekyb3d8bbwe;"
                r"C:\Users\me\AppData\Local\Microsoft\WindowsApps;"
                r"C:\Windows\System32\WindowsPowerShell\v1.0"
            )
        }

        child_environment = ROUTING_EVAL.child_environment(source)

        self.assertNotIn("Microsoft.PowerShell_", child_environment["PATH"])
        self.assertNotIn(r"\Microsoft\WindowsApps", child_environment["PATH"])
        self.assertIn(r"C:\Windows\System32\WindowsPowerShell\v1.0", child_environment["PATH"])
        self.assertEqual(child_environment["PYTHONIOENCODING"], "utf-8")


if __name__ == "__main__":
    unittest.main()
