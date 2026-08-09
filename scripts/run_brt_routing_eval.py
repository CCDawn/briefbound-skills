import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


SKILL_READ_RE = re.compile(
    r"(?:^|[\\/]+)(?P<name>ccdawn-[a-z0-9-]+)[\\/]+SKILL\.md",
    re.IGNORECASE,
)
WRONG_DECISION_SUBJECTS = ("错判", "误判", "选错", "错误决策")
WRONG_DECISION_EFFECTS = (
    "影响",
    "导致",
    "造成",
    "引发",
    "风险",
    "损失",
    "误删",
    "不可恢复",
    "返工",
    "越权",
    "泄露",
    "失败",
    "不一致",
)
CONDITIONAL_CONSEQUENCE_RE = re.compile(
    r"(?:否则|如果|若|直接(?:执行|实现|删除|修改|继续))"
    r"[^。！？\n]{0,80}(?:误|导致|造成|风险|损失|浪费|不可|无法|越权|泄露|失败|不一致|返工)"
)


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def find_codex_cli() -> Path:
    env_path = os.environ.get("CODEX_CLI_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    config_path = codex_home() / "config.toml"
    if config_path.is_file():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            config_path_value = (
                config.get("mcp_servers", {})
                .get("node_repl", {})
                .get("env", {})
                .get("CODEX_CLI_PATH")
            )
            if config_path_value and Path(config_path_value).is_file():
                return Path(config_path_value)
        except (OSError, tomllib.TOMLDecodeError):
            pass

    command = shutil.which("codex.exe") or shutil.which("codex")
    if command and Path(command).is_file():
        return Path(command)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates = list((Path(local_app_data) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        candidates = [path for path in candidates if path.is_file()]
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)

    raise SystemExit("Codex CLI not found. Set CODEX_CLI_PATH to the current codex executable.")


def child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if source is None else source)
    environment["PYTHONIOENCODING"] = "utf-8"
    if os.name != "nt":
        return environment

    path_separator = ";" if os.name == "nt" else os.pathsep
    path_entries = environment.get("PATH", "").split(path_separator)
    environment["PATH"] = path_separator.join(
        entry
        for entry in path_entries
        if "\\windowsapps\\microsoft.powershell_" not in entry.lower()
        and "\\microsoft\\windowsapps" not in entry.lower()
    )
    return environment


def parse_events(text: str) -> tuple[list[dict], list[str], str]:
    events: list[dict] = []
    commands: dict[str, str] = {}
    successful_command_ids: set[str] = set()
    last_message = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") == "command_execution":
            command_id = str(item.get("id", ""))
            commands[command_id] = str(item.get("command", ""))
            if event.get("type") == "item.completed" and item.get("exit_code") == 0:
                successful_command_ids.add(command_id)
        elif item.get("type") == "agent_message" and item.get("text"):
            last_message = str(item["text"])

    skill_reads = {
        match.group("name").lower()
        for command_id in successful_command_ids
        for match in SKILL_READ_RE.finditer(commands.get(command_id, ""))
    }
    return events, sorted(skill_reads), last_message


def extract_thread_id(events: list[dict]) -> str | None:
    for event in events:
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
    return None


def case_turns(case: dict) -> list[dict]:
    initial = {
        key: value
        for key, value in case.items()
        if key not in {"id", "smoke", "followups", "workspace_files"}
    }
    turns = [initial]
    for followup in case.get("followups", []):
        turn = dict(followup)
        turn.setdefault("timeout_seconds", case["timeout_seconds"])
        turns.append(turn)
    return turns


def prepare_case_workspace(repo_root: Path, case_root: Path, case: dict) -> Path:
    workspace_files = case.get("workspace_files")
    if not workspace_files:
        return repo_root

    workspace = case_root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    for relative_name, content in workspace_files.items():
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or not relative_path.parts or ".." in relative_path.parts:
            raise ValueError(f"unsafe workspace fixture path: {relative_name}")
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return workspace


def build_turn_command(
    codex_cli: Path,
    repo_root: Path,
    prompt: str,
    output_path: Path,
    reasoning_effort: str,
    *,
    session_id: str | None = None,
    persist_session: bool = False,
    skip_git_repo_check: bool = False,
) -> list[str]:
    common = [
        "--json",
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-c",
        "notify=[]",
        "-o",
        str(output_path),
    ]
    if session_id is not None:
        command = [
            str(codex_cli),
            "exec",
            "resume",
            *common,
        ]
        if skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.extend([session_id, prompt])
        return command

    command = [
        str(codex_cli),
        "exec",
        *common,
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "-C",
        str(repo_root),
    ]
    if not persist_session:
        command.append("--ephemeral")
    if skip_git_repo_check:
        command.append("--skip-git-repo-check")
    command.append(prompt)
    return command


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def evaluate_final_response(case: dict, final_message: str) -> list[str]:
    failures: list[str] = []
    expected_any = case.get("expected_final_any", [])
    if expected_any and not any(term in final_message for term in expected_any):
        failures.append(f"final response lacks one of {expected_any}")
    missing_all = [term for term in case.get("expected_final_all", []) if term not in final_message]
    if missing_all:
        failures.append(f"final response lacks required terms: {missing_all}")
    forbidden_final = [term for term in case.get("forbidden_final_any", []) if term in final_message]
    if forbidden_final:
        failures.append(f"final response contains forbidden terms: {forbidden_final}")
    delegation = [
        term for term in case.get("forbidden_delegation_phrases", []) if term in final_message
    ]
    if delegation:
        failures.append(f"final response contains delegation phrases: {delegation}")

    question_count = final_message.count("?") + final_message.count("？")
    if question_count == 0 and (
        any(term in final_message for term in ("请确认", "请回复", "等待校准"))
        or re.search(r"回复.{0,20}按推荐", final_message)
    ):
        question_count = 1
    min_questions = case.get("min_questions")
    max_questions = case.get("max_questions")
    if min_questions is not None and question_count < min_questions:
        failures.append(f"question count {question_count} is below {min_questions}")
    if max_questions is not None and question_count > max_questions:
        failures.append(f"question count {question_count} exceeds {max_questions}")
    if case.get("require_recommendation") and "推荐" not in final_message:
        failures.append("final response lacks a recommendation")
    has_labeled_wrong_decision_impact = any(
        subject in final_message for subject in WRONG_DECISION_SUBJECTS
    ) and any(effect in final_message for effect in WRONG_DECISION_EFFECTS)
    has_conditional_consequence = bool(CONDITIONAL_CONSEQUENCE_RE.search(final_message))
    has_wrong_decision_impact = (
        has_labeled_wrong_decision_impact or has_conditional_consequence
    )
    if case.get("require_wrong_decision_impact") and not has_wrong_decision_impact:
        failures.append("final response lacks a wrong-decision impact")
    if case.get("require_wait_for_calibration") and not any(
        term in final_message for term in ("按推荐", "请回复", "等待", "确认后")
    ):
        failures.append("final response lacks a calibration wait")
    return failures


def run_case(
    codex_cli: Path,
    repo_root: Path,
    case: dict,
    reasoning_effort: str,
    artifact_root: Path | None,
) -> dict:
    if artifact_root is None:
        temp_context = tempfile.TemporaryDirectory(prefix=f"ccdawn-brt-{case['id']}-")
        case_root = Path(temp_context.name)
    else:
        temp_context = None
        case_root = artifact_root / case["id"]
        case_root.mkdir(parents=True, exist_ok=True)

    execution_root = prepare_case_workspace(repo_root, case_root, case)
    skip_git_repo_check = execution_root != repo_root
    turns = case_turns(case)
    persist_session = len(turns) > 1
    session_id: str | None = None
    turn_results: list[dict] = []

    for index, turn in enumerate(turns, start=1):
        if index > 1 and session_id is None:
            turn_results.append(
                {
                    "index": index,
                    "passed": False,
                    "timed_out": False,
                    "returncode": None,
                    "command_count": 0,
                    "skill_reads": [],
                    "failures": ["initial turn did not emit a resumable thread id"],
                    "final_message": "",
                }
            )
            break

        if len(turns) == 1:
            events_path = case_root / "events.jsonl"
            final_path = case_root / "final.txt"
        else:
            events_path = case_root / f"turn-{index}-events.jsonl"
            final_path = case_root / f"turn-{index}-final.txt"

        command = build_turn_command(
            codex_cli,
            execution_root,
            turn["prompt"],
            final_path,
            reasoning_effort,
            session_id=session_id if index > 1 else None,
            persist_session=persist_session,
            skip_git_repo_check=skip_git_repo_check,
        )
        popen_kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "stdin": subprocess.DEVNULL,
            "env": child_environment(),
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        timed_out = False
        try:
            output, _ = process.communicate(timeout=turn["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_process_tree(process)
            output, _ = process.communicate()

        events_path.write_text(output, encoding="utf-8")
        events, skill_reads, fallback_message = parse_events(output)
        if index == 1 and persist_session:
            session_id = extract_thread_id(events)
        final_message = (
            final_path.read_text(encoding="utf-8")
            if final_path.exists()
            else fallback_message
        )
        command_count = len(
            {
                str(event.get("item", {}).get("id", ""))
                for event in events
                if isinstance(event.get("item"), dict)
                and event["item"].get("type") == "command_execution"
            }
        )

        failures: list[str] = []
        if timed_out:
            failures.append(f"timed out after {turn['timeout_seconds']}s")
        if process.returncode != 0:
            failures.append(f"Codex exited with {process.returncode}")
        missing_reads = sorted(set(turn["expected_skill_reads"]) - set(skill_reads))
        if missing_reads:
            failures.append(f"missing skill reads: {missing_reads}")
        forbidden_reads = sorted(set(turn["forbidden_skill_reads"]) & set(skill_reads))
        if forbidden_reads:
            failures.append(f"forbidden skill reads: {forbidden_reads}")
        if command_count > turn["max_commands"]:
            failures.append(f"command count {command_count} exceeds {turn['max_commands']}")
        if command_count < turn.get("min_commands", 0):
            failures.append(f"command count {command_count} is below {turn['min_commands']}")
        failures.extend(evaluate_final_response(turn, final_message))

        turn_results.append(
            {
                "index": index,
                "passed": not failures,
                "timed_out": timed_out,
                "returncode": process.returncode,
                "command_count": command_count,
                "skill_reads": skill_reads,
                "failures": failures,
                "final_message": final_message.strip(),
            }
        )

    failures = [
        f"turn {turn['index']}: {failure}"
        for turn in turn_results
        for failure in turn["failures"]
    ]
    result = {
        "id": case["id"],
        "passed": not failures and len(turn_results) == len(turns),
        "timed_out": any(turn["timed_out"] for turn in turn_results),
        "returncode": next(
            (turn["returncode"] for turn in turn_results if turn["returncode"] not in (0, None)),
            0,
        ),
        "command_count": sum(turn["command_count"] for turn in turn_results),
        "skill_reads": sorted(
            {skill for turn in turn_results for skill in turn["skill_reads"]}
        ),
        "failures": failures,
        "final_message": turn_results[-1]["final_message"] if turn_results else "",
        "artifact_dir": str(case_root) if artifact_root is not None else None,
        "session_id": session_id,
        "turns": turn_results,
    }
    if temp_context is not None:
        temp_context.cleanup()
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live, read-only CCDawn BRT routing checks.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--cases", default=str(Path(__file__).resolve().parents[1] / "tests" / "live_routing_cases.json"))
    parser.add_argument("--case", action="append", dest="case_ids", help="Run a case by id; repeatable.")
    parser.add_argument("--all", action="store_true", help="Run every case instead of smoke cases only.")
    parser.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--artifacts", help="Optional directory for retained event and final-response files.")
    parser.add_argument("--allow-inactive", action="store_true", help="Allow a baseline run without the managed BRT activation block.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    selected = [
        case
        for case in cases
        if (args.case_ids and case["id"] in args.case_ids)
        or (not args.case_ids and (args.all or case["smoke"]))
    ]
    if not selected:
        raise SystemExit("No live routing cases selected.")

    activation_path = codex_home() / "AGENTS.md"
    activation_text = activation_path.read_text(encoding="utf-8") if activation_path.exists() else ""
    if "<!-- CCDawn BRT activation: start -->" not in activation_text and not args.allow_inactive:
        raise SystemExit(
            "CCDawn BRT global activation is absent. Run install.ps1 first or pass --allow-inactive for a baseline."
        )

    codex_cli = find_codex_cli()
    artifact_root = Path(args.artifacts).resolve() if args.artifacts else None
    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)

    print(f"Codex CLI: {codex_cli}")
    print(f"Cases: {', '.join(case['id'] for case in selected)}")
    results = [run_case(codex_cli, repo_root, case, args.reasoning_effort, artifact_root) for case in selected]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{status} {result['id']}: commands={result['command_count']}, "
            f"skills={result['skill_reads']}"
        )
        if len(result["turns"]) > 1:
            for turn in result["turns"]:
                turn_status = "PASS" if turn["passed"] else "FAIL"
                print(
                    f"  turn {turn['index']} {turn_status}: commands={turn['command_count']}, "
                    f"skills={turn['skill_reads']}"
                )
            if result["session_id"]:
                print(f"  session: {result['session_id']}")
        for failure in result["failures"]:
            print(f"  - {failure}")
        if not result["passed"]:
            preview = result["final_message"].replace("\n", " ")[:300]
            print(f"  final: {preview}")

    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
