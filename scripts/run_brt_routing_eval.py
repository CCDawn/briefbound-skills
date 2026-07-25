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


def parse_events(text: str) -> tuple[list[dict], list[str], str]:
    events: list[dict] = []
    command_ids: set[str] = set()
    skill_reads: set[str] = set()
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
            command_ids.add(str(item.get("id", "")))
            command = str(item.get("command", ""))
            skill_reads.update(match.group("name").lower() for match in SKILL_READ_RE.finditer(command))
        elif item.get("type") == "agent_message" and item.get("text"):
            last_message = str(item["text"])

    return events, sorted(skill_reads), last_message


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
    if question_count == 0 and any(
        term in final_message for term in ("请确认", "请回复", "等待校准")
    ):
        question_count = len(re.findall(r"(?m)^\s*\d+[.、)]\s+", final_message))
    min_questions = case.get("min_questions")
    max_questions = case.get("max_questions")
    if min_questions is not None and question_count < min_questions:
        failures.append(f"question count {question_count} is below {min_questions}")
    if max_questions is not None and question_count > max_questions:
        failures.append(f"question count {question_count} exceeds {max_questions}")
    if case.get("require_recommendation") and "推荐" not in final_message:
        failures.append("final response lacks a recommendation")
    if case.get("require_wrong_decision_impact") and not any(
        term in final_message for term in ("错判影响", "错误决策影响", "误判影响")
    ):
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

    events_path = case_root / "events.jsonl"
    final_path = case_root / "final.txt"
    command = [
        str(codex_cli),
        "exec",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "-C",
        str(repo_root),
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-c",
        "notify=[]",
        "-o",
        str(final_path),
        case["prompt"],
    ]
    popen_kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **popen_kwargs)
    timed_out = False
    try:
        output, _ = process.communicate(timeout=case["timeout_seconds"])
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process_tree(process)
        output, _ = process.communicate()

    events_path.write_text(output, encoding="utf-8")
    events, skill_reads, fallback_message = parse_events(output)
    final_message = final_path.read_text(encoding="utf-8") if final_path.exists() else fallback_message
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
        failures.append(f"timed out after {case['timeout_seconds']}s")
    if process.returncode != 0:
        failures.append(f"Codex exited with {process.returncode}")
    missing_reads = sorted(set(case["expected_skill_reads"]) - set(skill_reads))
    if missing_reads:
        failures.append(f"missing skill reads: {missing_reads}")
    forbidden_reads = sorted(set(case["forbidden_skill_reads"]) & set(skill_reads))
    if forbidden_reads:
        failures.append(f"forbidden skill reads: {forbidden_reads}")
    if command_count > case["max_commands"]:
        failures.append(f"command count {command_count} exceeds {case['max_commands']}")
    if command_count < case.get("min_commands", 0):
        failures.append(f"command count {command_count} is below {case['min_commands']}")
    failures.extend(evaluate_final_response(case, final_message))

    result = {
        "id": case["id"],
        "passed": not failures,
        "timed_out": timed_out,
        "returncode": process.returncode,
        "command_count": command_count,
        "skill_reads": skill_reads,
        "failures": failures,
        "final_message": final_message.strip(),
        "artifact_dir": str(case_root) if artifact_root is not None else None,
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
        for failure in result["failures"]:
            print(f"  - {failure}")
        if not result["passed"]:
            preview = result["final_message"].replace("\n", " ")[:300]
            print(f"  final: {preview}")

    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
