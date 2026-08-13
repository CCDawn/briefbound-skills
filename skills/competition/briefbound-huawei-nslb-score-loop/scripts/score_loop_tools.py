#!/usr/bin/env python3
"""Utility checks for the Huawei NSLB score loop.

The tool is intentionally read-only. It helps the coordinator validate the
active baseline, detect duplicate experiment ideas, and rank child-agent
results before any ledger or source mutation.
"""

from __future__ import annotations

import argparse
import difflib
import io
import os
import hashlib
import json
import math
import re
import shutil
import sys
import time
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FAMILY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("large_sparse", ("large sparse", "large-sparse", "large_sparse")),
    ("leaf_band", ("leaf-band", "leafband", "load5", "load-5", "9257")),
    ("official_permutation", ("officialpermutation", "permutation", "official seed")),
    ("online_fit_core", ("online_fit_core", "online fit core")),
    ("hidden_shape", ("hidden_shape", "hidden shape")),
    ("random_low_port", ("random-low-port", "random low-port", "random_medium")),
    ("history_smoothing", ("history smoothing", "history-spread", "recolor")),
    ("capacity_shadow", ("capacity shadow", "shadow selector")),
    ("hot_destination", ("hot-destination", "hot destination", "hot_dst")),
    ("projected_peak", ("projected peak", "projectedglobalpeak")),
    ("paired_swap", ("paired-swap", "paired swap", "same-phase swap")),
    ("runtime", ("runtime", "timeout", "5s")),
)

MECHANISM_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("residual_target", ("residual-target", "residual target", "residual_target")),
    ("guard", ("guard", "predicate", "gate", "selector")),
    ("ordering", ("order", "ordering", "tie-break", "tie break", "priority")),
    ("repair", ("repair", "rollback", "cleanup", "fix")),
    ("swap", ("swap", "paired", "exchange")),
    ("widen", ("widen", "broaden", "expand", "generalize")),
    ("smoothing", ("smoothing", "history", "recolor")),
    ("runtime_slim", ("runtime-slim", "slim", "source size", "overhead")),
    ("benchmark", ("benchmark", "suite", "forensics", "diagnostic")),
    ("cycle", ("cycle", "augmenting", "matching", "two-hop")),
)

SHAPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("job32_phase6", ("job32-phase6", "job32 phase6", "job32_phase6")),
    ("job28_phase7", ("job28-phase7", "job28 phase7", "job28_phase7")),
    ("job28_phase6", ("job28-phase6", "job28 phase6", "job28_phase6")),
    ("phase6_residual", ("phase6", "phase 6", "phase>=6", "phase count 6")),
    ("phase4_6_residual", ("phase4", "phase 4", "phase5", "phase 5", "phase 4-6")),
    ("flow4096", ("flow4096", "flow 4096", "4096 flow")),
    ("flow3072", ("flow3072", "flow 3072", "3072 flow")),
    ("jobcount24_guard", ("gjobcount<=24", "jobcount<=24", "job count <=24", "gjobcount 24")),
    ("jobcount28_risk", ("gjobcount=28", "jobcount=28", "job count 28")),
    ("leafcount100", ("leafcount=100", "leaf count 100", "leafcount 100")),
    ("load5_leaf_band", ("load5", "load-5", "leaf band", "leaf-band")),
    ("official_permutation_shape", ("official permutation", "permutation shape", "official seed")),
    ("capacity_pressure", ("capacity pressure", "capacity shadow", "over capacity")),
    ("runtime_sparse_history", ("runtime_sparse_history", "sparse history", "5s")),
)

HIGH_VALUE_DELTAS = (
    "onlineFitCoreWeighted",
    "online_fit_core",
    "online_fit_coreWeighted",
    "onlineFitV2Weighted",
    "online_fit_v2",
    "hiddenShapeWeighted",
    "hidden_shape",
    "hiddenLeafBandForensicsWeighted",
    "hidden_leaf_band_forensics",
    "officialSeedSweepWeighted",
    "official_seed_sweep",
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_MUTATION_SPACE = SKILL_ROOT / "references" / "mutation_space.json"
SKILL_MD = SKILL_ROOT / "SKILL.md"
PROFILE_MD = SKILL_ROOT / "references" / "huawei-nslb-profile.md"
MAX_SUBMISSION_BASENAME_LENGTH = 48
DEFAULT_EPOCH_LANE_LIMIT = 6
DEFAULT_MAX_ACTIVE_WORKERS = 6
LOCAL_OPTIMUM_LANE_TOKENS = (
    "residual_envelope",
    "samecase",
    "same_case",
    "counterfactual",
    "alternating_cycle",
    "phase_residue",
    "044_style",
    "exact_neighbor",
    "online_confirmed_exploit",
    "regret_shadow_price",
)
GLOBAL_BREAKOUT_LANE_TOKENS = (
    "outside_residual_envelope",
    "moonshot",
    "two_stage",
    "pdflegal",
    "metamorphic",
    "adversarial_proxy",
    "small_enumerator",
    "combination",
    "synergy",
    "objective_reframe",
    "online_submission_revalidation",
    "dataset_candidate_decision",
    "mechanism_breakout",
    "shadow_assignment_frontier",
)
EXCLUDED_COPY_NAMES = {
    ".git",
    "build",
    "dist",
    "tmp",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

CHILD_REQUIRED_FIELDS: tuple[str, ...] = (
    "worker",
    "basedOn",
    "baselineSha256",
    "hypothesis",
    "changedFiles",
    "checksRun",
    "scores",
    "deltasVsBaseline",
    "notableRegressions",
    "runtimeRisk",
    "promotionCandidate",
    "result",
    "summary",
    "avoidNextTime",
)

DATASET_CANDIDATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "candidateId",
    "sourceOnlineFeedback",
    "caseFamily",
    "caseShape",
    "hypothesis",
    "explainsPositive",
    "rejectsNeutralOrNegative",
    "promotionGateImpact",
)


def extract_first_json_value(text: str) -> Any:
    decoder = json.JSONDecoder()
    fence_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    for match in fence_pattern.finditer(text):
        candidate = match.group(1).strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    for match in re.finditer(r"[\{\[]", text):
        try:
            value, _end = decoder.raw_decode(text[match.start() :])
            return value
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("no JSON object found in text", text, 0)


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if path.name == "child_result.json":
            return extract_first_json_value(text)
        raise


def write_json(data: Any) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def capture_json_output(func, args: argparse.Namespace) -> Any:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(args)
    text = buffer.getvalue().strip()
    return json.loads(text) if text else {}


def atomic_write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
    return parsed


def iso_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None


def tail_text(path: Path, *, max_bytes: int = 12000, max_lines: int = 20) -> str:
    try:
        with path.open("rb") as handle:
            size = path.stat().st_size
            handle.seek(max(0, size - max_bytes))
            data = handle.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def latest_compile_error_tail(workspace: Path) -> dict[str, str]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for base in (workspace, workspace / "build"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".log", ".err", ".txt"}:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(path)
    for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
        tail = tail_text(path)
        lower = tail.lower()
        if any(token in lower for token in ("error:", "fatal error", "undefined reference", "compilation", "compile failed", "g++")):
            return {"path": str(path), "tail": tail}
    return {"path": "", "tail": ""}


def child_result_mentions_compile_failure(result: dict[str, Any]) -> bool:
    text = json.dumps(
        {
            "checksRun": result.get("checksRun"),
            "result": result.get("result"),
            "summary": result.get("summary"),
            "currentEvidence": result.get("currentEvidence"),
            "evidenceNotes": result.get("evidenceNotes"),
            "notableRegressions": result.get("notableRegressions"),
        },
        ensure_ascii=False,
    ).lower()
    failure_phrases = (
        "compile failed",
        "compilation failed",
        "compiler failed",
        "failed to compile",
        "compile error",
        "compilation error",
        "compiler error",
        "g++ error",
        "g++ failed",
    )
    return any(phrase in text for phrase in failure_phrases)


def augment_compile_failure_result(result: dict[str, Any], workspace: Path) -> bool:
    if not child_result_mentions_compile_failure(result) or result.get("compileErrorTail"):
        return False
    compile_tail = latest_compile_error_tail(workspace)
    tail = compile_tail.get("tail", "").strip()
    if not tail:
        return False
    result["compileErrorTail"] = tail
    result.setdefault("artifactPaths", [])
    if isinstance(result["artifactPaths"], list) and compile_tail.get("path"):
        result["artifactPaths"].append(compile_tail["path"])
    if isinstance(result.get("currentEvidence"), dict):
        result["currentEvidence"].setdefault("compileErrorTail", tail)
    return True
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001
        return None


def latest_workspace_activity(workspace: Path) -> dict[str, Any]:
    candidates = [
        workspace / "child_result.json",
        workspace / "worker_started.json",
        workspace / "worker_heartbeat.json",
        workspace / "src" / "Solution.cpp",
        workspace / "build" / "score_loop_candidate.exe",
    ]
    benchmark_root = workspace / "build" / "benchmarks"
    if benchmark_root.exists():
        candidates.extend(benchmark_root.rglob("report.json"))
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return {"path": "", "updatedAt": ""}
    latest = max(existing, key=lambda path: path.stat().st_mtime)
    return {"path": str(latest), "updatedAt": iso_from_mtime(latest)}


def workspace_partial_evidence(workspace: Path, expected_hash: str = "") -> dict[str, Any]:
    source_path = workspace / "src" / "Solution.cpp"
    exe_path = workspace / "build" / "score_loop_candidate.exe"
    heartbeat_path = workspace / "worker_heartbeat.json"
    report_paths: list[Path] = []
    benchmark_root = workspace / "build" / "benchmarks"
    if benchmark_root.exists():
        report_paths = sorted(benchmark_root.rglob("report.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    source_hash = sha256_file(source_path) if source_path.exists() else ""
    source_changed = bool(expected_hash and source_hash and source_hash.lower() != expected_hash.lower())
    evidence_types: list[str] = []
    if source_changed:
        evidence_types.append("source-diff")
    if exe_path.exists():
        evidence_types.append("candidate-exe")
    if report_paths:
        evidence_types.append("benchmark-report")
    if heartbeat_path.exists():
        evidence_types.append("heartbeat")
    compile_tail = latest_compile_error_tail(workspace)
    if compile_tail.get("tail"):
        evidence_types.append("compile-error-tail")
    paths = []
    if source_changed:
        paths.append(str(source_path))
    if exe_path.exists():
        paths.append(str(exe_path))
    paths.extend(str(path) for path in report_paths[:5])
    if heartbeat_path.exists():
        paths.append(str(heartbeat_path))
    if compile_tail.get("path"):
        paths.append(str(compile_tail["path"]))
    return {
        "hasPartial": bool(evidence_types),
        "evidenceTypes": evidence_types,
        "paths": paths,
        "compileErrorTail": compile_tail.get("tail", ""),
        "sourceSha256": source_hash,
        "expectedBaselineSha256": expected_hash,
        "reportCount": len(report_paths),
        "recoveryAction": (
            "recover workspace artifacts into child_result.json or rerun the smallest decisive test before cancelling"
            if evidence_types
            else "none"
        ),
    }


def worker_progress_monitor(worker: dict[str, Any], workspace: Path, now_dt: datetime) -> dict[str, Any]:
    started_path = workspace / "worker_started.json"
    heartbeat_path = workspace / "worker_heartbeat.json"
    result_path = workspace / "child_result.json"
    assigned_at = parse_iso_datetime(worker.get("assignedAt"))
    minutes_since_assigned = None
    if assigned_at is not None:
        minutes_since_assigned = round(max(0.0, (now_dt - assigned_at).total_seconds() / 60.0), 2)
    heartbeat = load_json_if_exists(heartbeat_path)
    activity = latest_workspace_activity(workspace)
    last_heartbeat_at = ""
    if isinstance(heartbeat, dict):
        last_heartbeat_at = str(heartbeat.get("updatedAt") or heartbeat.get("timestamp") or "")
    if heartbeat_path.exists() and not last_heartbeat_at:
        last_heartbeat_at = iso_from_mtime(heartbeat_path)
    raw_status = str(worker.get("status") or "")
    if result_path.exists():
        state = "completed-pending-collect"
    elif heartbeat_path.exists():
        state = "running-with-progress"
    elif started_path.exists():
        state = "started-no-heartbeat"
    elif raw_status == "active" and minutes_since_assigned is not None and minutes_since_assigned >= 5:
        state = "not-started-or-prompt-not-consumed"
    elif raw_status == "active":
        state = "active-waiting-for-start-artifact"
    elif raw_status == "ready":
        state = "ready-not-spawned"
    else:
        state = raw_status or "unknown"
    recommended_action = "none"
    if state == "not-started-or-prompt-not-consumed":
        recommended_action = "send_input interrupt=true with launchMessage; if still unchanged after one bounded wait, pool-update cancelled with blocker"
    elif state == "started-no-heartbeat":
        recommended_action = "check agent output or send a concise continue/write-heartbeat instruction before cancelling"
    elif state == "running-with-progress":
        recommended_action = "wait within lane budget; monitor heartbeat age and expected child_result"
    return {
        "state": state,
        "startedPath": str(started_path),
        "startedExists": started_path.exists(),
        "heartbeatPath": str(heartbeat_path),
        "heartbeatExists": heartbeat_path.exists(),
        "lastHeartbeatAt": last_heartbeat_at,
        "lastWorkspaceActivity": activity,
        "minutesSinceAssigned": minutes_since_assigned,
        "recommendedAction": recommended_action,
    }


@contextmanager
def file_lock(path: Path, *, timeout_seconds: float = 30.0, poll_seconds: float = 0.05):
    lock_path = path.with_suffix(path.suffix + ".lock")
    start = time.monotonic()
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}\n".encode("utf-8"))
        except FileExistsError:
            if time.monotonic() - start > timeout_seconds:
                raise SystemExit(f"timed out waiting for lock: {lock_path}")
            time.sleep(poll_seconds)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_root(value: str | None) -> Path:
    return Path(value).resolve() if value else Path.cwd().resolve()


def ledger_path(root: Path) -> Path:
    return root / "docs" / "optimization-ledger.json"


def main_workspace_guard(root: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {}) if isinstance(ledger, dict) else {}
    source_rel = str(baseline.get("sourcePath", "src/Solution.cpp"))
    source_path = root / source_rel
    expected = str(baseline.get("sourceSha256", "")).lower()
    actual = sha256_file(source_path).lower() if source_path.exists() else ""
    return {
        "project": str(root),
        "currentBaseline": baseline.get("id", ""),
        "sourcePath": str(source_path),
        "expectedSourceSha256": expected,
        "actualSourceSha256": actual,
        "sourceHashMatches": bool(expected and actual and expected == actual),
    }


def submission_map_path(root: Path) -> Path:
    return root / "docs" / "submission-map.json"


def dataset_evolution_path(root: Path) -> Path:
    return root / "docs" / "dataset-evolution-ledger.json"


def search_graph_path(root: Path) -> Path:
    return root / "docs" / "search-graph.json"


def attempt_cards_dir(root: Path) -> Path:
    return root / "docs" / "attempt-cards"


def failed_diffs_dir(root: Path) -> Path:
    return root / "docs" / "failed_diffs"


def failed_diffs_index_path(root: Path) -> Path:
    return root / "docs" / "failed-diffs-index.json"


def mutation_space_path(value: str | None = None) -> Path:
    return Path(value).resolve() if value else DEFAULT_MUTATION_SPACE


def text_of(record: dict[str, Any]) -> str:
    fields = [
        "id",
        "hypothesis",
        "description",
        "reason",
        "result",
        "failureReason",
        "avoidNextTime",
        "summary",
    ]
    parts: list[str] = []
    for field in fields:
        value = record.get(field)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return " ".join(parts).lower()


def classify(text: str, rules: tuple[tuple[str, tuple[str, ...]], ...], default: str) -> str:
    for label, needles in rules:
        if any(needle in text for needle in needles):
            return label
    return default


def direction_from(text: str) -> str:
    if any(word in text for word in ("disable", "remove", "rollback", "guard", "tighten")):
        return "guard"
    if any(word in text for word in ("widen", "expand", "generalize", "broaden")):
        return "enable"
    if any(word in text for word in ("order", "priority", "tie-break")):
        return "reorder"
    if any(word in text for word in ("replace", "swap", "selector")):
        return "replace"
    if any(word in text for word in ("increase", "extra", "more")):
        return "increase"
    if any(word in text for word in ("decrease", "reduce", "less")):
        return "decrease"
    return "unknown"


def baseline_id_text(value: Any, default: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("baseline") or value.get("baselineId") or default or "")
    return str(value or default or "")


def fingerprint(record: dict[str, Any], *, default_based_on: str = "") -> dict[str, str]:
    blob = text_of(record)
    based_on = baseline_id_text(
        record.get("basedOn") or record.get("based_on") or record.get("basedOnBaseline"),
        default_based_on,
    ) or "unknown"
    family = str(record.get("affectedFamily") or record.get("affected_family") or "")
    if not family:
        family = classify(blob, FAMILY_KEYWORDS, "unknown")
    mechanism = str(record.get("changedMechanism") or record.get("changed_mechanism") or "")
    if not mechanism:
        mechanism = classify(blob, MECHANISM_KEYWORDS, "unknown")
    direction = str(record.get("direction") or direction_from(blob))
    return {
        "based_on": based_on,
        "affected_family": family,
        "changed_mechanism": mechanism,
        "parameter_or_rule": str(record.get("parameter_or_rule") or record.get("parameter") or ""),
        "direction": direction,
    }


def fingerprint_key(fp: dict[str, str]) -> str:
    return "|".join(
        re.sub(r"\s+", "_", fp.get(part, "").strip().lower())
        for part in ("based_on", "affected_family", "changed_mechanism", "parameter_or_rule", "direction")
    )


def ledger_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for bucket in ("successfulExperiments", "failedExperiments", "onlineFeedback", "calibrationRecords"):
        values = ledger.get(bucket, [])
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict):
                    clone = dict(item)
                    clone["_bucket"] = bucket
                    records.append(clone)
    return records


def online_best_state(baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_id = str(baseline.get("id") or "")
    scores = baseline.get("scores", {}) if isinstance(baseline, dict) else {}
    best_baseline = str(scores.get("bestKnownOnlineBaseline") or "")
    best_score = as_float(scores.get("bestKnownOnlineScore"))
    current_online = as_float(scores.get("onlineScore"))
    if best_baseline and baseline_id == best_baseline:
        state = "online-best-active"
        severity = "green"
        next_action = "safe-to-exploit"
    elif current_online is not None and best_score is not None and current_online >= best_score:
        state = "online-confirmed-nonworse"
        severity = "green"
        next_action = "safe-to-exploit-after-ledger-review"
    elif current_online is not None and best_score is not None and current_online < best_score:
        state = "online-regressed-branch"
        severity = "red"
        next_action = "restore-online-best-before-edit-lanes"
    else:
        state = "online-unconfirmed-branch"
        severity = "yellow"
        next_action = "prefer-online-best-or-diagnose-before-more-edits"
    return {
        "state": state,
        "severity": severity,
        "currentBaseline": baseline_id,
        "bestKnownOnlineBaseline": best_baseline,
        "bestKnownOnlineScore": best_score,
        "currentOnlineScore": current_online,
        "nextAction": next_action,
    }


def command_status(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    source_path = root / str(baseline.get("sourcePath", "src/Solution.cpp"))
    source_hash = sha256_file(source_path) if source_path.exists() else None
    expected_hash = str(baseline.get("sourceSha256", "")).lower()
    scores = baseline.get("scores", {})
    online_state = online_best_state(baseline)
    output = {
        "project": str(root),
        "currentBaseline": baseline.get("id"),
        "expectedSourceSha256": expected_hash,
        "actualSourceSha256": source_hash,
        "sourceHashMatches": bool(source_hash and source_hash.lower() == expected_hash),
        "bestKnownOnlineScore": scores.get("bestKnownOnlineScore"),
        "bestKnownOnlineBaseline": scores.get("bestKnownOnlineBaseline"),
        "currentOnlineScore": scores.get("onlineScore"),
        "onlineBestState": online_state,
        "firstPlaceScoreSnapshot": scores.get("firstPlaceScoreSnapshot"),
        "gapToFirstPlaceUsingBestKnownOnline": scores.get("gapToFirstPlaceUsingBestKnownOnline"),
        "warnings": [],
    }
    if not output["sourceHashMatches"]:
        output["warnings"].append("source hash drift: restore or classify before editing")
    if online_state["severity"] == "yellow":
        output["warnings"].append("local active baseline is not best-known online; use diagnose/proposal lanes or restore-online-best before exploit")
    elif online_state["severity"] == "red":
        output["warnings"].append("local active baseline regressed online; restore-online-best before edit lanes")
    write_json(output)
    return 0 if output["sourceHashMatches"] else 2


def command_index(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    current_id = str(ledger.get("currentBaseline", {}).get("id", ""))
    rows: list[dict[str, Any]] = []
    seen: dict[str, list[str]] = {}
    for record in ledger_records(ledger):
        fp = fingerprint(record, default_based_on=current_id)
        key = fingerprint_key(fp)
        seen.setdefault(key, []).append(str(record.get("id") or record.get("baseline") or "unknown"))
        rows.append(
            {
                "id": record.get("id") or record.get("baseline"),
                "bucket": record.get("_bucket"),
                "fingerprint": fp,
                "fingerprintKey": key,
                "result": record.get("result") or record.get("status"),
                "retryPolicy": record.get("retryPolicy"),
                "avoidNextTime": record.get("avoidNextTime"),
            }
        )
    duplicates = {key: ids for key, ids in seen.items() if len(ids) > 1 and "unknown" not in key}
    output = {"count": len(rows), "duplicates": duplicates, "entries": rows if args.verbose else rows[-20:]}
    write_json(output)
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    current_id = str(ledger.get("currentBaseline", {}).get("id", ""))
    candidate = {
        "id": "candidate",
        "basedOn": args.based_on or current_id,
        "hypothesis": args.hypothesis,
        "affectedFamily": args.family or "",
        "changedMechanism": args.mechanism or "",
        "direction": args.direction or "",
    }
    cand_fp = fingerprint(candidate, default_based_on=current_id)
    cand_key = fingerprint_key(cand_fp)
    matches: list[dict[str, Any]] = []
    near_matches: list[dict[str, Any]] = []
    for record in ledger_records(ledger):
        fp = fingerprint(record, default_based_on=current_id)
        key = fingerprint_key(fp)
        if key == cand_key:
            matches.append(
                {
                    "id": record.get("id") or record.get("baseline"),
                    "bucket": record.get("_bucket"),
                    "result": record.get("result") or record.get("status"),
                    "failureReason": record.get("failureReason"),
                    "avoidNextTime": record.get("avoidNextTime"),
                }
            )
        elif (
            fp.get("affected_family") == cand_fp.get("affected_family")
            and fp.get("changed_mechanism") == cand_fp.get("changed_mechanism")
            and fp.get("direction") == cand_fp.get("direction")
        ):
            near_matches.append(
                {
                    "id": record.get("id") or record.get("baseline"),
                    "bucket": record.get("_bucket"),
                    "basedOn": fp.get("based_on"),
                    "result": record.get("result") or record.get("status"),
                    "failureReason": record.get("failureReason"),
                    "avoidNextTime": record.get("avoidNextTime"),
                }
            )
    decision = "allowed"
    if matches:
        decision = "duplicate-needs-new-mechanism-or-guard"
    elif near_matches:
        decision = "near-duplicate-review-ledger-lessons"
    write_json(
        {
            "candidateFingerprint": cand_fp,
            "fingerprintKey": cand_key,
            "decision": decision,
            "matches": matches,
            "nearMatches": near_matches[:10],
        }
    )
    return 1 if matches else 0


def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def flatten_numbers(data: Any, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_numbers(value, next_prefix))
    else:
        number = as_float(data)
        if number is not None:
            out[prefix] = number
    return out


def delta_from(result: dict[str, Any], name: str) -> float | None:
    deltas = flatten_numbers(result.get("deltasVsBaseline", {}))
    for key, value in deltas.items():
        normalized = key.replace(".", "_").lower()
        if name.lower() in normalized:
            return value
    return None


def family_weight(weights: dict[str, Any], family_name: str) -> float:
    families = weights.get("families", {}) if isinstance(weights, dict) else {}
    family = families.get(family_name, {}) if isinstance(families, dict) else {}
    return float(family.get("current_weight", 0.5)) if isinstance(family, dict) else 0.5


def mechanism_weight(weights: dict[str, Any], family_name: str, mechanism_name: str) -> float:
    families = weights.get("families", {}) if isinstance(weights, dict) else {}
    family = families.get(family_name, {}) if isinstance(families, dict) else {}
    mechanisms = family.get("mechanisms", {}) if isinstance(family, dict) else {}
    mechanism = mechanisms.get(mechanism_name, {}) if isinstance(mechanisms, dict) else {}
    if isinstance(mechanism, dict) and "current_weight" in mechanism:
        return float(mechanism.get("current_weight", 0.5))
    return family_weight(weights, family_name)


def shape_weight(weights: dict[str, Any], family_name: str, mechanism_name: str, shape_name: str) -> float:
    families = weights.get("families", {}) if isinstance(weights, dict) else {}
    family = families.get(family_name, {}) if isinstance(families, dict) else {}
    mechanisms = family.get("mechanisms", {}) if isinstance(family, dict) else {}
    mechanism = mechanisms.get(mechanism_name, {}) if isinstance(mechanisms, dict) else {}
    shapes = mechanism.get("shapes", {}) if isinstance(mechanism, dict) else {}
    shape = shapes.get(shape_name, {}) if isinstance(shapes, dict) else {}
    if isinstance(shape, dict) and "current_weight" in shape:
        return float(shape.get("current_weight", 0.5))
    return mechanism_weight(weights, family_name, mechanism_name)


def result_family(result: dict[str, Any]) -> str:
    explicit = result.get("affected_family") or result.get("affectedFamily")
    if explicit:
        return str(explicit)
    return classify(json.dumps(result, ensure_ascii=False).lower(), FAMILY_KEYWORDS, "unknown")


def result_mechanism(result: dict[str, Any]) -> str:
    explicit = result.get("changed_mechanism") or result.get("changedMechanism")
    if explicit:
        return str(explicit)
    return classify(json.dumps(result, ensure_ascii=False).lower(), MECHANISM_KEYWORDS, "unknown")


def result_shape(result: dict[str, Any]) -> str:
    explicit = result.get("hidden_shape") or result.get("hiddenShape") or result.get("shape")
    if explicit:
        return str(explicit)
    return classify(json.dumps(result, ensure_ascii=False).lower(), SHAPE_KEYWORDS, "unknown")


def lane_shape(lane: dict[str, Any]) -> str:
    explicit = lane.get("hidden_shape") or lane.get("hiddenShape") or lane.get("shape")
    if explicit:
        return str(explicit)
    shape_fields = {
        key: lane.get(key)
        for key in (
            "lane",
            "attempt",
            "knob",
            "hypothesis",
            "uncertainty_reduced",
            "expected_gain",
            "known_risk",
        )
        if key in lane
    }
    text = json.dumps(shape_fields, ensure_ascii=False).lower()
    has_jobs22 = "jobs22" in text or "gjobcount==22" in text or "jobcount==22" in text
    has_leaf64 = "leaf64" in text or "gleafcount==64" in text or "leafcount==64" in text
    has_phase4 = "phase4" in text or "phasecount==4" in text
    has_flow1536 = "flow1536" in text or "flowsperphase==1536" in text
    if has_jobs22 and has_leaf64 and has_phase4 and has_flow1536:
        return "jobs22_leaf64_p12_r4_phase4_flow1536"
    return classify(text, SHAPE_KEYWORDS, "unknown")


def apply_lane_metadata(result: dict[str, Any], lane: dict[str, Any] | None) -> dict[str, Any]:
    """Use manifest lane metadata as the canonical label for worker results."""
    if not lane:
        return dict(result)
    enriched = dict(result)
    family = lane.get("affected_family") or lane.get("affectedFamily")
    mechanism = lane.get("changed_mechanism") or lane.get("changedMechanism")
    shape = lane_shape(lane)
    if family:
        enriched["affectedFamily"] = str(family)
        enriched["affected_family"] = str(family)
    if mechanism:
        enriched["changedMechanism"] = str(mechanism)
        enriched["changed_mechanism"] = str(mechanism)
    if shape and shape != "unknown":
        enriched["hiddenShape"] = shape
        enriched["hidden_shape"] = shape
    if lane.get("lane"):
        enriched.setdefault("lane", lane.get("lane"))
        enriched.setdefault("laneId", lane.get("lane"))
    if lane.get("attempt"):
        enriched.setdefault("attempt", lane.get("attempt"))
        enriched.setdefault("attemptId", lane.get("attempt"))
    return enriched


def epoch_manifest_for_child(child_path: Path) -> tuple[Path | None, dict[str, Any] | None]:
    for parent in [child_path.parent, *child_path.parents]:
        manifest_path = parent / "epoch_manifest.json"
        if manifest_path.exists():
            loaded = load_json(manifest_path)
            return parent, loaded if isinstance(loaded, dict) else None
    return None, None


def lane_for_child_path(child_path: Path, manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not manifest:
        return None
    resolved = child_path.resolve()
    for lane in manifest.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        workspace_text = str(lane.get("workspace", ""))
        if not workspace_text:
            continue
        try:
            workspace = Path(workspace_text).resolve()
            if resolved == workspace / "child_result.json" or workspace in resolved.parents:
                return lane
        except OSError:
            continue
    return None


def closeout_for_child(child_path: Path) -> tuple[Path | None, dict[str, Any] | None]:
    run_dir, _manifest = epoch_manifest_for_child(child_path)
    if not run_dir:
        return None, None
    closeout_path = run_dir / "epoch_closeout.json"
    if not closeout_path.exists():
        return closeout_path, None
    loaded = load_json(closeout_path)
    return closeout_path, loaded if isinstance(loaded, dict) else None


def safe_artifact_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned[:160] or f"attempt-{int(time.time())}"


CONTROL_SIGNATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("guard_predicate", ("if (", "if(", "&&", "||", "continue", "return false", "return true")),
    ("threshold_numeric", ("<=", ">=", "< ", "> ", "==", "!=", "limit", "threshold")),
    ("score_weight", ("weighted", "delta", "cost", "score", "penalty", "12 *", "5 *")),
    ("bandwidth_ratio", ("gbandwidthratio", "bandwidth", "capacity")),
    ("tie_break", ("bestscore", "second", "bestport", "port <", "tie", "rank")),
    ("sort_order", ("sort(", "stable_sort", "priority", "order")),
    ("loop_bound", ("for (", "while (", "break", "candidate", "top")),
    ("runtime_cap", ("time", "clock", "timeout", "budget", "maxmoves", "32")),
    ("source_transition", ("sourcetransition", "source transition", "transitiondelta")),
    ("phase_inner", ("phaseinner", "phase_inner", "innerdelta")),
    ("max_single", ("maxsingle", "max_single", "maxout", "max load")),
    ("projected_global", ("projectedglobal", "projected_global", "globalpeak")),
    ("job_between", ("jobbetween", "job_between")),
    ("residual_repair", ("residual", "repair", "hotphase", "hot phase")),
    ("randomness", ("random", "shuffle", "rng")),
)


KNOWN_FUNCTION_HINTS: tuple[str, ...] = (
    "chooseGreedyPort",
    "improveHotPhasePorts",
    "assignOfficialHotSourceJob",
    "assignOfficialPhaseCapacityJob",
    "improveOfficialPhaseCapacitySwaps",
    "improveLeafBandPairedSamePhaseSwaps",
    "improveOfficialSourceTransitions",
    "evaluateOfficialAssignment",
    "shouldUseOfficialResidualRepair",
    "assignOfficialPorts",
    "syncPortsFromUniqueFlows",
    "solveJob",
    "scoreOfficialAssignment",
    "computeJobMetrics",
    "repair",
    "residual",
)


def normalize_diff_line(line: str) -> str:
    text = re.sub(r"//.*", "", line.strip())
    text = re.sub(r"\b\d+\b", "<num>", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def target_functions_from_text(text: str) -> list[str]:
    lower = text.lower()
    found = [name for name in KNOWN_FUNCTION_HINTS if name.lower() in lower]
    extra = []
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_:<>]*)\s*\([^;{}]*\)\s*\{", text):
        name = match.group(1).split("::")[-1]
        if name and name not in found and len(name) > 3:
            extra.append(name)
    return list(dict.fromkeys([*found, *extra[:6]]))


def control_tags_from_text(text: str) -> list[str]:
    lower = text.lower()
    tags = [
        label
        for label, needles in CONTROL_SIGNATURE_RULES
        if any(needle in lower for needle in needles)
    ]
    if re.search(r"[-+]\s*(?:const\s+)?(?:int|double|long|float)\s+\w+\s*=", text):
        tags.append("constant_assignment")
    return sorted(set(tags))


def unified_source_diff(before: Path, after: Path, *, from_label: str = "baseline", to_label: str = "candidate") -> str:
    if not before.exists() or not after.exists():
        return ""
    before_lines = before.read_text(encoding="utf-8", errors="replace").splitlines()
    after_lines = after.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
            n=3,
        )
    )


def baseline_snapshot_for_child(root: Path, child: dict[str, Any], lane: dict[str, Any] | None) -> Path | None:
    based_on = baseline_id_text(
        child.get("basedOn") or child.get("based_on") or (lane or {}).get("based_on"),
        "",
    )
    if based_on:
        snapshot = root / "docs" / "baselines" / based_on / "Solution.cpp"
        if snapshot.exists():
            return snapshot
    expected = str(child.get("baselineSha256") or (lane or {}).get("baseline_sha256") or "").lower()
    if expected:
        baseline_dir = root / "docs" / "baselines"
        if baseline_dir.exists():
            for path in baseline_dir.rglob("Solution.cpp"):
                try:
                    if sha256_file(path).lower() == expected:
                        return path
                except OSError:
                    continue
    return None


def diff_text_for_child(root: Path, child_path: Path, child: dict[str, Any], lane: dict[str, Any] | None) -> tuple[str, Path | None]:
    workspace = child_path.parent
    candidate = workspace / "src" / "Solution.cpp"
    baseline = baseline_snapshot_for_child(root, child, lane)
    if baseline and candidate.exists():
        diff_text = unified_source_diff(
            baseline,
            candidate,
            from_label=str(baseline),
            to_label=str(candidate),
        )
        if diff_text:
            return diff_text, baseline
    for key in ("unifiedDiff", "diff", "patch", "attemptedDiffSummary", "mutationSummary", "architectureSummary", "diffSummary"):
        value = child.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), baseline
    return "", baseline


def static_diff_signature(diff_text: str, child: dict[str, Any], lane: dict[str, Any] | None) -> dict[str, Any]:
    context_text = "\n".join(
        [
            diff_text,
            str(child.get("hypothesis") or ""),
            str(child.get("summary") or ""),
            str((lane or {}).get("hypothesis") or ""),
            str(child.get("attemptedDiffSummary") or child.get("mutationSummary") or child.get("architectureSummary") or ""),
        ]
    )
    changed_lines = [
        line
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    normalized_changes = [normalize_diff_line(line) for line in changed_lines if normalize_diff_line(line)]
    functions = target_functions_from_text(context_text)
    control_tags = control_tags_from_text(context_text)
    key_constants = sorted(
        set(
            token
            for token in re.findall(r"\b(?:g[A-Z][A-Za-z0-9_]*|phaseInner|sourceTransition|maxSingle|projectedGlobal|weightedDelta|gBandwidthRatio)\b", context_text)
        )
    )
    signature_material = {
        "functions": functions,
        "controlTags": control_tags,
        "keyConstants": key_constants,
        "normalizedChanges": normalized_changes[:80],
    }
    signature_hash = hashlib.sha256(json.dumps(signature_material, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "targetFunctions": functions,
        "controlTags": control_tags,
        "keyConstants": key_constants,
        "normalizedChangeCount": len(normalized_changes),
        "signatureHash": signature_hash,
    }


def load_or_default_failed_diffs_index(root: Path) -> dict[str, Any]:
    path = failed_diffs_index_path(root)
    if path.exists():
        loaded = load_json(path)
        if isinstance(loaded, dict):
            loaded.setdefault("version", 1)
            loaded.setdefault("updatedAt", None)
            loaded.setdefault("records", [])
            return loaded
    return {
        "version": 1,
        "updatedAt": None,
        "purpose": "Index rejected/failed solver diffs as reusable mutation material for risk resurrection and novelty checks.",
        "records": [],
    }


def compile_status_from_child(child: dict[str, Any]) -> str:
    compile_checks: list[dict[str, Any]] = []
    checks_run = child.get("checksRun")
    if not isinstance(checks_run, list):
        checks_run = []
    for item in checks_run:
        if not isinstance(item, dict):
            continue
        text = json.dumps(
            {
                "command": item.get("command"),
                "normalized": item.get("normalized"),
                "name": item.get("name"),
            },
            ensure_ascii=False,
        ).lower()
        if "g++" in text or "compile" in text or "compiler" in text:
            compile_checks.append(item)
    if compile_checks:
        last = compile_checks[-1]
        status_text = str(last.get("status") or last.get("result") or "").lower()
        if any(token in status_text for token in ("passed", "success", "ok", "fixed")):
            return "SUCCESS"
        if any(token in status_text for token in ("failed", "error")):
            return "FAILED"
    if child.get("compileErrorTail"):
        return "FAILED"
    text = json.dumps(
        {
            "checksRun": child.get("checksRun"),
            "summary": child.get("summary"),
            "currentEvidence": child.get("currentEvidence"),
        },
        ensure_ascii=False,
    ).lower()
    if "g++" in text or "compile" in text or "compilation" in text:
        if child_result_mentions_compile_failure(child):
            return "FAILED"
        return "SUCCESS"
    return "UNKNOWN"


def first_kill_status_from_child(child: dict[str, Any]) -> str:
    if compile_status_from_child(child) == "FAILED":
        return "COMPILE_FAILED"
    deltas = {
        key: value
        for key, value in flatten_numbers(child.get("deltasVsBaseline", {})).items()
        if not any(token in key.lower() for token in ("baseline", "candidate", "reference"))
    }
    if any(value < -1e-9 for value in deltas.values()):
        return "FAILED_REGRESSION"
    if any(value > 1e-9 for value in deltas.values()):
        return "MOVED_POSITIVE"
    text = json.dumps(
        {
            "result": child.get("result"),
            "summary": child.get("summary"),
            "currentEvidence": child.get("currentEvidence"),
        },
        ensure_ascii=False,
    ).lower()
    if any(token in text for token in ("flat", "no-op", "0 delta", "neutral")):
        return "FLAT"
    if any(token in text for token in ("timeout", "runtime")):
        return "FAILED_RUNTIME"
    return "UNKNOWN"


def should_archive_failed_diff(child: dict[str, Any], diff_text: str) -> bool:
    if child.get("promotionCandidate") is True:
        return False
    if diff_text.strip():
        return True
    changed = [normalize_rel_path(item) for item in child.get("changedFiles", [])]
    return any(item == "src/Solution.cpp" for item in changed)


def make_failed_diff_record(root: Path, child_path: Path, child: dict[str, Any], lane: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    diff_text, baseline_snapshot = diff_text_for_child(root, child_path, child, lane)
    if not should_archive_failed_diff(child, diff_text):
        return None, diff_text
    attempt_id = attempt_id_from_child(child, child_path)
    static_sig = static_diff_signature(diff_text, child, lane)
    deltas = flatten_numbers(child.get("deltasVsBaseline", {}))
    record_id = safe_artifact_id(f"fd-{attempt_id}")[:120]
    patch_path = failed_diffs_dir(root) / f"{record_id}.patch"
    record = {
        "version": 1,
        "diffId": record_id,
        "attemptId": attempt_id,
        "lane": child.get("laneId") or child.get("lane") or (lane or {}).get("lane"),
        "sourceChildResult": str(child_path),
        "basedOn": baseline_id_text(child.get("basedOn") or (lane or {}).get("based_on"), ""),
        "baselineSha256": child.get("baselineSha256") or (lane or {}).get("baseline_sha256"),
        "baselineSnapshot": str(baseline_snapshot) if baseline_snapshot else "",
        "family": result_family(child),
        "mechanism": result_mechanism(child),
        "shape": result_shape(child),
        "targetFunctions": static_sig["targetFunctions"],
        "controlTags": static_sig["controlTags"],
        "keyConstants": static_sig["keyConstants"],
        "staticSignatureHash": static_sig["signatureHash"],
        "compilation": compile_status_from_child(child),
        "firstKillResult": first_kill_status_from_child(child),
        "metricDeltas": deltas,
        "result": child.get("result"),
        "summary": child.get("summary"),
        "avoidNextTime": child.get("avoidNextTime"),
        "patchPath": str(patch_path),
        "diffSha256": hashlib.sha256(diff_text.encode("utf-8", errors="replace")).hexdigest() if diff_text else "",
        "recordedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    return record, diff_text


def upsert_failed_diff_record(index: dict[str, Any], record: dict[str, Any]) -> None:
    records = [item for item in index.get("records", []) if isinstance(item, dict)]
    key = str(record.get("diffId") or "")
    replaced = False
    output: list[dict[str, Any]] = []
    for item in records:
        if key and str(item.get("diffId") or "") == key:
            merged = dict(item)
            merged.update(record)
            output.append(merged)
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(record)
    index["records"] = output
    index["updatedAt"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def novelty_assessment_for_signature(index: dict[str, Any], signature: dict[str, Any], family: str, mechanism: str) -> dict[str, Any]:
    records = [item for item in index.get("records", []) if isinstance(item, dict)]
    signature_hash = str(signature.get("signatureHash") or "")
    exact = [item for item in records if signature_hash and str(item.get("staticSignatureHash") or "") == signature_hash]
    target_functions = set(str(item) for item in signature.get("targetFunctions", []))
    control_tags = set(str(item) for item in signature.get("controlTags", []))
    near: list[dict[str, Any]] = []
    for item in records:
        item_functions = set(str(value) for value in item.get("targetFunctions", []) if value)
        item_tags = set(str(value) for value in item.get("controlTags", []) if value)
        same_family = family and family != "unknown" and str(item.get("family") or "") == family
        same_mechanism = mechanism and mechanism != "unknown" and str(item.get("mechanism") or "") == mechanism
        function_overlap = bool(target_functions and item_functions and target_functions & item_functions)
        tag_overlap = len(control_tags & item_tags)
        if (same_family and same_mechanism and function_overlap) or (function_overlap and tag_overlap >= 2):
            near.append(item)
    decision = "novel"
    if exact:
        decision = "duplicate-static-signature"
    elif len(near) >= 2:
        decision = "near-duplicate-requires-new-causal-variable"
    return {
        "decision": decision,
        "exactMatches": [item.get("diffId") for item in exact[:5]],
        "nearMatches": [item.get("diffId") for item in near[:8]],
        "nearMatchCount": len(near),
    }


def failed_diff_context(root: Path, *, limit: int = 8) -> dict[str, Any]:
    index = load_or_default_failed_diffs_index(root)
    records = [item for item in index.get("records", []) if isinstance(item, dict)]
    compilable = [item for item in records if item.get("compilation") == "SUCCESS"]
    reusable = [
        item
        for item in compilable
        if item.get("firstKillResult") in ("MOVED_POSITIVE", "FAILED_REGRESSION", "FLAT", "UNKNOWN")
    ]
    return {
        "indexPath": str(failed_diffs_index_path(root)),
        "failedDiffsDir": str(failed_diffs_dir(root)),
        "recordCount": len(records),
        "compilableCount": len(compilable),
        "recentRecords": records[-limit:],
        "riskResurrectionCandidates": reusable[-limit:],
        "rule": "Use compilable failed diffs as mutation material. Exact static-signature repeats require a named new causal variable.",
    }


def compact_failed_diff_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "diffId": item.get("diffId"),
        "patchPath": item.get("patchPath"),
        "sourceChildResult": item.get("sourceChildResult"),
        "family": item.get("family"),
        "mechanism": item.get("mechanism"),
        "shape": item.get("shape"),
        "targetFunctions": item.get("targetFunctions", []),
        "controlTags": item.get("controlTags", []),
        "staticSignatureHash": item.get("staticSignatureHash"),
        "compilation": item.get("compilation"),
        "firstKillResult": item.get("firstKillResult"),
        "metricDeltas": item.get("metricDeltas", {}),
        "result": item.get("result"),
        "summary": item.get("summary"),
        "avoidNextTime": item.get("avoidNextTime"),
    }


def failed_diff_records_by_ids(root: Path, diff_ids: list[Any], *, limit: int = 6) -> list[dict[str, Any]]:
    wanted = [str(item) for item in diff_ids if str(item or "").strip()]
    if not wanted:
        return []
    wanted_set = set(wanted)
    index = load_or_default_failed_diffs_index(root)
    records = [item for item in index.get("records", []) if isinstance(item, dict)]
    selected = [item for item in records if str(item.get("diffId") or "") in wanted_set]
    order = {diff_id: idx for idx, diff_id in enumerate(wanted)}
    selected.sort(key=lambda item: order.get(str(item.get("diffId") or ""), 9999))
    return [compact_failed_diff_record(item) for item in selected[:limit]]


def recovery_records_for_lane(root: Path, lane: dict[str, Any], *, limit: int = 4) -> list[dict[str, Any]]:
    explicit_records = lane.get("recoveredDiffs")
    if isinstance(explicit_records, list) and explicit_records:
        return [
            compact_failed_diff_record(item) if isinstance(item, dict) else {"diffId": str(item)}
            for item in explicit_records[:limit]
        ]
    signal = lane.get("banditSignal", {}) if isinstance(lane.get("banditSignal", {}), dict) else {}
    diff_ids: list[Any] = []
    for key in ("resurrectionPatchIds", "patchIds", "recoveredDiffIds"):
        values = signal.get(key) if isinstance(signal, dict) else None
        if isinstance(values, list):
            diff_ids.extend(values)
    if isinstance(lane.get("recoveredDiffIds"), list):
        diff_ids.extend(lane.get("recoveredDiffIds", []))
    if diff_ids:
        return failed_diff_records_by_ids(root, diff_ids, limit=limit)

    is_resurrection = any(
        token in str(lane.get(key) or "").lower()
        for key in ("lane", "attempt", "noveltyClass", "changed_mechanism")
        for token in ("resurrect", "recovery", "failed_diff", "legacy")
    )
    if not (is_resurrection or controlled_risk_lane(lane) or architecture_breakout_lane(lane)):
        return []
    family = str(lane.get("affected_family") or lane.get("affectedFamily") or "unknown")
    mechanism = str(lane.get("changed_mechanism") or lane.get("changedMechanism") or "unknown")
    index = load_or_default_failed_diffs_index(root)
    candidates = [
        item
        for item in index.get("records", [])
        if isinstance(item, dict)
        and item.get("compilation") == "SUCCESS"
        and item.get("patchPath")
        and (
            (family != "unknown" and str(item.get("family") or "") == family)
            or (mechanism != "unknown" and str(item.get("mechanism") or "") == mechanism)
        )
    ]
    candidates.sort(
        key=lambda item: (
            item.get("firstKillResult") == "MOVED_POSITIVE",
            str(item.get("recordedAt") or ""),
        ),
        reverse=True,
    )
    return [compact_failed_diff_record(item) for item in candidates[:limit]]


def bandit_signal_for_idea(root: Path, idea: dict[str, Any]) -> dict[str, Any]:
    family = str(idea.get("affected_family") or idea.get("affectedFamily") or "unknown")
    mechanism = str(idea.get("changed_mechanism") or idea.get("changedMechanism") or "unknown")
    graph = load_or_default_search_graph(root)
    nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    same_nodes = [
        item
        for item in nodes
        if str(item.get("family") or "") == family and str(item.get("mechanism") or "") == mechanism
    ]
    successes = [
        item
        for item in same_nodes
        if item.get("promotionCandidate") is True or bool(item.get("positiveDeltaKeys"))
    ]
    index = load_or_default_failed_diffs_index(root)
    failed_records = [
        item
        for item in index.get("records", [])
        if isinstance(item, dict)
        and str(item.get("family") or "") == family
        and str(item.get("mechanism") or "") == mechanism
    ]
    partial = [
        item
        for item in failed_records
        if item.get("compilation") == "SUCCESS" and item.get("firstKillResult") == "MOVED_POSITIVE"
    ]
    idea_text = json.dumps(
        {
            "lane": idea.get("lane"),
            "hypothesis": idea.get("hypothesis"),
            "targetComponent": idea.get("targetComponent"),
            "smallestDecisiveTest": idea.get("smallestDecisiveTest"),
            "killCondition": idea.get("killCondition"),
        },
        ensure_ascii=False,
    )
    signature = static_diff_signature(idea_text, {"hypothesis": idea_text}, None)
    novelty = novelty_assessment_for_signature(index, signature, family, mechanism)
    success_value = len(successes) + (0.5 * len(partial))
    failure_value = len(failed_records)
    posterior_mean = (1.0 + success_value) / (2.0 + success_value + failure_value)
    boost = (posterior_mean - 0.5) * 14.0
    if novelty["decision"] == "duplicate-static-signature":
        boost -= 22
    elif novelty["decision"] == "near-duplicate-requires-new-causal-variable":
        boost -= 8
    if partial:
        boost += min(6.0, 2.0 * len(partial))
    if posterior_mean >= 0.62:
        hint = "exploit-more-workers"
    elif posterior_mean <= 0.35 and novelty["decision"] != "novel":
        hint = "require-new-causal-variable"
    elif partial:
        hint = "resurrect-with-new-guard"
    else:
        hint = "balanced-explore"
    return {
        "family": family,
        "mechanism": mechanism,
        "successes": len(successes),
        "failedDiffs": len(failed_records),
        "partialPositiveFailedDiffs": len(partial),
        "posteriorMean": round(posterior_mean, 4),
        "scoreBoost": round(boost, 4),
        "allocationHint": hint,
        "novelty": novelty,
        "resurrectionPatchIds": [item.get("diffId") for item in partial[-4:]],
    }


def bandit_signals_for_ideas(root: Path, ideas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(idea.get("lane")): bandit_signal_for_idea(root, idea)
        for idea in ideas
        if str(idea.get("lane") or "")
    }


def archive_failed_diff_for_child(
    root: Path,
    run_dir: Path,
    child_path: Path,
    loaded_child: dict[str, Any],
    *,
    write: bool,
) -> dict[str, Any]:
    _child_run_dir, manifest = epoch_manifest_for_child(child_path)
    lane = lane_for_child_path(child_path, manifest)
    child = apply_lane_metadata(loaded_child, lane)
    record, diff_text = make_failed_diff_record(root, child_path, child, lane)
    if not record:
        return {"source": str(child_path), "archived": False, "reason": "not a failed solver diff"}
    index_path = failed_diffs_index_path(root)
    project_patch = Path(str(record.get("patchPath")))
    epoch_patch = run_dir / "failed_diffs" / project_patch.name
    if write:
        failed_diffs_dir(root).mkdir(parents=True, exist_ok=True)
        epoch_patch.parent.mkdir(parents=True, exist_ok=True)
        patch_body = diff_text or str(record.get("summary") or "")
        project_patch.write_text(patch_body + ("\n" if patch_body and not patch_body.endswith("\n") else ""), encoding="utf-8")
        epoch_patch.write_text(patch_body + ("\n" if patch_body and not patch_body.endswith("\n") else ""), encoding="utf-8")
        with file_lock(index_path):
            index = load_or_default_failed_diffs_index(root)
            upsert_failed_diff_record(index, record)
            atomic_write_json(index_path, index)
    return {
        "source": str(child_path),
        "archived": write,
        "record": record,
        "indexPath": str(index_path),
        "projectPatchPath": str(project_patch),
        "epochPatchPath": str(epoch_patch),
    }


def load_or_default_search_graph(root: Path) -> dict[str, Any]:
    path = search_graph_path(root)
    if path.exists():
        loaded = load_json(path)
        if isinstance(loaded, dict):
            loaded.setdefault("version", 1)
            loaded.setdefault("nodes", [])
            loaded.setdefault("edges", [])
            loaded.setdefault("fusionCandidates", [])
            return loaded
    return {
        "version": 1,
        "updatedAt": None,
        "nodes": [],
        "edges": [],
        "fusionCandidates": [],
        "notes": [
            "Search graph is infrastructure, not a creativity gate.",
            "A node records one attempt; fusion candidates are suggestions, not automatic bundles.",
        ],
    }


def positive_delta_keys(deltas: Any) -> list[str]:
    if not isinstance(deltas, dict):
        return []
    keys: list[str] = []
    for key, value in deltas.items():
        number = as_float(value)
        if number is not None and number > 0:
            keys.append(str(key))
    return keys


def attempt_id_from_child(child: dict[str, Any], child_path: Path) -> str:
    return str(
        child.get("attemptId")
        or child.get("attempt")
        or child.get("worker")
        or child.get("laneId")
        or child.get("lane")
        or child_path.parent.name
    )


def attempt_card_path(root: Path, attempt_id: str) -> Path:
    return attempt_cards_dir(root) / f"{safe_artifact_id(attempt_id)}.json"


def attempt_card_from_child_result(root: Path, child_path: Path) -> dict[str, Any]:
    loaded_child = load_json(child_path)
    run_dir, manifest = epoch_manifest_for_child(child_path)
    lane = lane_for_child_path(child_path, manifest)
    child = apply_lane_metadata(loaded_child, lane)
    attempt_id = attempt_id_from_child(child, child_path)
    rank_score, strengths, risks = score_child(child, load_or_default_weights(root))
    based_on = baseline_id_text(child.get("basedOn") or child.get("based_on") or (lane or {}).get("based_on"), "")
    fusion_of = child.get("fusionOf") or child.get("fusion_of") or (lane or {}).get("fusionOf") or []
    if isinstance(fusion_of, str):
        fusion_of = [fusion_of]
    if not isinstance(fusion_of, list):
        fusion_of = []
    reusable_components = child.get("reusableComponents") or child.get("reusable_components") or []
    if isinstance(reusable_components, str):
        reusable_components = [reusable_components]
    if not reusable_components and positive_delta_keys(child.get("deltasVsBaseline")):
        reusable_components = [
            f"{result_family(child)}/{result_mechanism(child)} moved {', '.join(positive_delta_keys(child.get('deltasVsBaseline'))[:4])}"
        ]
    failed_diff_record, _diff_text = make_failed_diff_record(root, child_path, child, lane)
    return {
        "version": 1,
        "id": attempt_id,
        "recordedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "sourceChildResult": str(child_path),
        "runDir": str(run_dir) if run_dir else "",
        "lane": child.get("laneId") or child.get("lane") or (lane or {}).get("lane"),
        "parent": based_on,
        "basedOn": based_on,
        "baselineSha256": child.get("baselineSha256"),
        "family": result_family(child),
        "mechanism": result_mechanism(child),
        "shape": result_shape(child),
        "hypothesis": child.get("hypothesis"),
        "plan": child.get("plan") or child.get("strategy") or (lane or {}).get("hypothesis"),
        "diffSummary": child.get("attemptedDiffSummary") or child.get("mutationSummary") or child.get("architectureSummary"),
        "changedFiles": child.get("changedFiles", []),
        "checksRun": child.get("checksRun", []),
        "scores": child.get("scores", {}),
        "deltasVsBaseline": child.get("deltasVsBaseline", {}),
        "positiveDeltaKeys": positive_delta_keys(child.get("deltasVsBaseline")),
        "notableRegressions": child.get("notableRegressions", []),
        "runtimeRisk": child.get("runtimeRisk"),
        "promotionCandidate": child.get("promotionCandidate"),
        "result": child.get("result"),
        "summary": child.get("summary"),
        "avoidNextTime": child.get("avoidNextTime"),
        "lesson": lesson_items(child.get("avoidNextTime")) or lesson_items(child.get("summary")),
        "reusableComponents": reusable_components,
        "fusionOf": fusion_of,
        "rankScore": round(rank_score, 4),
        "strengths": strengths,
        "risks": risks,
        "onlineResult": child.get("onlineResult"),
        "failedDiffCandidate": failed_diff_record,
        "searchTags": list(
            dict.fromkeys(
                [
                    str(child.get("result") or ""),
                    result_family(child),
                    result_mechanism(child),
                    result_shape(child),
                    *[str(item) for item in child.get("searchTags", []) if item],
                ]
            )
        ),
    }


def upsert_list_item(items: list[Any], item: dict[str, Any], key: str = "id") -> tuple[list[Any], bool]:
    replaced = False
    output: list[Any] = []
    item_id = str(item.get(key) or "")
    for existing in items:
        if isinstance(existing, dict) and item_id and str(existing.get(key) or "") == item_id:
            merged = dict(existing)
            merged.update(item)
            output.append(merged)
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(item)
    return output, replaced


def graph_node_from_card(card: dict[str, Any], card_path: Path | None = None) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "type": "attempt",
        "parent": card.get("parent") or card.get("basedOn"),
        "family": card.get("family"),
        "mechanism": card.get("mechanism"),
        "shape": card.get("shape"),
        "result": card.get("result"),
        "promotionCandidate": card.get("promotionCandidate"),
        "rankScore": card.get("rankScore"),
        "positiveDeltaKeys": card.get("positiveDeltaKeys", []),
        "reusableComponents": card.get("reusableComponents", []),
        "lesson": card.get("lesson", []),
        "summary": card.get("summary"),
        "failedDiff": card.get("failedDiffCandidate"),
        "cardPath": str(card_path) if card_path else "",
        "childResult": card.get("sourceChildResult"),
        "updatedAt": card.get("recordedAt"),
    }


def graph_edges_from_card(card: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    node_id = str(card.get("id") or "")
    parent = str(card.get("parent") or card.get("basedOn") or "")
    if node_id and parent:
        edges.append({"from": parent, "to": node_id, "kind": "parent-baseline"})
    for source in card.get("fusionOf", []):
        if node_id and source:
            edges.append({"from": str(source), "to": node_id, "kind": "fusion-source"})
    return edges


def fusion_candidates_from_nodes(nodes: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    useful = [
        node
        for node in nodes
        if isinstance(node, dict)
        and node.get("promotionCandidate") is not True
        and (
            node.get("positiveDeltaKeys")
            or node.get("reusableComponents")
            or str(node.get("result") or "").lower() in ("needs-more-evidence", "inconclusive", "rejected", "reject")
        )
    ]
    candidates: list[dict[str, Any]] = []
    for i, left in enumerate(useful):
        for right in useful[i + 1 :]:
            if left.get("id") == right.get("id"):
                continue
            if left.get("mechanism") == right.get("mechanism") and left.get("family") == right.get("family"):
                continue
            same_parent = bool(left.get("parent") and left.get("parent") == right.get("parent"))
            if not same_parent and len(candidates) >= limit:
                continue
            candidates.append(
                {
                    "sources": [left.get("id"), right.get("id")],
                    "families": [left.get("family"), right.get("family")],
                    "mechanisms": [left.get("mechanism"), right.get("mechanism")],
                    "parent": left.get("parent") if same_parent else "",
                    "reason": (
                        "Different mechanisms left reusable local evidence without promotion; test only as a named synergy "
                        "hypothesis with same-case component evidence, not as a blind bundle."
                    ),
                    "smallestDecisiveTest": "baseline vs A vs B vs A+B on one named case, with component deltas and rollback boundary",
                }
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def update_search_graph_from_card(root: Path, card: dict[str, Any], *, write: bool) -> dict[str, Any]:
    graph_path = search_graph_path(root)
    graph = load_or_default_search_graph(root)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    card_path = attempt_card_path(root, str(card.get("id") or "attempt"))
    node = graph_node_from_card(card, card_path)
    nodes, replaced_node = upsert_list_item([item for item in graph.get("nodes", []) if isinstance(item, dict)], node)
    edge_keys = {
        (str(edge.get("from")), str(edge.get("to")), str(edge.get("kind")))
        for edge in graph.get("edges", [])
        if isinstance(edge, dict)
    }
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    new_edges = []
    for edge in graph_edges_from_card(card):
        key = (str(edge.get("from")), str(edge.get("to")), str(edge.get("kind")))
        if key not in edge_keys:
            new_edges.append(edge)
            edge_keys.add(key)
    edges.extend(new_edges)
    graph.update(
        {
            "updatedAt": now,
            "nodes": nodes,
            "edges": edges,
            "fusionCandidates": fusion_candidates_from_nodes(nodes),
        }
    )
    if write:
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        attempt_cards_dir(root).mkdir(parents=True, exist_ok=True)
        atomic_write_json(card_path, card)
        with file_lock(graph_path):
            latest = load_or_default_search_graph(root)
            latest_nodes, _ = upsert_list_item(
                [item for item in latest.get("nodes", []) if isinstance(item, dict)],
                graph_node_from_card(card, card_path),
            )
            latest_edge_keys = {
                (str(edge.get("from")), str(edge.get("to")), str(edge.get("kind")))
                for edge in latest.get("edges", [])
                if isinstance(edge, dict)
            }
            latest_edges = [edge for edge in latest.get("edges", []) if isinstance(edge, dict)]
            for edge in graph_edges_from_card(card):
                key = (str(edge.get("from")), str(edge.get("to")), str(edge.get("kind")))
                if key not in latest_edge_keys:
                    latest_edges.append(edge)
                    latest_edge_keys.add(key)
            latest.update(
                {
                    "updatedAt": now,
                    "nodes": latest_nodes,
                    "edges": latest_edges,
                    "fusionCandidates": fusion_candidates_from_nodes(latest_nodes),
                }
            )
            atomic_write_json(graph_path, latest)
            graph = latest
    return {
        "graphPath": str(graph_path),
        "cardPath": str(card_path),
        "write": write,
        "nodeReplaced": replaced_node,
        "node": node,
        "fusionCandidates": graph.get("fusionCandidates", [])[:8],
    }


def attach_online_result_to_search_graph(root: Path, record: dict[str, Any], *, write: bool) -> dict[str, Any]:
    graph_path = search_graph_path(root)
    attempt = str(record.get("submitted_attempt") or record.get("baseline") or record.get("attempt") or "")
    if not attempt:
        return {"graphPath": str(graph_path), "write": write, "matched": False, "reason": "missing attempt id"}
    graph = load_or_default_search_graph(root)
    matched = False
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    online_result = {
        "onlineScore": record.get("online_score") or record.get("score") or record.get("onlineScore"),
        "deltaVsBest": record.get("online_delta_vs_best") or record.get("delta"),
        "actualDirection": record.get("actual_direction") or record.get("actual"),
        "calibrationResult": record.get("calibration_result"),
        "updatedAt": now,
        "sourceRecordId": record.get("id"),
    }
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if str(node.get("id") or "") == attempt or attempt in str(node.get("id") or ""):
            node["onlineResult"] = online_result
            node["updatedAt"] = now
            matched = True
            card_text = str(node.get("cardPath") or "")
            if write and card_text:
                card_path = Path(card_text)
                if card_path.exists():
                    try:
                        card = load_json(card_path)
                        if isinstance(card, dict):
                            card["onlineResult"] = online_result
                            card["recordedAt"] = now
                            atomic_write_json(card_path, card)
                    except Exception:
                        pass
    graph["updatedAt"] = now
    if write and matched:
        with file_lock(graph_path):
            atomic_write_json(graph_path, graph)
    return {"graphPath": str(graph_path), "write": write, "matched": matched, "attempt": attempt, "onlineResult": online_result}


def search_system_context(root: Path, *, limit: int = 8) -> dict[str, Any]:
    graph_path = search_graph_path(root)
    cards_dir = attempt_cards_dir(root)
    graph = load_or_default_search_graph(root)
    nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    recent_nodes = nodes[-limit:]
    return {
        "searchGraphPath": str(graph_path),
        "searchGraphExists": graph_path.exists(),
        "attemptCardsDir": str(cards_dir),
        "attemptCardsExists": cards_dir.exists(),
        "nodeCount": len(nodes),
        "edgeCount": len([item for item in graph.get("edges", []) if isinstance(item, dict)]),
        "recentNodes": recent_nodes,
        "fusionCandidates": graph.get("fusionCandidates") or fusion_candidates_from_nodes(nodes, limit=limit),
        "rule": "Search graph and attempt cards are always-on memory. They suggest revival/fusion/ablation; they never block bounded exploration by themselves.",
    }


def score_child(result: dict[str, Any], weights: dict[str, Any] | None = None) -> tuple[float, list[str], list[str]]:
    score = 0.0
    strengths: list[str] = []
    risks: list[str] = []
    weights = weights or {}
    affected_family = result_family(result)
    weight = family_weight(weights, affected_family)
    if affected_family != "unknown":
        strengths.append(f"family weight {affected_family}={weight:.2f}")
    mechanism = result_mechanism(result)
    mechanism_weight_value = mechanism_weight(weights, affected_family, mechanism)
    if mechanism != "unknown":
        strengths.append(f"mechanism weight {affected_family}/{mechanism}={mechanism_weight_value:.2f}")
        weight = (weight * 0.7) + (mechanism_weight_value * 0.3)
    shape = result_shape(result)
    shape_weight_value = shape_weight(weights, affected_family, mechanism, shape)
    if shape != "unknown":
        strengths.append(f"shape weight {affected_family}/{mechanism}/{shape}={shape_weight_value:.2f}")
        weight = (weight * 0.8) + (shape_weight_value * 0.2)
    if result.get("promotionCandidate") is True:
        score += 25
        strengths.append("worker marked promotionCandidate")
    elif result.get("promotionCandidate") is False:
        score -= 8
        risks.append("worker did not mark promotionCandidate")
    result_text = json.dumps(result, ensure_ascii=False).lower()
    risk_text = json.dumps(
        {
            "result": result.get("result"),
            "summary": result.get("summary"),
            "failureReason": result.get("failureReason"),
            "notableRegressions": result.get("notableRegressions"),
            "runtimeRisk": result.get("runtimeRisk"),
        },
        ensure_ascii=False,
    ).lower()
    if any(word in risk_text for word in ("timeout", "runtime risk", "risky", "over budget")):
        score -= 20
        risks.append("runtime risk")
    negative_deltas = [
        value
        for value in flatten_numbers(result.get("deltasVsBaseline", {})).values()
        if value < -1e-9
    ]
    text_regression = re.search(r"\b(regresses|regressed|catastrophic)\b", risk_text) is not None
    text_worse = re.search(r"(?<!non-)worse\b", risk_text) is not None
    if result.get("notableRegressions") or negative_deltas or text_regression or text_worse:
        score -= 12
        risks.append("regression mentioned")
    if "no-op" in result_text or "0 delta" in result_text or "flat" in result_text:
        score -= 6
        risks.append("flat/no-op evidence")
    for name in HIGH_VALUE_DELTAS:
        value = delta_from(result, name)
        if value is None:
            continue
        if value > 1e-9:
            score += 8 * (0.5 + weight)
            strengths.append(f"{name} positive")
        elif value < -1e-9:
            score -= 16 * (0.5 + weight)
            risks.append(f"{name} negative")
    for name in ("quickWeighted", "fullWeighted", "officialWeighted", "pdfstressWeighted"):
        value = delta_from(result, name)
        if value is None:
            continue
        if value > 1e-9:
            score += 2
        elif value < -1e-9:
            score -= 3
    return score, strengths, risks


def command_rank_children(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    weights = load_or_default_weights(project_root(args.project)) if args.project else {}
    missing, rows = rank_child_results(run_dir, weights)
    write_json({"runDir": str(run_dir), "missingChildResults": missing, "ranked": rows})
    return 0


def validate_child_result(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in CHILD_REQUIRED_FIELDS:
        if field not in result:
            errors.append(f"missing required field: {field}")
    for field in ("changedFiles", "checksRun", "notableRegressions"):
        if field in result and not isinstance(result[field], list):
            errors.append(f"{field} must be a list")
    for field in ("scores", "deltasVsBaseline"):
        if field in result and not isinstance(result[field], dict):
            errors.append(f"{field} must be an object")
    if "promotionCandidate" in result and not isinstance(result["promotionCandidate"], bool):
        errors.append("promotionCandidate must be boolean")
    if result.get("promotionCandidate") is True:
        checks = json.dumps(result.get("checksRun", []), ensure_ascii=False).lower()
        if "run_regression" not in checks:
            warnings.append("promotion candidate did not report run_regression")
        if "quick" not in checks and "full" not in checks:
            warnings.append("promotion candidate did not report quick/full benchmark")
        if not result.get("deltasVsBaseline"):
            errors.append("promotion candidate must include deltasVsBaseline")
        if not result.get("currentEvidence"):
            errors.append("promotion candidate must include currentEvidence")
    checks_text = json.dumps(result.get("checksRun", []), ensure_ascii=False).lower()
    if "--suite diagnostic-only" in checks_text or "suite diagnostic-only" in checks_text:
        errors.append("diagnostic-only is not a benchmark suite; remove benchmark.py --suite diagnostic-only")
    if not str(result.get("baselineSha256", "")):
        errors.append("baselineSha256 is empty")
    if not str(result.get("summary", "")).strip():
        errors.append("summary is empty")
    if "currentEvidence" in result and not isinstance(result["currentEvidence"], (list, dict, str)):
        errors.append("currentEvidence must be a list, object, or string")
    if "priorEvidence" in result and not isinstance(result["priorEvidence"], (list, dict, str)):
        errors.append("priorEvidence must be a list, object, or string")
    return errors, warnings


ARTIFACT_HINT_KEYS = (
    "artifact",
    "artifactpath",
    "artifactpaths",
    "artifacts",
    "generatedartifact",
    "generatedartifacts",
    "newartifact",
    "newartifacts",
    "report",
    "reportpath",
    "generator",
    "casefact",
    "casefacts",
    "generatedcasefact",
    "generatedcasefacts",
)


ARTIFACT_COUNT_KEYS = (
    "casecount",
    "checkedcases",
    "generatedcases",
    "enumeratedcases",
    "dominatedcountfound",
)


def collect_artifact_evidence(value: Any, *, parent_key: str = "") -> tuple[list[str], list[str]]:
    refs: list[str] = []
    facts: list[str] = []
    key_norm = re.sub(r"[^a-z0-9]", "", parent_key.lower())
    if isinstance(value, dict):
        for key, child in value.items():
            child_refs, child_facts = collect_artifact_evidence(child, parent_key=str(key))
            refs.extend(child_refs)
            facts.extend(child_facts)
    elif isinstance(value, list):
        for child in value:
            child_refs, child_facts = collect_artifact_evidence(child, parent_key=parent_key)
            refs.extend(child_refs)
            facts.extend(child_facts)
    elif isinstance(value, str):
        text = value.strip()
        if any(token in key_norm for token in ARTIFACT_HINT_KEYS):
            refs.append(text)
        elif any(suffix in text.lower() for suffix in (".py", ".json", ".md", ".txt", ".csv")):
            refs.append(text)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if any(token in key_norm for token in ARTIFACT_COUNT_KEYS) and float(value) >= 0:
            facts.append(f"{parent_key}={value}")
    return refs, facts


def artifact_path_exists(ref: str, workspace: Path | None) -> bool:
    text = ref.strip()
    if not text or "\n" in text or len(text) > 260:
        return False
    try:
        path = Path(text)
        if path.is_absolute():
            return path.exists()
        if workspace:
            return (workspace / path).exists()
    except OSError:
        return False
    return False


def new_artifact_evidence_status(result: dict[str, Any], lane: dict[str, Any]) -> tuple[bool, str]:
    workspace_text = str(lane.get("workspace") or "").strip()
    workspace = Path(workspace_text).resolve() if workspace_text else None
    refs: list[str] = []
    facts: list[str] = []
    for key in (
        "artifactPaths",
        "artifacts",
        "generatedArtifacts",
        "newArtifacts",
        "reports",
        "datasetCandidate",
        "currentEvidence",
        "evidenceNotes",
        "scores",
    ):
        child_refs, child_facts = collect_artifact_evidence(result.get(key), parent_key=key)
        refs.extend(child_refs)
        facts.extend(child_facts)
    refs = list(dict.fromkeys(ref for ref in refs if ref))
    facts = list(dict.fromkeys(fact for fact in facts if fact))
    existing = [ref for ref in refs if artifact_path_exists(ref, workspace)]
    result_text = json.dumps(result, ensure_ascii=False).lower()
    generated_text = any(token in result_text for token in ("generated", "enumeration", "enumerated", "checkedcases", "casecount"))
    ok = bool(existing) or (bool(refs) and generated_text) or (bool(facts) and generated_text)
    detail = (
        f"existing={existing[:4]}, refs={refs[:6]}, facts={facts[:6]}"
        if ok
        else "no artifactPaths/generatedArtifacts/currentEvidence artifact/report or generated-case evidence found"
    )
    return ok, detail


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;\n]", text) if part.strip()]


def candidate_id_slug(*parts: Any) -> str:
    raw = "-".join(str(part) for part in parts if str(part or "").strip())
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-_").lower()
    return slug[:80] or "dataset-candidate"


def load_or_default_dataset_ledger(root: Path) -> dict[str, Any]:
    path = dataset_evolution_path(root)
    if path.exists():
        data = load_json(path)
        if isinstance(data, dict):
            data.setdefault("version", 1)
            data.setdefault("updatedAt", None)
            data.setdefault("candidates", [])
            data.setdefault("promoted", [])
            data.setdefault("frozen", [])
            data.setdefault("history", [])
            return data
    return {
        "version": 1,
        "updatedAt": None,
        "purpose": "Track offline proxy dataset candidates derived from real online feedback before they become promotion gates.",
        "candidates": [],
        "promoted": [],
        "frozen": [],
        "history": [],
    }


def online_record_label(record: dict[str, Any]) -> str:
    return str(
        record.get("baseline")
        or record.get("submitted_attempt")
        or record.get("attempt")
        or record.get("id")
        or ""
    )


def online_record_matches(record: dict[str, Any], needle: str) -> bool:
    target = needle.lower()
    if not target:
        return False
    haystack = json.dumps(record, ensure_ascii=False).lower()
    return target in haystack


def find_online_feedback_record(ledger: dict[str, Any], attempt_or_id: str) -> dict[str, Any] | None:
    for record in reversed(ledger_online_evaluations(ledger)):
        if online_record_matches(record, attempt_or_id):
            return record
    return None


def latest_online_feedback_record(ledger: dict[str, Any]) -> dict[str, Any] | None:
    records = ledger_online_evaluations(ledger)
    return records[-1] if records else None


def dataset_candidate_schema_errors(candidate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in DATASET_CANDIDATE_REQUIRED_FIELDS:
        value = candidate.get(field)
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            errors.append(f"datasetCandidate missing required field: {field}")
    for field in ("explainsPositive", "rejectsNeutralOrNegative"):
        if field in candidate and not isinstance(candidate[field], list):
            errors.append(f"datasetCandidate.{field} must be a list")
    if "artifactPaths" in candidate and not isinstance(candidate["artifactPaths"], list):
        errors.append("datasetCandidate.artifactPaths must be a list")
    if "generatedCaseFacts" in candidate and not isinstance(candidate["generatedCaseFacts"], (list, dict, str)):
        errors.append("datasetCandidate.generatedCaseFacts must be a list, object, or string")
    return errors


def dataset_candidate_artifact_status(
    candidate: dict[str, Any],
    lane: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    workspace_text = str((lane or {}).get("workspace") or "").strip()
    workspace = Path(workspace_text).resolve() if workspace_text else None
    refs = normalize_string_list(candidate.get("artifactPaths"))
    refs.extend(normalize_string_list(candidate.get("generatedArtifacts")))
    refs.extend(normalize_string_list(candidate.get("reportPaths")))
    refs = list(dict.fromkeys(ref for ref in refs if ref))
    existing = [ref for ref in refs if artifact_path_exists(ref, workspace)]
    facts = normalize_string_list(candidate.get("generatedCaseFacts") or candidate.get("caseFacts"))
    case_count = as_float(candidate.get("caseCount") or candidate.get("generatedCaseCount"))
    has_generated_fact = bool(facts) or (case_count is not None and case_count > 0)
    ok = bool(existing) or (bool(refs) and has_generated_fact) or has_generated_fact
    if ok:
        return True, f"existing={existing[:4]}, refs={refs[:6]}, facts={facts[:6]}, caseCount={case_count}"
    return False, "no artifactPaths/reportPaths or generatedCaseFacts/caseCount found"


def dataset_candidate_from_child_result(result: dict[str, Any]) -> dict[str, Any] | None:
    candidate = result.get("datasetCandidate")
    if isinstance(candidate, dict):
        return candidate
    evidence = result.get("currentEvidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("datasetCandidate"), dict):
        return evidence["datasetCandidate"]
    notes = result.get("evidenceNotes")
    if isinstance(notes, dict) and isinstance(notes.get("datasetCandidate"), dict):
        return notes["datasetCandidate"]
    return None


def validate_dataset_candidate_against_online(
    candidate: dict[str, Any],
    online_evaluations: list[dict[str, Any]],
    *,
    strict: bool = False,
    lane: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors = dataset_candidate_schema_errors(candidate)
    warnings: list[str] = []
    explains = normalize_string_list(candidate.get("explainsPositive"))
    rejects = normalize_string_list(candidate.get("rejectsNeutralOrNegative"))
    artifact_ok, artifact_detail = dataset_candidate_artifact_status(candidate, lane)
    if strict and not artifact_ok:
        errors.append("datasetCandidate needs an auditable artifact path or generated case facts under strict validation")
    positives = [
        record
        for record in online_evaluations
        if str(record.get("actual_direction") or online_actual_from_delta(record.get("delta"), str(record.get("status", "")))) == "up"
    ]
    neutral_or_negative = [
        record
        for record in online_evaluations
        if str(record.get("actual_direction") or online_actual_from_delta(record.get("delta"), str(record.get("status", "")))) in ("neutral", "down")
    ]
    positive_matches = [
        online_record_label(record)
        for record in positives
        if any(online_record_matches(record, item) for item in explains)
    ]
    reject_matches = [
        online_record_label(record)
        for record in neutral_or_negative
        if any(online_record_matches(record, item) for item in rejects)
    ]
    if strict and positives and not positive_matches:
        warnings.append("datasetCandidate explainsPositive does not match any historical positive online record by text")
    if strict and neutral_or_negative and not reject_matches:
        warnings.append("datasetCandidate rejectsNeutralOrNegative does not match any historical neutral/down online record by text")
    status = "validated" if not errors else "needs-work"
    return {
        "status": status,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "artifactEvidence": {"ok": artifact_ok, "detail": artifact_detail},
        "historicalOnlineCoverage": {
            "positiveRecords": [online_record_label(record) for record in positives],
            "neutralOrNegativeRecords": [online_record_label(record) for record in neutral_or_negative],
            "explainedPositiveMatches": positive_matches,
            "rejectedNeutralOrNegativeMatches": reject_matches,
        },
    }


def find_dataset_candidate(dataset_ledger: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    for bucket in ("candidates", "promoted", "frozen"):
        for candidate in dataset_ledger.get(bucket, []):
            if isinstance(candidate, dict) and str(candidate.get("candidateId")) == candidate_id:
                return candidate
    return None


def upsert_dataset_candidate(dataset_ledger: dict[str, Any], candidate: dict[str, Any], *, force: bool = False) -> None:
    candidate_id = str(candidate.get("candidateId") or "")
    if not candidate_id:
        raise SystemExit("dataset candidate must include candidateId")
    existing = [
        item
        for item in dataset_ledger.get("candidates", [])
        if isinstance(item, dict) and str(item.get("candidateId")) == candidate_id
    ]
    if existing and not force:
        raise SystemExit(f"dataset candidate already exists: {candidate_id}; use --force to replace")
    if force and existing:
        dataset_ledger["candidates"] = [
            item
            for item in dataset_ledger.get("candidates", [])
            if not (isinstance(item, dict) and str(item.get("candidateId")) == candidate_id)
        ]
    dataset_ledger.setdefault("candidates", []).append(candidate)


def normalize_rel_path(value: Any) -> str:
    text = str(value).replace("\\", "/").strip()
    if not text:
        return ""
    try:
        path = Path(text)
        if path.is_absolute():
            parts = list(path.parts)
            if "src" in parts:
                idx = parts.index("src")
                return "/".join(parts[idx:])
            if "tools" in parts:
                idx = parts.index("tools")
                return "/".join(parts[idx:])
            if "tmp" in parts:
                idx = parts.index("tmp")
                return "/".join(parts[idx:])
        return text
    except Exception:  # noqa: BLE001
        return text


def lane_for_child_result(manifest: dict[str, Any], child_path: Path) -> dict[str, Any] | None:
    resolved = child_path.resolve()
    for lane in manifest.get("lanes", []):
        workspace = Path(str(lane.get("workspace", ""))).resolve()
        expected = workspace / "child_result.json"
        if resolved == expected.resolve() or workspace in resolved.parents:
            return lane
    return None


def command_tokens_for_suite(suite: str) -> list[str]:
    text = str(suite).strip().lower()
    if not text:
        return []
    tokens = {text, text.replace("_", " "), text.replace(" ", "_")}
    if text == "run_regression":
        tokens.add("run_regression")
    return sorted(token for token in tokens if token)


def child_has_first_kill_scorer_suite(result: dict[str, Any], lane: dict[str, Any], checks_text: str) -> bool:
    suite_tokens = {
        "online_fit_core",
        "large_sparse_forensics",
        "hidden_shape",
        "official_seed_sweep",
        "quick",
    }
    for suite in lane.get("commands", []):
        suite_text = str(suite).strip().lower()
        if not suite_text or suite_text in {"diagnostic-only", "run_regression"}:
            continue
        suite_tokens.update(command_tokens_for_suite(suite_text))
    for suite in result.get("scores", {}) if isinstance(result.get("scores", {}), dict) else {}:
        suite_tokens.update(command_tokens_for_suite(str(suite)))
    return any(token and token in checks_text for token in suite_tokens)


def child_based_on_matches_lane(result: dict[str, Any], lane: dict[str, Any], expected_sha: str) -> bool:
    child_based_on = result.get("basedOn")
    lane_based_on = str(lane.get("based_on") or "")
    if not child_based_on or not lane_based_on:
        return True
    if isinstance(child_based_on, dict):
        child_id = str(child_based_on.get("id") or child_based_on.get("baseline") or "")
        child_sha = str(child_based_on.get("sourceSha256") or child_based_on.get("sha256") or "").lower()
        if child_id != lane_based_on:
            return False
        return not expected_sha or not child_sha or child_sha == expected_sha
    return str(child_based_on) == lane_based_on


def stopped_for_missing_executable_target(result: dict[str, Any]) -> bool:
    if result.get("promotionCandidate") is True:
        return False
    result_text = str(result.get("result") or "").lower()
    if result_text not in {
        "needs-more-evidence",
        "proposal-only",
        "rejected",
        "reject",
        "inconclusive",
        "blocked",
        "blocked-by-missing-witness",
        "blocked-by-missing-target",
    }:
        return False
    evidence_text = json.dumps(
        {
            "summary": result.get("summary"),
            "avoidNextTime": result.get("avoidNextTime"),
            "currentEvidence": result.get("currentEvidence"),
            "evidenceNotes": result.get("evidenceNotes"),
            "architectureSummary": result.get("architectureSummary"),
            "blocker": result.get("blocker"),
        },
        ensure_ascii=False,
    ).lower()
    missing_words = ("missing", "no concrete", "not available", "not provided", "lacks", "without")
    target_words = ("witness", "target", "case", "artifact", "selector", "score-term", "scorer term")
    return any(word in evidence_text for word in missing_words) and any(word in evidence_text for word in target_words)


def non_promotional_learning_result(result: dict[str, Any]) -> bool:
    if result.get("promotionCandidate") is True:
        return False
    result_text = str(result.get("result") or "").lower()
    return result_text in {
        "needs-more-evidence",
        "proposal-only",
        "rejected",
        "reject",
        "inconclusive",
        "blocked",
        "blocked-by-missing-witness",
        "blocked-by-missing-target",
        "no-current-gradient",
    }


def counterfactual_witness_status(result: dict[str, Any], lane: dict[str, Any]) -> tuple[bool, str]:
    evidence = {
        "counterfactualWitnesses": result.get("counterfactualWitnesses"),
        "witnessSearchSummary": result.get("witnessSearchSummary"),
        "currentEvidence": result.get("currentEvidence"),
        "evidenceNotes": result.get("evidenceNotes"),
        "artifactPaths": result.get("artifactPaths"),
        "generatedArtifacts": result.get("generatedArtifacts"),
        "newArtifacts": result.get("newArtifacts"),
    }
    text = json.dumps(evidence, ensure_ascii=False).lower()
    has_witness_fields = all(
        token in text
        for token in ("case", "flow", "baseline", "alternative")
    ) and any(token in text for token in ("component", "phase_inner", "phasebetween", "phase_between", "max_global", "score"))
    has_empty_search = (
        ("attempted" in text or "searched" in text or "enumerated" in text)
        and any(token in text for token in ("no witness", "empty", "none improved", "0 witness", "zero witness"))
    )
    artifact_ok, artifact_detail = new_artifact_evidence_status(result, lane)
    if artifact_ok and (has_witness_fields or has_empty_search):
        return True, "counterfactual witness artifact/search summary present"
    return False, f"artifact_ok={artifact_ok}; witness_fields={has_witness_fields}; empty_search={has_empty_search}; {artifact_detail}"


def validate_child_against_lane(
    result: dict[str, Any],
    lane: dict[str, Any],
    *,
    strict: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected_sha = str(lane.get("baseline_sha256") or "").lower()
    observed_sha = str(result.get("baselineSha256") or "").lower()
    if expected_sha and observed_sha and expected_sha != observed_sha:
        errors.append(f"baselineSha256 mismatch: expected {expected_sha}, got {observed_sha}")
    if str(result.get("basedOn", "")) and str(lane.get("based_on", "")):
        if not child_based_on_matches_lane(result, lane, expected_sha):
            warnings.append(f"basedOn differs from lane: lane={lane.get('based_on')} child={result.get('basedOn')}")
    allowed = [normalize_rel_path(item) for item in lane.get("allowed_files", [])]
    changed = [normalize_rel_path(item) for item in result.get("changedFiles", [])]
    if allowed and "tmp diagnostics" not in allowed:
        allowed_src = [item for item in allowed if item and item not in ("none", "proposal-only")]
        for item in changed:
            if not item:
                continue
            if item == "child_result.json" or item.endswith("/child_result.json"):
                continue
            if not any(item == allowed_item or item.startswith(f"{allowed_item}/") for allowed_item in allowed_src):
                errors.append(f"changed file outside lane scope: {item}")
    checks_text = json.dumps(result.get("checksRun", []), ensure_ascii=False).lower()
    if "--suite diagnostic-only" in checks_text or "suite diagnostic-only" in checks_text:
        errors.append("diagnostic-only is a lane mode, not a benchmark suite")
    if not controlled_risk_lane(lane) and not architecture_breakout_lane(lane):
        missing_suites: list[str] = []
        for suite in lane.get("commands", []):
            if str(suite) == "diagnostic-only":
                continue
            tokens = command_tokens_for_suite(str(suite))
            if tokens and not any(token in checks_text for token in tokens):
                missing_suites.append(str(suite))
        if missing_suites:
            message = f"missing required lane checks: {missing_suites}"
            if strict or result.get("promotionCandidate") is True:
                errors.append(message)
            else:
                warnings.append(message)
    current_evidence = result.get("currentEvidence")
    evidence_notes = result.get("evidenceNotes", {}) if isinstance(result.get("evidenceNotes", {}), dict) else {}
    decisive_result = evidence_notes.get("smallestDecisiveTestResult")
    if strict and lane.get("smallestDecisiveTest") and not current_evidence and not decisive_result:
        errors.append("missing currentEvidence/smallestDecisiveTestResult for expert lane")
    if not current_evidence and result.get("priorEvidence"):
        result_text = str(result.get("result", "")).lower()
        if result.get("promotionCandidate") is True:
            errors.append("promotionCandidate cannot rely only on priorEvidence without currentEvidence")
        elif result_text not in ("proposal-only", "rejected", "reject", "inconclusive"):
            warnings.append("result relies on priorEvidence without currentEvidence; should be proposal-only/rejected/inconclusive")
    budget = result.get("budgetUsed", {})
    if budget and not isinstance(budget, (dict, int, float, str)):
        errors.append("budgetUsed must be an object, number, or string")
    if result.get("budgetExceeded") is True and str(result.get("result", "")).lower() not in ("proposal-only", "rejected", "reject", "inconclusive"):
        warnings.append("budgetExceeded=true should normally close as proposal-only/rejected/inconclusive")
    if bool(lane.get("requiresNewArtifact")):
        artifact_ok, artifact_detail = new_artifact_evidence_status(result, lane)
        if not artifact_ok:
            if non_promotional_learning_result(result):
                warnings.append(
                    "requiresNewArtifact lane produced no auditable artifact; accepted only as negative/proposal learning evidence"
                )
            else:
                errors.append(
                    "requiresNewArtifact lane did not provide auditable new artifact evidence; "
                    "include artifactPaths/generatedArtifacts/newArtifacts or currentEvidence artifact/report entries"
                )
    if bool(lane.get("requiresCounterfactualWitness")):
        witness_ok, witness_detail = counterfactual_witness_status(result, lane)
        if not witness_ok:
            if non_promotional_learning_result(result):
                warnings.append(
                    "counterfactual-witness lane produced no strict witness/empty-search proof; accepted only as negative/proposal learning evidence; "
                    f"{witness_detail}"
                )
            else:
                errors.append(
                    "counterfactual-witness lane must provide exact witness evidence or a bounded empty-search proof "
                    f"(case/flow/baselinePort/alternativePort/componentDeltas); {witness_detail}"
                )
    if bool(lane.get("requiresDatasetCandidate") or lane.get("datasetEvolutionLane")):
        dataset_candidate = dataset_candidate_from_child_result(result)
        if not dataset_candidate:
            if non_promotional_learning_result(result):
                warnings.append(
                    "dataset-evolution lane produced no datasetCandidate; accepted only as diagnostic/no-progress learning evidence"
                )
            else:
                errors.append(
                    "dataset-evolution lane requires datasetCandidate with candidateId, sourceOnlineFeedback, "
                    "caseFamily, caseShape, explainsPositive, rejectsNeutralOrNegative, and promotionGateImpact"
                )
        else:
            candidate_errors = dataset_candidate_schema_errors(dataset_candidate)
            errors.extend(candidate_errors)
            if strict:
                artifact_ok, artifact_detail = dataset_candidate_artifact_status(dataset_candidate, lane)
                if not artifact_ok:
                    errors.append(f"datasetCandidate lacks auditable generated/proxy evidence: {artifact_detail}")
    if bool(lane.get("requiresMutationAttempt")):
        changed = [normalize_rel_path(item) for item in result.get("changedFiles", [])]
        mutation_attempted = result.get("mutationAttempted") is True or any(item == "src/Solution.cpp" for item in changed)
        if not mutation_attempted:
            errors.append("controlled-risk lane requires mutationAttempted=true or changedFiles including src/Solution.cpp")
        attempt_detail = result.get("attemptedDiffSummary") or result.get("mutationSummary") or result.get("currentEvidence")
        if not attempt_detail:
            errors.append("controlled-risk lane requires attemptedDiffSummary/mutationSummary/currentEvidence describing the mutation")
        if strict:
            has_compile_check = "g++" in checks_text or "compile" in checks_text
            has_first_kill_suite = child_has_first_kill_scorer_suite(result, lane, checks_text)
            failure_text = json.dumps(
                {
                    "result": result.get("result"),
                    "summary": result.get("summary"),
                    "currentEvidence": result.get("currentEvidence"),
                    "evidenceNotes": result.get("evidenceNotes"),
                    "notableRegressions": result.get("notableRegressions"),
                },
                ensure_ascii=False,
            ).lower()
            compile_failed = "compile fail" in failure_text or "compilation fail" in failure_text
            if not has_compile_check:
                errors.append("controlled-risk lane requires a compile check in checksRun")
            if not has_first_kill_suite and not compile_failed:
                errors.append("controlled-risk lane requires one first-kill scorer suite unless the mutation failed to compile")
    if online_confirmed_exploit_lane(lane):
        evidence_text = json.dumps(
            {
                "checksRun": result.get("checksRun"),
                "currentEvidence": result.get("currentEvidence"),
                "evidenceNotes": result.get("evidenceNotes"),
                "summary": result.get("summary"),
                "deltasVsBaseline": result.get("deltasVsBaseline"),
            },
            ensure_ascii=False,
        ).lower()
        if not any(token in evidence_text for token in ("forensic", "comparator", "probe", "target case", "conflict")):
            errors.append("044-style exploit lane requires forensic/probe/comparator evidence before patch")
        if result.get("promotionCandidate") is True and not result.get("deltasVsBaseline"):
            errors.append("044-style exploit promotionCandidate requires measurable deltasVsBaseline")
    if bool(lane.get("requiresArchitectureAttempt") or lane.get("architectureBreakoutLane")):
        changed = [normalize_rel_path(item) for item in result.get("changedFiles", [])]
        architecture_attempted = result.get("architectureAttempted") is True or any(item == "src/Solution.cpp" for item in changed)
        missing_executable_target = stopped_for_missing_executable_target(result)
        if not architecture_attempted:
            if missing_executable_target:
                warnings.append("architecture-breakout lane stopped before edit because no executable witness/target artifact was available")
            else:
                errors.append("architecture-breakout lane requires architectureAttempted=true or changedFiles including src/Solution.cpp")
        architecture_detail = (
            result.get("architectureSummary")
            or result.get("attemptedDiffSummary")
            or result.get("mutationSummary")
            or result.get("currentEvidence")
        )
        if not architecture_detail:
            errors.append("architecture-breakout lane requires architectureSummary/attemptedDiffSummary/currentEvidence")
        if strict:
            has_compile_check = "g++" in checks_text or "compile" in checks_text
            has_first_kill_suite = child_has_first_kill_scorer_suite(result, lane, checks_text)
            if architecture_attempted and not has_compile_check:
                errors.append("architecture-breakout lane requires a compile check in checksRun")
            if architecture_attempted and not has_first_kill_suite:
                errors.append("architecture-breakout lane requires at least one first-kill scorer suite in checksRun")
            if not architecture_attempted and missing_executable_target and (has_compile_check or has_first_kill_suite):
                warnings.append("architecture-breakout lane reported missing executable target but still ran edit-stage checks")
    return errors, warnings


def command_validate_child(args: argparse.Namespace) -> int:
    path = Path(args.child_result).resolve()
    result = load_json(path)
    errors, warnings = validate_child_result(result)
    lane: dict[str, Any] | None = None
    if args.run_dir:
        manifest = load_or_infer_epoch_manifest(Path(args.run_dir).resolve())
        lane = lane_for_child_result(manifest, path)
        if lane is None:
            errors.append("child_result does not belong to any lane in epoch manifest")
        else:
            lane_errors, lane_warnings = validate_child_against_lane(result, lane, strict=args.strict)
            errors.extend(lane_errors)
            warnings.extend(lane_warnings)
    output = {
        "childResult": str(path),
        "valid": not errors,
        "project": str(project_root(args.project)) if getattr(args, "project", None) else "",
        "lane": lane.get("lane") if lane else None,
        "errors": errors,
        "warnings": warnings,
        "requiredFields": list(CHILD_REQUIRED_FIELDS),
    }
    write_json(output)
    return 0 if not errors else 1


def failure_counts(ledger: dict[str, Any]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for record in ledger_records(ledger):
        if record.get("_bucket") != "failedExperiments":
            continue
        fp = fingerprint(record, default_based_on=str(ledger.get("currentBaseline", {}).get("id", "")))
        key = (fp.get("affected_family", "unknown"), fp.get("changed_mechanism", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def command_suggest_lanes(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    current_id = str(baseline.get("id", ""))
    scores = baseline.get("scores", {})
    counts = failure_counts(ledger)
    suggestions: list[dict[str, Any]] = []

    def add(lane: str, state: str, family: str, mechanism: str, hypothesis: str, reason: str, budget: str) -> None:
        if counts.get((family, mechanism), 0) >= args.max_prior_failures:
            suggestions.append(
                {
                    "lane": lane,
                    "direction_state": "freeze",
                    "affected_family": family,
                    "changed_mechanism": mechanism,
                    "hypothesis": hypothesis,
                    "reason": f"frozen: {counts[(family, mechanism)]} prior failures with same family/mechanism",
                    "budget": "stop",
                    "based_on": current_id,
                }
            )
            return
        suggestions.append(
            {
                "lane": lane,
                "direction_state": state,
                "affected_family": family,
                "changed_mechanism": mechanism,
                "hypothesis": hypothesis,
                "reason": reason,
                "budget": budget,
                "based_on": current_id,
            }
        )

    best_online = scores.get("bestKnownOnlineBaseline")
    if best_online and best_online != current_id:
        add(
            "benchmark-alignment",
            "diagnose",
            "online_fit_core",
            "benchmark",
            "Explain why local active baseline differs from best-known online and identify the smallest offline suite gap.",
            "local active baseline is not best-known online",
            "medium",
        )
    add(
        "large-sparse-target-forensics",
        "diagnose",
        "large_sparse",
        "benchmark",
        "Find a named residual target before widening large-sparse repair.",
        "large-sparse is online-important but widening without target has caused no-op/runtime risk",
        "medium",
    )
    add(
        "leaf-band-guard-audit",
        "diagnose",
        "leaf_band",
        "guard",
        "Audit positive and negative leaf-band seeds before more paired-swap guard edits.",
        "leaf-band proxy gains are fragile and can regress online_fit_core",
        "low",
    )
    add(
        "capacity-shadow-micro-selector",
        "explore",
        "capacity_shadow",
        "guard",
        "Try one selector-only capacity-shadow hypothesis with explicit online_fit_core non-regression.",
        "capacity-shadow has online-aligned history but selector no-ops are common",
        "low",
    )
    add(
        "runtime-headroom",
        "explore",
        "runtime",
        "runtime_slim",
        "Reduce overhead without changing scores to create headroom for future repair.",
        "prior runtime-slim support successfully reduced source/overhead while preserving behavior",
        "medium",
    )
    write_json({"currentBaseline": current_id, "suggestions": suggestions})
    return 0


EXPERT_PANEL_ROLES: tuple[dict[str, Any], ...] = (
    {
        "role": "Online Forensics Expert",
        "quota": 1,
        "mandate": "Infer hidden dataset distribution from online positive, neutral, and negative feedback.",
    },
    {
        "role": "Algorithm Mechanism Expert",
        "quota": 1,
        "mandate": "Propose new single-cause mechanisms beyond guard widening and threshold tweaks.",
    },
    {
        "role": "Benchmark/Data Generator Expert",
        "quota": 1,
        "mandate": "Create proxy cases that explain online feedback rather than merely improving existing suites.",
    },
    {
        "role": "Dataset Evolution Expert",
        "quota": 1,
        "mandate": "Turn online feedback into validated offline dataset candidates, then promote or freeze them.",
    },
    {
        "role": "Counterfactual Debugger",
        "quota": 1,
        "mandate": "Audit current solver decision points by replaying second-best or rejected choices.",
    },
    {
        "role": "Risk/Runtime Gatekeeper",
        "quota": 1,
        "mandate": "Define kill conditions, runtime limits, and duplicate guards before worker time is spent.",
    },
    {
        "role": "Exploit Strategist",
        "quota": 1,
        "mandate": "Extract the smallest safe extension from online-confirmed positive signals.",
    },
)

STAGNATION_REPEATED_LANES = {
    "online_discriminator-positive_vs_neutral",
    "hidden_proxy_generator-online_neutral_decoys",
    "risk_gatekeeper-duplicate_and_runtime_filter",
    "exploit_strategist-minimal_confirmed_signal_extension",
}


STAGNATION_BAD_RESULT_TOKENS = (
    "reject",
    "needs-more-evidence",
    "proposal-only",
    "flat",
    "no-op",
    "not-dispatched",
    "blocked",
    "inconclusive",
)


STAGNATION_BREAKOUT_ROLES: tuple[dict[str, Any], ...] = (
    {
        "role": "Adversarial Proxy Builder",
        "quota": 1,
        "mandate": "Create new PDF-legal adversarial cases or a generator; do not only audit existing suites.",
    },
    {
        "role": "Small Exhaustive Enumerator",
        "quota": 1,
        "mandate": "Use tiny brute force/enumeration to find solver choices that are dominated under the official scorer.",
    },
    {
        "role": "Mechanism Breakout Expert",
        "quota": 1,
        "mandate": "Explore a mechanism outside the baseline-044 residual guard envelope.",
    },
    {
        "role": "Promotion Candidate Revalidator",
        "quota": 1,
        "mandate": "Re-open exactly one prior tiny positive candidate and require full parent-gate evidence before promotion.",
    },
)


VALIDATION_DOCTRINE: dict[str, Any] = {
    "name": "grandmaster-validation-doctrine",
    "principle": (
        "Trust validation only after making validation trustworthy. Treat online score as an expensive, sparse, noisy "
        "extra validation fold that calibrates local folds; do not treat local score or online score as an oracle."
    ),
    "validationHierarchy": [
        "same-case mechanism/component-delta witness",
        "offline fold with historical online-transfer evidence",
        "negative-control fold built from online-neutral/down shapes",
        "online fold feedback used for calibration and dataset evolution",
    ],
    "candidateRequirements": [
        "name the validation thesis before promotion",
        "state which local fold should predict online movement",
        "cite online-positive records preserved and neutral/down records rejected",
        "state the falsifier that would downgrade this local evidence",
    ],
    "onlineFoldRule": (
        "One online result updates trust for the tested family/mechanism/shape. It does not license broad variants, "
        "and it does not erase a plausible mechanism outside the tested shape."
    ),
    "stagnationRule": (
        "When local gains stop transferring, spend work on validation repair, negative controls, counterfactual witnesses, "
        "or a bounded architecture sidecar instead of more proxy-score hill climbing."
    ),
}


ARCHITECTURE_BREAKOUT_ROLES: tuple[dict[str, Any], ...] = (
    {
        "role": "Architecture Inventor",
        "quota": 2,
        "mandate": "Invent solver-level alternatives, not another guard or threshold tweak; each idea must name the scoring objective it changes.",
    },
    {
        "role": "Search Policy Hacker",
        "quota": 1,
        "mandate": "Try a different candidate-generation/search policy such as beam, regret, shadow assignment, or rollback frontier.",
    },
    {
        "role": "Scorer Surrogate Builder",
        "quota": 1,
        "mandate": "Build a lightweight local objective/surrogate that can guide risky architecture experiments faster than full suites.",
    },
    {
        "role": "Moonshot Architect",
        "quota": 1,
        "mandate": "Propose one high-variance architecture rewrite with a hard rollback boundary and a first-kill scorer.",
    },
)


def divergent_expert_ideas(
    current_id: str,
    online_items: list[dict[str, Any]],
    experience_context: dict[str, Any],
    stagnation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate non-template concept-collision ideas before portfolio selection.

    These are deliberately more specific than the standard mutation-template lanes.
    The coordinator still converges with duplicate checks, stop conditions, and
    first-kill tests, but the candidate pool should not be dominated by recurring
    lane templates.
    """

    positive_records = [
        str(item.get("attempt") or item.get("shape") or "")
        for item in online_items
        if item.get("actual") == "up"
    ]
    neutral_records = [
        str(item.get("attempt") or item.get("shape") or "")
        for item in online_items
        if item.get("actual") in ("neutral", "down")
    ]
    positive_anchor = ", ".join(item for item in positive_records[-2:] if item) or "baseline-036/044 online-positive residual core"
    neutral_anchor = ", ".join(item for item in neutral_records[-4:] if item) or "post-044 neutral decoys"
    recent_failed = experience_context.get("failedLessons", []) if isinstance(experience_context, dict) else []
    recent_success = experience_context.get("successfulLessons", []) if isinstance(experience_context, dict) else []
    failed_hint = str((recent_failed[-1] or {}).get("avoidNextTime") if recent_failed else "")[:260]
    success_hint = str((recent_success[-1] or {}).get("summary") if recent_success else "")[:260]
    forbidden_reuse = stagnation.get("forbiddenReuse", []) if isinstance(stagnation, dict) else []

    common = {
        "origin": "freeform-concept-collision",
        "freeformDivergence": True,
        "stagnationLane": bool(isinstance(stagnation, dict) and stagnation.get("active")),
        "based_on": current_id,
        "forbiddenReuse": forbidden_reuse,
        "requiredContext": [
            "docs/optimization-ledger.json onlineEvaluations",
            "docs/exploration-index.json recent worker lessons",
            "docs/online-offline-weights.json family/mechanism weights",
            "docs/official-pdf-rules.md legality constraints",
            "current src/Solution.cpp decision point relevant to the lane",
        ],
    }

    ideas = [
        {
            **common,
            "expertRole": "Counterfactual Census Lead",
            "lane": "diverge_residual_envelope-counterfactual_census",
            "direction_state": "diagnose",
            "affected_family": "large_sparse",
            "changed_mechanism": "residual_envelope_counterfactual_census",
            "hidden_shape": "phase6_flow4096_same_case_port_move",
            "hypothesis": (
                "Turn the repeated 'missing witness' blocker into an executable census: enumerate exact same-case "
                "baseline ports, alternative ports, and scorer-component deltas inside the baseline-044 residual envelope."
            ),
            "conceptCollision": [
                "baseline-044 online-positive phase6 residual envelope",
                "post-044 neutral branches failed without same-case movement",
                "counterfactual replay before solver mutation",
            ],
            "whyNow": (
                "Recent epochs repeatedly stopped at missing exact comparator evidence. The next useful gradient is not another "
                "proposal; it is a concrete witness table naming case/flow/baseline-port/alternative-port/component deltas."
            ),
            "smallestDecisiveTest": (
                "For one PDF-legal phase6/flow4096 case, inspect 20-80 candidate flows and emit a table with baseline port, "
                "one or more legal alternative ports, phase_inner, phase_between, job_between, max_single, max_global, score delta, "
                "and legality/runtime notes."
            ),
            "killCondition": (
                "Reject as no-current-gradient if no legal alternative port improves any target component without worsening "
                "phase_inner/phase_between/job_between/max load; otherwise output the best 3 counterfactual witnesses for Phase B."
            ),
            "expectedArtifact": "residual_envelope_counterfactual_census.json plus a short witness summary",
            "workerType": "diagnostic",
            "noveltyClass": "counterfactual_census",
            "attackTrack": "witness-main",
            "attackThesisRole": "find same-case scorer-moving witnesses before any solver edit",
            "requiresNewArtifact": True,
            "requiresCounterfactualWitness": True,
            "counterfactualWitnessSchema": [
                "caseId",
                "flowId",
                "baselinePort",
                "alternativePort",
                "componentDeltas.phase_inner",
                "componentDeltas.phase_between",
                "componentDeltas.job_between",
                "componentDeltas.max_single",
                "componentDeltas.max_global",
                "scoreDelta",
                "legality",
            ],
            "commands": ["diagnostic-only"],
        },
        {
            **common,
            "expertRole": "Phase Residue Mechanism Inventor",
            "lane": "diverge_phase_residue-alternating_cycle_oracle",
            "direction_state": "diagnose",
            "affected_family": "large_sparse",
            "changed_mechanism": "phase_residue_alternating_cycle",
            "hidden_shape": "phase6_flow4096_in_envelope_residue",
            "hypothesis": (
                "After baseline-044 residual repair has cleared phase_inner, remaining phase residue may need an alternating-cycle "
                "move across two or three sources instead of another guard or source-transition preference."
            ),
            "conceptCollision": [
                "baseline-044 online-positive residual envelope",
                "matching/augmenting-path style local repair",
                "phase_between residue rather than phase_inner",
            ],
            "whyNow": f"Positive anchor: {positive_anchor}. Neutral controls to avoid: {neutral_anchor}.",
            "smallestDecisiveTest": (
                "On one named phase6 flow4096 seed such as 9349 or 9377, materialize a same-case comparator that tries a bounded "
                "alternating cycle and reports phase_inner, phase_between, job_between, max_single, max_global, emitted-port diffs, and score delta."
            ),
            "killCondition": "Reject if the cycle is score-flat, worsens phase_inner/job/load, or only recreates source-transition smoothing.",
            "expectedArtifact": "phase_residue_cycle_oracle_report.json with same-case component deltas",
            "workerType": "diagnostic",
            "noveltyClass": "phase_residue_oracle",
            "attackTrack": "witness-main",
            "attackThesisRole": "test a multi-flow witness mechanism inside the same residual envelope",
            "requiresNewArtifact": True,
            "requiresCounterfactualWitness": True,
            "commands": ["diagnostic-only"],
        },
        {
            **common,
            "expertRole": "Local Search Architect",
            "lane": "diverge_repair_operator-regret_shadow_price",
            "direction_state": "explore",
            "affected_family": "large_sparse",
            "changed_mechanism": "regret_shadow_price_repair",
            "hidden_shape": "in_envelope_load_phase_tradeoff",
            "hypothesis": (
                "Replace a binary residual accept/reject decision with a tiny shadow-price regret term: accept a move only when "
                "phase residue falls and projected load shadow prices are non-worse."
            ),
            "conceptCollision": [
                "official scorer has 80% load terms",
                "residual repair success was phase-local",
                "post-044 selector gains were neutral unless tied to load-safe scorer movement",
            ],
            "whyNow": f"Recent success hint: {success_hint or positive_anchor}",
            "smallestDecisiveTest": (
                "Patch exactly one candidate ranking/acceptance point in the isolated workspace, compile once, and run large_sparse_forensics "
                "as first-kill. Continue only if the target suite improves without online_fit_core collapse."
            ),
            "killCondition": "Reject and revert if large_sparse_forensics is flat/worse, online_fit_core collapses, or the diff becomes a broad blended frontier.",
            "expectedArtifact": "one regret-shadow-price patch plus first-kill scorer result",
            "workerType": "edit",
            "noveltyClass": "regret_shadow_price",
            "attackTrack": "risk-sidecar",
            "attackThesisRole": "run one bounded architecture/mutation probe while the witness track searches",
            "architectureBreakoutLane": True,
            "requiresArchitectureAttempt": True,
            "riskLevel": "R2",
            "architectureBudget": "one candidate-ranking hook; one first-kill suite before any broad gate",
            "commands": ["large_sparse_forensics", "online_fit_core"],
        },
        {
            **common,
            "expertRole": "Combination Theorist",
            "lane": "diverge_combination-neutral_components_synergy_test",
            "direction_state": "diagnose",
            "affected_family": "combination_search",
            "changed_mechanism": "neutral_component_synergy",
            "hidden_shape": "post044_neutral_components_with_positive_core",
            "hypothesis": (
                "Some online-neutral local components may be useful only when paired with the online-positive residual core; test synergy as "
                "same-case component movement, not as a blind bundle."
            ),
            "conceptCollision": [
                "baseline-049/050/051 were neutral alone",
                "baseline-044 core is positive",
                "same-case witness can distinguish synergy from noisy stacking",
            ],
            "whyNow": "The user explicitly asked whether non-improving optimizations might combine into a real gain.",
            "smallestDecisiveTest": (
                "Build a matrix over one target case: baseline, component A, component B, and A+B. Report whether A+B moves a scorer component "
                "that neither component moves alone, with phase_inner/job/max load non-worse."
            ),
            "killCondition": "Reject if A+B is just the max of individual neutral effects, if it lacks same-case evidence, or if it stacks known neutral decoys blindly.",
            "expectedArtifact": "neutral_component_synergy_matrix.json",
            "workerType": "diagnostic",
            "noveltyClass": "combination_synergy",
            "attackTrack": "witness-support",
            "attackThesisRole": "test whether neutral components combine only when same-case components move",
            "requiresNewArtifact": True,
            "commands": ["diagnostic-only"],
        },
        {
            **common,
            "expertRole": "Counterexample Miner",
            "lane": "diverge_pdflegal_microcase-metamorphic_generator",
            "direction_state": "diagnose",
            "affected_family": "hidden_dataset_fit",
            "changed_mechanism": "metamorphic_case_generator",
            "hidden_shape": "pdflegal_phase_residue_counterexamples",
            "hypothesis": (
                "Instead of another fixed suite, generate metamorphic PDF-legal sibling cases that preserve the 044 core but mutate one causal axis "
                "at a time: source overlap, destination overlap, per-port tail, and phase adjacency."
            ),
            "conceptCollision": [
                "PDF legality constraints",
                "online-positive vs neutral branch ranking",
                "metamorphic testing for one-causal-axis changes",
            ],
            "whyNow": "The offline suite needs dynamic evolution that explains why local positives stopped transferring.",
            "smallestDecisiveTest": (
                "Produce 3-5 PDF-legal sibling case descriptions or generated files, each naming the one causal axis changed and the expected "
                "baseline-044 vs neutral-decoy ranking."
            ),
            "killCondition": "Reject if cases are repeat-heavy, non-PDF-legal, or only replay phase7/job28/job32/jobs22 neutral boundaries.",
            "expectedArtifact": "metamorphic_phase_residue_cases.json",
            "workerType": "diagnostic",
            "noveltyClass": "metamorphic_dataset",
            "attackTrack": "witness-support",
            "attackThesisRole": "supply PDF-legal sibling cases for the witness census",
            "requiresNewArtifact": True,
            "commands": ["diagnostic-only"],
        },
        {
            **common,
            "expertRole": "Scorer Surrogate Builder",
            "lane": "diverge_fast_surrogate-component_delta_trace",
            "direction_state": "diagnose",
            "affected_family": "scorer_surrogate",
            "changed_mechanism": "component_delta_trace",
            "hidden_shape": "fast_first_kill_proxy",
            "hypothesis": (
                "Iteration is slow because broad suites are used too early; create a tiny component-delta trace that can kill flat ideas before "
                "full online_fit_core or large_sparse_forensics runs."
            ),
            "conceptCollision": [
                "slow offline loops",
                "component-level scorer movement",
                "worker first-kill budget",
            ],
            "whyNow": "Recent epochs spent time proving flatness late; a sharper first-kill proxy can make risk-taking cheaper.",
            "smallestDecisiveTest": (
                "Write a report or script sketch that extracts component deltas for one named case and defines the pass/fail threshold for edit lanes."
            ),
            "killCondition": "Reject if it only recommends running existing broad suites or cannot name the scorer components it will trace.",
            "expectedArtifact": "component_delta_trace_plan.json or tiny script/report",
            "workerType": "diagnostic",
            "noveltyClass": "fast_surrogate",
            "attackTrack": "witness-support",
            "attackThesisRole": "make counterfactual witnesses cheap to score before broad suites",
            "requiresNewArtifact": True,
            "commands": ["diagnostic-only"],
        },
        {
            **common,
            "expertRole": "Negative Space Strategist",
            "lane": "diverge_negative_space-online_neutral_inversion",
            "direction_state": "diagnose",
            "affected_family": "strategy_pivot",
            "changed_mechanism": "neutral_inversion",
            "hidden_shape": "what_044_does_not_change",
            "hypothesis": (
                "Look at what neutral branches changed that 044 did not need, then invert that: search for a feature 044 changed and all neutral "
                "branches failed to change, rather than optimizing the same local score."
            ),
            "conceptCollision": [
                "online feedback inversion",
                "negative controls",
                "causal feature search rather than benchmark score chase",
            ],
            "whyNow": f"Failed/frozen hint to avoid: {failed_hint or neutral_anchor}",
            "smallestDecisiveTest": (
                "Produce a table with at least four post-044 attempts, the feature they changed, whether 044 changed it, and one new non-template lane implied by the inversion."
            ),
            "killCondition": "Reject if it only repeats the promoted post044 contrast dataset or cannot produce a new executable lane.",
            "expectedArtifact": "online_neutral_inversion_table.json plus one lane proposal",
            "workerType": "diagnostic",
            "noveltyClass": "negative_space_strategy",
            "attackTrack": "thesis-support",
            "attackThesisRole": "keep the thesis pointed away from known online-neutral changes",
            "requiresNewArtifact": True,
            "commands": ["diagnostic-only"],
        },
    ]
    return ideas


def cross_branch_fusion_ideas(
    current_id: str,
    search_system: dict[str, Any],
    stagnation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for idx, candidate in enumerate(search_system.get("fusionCandidates", [])[:3], start=1):
        sources = [str(item) for item in candidate.get("sources", []) if item]
        if len(sources) < 2:
            continue
        mechanisms = [str(item) for item in candidate.get("mechanisms", []) if item]
        ideas.append(
            {
                "origin": "search-graph-fusion",
                "freeformDivergence": True,
                "expertRole": "Cross-Branch Fusion Strategist",
                "lane": f"search_graph_fusion-{idx}-{'-'.join(safe_artifact_id(item)[:18] for item in sources)}",
                "direction_state": "diagnose",
                "affected_family": "cross_branch_fusion",
                "changed_mechanism": "synergy_matrix",
                "hidden_shape": "two_component_interaction",
                "based_on": current_id,
                "hypothesis": (
                    f"Test whether two non-promoted branches ({', '.join(sources)}) interact positively. "
                    "This is not a bundle proposal until same-case component evidence proves synergy."
                ),
                "conceptCollision": [
                    "AIDE/MLEvolve branch search",
                    "post-044 neutral components may combine only with component evidence",
                    "Kaggle-style ensemble discipline without blind stacking",
                ],
                "whyNow": candidate.get("reason") or "Search graph found reusable non-promoted evidence from different mechanisms.",
                "fusionSources": sources,
                "smallestDecisiveTest": candidate.get("smallestDecisiveTest")
                or "baseline vs A vs B vs A+B on one named case, with component deltas and rollback boundary",
                "killCondition": (
                    "Reject if A+B lacks same-case component movement beyond A and B, worsens a high-weight component, "
                    "or requires bundling broad unverified diffs."
                ),
                "expectedArtifact": "cross_branch_synergy_matrix.json plus a yes/no fusion lane recommendation",
                "workerType": "diagnostic",
                "noveltyClass": "cross_branch_fusion",
                "stagnationLane": bool(isinstance(stagnation, dict) and stagnation.get("active")),
                "requiresNewArtifact": True,
                "fusionOf": sources,
                "commands": ["diagnostic-only"],
                "requiredContext": [
                    "docs/search-graph.json",
                    "docs/attempt-cards/<fusion sources>.json",
                    "docs/optimization-ledger.json onlineEvaluations",
                ],
                "attackTrack": "fusion-support",
                "attackThesisRole": "test cross-branch synergy without blind patch stacking",
                "qualityScoreOverrideReason": f"search graph fusion candidate from mechanisms: {', '.join(mechanisms)}",
            }
        )
    return ideas


def component_ablation_ideas(current_id: str, root: Path, stagnation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    active = bool(isinstance(stagnation, dict) and stagnation.get("active"))
    if not active:
        return []
    source_path = root / "src" / "Solution.cpp"
    detected: list[str] = []
    if source_path.exists():
        text = source_path.read_text(encoding="utf-8", errors="ignore")
        for name in (
            "chooseGreedyPort",
            "improveOfficialSourceTransitions",
            "residual",
            "rollback",
            "capacity",
            "phase",
            "job",
        ):
            if name.lower() in text.lower():
                detected.append(name)
    component_hint = ", ".join(dict.fromkeys(detected[:8])) or "selector/residual/capacity/tie-break modules"
    return [
        {
            "origin": "component-ablation-operator",
            "freeformDivergence": True,
            "expertRole": "Component Ablation Lead",
            "lane": "component_ablation-score_sensitivity_map",
            "direction_state": "diagnose",
            "affected_family": "component_sensitivity",
            "changed_mechanism": "ablation_map",
            "hidden_shape": "post_stagnation_component_importance",
            "based_on": current_id,
            "hypothesis": (
                "Before another mutation round, identify which solver component is actually moving the online-aligned proxy. "
                f"Detected likely components: {component_hint}."
            ),
            "conceptCollision": [
                "MLE-STAR component refinement",
                "Ablate before deepening",
                "Online-aligned fold weights, not raw local score chasing",
            ],
            "whyNow": "Stagnation means the search may be attacking the wrong module; ablation should choose where high-risk work deserves time.",
            "smallestDecisiveTest": (
                "Produce a component sensitivity table for 3-6 named solver regions: component, expected scorer term, cheapest toggle/probe, "
                "proxy fold to run, predicted online relation, and reject condition."
            ),
            "killCondition": "Reject if it only names files/functions without mapping them to scorer components and one executable follow-up lane.",
            "expectedArtifact": "component_ablation_map.json plus one next-lane recommendation",
            "workerType": "diagnostic",
            "noveltyClass": "component_ablation",
            "stagnationLane": True,
            "requiresNewArtifact": True,
            "commands": ["diagnostic-only"],
            "requiredContext": [
                "src/Solution.cpp targeted function map",
                "docs/online-offline-weights.json",
                "docs/search-graph.json",
                "recent failed attempt cards",
            ],
            "attackTrack": "ablation-support",
            "attackThesisRole": "choose the next component to refine instead of mutating every module equally",
        }
    ]


def recent_online_items(ledger: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    items = ledger_online_evaluations(ledger)
    normalized: list[dict[str, Any]] = []
    for item in items[-limit:]:
        delta = as_float(item.get("delta") or item.get("online_delta_vs_best"))
        normalized.append(
            {
                "attempt": item.get("baseline") or item.get("submitted_attempt") or item.get("attempt"),
                "score": item.get("score") or item.get("online_score"),
                "delta": delta,
                "status": item.get("status", ""),
                "family": item.get("affected_family") or item.get("affectedFamily") or family_from_online_record(item),
                "mechanism": item.get("changed_mechanism") or item.get("changedMechanism") or mechanism_from_online_record(item),
                "shape": item.get("hidden_shape") or item.get("hiddenShape") or item.get("shape") or "",
                "actual": online_actual_from_delta(delta, str(item.get("status", ""))),
                "note": item.get("note") or item.get("hidden_dataset_hypothesis") or "",
            }
        )
    return normalized


def project_memory_context(root: Path) -> dict[str, Any]:
    memory_root = root / ".docs" / "project-memory"
    context: dict[str, Any] = {
        "indexPath": str(memory_root / "INDEX.md"),
        "memoryPath": str(memory_root / "memory.json"),
        "profilePath": str(memory_root / "profile.json"),
        "lanePath": str(memory_root / "lanes" / "competition-huawei-nslb.json"),
        "available": memory_root.exists(),
    }
    index_path = memory_root / "INDEX.md"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8-sig")
        context["indexExcerpt"] = "\n".join(text.splitlines()[:40])
    memory_path = memory_root / "memory.json"
    if memory_path.exists():
        try:
            memory = load_json(memory_path)
            context["summary"] = memory.get("summary", {})
            context["recentUpdates"] = memory.get("recentUpdates", [])[:8]
        except Exception as exc:  # noqa: BLE001
            context["memoryError"] = str(exc)
    lane_path = memory_root / "lanes" / "competition-huawei-nslb.json"
    if lane_path.exists():
        try:
            lane = load_json(lane_path)
            context["laneSummary"] = {
                "title": lane.get("title"),
                "status": lane.get("status"),
                "focus": lane.get("focus"),
                "lastUpdated": lane.get("lastUpdated"),
            }
        except Exception as exc:  # noqa: BLE001
            context["laneError"] = str(exc)
    return context


def ledger_experience_context(ledger: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    successes = [
        {
            "id": item.get("id") or item.get("promotedAs"),
            "promotedAs": item.get("promotedAs"),
            "basedOn": item.get("basedOn"),
            "family": item.get("affectedFamily") or item.get("affected_family"),
            "mechanism": item.get("changedMechanism") or item.get("changed_mechanism"),
            "result": item.get("result"),
            "summary": item.get("summary") or item.get("reason"),
            "avoidNextTime": item.get("avoidNextTime"),
        }
        for item in ledger.get("successfulExperiments", [])[-limit:]
        if isinstance(item, dict)
    ]
    failures = [
        {
            "id": item.get("id"),
            "basedOn": item.get("basedOn"),
            "family": item.get("affectedFamily") or item.get("affected_family"),
            "mechanism": item.get("changedMechanism") or item.get("changed_mechanism"),
            "result": item.get("result"),
            "failureReason": item.get("failureReason"),
            "avoidNextTime": item.get("avoidNextTime"),
        }
        for item in ledger.get("failedExperiments", [])[-limit:]
        if isinstance(item, dict)
    ]
    return {
        "currentBaseline": ledger.get("currentBaseline", {}).get("id"),
        "successfulLessons": successes,
        "failedLessons": failures,
        "onlineEvaluations": recent_online_items(ledger, limit=limit),
    }


def compact_items(items: Any, *, limit: int = 6) -> list[Any]:
    if not isinstance(items, list):
        return []
    return items[-limit:] if len(items) > limit else list(items)


def lane_phase(lane: dict[str, Any]) -> str:
    explicit = str(lane.get("phase") or "").strip().upper()
    if explicit in ("A", "B"):
        return explicit
    worker_type = str(lane.get("workerType") or "").lower()
    direction = str(lane.get("direction_state") or "").lower()
    lane_name = str(lane.get("lane") or "").lower()
    if "edit" in worker_type or direction == "exploit":
        return "B"
    if any(token in worker_type for token in ("diagnostic", "review", "proposal-only", "forensics", "gatekeeper")):
        return "A"
    if any(token in lane_name for token in ("discriminator", "proxy", "forensics", "auditor", "gatekeeper")):
        return "A"
    if direction in ("diagnose", "proposal", "proposal-only", "review"):
        return "A"
    return "B"


def command_budget_for_lane(lane: dict[str, Any]) -> tuple[int, int]:
    phase = str(lane.get("phase") or lane_phase(lane)).upper()
    worker_type = str(lane.get("workerType") or "").lower()
    if phase == "A" or any(token in worker_type for token in ("diagnostic", "review", "proposal-only")):
        return 8, 20
    if architecture_breakout_lane(lane):
        return 18, 55
    return 12, 35


def diagnostic_allowed_commands(lane: dict[str, Any]) -> list[str]:
    commands = [str(item) for item in lane.get("commands", [])]
    allowed = [
        "Get-FileHash src\\Solution.cpp -Algorithm SHA256",
        "rg -n --glob '!tmp/**' --glob '!build/**' --glob '!dist/**' <targeted-pattern> <specific-file-or-dir> --max-count 20",
        "Get-Content <small-file> -TotalCount <n> or -Tail <n>",
        "python score_loop_tools.py status/index/check/suggest-lanes/epoch-board",
        "python - <<read-only diagnostic script over small selected files>",
        "git diff -- src/Solution.cpp",
        "NEVER: recursive rg over tmp/score-loop-epochs, workspaces, build, dist, or the whole project root",
    ]
    for command in commands:
        if command and command not in ("diagnostic-only", "run_regression"):
            allowed.append(f"python tools\\benchmark.py --suite {command} --exe build\\score_loop_candidate.exe --discard-case-files")
    allowed.append("NEVER: python tools\\benchmark.py --suite diagnostic-only")
    allowed.append("NEVER inside worker: python tools\\benchmark.py --compare-baselines")
    return allowed


def allowed_commands_for_lane(lane: dict[str, Any]) -> list[str]:
    phase = str(lane.get("phase") or lane_phase(lane)).upper()
    worker_type = str(lane.get("workerType") or "").lower()
    if phase == "A" or any(token in worker_type for token in ("diagnostic", "review", "proposal-only")):
        return diagnostic_allowed_commands(lane)
    commands = [
        "Get-FileHash src\\Solution.cpp -Algorithm SHA256",
        "g++ -std=c++17 -O2 -pipe src\\Solution.cpp -o build\\score_loop_candidate.exe",
    ]
    for command in lane.get("commands", []):
        command_text = str(command)
        if command_text == "run_regression":
            commands.append("python tools\\run_regression.py")
        elif command_text == "diagnostic-only":
            commands.extend(diagnostic_allowed_commands(lane))
        elif command_text:
            commands.append(f"python tools\\benchmark.py --suite {command_text} --exe build\\score_loop_candidate.exe --discard-case-files")
    commands.append("git diff -- src/Solution.cpp")
    commands.append("NEVER: python tools\\benchmark.py --suite diagnostic-only")
    commands.append("NEVER inside worker: python tools\\benchmark.py --compare-baselines")
    return list(dict.fromkeys(commands))


def phase_prerequisites_for_lane(lane: dict[str, Any]) -> list[str]:
    if (
        bool(lane.get("riskOverride"))
        or bool(lane.get("controlledRiskLane"))
        or bounded_free_edit_lane(lane)
        or architecture_breakout_lane(lane)
        or online_confirmed_exploit_lane(lane)
    ):
        return []
    if str(lane.get("phase") or lane_phase(lane)).upper() != "B":
        return []
    return ["phaseA-current-evidence"]


def controlled_risk_lane(lane: dict[str, Any]) -> bool:
    return bool(lane.get("riskOverride") or lane.get("controlledRiskLane") or lane.get("requiresMutationAttempt"))


def bounded_free_edit_lane(lane: dict[str, Any]) -> bool:
    worker_type = str(lane.get("workerType") or "").lower()
    direction = str(lane.get("direction_state") or "").lower()
    allowed = [normalize_rel_path(item) for item in lane.get("allowed_files", [])]
    can_touch_solver = "src/Solution.cpp" in allowed or worker_type in ("edit", "edit-or-proposal")
    has_bounds = bool(str(lane.get("smallestDecisiveTest") or lane.get("uncertainty_reduced") or "").strip()) and bool(
        str(lane.get("killCondition") or "").strip()
    )
    has_exploration_pressure = bool(
        lane.get("stagnationLane")
        or lane.get("freeformDivergence")
        or lane.get("riskOverride")
        or lane.get("noveltyClass")
        or str(lane.get("attackTrack") or "") == "risk-sidecar"
    )
    return bool(can_touch_solver and has_bounds and has_exploration_pressure and direction in ("explore", "exploit"))


def online_confirmed_exploit_lane(lane: dict[str, Any]) -> bool:
    return bool(lane.get("onlineConfirmedExploitLane") or lane.get("forensicBeforePatch"))


def architecture_breakout_lane(lane: dict[str, Any]) -> bool:
    novelty = str(lane.get("noveltyClass") or "").lower()
    risk_level = str(lane.get("riskLevel") or "").upper()
    return bool(
        lane.get("architectureBreakoutLane")
        or lane.get("requiresArchitectureAttempt")
        or novelty in ("architecture_breakout", "moonshot_architecture", "search_policy_breakout", "scorer_surrogate")
        or risk_level in ("R2", "R3")
    )


def controlled_risk_active(manifest: dict[str, Any]) -> bool:
    board = manifest.get("board", {}) if isinstance(manifest.get("board", {}), dict) else {}
    stagnation = board.get("stagnationMode", {}) if isinstance(board.get("stagnationMode", {}), dict) else {}
    risk_mode = board.get("controlledRiskMode", {}) if isinstance(board.get("controlledRiskMode", {}), dict) else {}
    return bool(risk_mode.get("active") or stagnation.get("active"))


def innovation_active(manifest: dict[str, Any]) -> bool:
    board = manifest.get("board", {}) if isinstance(manifest.get("board", {}), dict) else {}
    stagnation = board.get("stagnationMode", {}) if isinstance(board.get("stagnationMode", {}), dict) else {}
    innovation = board.get("innovationMode", {}) if isinstance(board.get("innovationMode", {}), dict) else {}
    return bool(innovation.get("active") or stagnation.get("active"))


def build_worker_context(root: Path, board: dict[str, Any], ledger: dict[str, Any], lane: dict[str, Any]) -> dict[str, Any]:
    baseline = ledger.get("currentBaseline", {}) if isinstance(ledger, dict) else {}
    experience = ledger_experience_context(ledger, limit=10) if isinstance(ledger, dict) else {}
    command_budget = int(lane.get("commandBudget") or command_budget_for_lane(lane)[0])
    time_budget = int(lane.get("timeBudgetMinutes") or command_budget_for_lane(lane)[1])
    recovered_diffs = recovery_records_for_lane(root, lane, limit=4)
    return {
        "purpose": "Compact worker context. Read this before opening full ledger, memory, SKILL.md, or large source chunks.",
        "project": str(root),
        "baseline": {
            "id": baseline.get("id") or board.get("currentBaseline"),
            "sourceSha256": baseline.get("sourceSha256") or board.get("baselineSha256"),
            "bestKnownOnlineBaseline": baseline.get("scores", {}).get("bestKnownOnlineBaseline") if isinstance(baseline.get("scores", {}), dict) else "",
            "bestKnownOnlineScore": baseline.get("scores", {}).get("bestKnownOnlineScore") if isinstance(baseline.get("scores", {}), dict) else "",
        },
        "lane": {
            "id": lane.get("lane"),
            "attempt": lane.get("attempt"),
            "phase": lane.get("phase") or lane_phase(lane),
            "workerType": lane.get("workerType"),
            "hypothesis": lane.get("hypothesis"),
            "smallestDecisiveTest": lane.get("smallestDecisiveTest") or lane.get("uncertainty_reduced"),
            "killCondition": lane.get("killCondition"),
            "affectedFamily": lane.get("affected_family"),
            "changedMechanism": lane.get("changed_mechanism"),
            "hiddenShape": lane_shape(lane),
            "allowedFiles": lane.get("allowed_files", []),
        },
        "stagnation": {
            "active": bool(board.get("stagnationMode", {}).get("active")) if isinstance(board.get("stagnationMode", {}), dict) else False,
            "escapeLevel": board.get("stagnationMode", {}).get("escapeLevel") if isinstance(board.get("stagnationMode", {}), dict) else 0,
            "lane": bool(lane.get("stagnationLane")),
            "escapeLane": bool(lane.get("escapeLane")),
            "noveltyClass": lane.get("noveltyClass"),
            "requiresNewArtifact": bool(lane.get("requiresNewArtifact")),
            "forbiddenReuse": lane.get("forbiddenReuse", []),
            "modeRule": board.get("stagnationMode", {}).get("modeRule") if isinstance(board.get("stagnationMode", {}), dict) else "",
        },
        "controlledRisk": {
            "active": bool(board.get("controlledRiskMode", {}).get("active")) if isinstance(board.get("controlledRiskMode", {}), dict) else False,
            "lane": controlled_risk_lane(lane),
            "riskBudget": lane.get("riskBudget"),
            "requiresMutationAttempt": bool(lane.get("requiresMutationAttempt")),
            "forensicBeforePatch": online_confirmed_exploit_lane(lane),
            "riskLimit": lane.get("riskLimit"),
        },
        "onlineConfirmedExploit": {
            "lane": online_confirmed_exploit_lane(lane),
            "sourcePositiveSignal": lane.get("sourcePositiveSignal"),
            "forensicBeforePatch": bool(lane.get("forensicBeforePatch")),
            "exactTargetRule": lane.get("exactTargetRule"),
            "doNotBroaden": lane.get("doNotBroaden"),
        },
        "innovation": {
            "active": bool(board.get("innovationMode", {}).get("active")) if isinstance(board.get("innovationMode", {}), dict) else False,
            "architectureBreakoutLane": architecture_breakout_lane(lane),
            "riskLevel": lane.get("riskLevel"),
            "requiresArchitectureAttempt": bool(lane.get("requiresArchitectureAttempt")),
            "architectureBudget": lane.get("architectureBudget"),
            "allowedExperimentScope": lane.get("allowedExperimentScope"),
            "modeRule": board.get("innovationMode", {}).get("rule") if isinstance(board.get("innovationMode", {}), dict) else "",
        },
        "evidenceAnchors": lane.get("evidenceAnchors", {}),
        "qualityScore": lane.get("qualityScore", {}),
        "lessons": {
            "successful": compact_items(experience.get("successfulLessons"), limit=6),
            "failedOrFrozen": compact_items(experience.get("failedLessons"), limit=8),
            "recentOnline": compact_items(experience.get("onlineEvaluations"), limit=8),
        },
        "searchSystem": search_system_context(root, limit=6),
        "failedDiffFurnace": failed_diff_context(root, limit=6),
        "banditSignal": bandit_signal_for_idea(root, lane),
        "recoveredFailedDiffs": recovered_diffs,
        "recoveryContract": {
            "active": bool(recovered_diffs),
            "rule": "If recoveredFailedDiffs is non-empty, an edit/architecture/fusion worker must apply, recreate, or deliberately supersede one patch before first-kill. If no recovered patch can be used, return blocked-by-missing-target with a concrete reason.",
        },
        "budgets": {
            "shellCommandLimit": command_budget,
            "timeBudgetMinutes": time_budget,
            "afterBudget": "Stop and write child_result.json as rejected/inconclusive/proposal-only with the best lesson; do not keep searching.",
        },
        "allowedCommands": allowed_commands_for_lane(lane),
        "evidenceRules": {
            "currentEvidenceRequired": "currentEvidence must include this epoch's smallestDecisiveTestResult; old child results cannot replace it.",
            "priorEvidenceAllowed": "priorEvidence may cite old epochs only as background.",
            "staleEvidenceBoundary": "If currentEvidence is empty and the conclusion relies on an older epoch, result must be proposal-only or rejected, never promotionCandidate=true.",
            "diagnosticOnlySuiteBan": "`diagnostic-only` is a lane mode, not a benchmark suite; never run benchmark.py --suite diagnostic-only.",
        },
    }


def duplicate_note_for_idea(idea: dict[str, Any], frozen_patterns: list[Any], counts: dict[tuple[str, str], int]) -> str:
    text = json.dumps(idea, ensure_ascii=False).lower()
    matching_frozen = [
        str(pattern)
        for pattern in frozen_patterns
        if str(pattern).strip() and str(pattern).lower()[:80] in text
    ]
    family = str(idea.get("affected_family", "unknown"))
    mechanism = str(idea.get("changed_mechanism", "unknown"))
    prior = counts.get((family, mechanism), 0)
    notes: list[str] = []
    if prior:
        notes.append(f"{prior} prior failures for {family}/{mechanism}")
    if matching_frozen:
        notes.append("matches frozen pattern text")
    return "; ".join(notes) if notes else "no direct duplicate fingerprint"


def first_nonempty(items: Any) -> Any:
    if isinstance(items, list):
        for item in reversed(items):
            if item:
                return item
    return None


def evidence_anchors_for_idea(idea: dict[str, Any], experience: dict[str, Any], online_items: list[dict[str, Any]]) -> dict[str, Any]:
    family = str(idea.get("affected_family") or "")
    mechanism = str(idea.get("changed_mechanism") or "")
    successes = experience.get("successfulLessons", []) if isinstance(experience, dict) else []
    failures = experience.get("failedLessons", []) if isinstance(experience, dict) else []
    online = online_items or experience.get("onlineEvaluations", []) if isinstance(experience, dict) else online_items

    def related(item: dict[str, Any]) -> bool:
        blob = json.dumps(item, ensure_ascii=False).lower()
        return bool((family and family.lower() in blob) or (mechanism and mechanism.lower() in blob))

    success = first_nonempty([item for item in successes if isinstance(item, dict) and related(item)]) or first_nonempty(successes)
    failure = first_nonempty([item for item in failures if isinstance(item, dict) and related(item)]) or first_nonempty(failures)
    online_record = first_nonempty([item for item in online if isinstance(item, dict) and related(item)]) or first_nonempty(online)
    return {
        "successfulLesson": success or "none-available",
        "failedOrFrozenLesson": failure or "none-available",
        "onlineFeedbackRecord": online_record or "none-available",
    }


def lane_id_from_ranked_item(item: dict[str, Any]) -> str:
    path_text = str(item.get("path") or "").replace("\\", "/")
    marker = "/workspaces/"
    if marker in path_text:
        rest = path_text.split(marker, 1)[1]
        lane_id = rest.split("/", 1)[0].strip()
        if lane_id:
            return lane_id
    worker = item.get("worker")
    if isinstance(worker, str) and worker.strip():
        return worker.strip()
    if isinstance(worker, dict):
        for key in ("id", "lane", "role", "type"):
            value = str(worker.get(key) or "").strip()
            if value:
                return value
    return "unknown"


def closeout_parent_gate_ready(closeout: dict[str, Any]) -> bool:
    decision = str(closeout.get("topDecision") or "").lower()
    if any(token in decision for token in ("reject", "needs-more-evidence", "blocked", "inconclusive")):
        return False
    return any(token in decision for token in ("eligible", "parent-gate", "promote", "accept"))


def closeout_is_stagnant(closeout: dict[str, Any]) -> bool:
    if closeout_parent_gate_ready(closeout):
        return False
    decision = str(closeout.get("topDecision") or "").lower()
    ranked = closeout.get("ranked", [])
    if any(token in decision for token in STAGNATION_BAD_RESULT_TOKENS):
        return True
    if isinstance(ranked, list) and ranked:
        results = " ".join(str(item.get("result") or "").lower() for item in ranked if isinstance(item, dict))
        has_candidate = any(bool(item.get("promotionCandidate")) for item in ranked if isinstance(item, dict))
        if not has_candidate:
            return True
        if any(token in results for token in STAGNATION_BAD_RESULT_TOKENS):
            return True
    return False


def recent_epoch_closeouts(root: Path, limit: int) -> list[dict[str, Any]]:
    epoch_root = root / "tmp" / "score-loop-epochs"
    if not epoch_root.exists():
        return []
    closeout_paths = [
        path / "epoch_closeout.json"
        for path in epoch_root.iterdir()
        if path.is_dir() and (path / "epoch_closeout.json").exists()
    ]
    closeout_paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    closeouts: list[dict[str, Any]] = []
    for path in closeout_paths[:limit]:
        try:
            closeout = load_json(path)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(closeout, dict):
            continue
        closeout["_closeoutPath"] = str(path)
        closeout["_epochId"] = path.parent.name
        closeouts.append(closeout)
    return closeouts


def closeout_run_dir(closeout: dict[str, Any]) -> Path | None:
    run_dir_text = str(closeout.get("runDir") or "").strip()
    if run_dir_text:
        return Path(run_dir_text).resolve()
    closeout_path = str(closeout.get("_closeoutPath") or "").strip()
    if closeout_path:
        return Path(closeout_path).resolve().parent
    return None


def manifest_for_closeout(closeout: dict[str, Any]) -> dict[str, Any] | None:
    run_dir = closeout_run_dir(closeout)
    if not run_dir:
        return None
    manifest_path = run_dir / "epoch_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        loaded = load_json(manifest_path)
    except Exception:  # noqa: BLE001
        return None
    return loaded if isinstance(loaded, dict) else None


def closeout_artifact_status(closeout: dict[str, Any]) -> dict[str, Any]:
    manifest = manifest_for_closeout(closeout)
    if not manifest:
        return {
            "stagnationModeActive": False,
            "newArtifactRequiredLanes": 0,
            "newArtifactDelivered": False,
            "newArtifactDeliveredCount": 0,
        }
    board = manifest.get("board", {}) if isinstance(manifest.get("board", {}), dict) else {}
    stagnation_mode = board.get("stagnationMode", {}) if isinstance(board.get("stagnationMode", {}), dict) else {}
    required_lanes = [
        lane
        for lane in manifest.get("lanes", [])
        if isinstance(lane, dict) and bool(lane.get("requiresNewArtifact"))
    ]
    delivered: list[str] = []
    missing: list[str] = []
    for lane in required_lanes:
        result_path = Path(str(lane.get("workspace", ""))).resolve() / "child_result.json"
        if not result_path.exists():
            missing.append(str(lane.get("lane") or result_path.parent.name))
            continue
        try:
            result = apply_lane_metadata(load_json(result_path), lane)
        except Exception:  # noqa: BLE001
            missing.append(str(lane.get("lane") or result_path.parent.name))
            continue
        ok, _detail = new_artifact_evidence_status(result, lane)
        if ok:
            delivered.append(str(lane.get("lane") or result_path.parent.name))
        else:
            missing.append(str(lane.get("lane") or result_path.parent.name))
    return {
        "stagnationModeActive": bool(stagnation_mode.get("active")),
        "newArtifactRequiredLanes": len(required_lanes),
        "newArtifactDelivered": bool(delivered),
        "newArtifactDeliveredCount": len(delivered),
        "newArtifactDeliveredLanes": delivered,
        "newArtifactMissingLanes": missing,
    }


def dataset_decision_backlog(root: Path) -> dict[str, Any]:
    dataset_ledger = load_or_default_dataset_ledger(root)
    candidates = [item for item in dataset_ledger.get("candidates", []) if isinstance(item, dict)]
    validated = [item for item in candidates if str(item.get("status", "candidate")) == "validated"]
    pending = [
        item
        for item in candidates
        if str(item.get("status", "candidate")) not in ("validated", "promoted", "frozen")
    ]
    return {
        "validatedBacklogCount": len(validated),
        "pendingCount": len(pending),
        "validatedBacklogIds": [str(item.get("candidateId") or "") for item in validated if item.get("candidateId")],
        "pendingIds": [str(item.get("candidateId") or "") for item in pending if item.get("candidateId")],
    }


def summarize_closeout_for_stagnation(closeout: dict[str, Any]) -> dict[str, Any]:
    ranked = closeout.get("ranked", [])
    ranked_items = [item for item in ranked if isinstance(item, dict)] if isinstance(ranked, list) else []
    lane_ids = [lane_id_from_ranked_item(item) for item in ranked_items]
    promotion_count = len([item for item in ranked_items if bool(item.get("promotionCandidate"))])
    top = closeout.get("topCandidate", {}) if isinstance(closeout.get("topCandidate", {}), dict) else {}
    artifact_status = closeout_artifact_status(closeout)
    summary = {
        "epoch": closeout.get("_epochId") or Path(str(closeout.get("runDir") or "")).name,
        "topDecision": closeout.get("topDecision", ""),
        "topResult": top.get("result") or (ranked_items[0].get("result") if ranked_items else ""),
        "promotionCandidateCount": promotion_count,
        "parentGateReady": closeout_parent_gate_ready(closeout),
        "stagnant": closeout_is_stagnant(closeout),
        "laneIds": lane_ids,
    }
    summary.update(artifact_status)
    return summary


def stagnation_context(root: Path, *, threshold: int = 2, force: bool = False) -> dict[str, Any]:
    threshold = max(1, int(threshold or 2))
    closeouts = recent_epoch_closeouts(root, limit=max(threshold + 2, 5))
    recent = closeouts[:threshold]
    summaries = [summarize_closeout_for_stagnation(item) for item in recent]
    stagnant_count = len([item for item in summaries if item.get("stagnant")])
    lane_counts: dict[str, int] = {}
    for summary in summaries:
        for lane_id in summary.get("laneIds", []):
            lane_counts[str(lane_id)] = lane_counts.get(str(lane_id), 0) + 1
    repeated_lane_ids = sorted(
        lane_id for lane_id, count in lane_counts.items() if count >= max(2, min(threshold, 3))
    )
    repeated_standard = sorted(set(repeated_lane_ids) & STAGNATION_REPEATED_LANES)
    repeated_local_lane_ids = sorted(
        lane_id
        for lane_id in repeated_lane_ids
        if any(token in str(lane_id).lower() for token in LOCAL_OPTIMUM_LANE_TOKENS)
    )
    repeated_breakout_lane_ids = sorted(
        lane_id
        for lane_id in repeated_lane_ids
        if any(token in str(lane_id).lower() for token in GLOBAL_BREAKOUT_LANE_TOKENS)
    )
    active = bool(force or (len(recent) >= threshold and stagnant_count >= threshold))
    recent_stagnation_mode = [item for item in summaries if item.get("stagnationModeActive")]
    second_order_active = bool(
        active
        and len(recent_stagnation_mode) >= threshold
        and all(
            item.get("stagnant")
            and not item.get("parentGateReady")
            and not item.get("newArtifactDelivered")
            for item in recent_stagnation_mode[:threshold]
        )
    )
    dataset_backlog = dataset_decision_backlog(root)
    artifact_only_stagnation = bool(
        active
        and len(recent_stagnation_mode) >= threshold
        and all(
            item.get("stagnant")
            and not item.get("parentGateReady")
            and item.get("newArtifactDelivered")
            for item in recent_stagnation_mode[:threshold]
        )
        and int(dataset_backlog.get("validatedBacklogCount") or 0) > 0
    )
    second_order_active = bool(second_order_active or artifact_only_stagnation)
    witness_stagnation_count = len(
        [
            item
            for item in summaries
            if item.get("stagnant")
            and any(
                ("counterfactual" in str(lane_id).lower())
                or ("witness" in str(lane_id).lower())
                or ("residual_envelope" in str(lane_id).lower())
                for lane_id in item.get("laneIds", [])
            )
        ]
    )
    witness_saturated = bool(active and witness_stagnation_count >= threshold)
    local_loop_epochs: list[str] = []
    local_loop_lane_counts: dict[str, int] = {}
    global_breakout_seen = False
    for summary in summaries:
        if not summary.get("stagnant"):
            continue
        lanes_text = " ".join(str(lane_id).lower() for lane_id in summary.get("laneIds", []))
        local_count = sum(1 for token in LOCAL_OPTIMUM_LANE_TOKENS if token in lanes_text)
        breakout_count = sum(1 for token in GLOBAL_BREAKOUT_LANE_TOKENS if token in lanes_text)
        if breakout_count:
            global_breakout_seen = True
        if local_count >= 2:
            local_loop_epochs.append(str(summary.get("epoch") or "unknown"))
            for lane_id in summary.get("laneIds", []):
                lane_text = str(lane_id).lower()
                if any(token in lane_text for token in LOCAL_OPTIMUM_LANE_TOKENS):
                    local_loop_lane_counts[str(lane_id)] = local_loop_lane_counts.get(str(lane_id), 0) + 1
    breakout_stagnation_active = bool(active and global_breakout_seen)
    local_optimum_active = bool(
        active
        and (
            len(local_loop_epochs) >= threshold
            or witness_saturated
            or bool(repeated_local_lane_ids)
            or breakout_stagnation_active
        )
    )
    global_perspective = {
        "active": local_optimum_active,
        "reason": (
            f"recent stagnant epochs require global perspective budget control"
            if local_optimum_active
            else ""
        ),
        "localLoopEpochs": local_loop_epochs,
        "localLoopLaneCounts": local_loop_lane_counts,
        "repeatedLocalLaneIds": repeated_local_lane_ids,
        "repeatedBreakoutLaneIds": repeated_breakout_lane_ids,
        "globalBreakoutSeenRecently": global_breakout_seen,
        "maxLocalEnvelopeLanes": 1 if local_optimum_active else 2,
        "minGlobalBreakoutLanes": 4 if local_optimum_active else 0,
        "requiredLaneFamilies": [
            "outside_residual_envelope",
            "pdflegal_or_dataset_materialization",
            "architecture_or_moonshot",
            "combination_or_objective_reframe",
        ] if local_optimum_active else [],
        "demoteTokens": list(LOCAL_OPTIMUM_LANE_TOKENS),
        "promoteTokens": list(GLOBAL_BREAKOUT_LANE_TOKENS),
        "rule": "When active, same-case/residual-envelope lanes are support-only; the main budget must sample outside-envelope mechanisms, dataset/proxy materialization, architecture/moonshot, fusion, or objective/online reframe.",
    }
    escape_level = 2 if second_order_active else 1 if active else 0
    reasons: list[str] = []
    if force:
        reasons.append("forced by --force-stagnation")
    if len(recent) >= threshold and stagnant_count >= threshold:
        reasons.append(f"last {threshold} closed epochs produced no accepted parent-gate/promotion path")
    if repeated_standard:
        reasons.append(f"repeated standard lanes: {', '.join(repeated_standard)}")
    if second_order_active:
        if artifact_only_stagnation:
            reasons.append(
                f"last {threshold} stagnation-mode epochs produced artifacts but no dataset promotion/freeze or parent-gate path"
            )
        else:
            reasons.append(f"last {threshold} stagnation-mode epochs produced no auditable new artifact or parent-gate path")
    if active and not reasons:
        reasons.append("stagnation mode active")
    if witness_saturated:
        reasons.append(
            f"last {threshold} stagnant epochs already spent counterfactual/witness pressure; demote witness-as-default and pivot toward architecture/objective/search-policy lanes"
        )
    if local_optimum_active:
        details = []
        if local_loop_epochs:
            details.append(f"localLoopEpochs={len(local_loop_epochs)}")
        if repeated_local_lane_ids:
            details.append(f"repeatedLocal={', '.join(repeated_local_lane_ids)}")
        if witness_saturated:
            details.append("witnessSaturated=true")
        if breakout_stagnation_active:
            details.append("globalBreakoutStagnant=true")
        reasons.append(global_perspective["reason"] + (f" ({'; '.join(details)})" if details else ""))
    return {
        "active": active,
        "escapeLevel": escape_level,
        "secondOrderActive": second_order_active,
        "witnessSaturated": witness_saturated,
        "globalPerspective": global_perspective,
        "localOptimumActive": local_optimum_active,
        "witnessStagnationCount": witness_stagnation_count,
        "threshold": threshold,
        "stagnantEpochCount": stagnant_count,
        "recentEpochs": summaries,
        "repeatedLaneIds": repeated_lane_ids,
        "repeatedStandardLaneIds": repeated_standard,
        "standardRepeatedTemplates": sorted(STAGNATION_REPEATED_LANES),
        "recommendedNovelLaneCount": 2,
        "newArtifactAdvisory": True,
        "forbiddenReuse": [
            "phase7/job28 neutral decoy as positive evidence",
            "job32 phase6 neutral decoy as positive evidence",
            "jobs22 leaf-band/capacity-shadow neutral decoy as positive evidence",
            "another risk gatekeeper that vetoes all mutation without naming a bounded high-variance lane",
            "another dataset/proxy artifact lane that does not end in promote/freeze/reject/merge",
        ],
        "datasetDecisionBacklog": dataset_backlog,
        "reasons": reasons,
        "modeRule": (
            "When active, selectedLanes should favor novel stagnation lanes, new artifacts/cases/enumeration, "
            "and fewer repeated standard diagnostic lanes. If escapeLevel=2, prefer an objective-reframe, dataset-candidate decision, "
            "or online-revalidation escape lane, but these are advisory unless the execution harness is unsafe. "
            "If witnessSaturated=true, do not make counterfactual witness the default attack thesis; keep it only as a support lane or pivot proof. "
            "If globalPerspective.active=true, make outside-envelope/global-breakout lanes the main budget and cap local residual/same-case lanes."
        ),
    }


def idea_quality_score(
    idea: dict[str, Any],
    *,
    counts: dict[tuple[str, str], int],
    frozen_patterns: list[Any],
    weights: dict[str, Any],
    online_items: list[dict[str, Any]],
    stagnation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 0.0
    strengths: list[str] = []
    risks: list[str] = []
    hard_missing: list[str] = []
    for field in ("hypothesis", "smallestDecisiveTest", "killCondition"):
        if str(idea.get(field) or "").strip():
            score += 6
        else:
            risks.append(f"missing {field}")
            hard_missing.append(field)
    for field in ("expertRole", "expectedArtifact"):
        if str(idea.get(field) or "").strip():
            score += 4
        else:
            risks.append(f"advisory missing {field}")
    worker_type = str(idea.get("workerType") or "")
    direction = str(idea.get("direction_state") or "")
    family = str(idea.get("affected_family") or "unknown")
    mechanism = str(idea.get("changed_mechanism") or "unknown")
    shape = str(idea.get("hidden_shape") or "unknown")
    if worker_type in ("diagnostic", "review", "proposal-only"):
        score += 6
        strengths.append("cheap information lane")
    if worker_type in ("edit", "edit-or-proposal"):
        score += 4
        strengths.append("can produce a patch candidate")
    if direction == "exploit":
        score += 3
    if bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")):
        score += 34
        strengths.append("044-style online-confirmed exploit lane")
    if bool(idea.get("freeformDivergence")):
        score += 24
        strengths.append("freeform divergent concept, not a stock lane template")
    if idea.get("origin") == "freeform-concept-collision":
        score += 8
        strengths.append("concept-collision generated")
    if "guard" in str(idea.get("hypothesis", "")).lower() or "threshold" in str(idea.get("hypothesis", "")).lower():
        if bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")):
            score -= 2
            risks.append("guard/threshold wording; allowed only because it is forensic-before-patch")
        else:
            score -= 8
            risks.append("guard/threshold wording")
    prior = counts.get((family, mechanism), 0)
    if prior:
        score -= min(18, prior * 6)
        risks.append(f"{prior} prior failures for {family}/{mechanism}")
    duplicate_risk = duplicate_note_for_idea(idea, frozen_patterns, counts)
    if duplicate_risk != "no direct duplicate fingerprint":
        score -= 10
        risks.append(duplicate_risk)
    weight = family_weight(weights, family)
    weight = (weight * 0.7) + (mechanism_weight(weights, family, mechanism) * 0.3)
    if shape != "unknown":
        weight = (weight * 0.8) + (shape_weight(weights, family, mechanism, shape) * 0.2)
    score += 10 * weight
    if online_items:
        score += 6
        strengths.append("recent online feedback available")
    if str(idea.get("whyNow") or "").strip():
        score += 4
    if str(idea.get("expectedArtifact") or "").lower().strip() in ("single-cause patch candidate or rejection", "minimal patch or proposal with one named target case"):
        score += 3
        strengths.append("single-cause artifact")
    stagnation_active = bool(isinstance(stagnation, dict) and stagnation.get("active"))
    witness_saturated = bool(isinstance(stagnation, dict) and stagnation.get("witnessSaturated"))
    if stagnation_active:
        lane_id = str(idea.get("lane") or "")
        witness_saturated = bool(isinstance(stagnation, dict) and stagnation.get("witnessSaturated"))
        global_perspective = stagnation.get("globalPerspective", {}) if isinstance(stagnation, dict) else {}
        global_active = bool(isinstance(global_perspective, dict) and global_perspective.get("active"))
        lane_text = " ".join(
            str(value or "").lower()
            for value in (
                idea.get("lane"),
                idea.get("hypothesis"),
                idea.get("changed_mechanism"),
                idea.get("hidden_shape"),
                idea.get("noveltyClass"),
            )
        )
        is_local_envelope = any(token in lane_text for token in LOCAL_OPTIMUM_LANE_TOKENS)
        is_global_breakout = any(token in lane_text for token in GLOBAL_BREAKOUT_LANE_TOKENS)
        repeated_standard = set(stagnation.get("repeatedStandardLaneIds", [])) if isinstance(stagnation, dict) else set()
        repeated_any = set(stagnation.get("repeatedLaneIds", [])) if isinstance(stagnation, dict) else set()
        if global_active:
            if is_global_breakout:
                score += 28
                strengths.append("global-perspective breakout lane")
                if lane_id in repeated_any:
                    score -= 18
                    risks.append("global breakout lane repeats a recent closed lane; requires a new causal variable")
            if is_local_envelope and not is_global_breakout:
                score -= 26
                risks.append("local residual/same-case loop is saturated; support-only unless it enables a global pivot")
            if bool(idea.get("architectureBreakoutLane")) or str(idea.get("riskLevel") or "").upper() in ("R2", "R3"):
                score += 10
                strengths.append("global-perspective architecture pressure")
            if "pdflegal" in lane_text or "metamorphic" in lane_text or "dataset" in lane_text:
                score += 10
                strengths.append("global-perspective dataset/proxy pressure")
            if "combination" in lane_text or "synergy" in lane_text or "objective_reframe" in lane_text:
                score += 8
                strengths.append("global-perspective fusion/reframe pressure")
        if bool(idea.get("stagnationLane")):
            score += 18
            strengths.append("stagnation breakout lane")
        if bool(idea.get("freeformDivergence")):
            score += 14
            strengths.append("stagnation freeform divergence")
        if bool(idea.get("requiresNewArtifact")):
            score += 8
            strengths.append("requires new artifact/case/enumeration")
        if bool(idea.get("requiresCounterfactualWitness")):
            if witness_saturated:
                score -= 8
                risks.append("counterfactual witness pressure is saturated; keep only if it changes target or supports a pivot")
            else:
                score += 18
                strengths.append("counterfactual witness main track")
        if bool(idea.get("escapeLane")):
            score += 16
            strengths.append("second-order stagnation escape lane")
        if bool(idea.get("controlledRiskLane")) or bool(idea.get("riskOverride")):
            score += 14
            strengths.append("controlled-risk mutation pressure")
        if bool(idea.get("architectureBreakoutLane")) or bool(idea.get("requiresArchitectureAttempt")):
            score += 22
            strengths.append("architecture breakout pressure")
        if str(idea.get("riskLevel") or "").upper() == "R3":
            score += 10
            strengths.append("moonshot risk budget")
        elif str(idea.get("riskLevel") or "").upper() == "R2":
            score += 6
            strengths.append("architecture risk budget")
        if str(idea.get("noveltyClass") or "").strip():
            score += 6
            strengths.append(f"novelty class: {idea.get('noveltyClass')}")
        if bool(idea.get("datasetDecisionLane")):
            score += 16
            strengths.append("forces dataset candidate decision backlog closure")
        if bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")):
            score += 14
            strengths.append("keeps online-positive exploit pressure alive during stagnation")
        if lane_id in repeated_standard or lane_id in STAGNATION_REPEATED_LANES:
            score -= 14
            risks.append("repeated standard stagnation template")
        elif lane_id in repeated_any:
            score -= 12 if global_active else 8
            risks.append("repeated recent lane")
        if lane_id == "hidden_proxy_generator-online_neutral_decoys" and not bool(idea.get("requiresNewArtifact")):
            score -= 16
            risks.append("proxy lane only audits known neutral decoys")
        if lane_id == "risk_gatekeeper-duplicate_and_runtime_filter" and not bool(idea.get("allowsHighVariance")):
            score -= 12
            risks.append("risk gatekeeper may block all exploration during stagnation")
        if lane_id == "risk_gatekeeper-duplicate_and_runtime_filter" and bool(idea.get("allowsHighVariance")):
            # Stagnation portfolios require a gatekeeper, but the repeated-lane
            # penalty can otherwise make the required review lane unselectable.
            score = max(score, 28)
            strengths.append("required bounded-exploration gatekeeper")
    return {
        "lane": idea.get("lane"),
        "score": round(score, 4),
        "onlineWeight": round(weight, 4),
        "strengths": strengths,
        "risks": risks,
        "decision": "selectable" if score >= 18 and not hard_missing else "proposal-only",
        "hardMissing": hard_missing,
        "governance": "hard checks are executable hypothesis, smallest decisive test, and kill condition; other quality issues are advisory",
    }


def select_idea_portfolio(
    ideas: list[dict[str, Any]],
    scores: dict[str, dict[str, Any]],
    max_lanes: int,
    stagnation: dict[str, Any] | None = None,
    *,
    freeform_first: bool = True,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    stagnation_active = bool(isinstance(stagnation, dict) and stagnation.get("active"))
    global_perspective = stagnation.get("globalPerspective", {}) if isinstance(stagnation, dict) else {}
    global_active = bool(isinstance(global_perspective, dict) and global_perspective.get("active"))
    repeated_any = set(stagnation.get("repeatedLaneIds", [])) if isinstance(stagnation, dict) else set()

    def lane_blob(idea: dict[str, Any]) -> str:
        return " ".join(
            str(value or "").lower()
            for value in (
                idea.get("lane"),
                idea.get("hypothesis"),
                idea.get("changed_mechanism"),
                idea.get("hidden_shape"),
                idea.get("noveltyClass"),
            )
        )

    def is_local_envelope_lane(idea: dict[str, Any]) -> bool:
        text = lane_blob(idea)
        return any(token in text for token in LOCAL_OPTIMUM_LANE_TOKENS)

    def is_global_breakout_lane(idea: dict[str, Any]) -> bool:
        text = lane_blob(idea)
        return any(token in text for token in GLOBAL_BREAKOUT_LANE_TOKENS)

    def is_repeated_local_lane(idea: dict[str, Any]) -> bool:
        lane_id = str(idea.get("lane") or "")
        return lane_id in repeated_any and is_local_envelope_lane(idea) and not is_global_breakout_lane(idea)

    def is_allowed_global_support_lane(idea: dict[str, Any]) -> bool:
        text = lane_blob(idea)
        if not is_local_envelope_lane(idea) or is_global_breakout_lane(idea):
            return True
        return "044_style" in text or "online_confirmed_exploit" in text

    max_local_envelope = int(global_perspective.get("maxLocalEnvelopeLanes") or (1 if global_active else 99)) if isinstance(global_perspective, dict) else 99

    def selected_local_envelope_count() -> int:
        return len([idea for idea in selected if is_local_envelope_lane(idea) and not is_global_breakout_lane(idea)])

    def add(predicate) -> None:
        nonlocal selected
        if len(selected) >= max_lanes:
            return
        candidates = [
            idea
            for idea in ideas
            if idea not in selected
            and predicate(idea)
            and scores.get(str(idea.get("lane")), {}).get("decision") == "selectable"
            and not (global_active and is_repeated_local_lane(idea))
            and not (
                global_active
                and is_local_envelope_lane(idea)
                and not is_global_breakout_lane(idea)
                and not is_allowed_global_support_lane(idea)
            )
        ]
        candidates.sort(key=lambda item: scores.get(str(item.get("lane")), {}).get("score", 0), reverse=True)
        if candidates:
            selected.append(candidates[0])

    if freeform_first:
        freeform_candidates = [
            idea
            for idea in ideas
            if bool(idea.get("freeformDivergence"))
            and scores.get(str(idea.get("lane")), {}).get("decision") == "selectable"
        ]
        freeform_candidates.sort(key=lambda item: scores.get(str(item.get("lane")), {}).get("score", 0), reverse=True)
        family_mechanisms: set[tuple[str, str]] = set()
        target_freeform = min(
            len(freeform_candidates),
            max(2, math.ceil(max_lanes * (0.60 if stagnation_active else 0.50))),
        )
        for idea in freeform_candidates:
            if len(selected) >= target_freeform:
                break
            if global_active and is_repeated_local_lane(idea):
                continue
            if global_active and is_local_envelope_lane(idea) and not is_global_breakout_lane(idea):
                if not is_allowed_global_support_lane(idea):
                    continue
                if selected_local_envelope_count() >= max_local_envelope:
                    continue
            key = (str(idea.get("affected_family") or ""), str(idea.get("changed_mechanism") or ""))
            if key in family_mechanisms:
                continue
            selected.append(idea)
            family_mechanisms.add(key)

    if stagnation_active:
        if int(stagnation.get("escapeLevel") or 0) >= 2:
            dataset_backlog = stagnation.get("datasetDecisionBacklog", {}) if isinstance(stagnation, dict) else {}
            if int(dataset_backlog.get("validatedBacklogCount") or 0) > 0:
                add(lambda idea: bool(idea.get("datasetDecisionLane")))
            add(lambda idea: bool(idea.get("escapeLane")))
        witness_saturated = bool(stagnation.get("witnessSaturated")) if isinstance(stagnation, dict) else False
        if global_active:
            add(lambda idea: "pdflegal" in lane_blob(idea) or "metamorphic" in lane_blob(idea) or bool(idea.get("datasetEvolutionLane")))
            add(lambda idea: "outside_residual_envelope" in lane_blob(idea) or "mechanism_breakout" in lane_blob(idea))
            add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R3")
            add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R2")
            add(lambda idea: "combination" in lane_blob(idea) or "synergy" in lane_blob(idea))
            add(lambda idea: bool(idea.get("escapeLane")) or "objective_reframe" in lane_blob(idea) or "online_submission_revalidation" in lane_blob(idea))
        if not witness_saturated and not global_active:
            add(lambda idea: bool(idea.get("requiresCounterfactualWitness")) or str(idea.get("attackTrack") or "") == "witness-main")
        else:
            add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R3")
            add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R2")
            add(lambda idea: bool(idea.get("controlledRiskLane")) or bool(idea.get("riskOverride")))
            add(lambda idea: bool(idea.get("escapeLane")) or str(idea.get("noveltyClass") or "") in ("objective_reframe", "mechanism_breakout"))
        add(lambda idea: bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")))
        add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R2")
        add(lambda idea: bool(idea.get("architectureBreakoutLane")) and str(idea.get("riskLevel") or "").upper() == "R3")
        add(lambda idea: bool(idea.get("controlledRiskLane")) or bool(idea.get("riskOverride")))
        add(lambda idea: str(idea.get("attackTrack") or "") == "witness-support")
        add(lambda idea: bool(idea.get("datasetEvolutionLane")) or "dataset_evolution" in str(idea.get("lane", "")))
        add(lambda idea: "gatekeeper" in str(idea.get("lane", "")) and bool(idea.get("allowsHighVariance")))
        add(lambda idea: bool(idea.get("stagnationLane")) and bool(idea.get("requiresNewArtifact")))
        add(lambda idea: bool(idea.get("stagnationLane")) and idea.get("noveltyClass") == "enumeration")
        add(lambda idea: bool(idea.get("stagnationLane")) and idea.get("noveltyClass") == "mechanism_breakout")
        add(
            lambda idea: (
                ("discriminator" in str(idea.get("lane", "")) or "forensics" in str(idea.get("lane", "")))
                and str(idea.get("lane", "")) not in STAGNATION_REPEATED_LANES
            )
        )
    else:
        add(lambda idea: bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")))
        add(lambda idea: "discriminator" in str(idea.get("lane", "")) or "forensics" in str(idea.get("lane", "")))
        add(lambda idea: "proxy" in str(idea.get("lane", "")) or "generator" in str(idea.get("lane", "")))
        add(lambda idea: bool(idea.get("datasetEvolutionLane")) or "dataset_evolution" in str(idea.get("lane", "")))
        add(lambda idea: "gatekeeper" in str(idea.get("lane", "")) or str(idea.get("workerType")) == "review")
        add(lambda idea: str(idea.get("workerType")) in ("edit", "edit-or-proposal") and idea.get("direction_state") != "exploit")
        add(lambda idea: idea.get("direction_state") == "exploit")

    remaining = [idea for idea in ideas if idea not in selected and scores.get(str(idea.get("lane")), {}).get("decision") == "selectable"]
    remaining.sort(key=lambda item: scores.get(str(item.get("lane")), {}).get("score", 0), reverse=True)
    repeated_standard_added = len([idea for idea in selected if str(idea.get("lane") or "") in STAGNATION_REPEATED_LANES])
    local_envelope_added = len([idea for idea in selected if is_local_envelope_lane(idea) and not is_global_breakout_lane(idea)])
    for idea in remaining:
        if len(selected) >= max_lanes:
            break
        if global_active and is_local_envelope_lane(idea) and not is_global_breakout_lane(idea):
            if idea in selected or is_repeated_local_lane(idea):
                continue
            if not is_allowed_global_support_lane(idea):
                continue
            if local_envelope_added >= max_local_envelope:
                continue
            local_envelope_added += 1
        if stagnation_active and str(idea.get("lane") or "") in STAGNATION_REPEATED_LANES:
            if repeated_standard_added >= 1:
                continue
            repeated_standard_added += 1
        if stagnation_active and str(idea.get("workerType")) in ("edit", "edit-or-proposal"):
            current_edit_count = len(
                [item for item in selected if str(item.get("workerType")) in ("edit", "edit-or-proposal")]
            )
            edit_limit = 4 if stagnation_active else 2
            if current_edit_count >= edit_limit:
                continue
        selected.append(idea)
    return selected[:max_lanes]


def build_attack_thesis(selected: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the selected portfolio without forcing a fixed 044/witness thesis."""
    lanes = [str(item.get("lane") or "") for item in selected if isinstance(item, dict)]
    global_breakout_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict)
        and any(
            token in " ".join(
                str(value or "").lower()
                for value in (
                    item.get("lane"),
                    item.get("hypothesis"),
                    item.get("changed_mechanism"),
                    item.get("hidden_shape"),
                    item.get("noveltyClass"),
                )
            )
            for token in GLOBAL_BREAKOUT_LANE_TOKENS
        )
    ]
    local_envelope_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict)
        and any(
            token in " ".join(
                str(value or "").lower()
                for value in (
                    item.get("lane"),
                    item.get("hypothesis"),
                    item.get("changed_mechanism"),
                    item.get("hidden_shape"),
                    item.get("noveltyClass"),
                )
            )
            for token in LOCAL_OPTIMUM_LANE_TOKENS
        )
        and str(item.get("lane") or "") not in global_breakout_lanes
    ]
    witness_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict)
        and (
            bool(item.get("requiresCounterfactualWitness"))
            or str(item.get("attackTrack") or "").startswith("witness")
            or "counterfactual" in str(item.get("lane") or "").lower()
        )
    ]
    risk_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict)
        and (
            str(item.get("attackTrack") or "") == "risk-sidecar"
            or bool(item.get("controlledRiskLane"))
            or bool(item.get("architectureBreakoutLane"))
            or bool(item.get("riskOverride"))
        )
    ]
    architecture_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict) and architecture_breakout_lane(item)
    ]
    online_exploit_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict) and online_confirmed_exploit_lane(item)
    ]
    dataset_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict) and (bool(item.get("datasetEvolutionLane")) or "dataset" in str(item.get("lane") or ""))
    ]
    escape_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict) and (bool(item.get("escapeLane")) or "objective_reframe" in str(item.get("lane") or ""))
    ]
    support_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if isinstance(item, dict)
        and str(item.get("lane") or "") not in set(witness_lanes)
        and str(item.get("lane") or "") not in set(risk_lanes)
        and str(item.get("lane") or "") not in set(dataset_lanes)
        and str(item.get("lane") or "") not in set(escape_lanes)
    ]
    if global_breakout_lanes and len(global_breakout_lanes) >= max(2, len(local_envelope_lanes)):
        name = "global breakout portfolio"
        goal = "Keep a live global view when the 044 residual neighborhood is exhausted: spend the main worker budget outside the local residual/same-case basin."
        main_track = "outside-envelope mechanism, dataset/proxy materialization, architecture/moonshot, fusion, or objective/online reframe"
        sidecar_track = "at most one residual/same-case support lane, used only to calibrate or falsify the global pivot"
        pivot_rule = "If a lane only produces another local empty witness or pure residual-neighbor tweak, freeze that causal variable and replace it with a different subsystem, fold, or objective hypothesis."
    elif escape_lanes:
        name = "hidden-objective reframe portfolio"
        goal = "Change the search objective when recent evidence says the old local gradient is stale; turn the reframe into one executable next epoch."
        main_track = "objective reframe, online calibration, or dataset decision"
        sidecar_track = "bounded architecture/mutation probe if source/workspace safety is clean"
        pivot_rule = "If the reframe only restates old residual/witness work, reject it and dispatch an architecture or search-policy lane instead."
    elif len(architecture_lanes) >= max(1, len(witness_lanes)):
        name = "architecture breakout portfolio"
        goal = "Sample a different solver/search-policy basin with isolated first-kill probes while preserving strict promotion gates."
        main_track = "architecture or search-policy mutation pressure"
        sidecar_track = "targeted witness, discriminator, or online-confirmed exploit support only when it sharpens the architecture test"
        pivot_rule = "If architecture probes are flat twice, change the solver subsystem or scorer surrogate, not another threshold around the same subsystem."
    elif online_exploit_lanes and len(online_exploit_lanes) >= len(witness_lanes):
        name = "online-confirmed exact-neighbor exploit portfolio"
        goal = "Exploit a real online-positive mechanism by probing exact neighboring shapes, without turning the proven signal into broad guard widening."
        main_track = "forensic-before-patch exact-neighbor exploit"
        sidecar_track = "architecture or validation lane may run beside it but cannot replace the forensic proof"
        pivot_rule = "If the exact-neighbor forensic is flat, reject that neighbor and choose a new mechanism or architecture lane."
    elif dataset_lanes and len(dataset_lanes) > len(risk_lanes):
        name = "validation repair portfolio"
        goal = "Make the offline fold more predictive of the online hidden fold before spending promotion or upload budget."
        main_track = "dataset/proxy/negative-control calibration"
        sidecar_track = "small code probe only if it tests the new validation claim"
        pivot_rule = "If generated proxies cannot rank online-positive above neutral/down records, freeze or reject them instead of adding more cases."
    elif witness_lanes:
        name = "counterfactual evidence portfolio"
        goal = "Produce same-case scorer-moving evidence or a bounded empty-search proof, while keeping mutation pressure alive when safe."
        main_track = "counterfactual witness or component-delta evidence"
        sidecar_track = "bounded architecture/mutation lane that does not wait for perfect evidence"
        pivot_rule = "If witness lanes produce no case/flow/component-delta witness for two epochs, demote witness to support and pivot to architecture/objective/search-policy lanes."
    else:
        name = "mechanism divergence portfolio"
        goal = "Test distinct causal mechanisms under a strict execution harness, then keep only current evidence or reusable negative lessons."
        main_track = "independent mechanism probes"
        sidecar_track = "validation or runtime support only as needed"
        pivot_rule = "If selected mechanisms are flat, change the causal family instead of polishing the same local proxy."
    return {
        "name": name,
        "goal": goal,
        "mainTrack": main_track,
        "sidecarTrack": sidecar_track,
        "selectedLanes": lanes,
        "globalBreakoutLanes": global_breakout_lanes,
        "localEnvelopeLanes": local_envelope_lanes,
        "witnessLanes": witness_lanes,
        "riskSidecarLanes": risk_lanes,
        "architectureLanes": architecture_lanes,
        "onlineConfirmedExploitLanes": online_exploit_lanes,
        "datasetLanes": dataset_lanes,
        "escapeLanes": escape_lanes,
        "supportLanes": support_lanes,
        "pivotRule": pivot_rule,
    }


def validation_thesis_for_idea(idea: dict[str, Any], online_items: list[dict[str, Any]]) -> dict[str, Any]:
    family = str(idea.get("affected_family") or "unknown")
    mechanism = str(idea.get("changed_mechanism") or "unknown")
    shape = str(idea.get("hidden_shape") or "unknown")
    positives = [
        str(item.get("attempt") or item.get("shape") or "")
        for item in online_items
        if isinstance(item, dict) and item.get("actual") == "up"
    ]
    neutral_down = [
        str(item.get("attempt") or item.get("shape") or "")
        for item in online_items
        if isinstance(item, dict) and item.get("actual") in ("neutral", "down")
    ]
    local_fold = "same-case component-delta witness"
    if idea.get("datasetEvolutionLane") or "dataset" in str(idea.get("lane") or "").lower():
        local_fold = "dynamic proxy/dataset candidate fold"
    elif idea.get("architectureBreakoutLane") or idea.get("controlledRiskLane") or idea.get("workerType") in ("edit", "edit-or-proposal"):
        local_fold = "first-kill scorer fold plus parent promotion gate"
    elif idea.get("requiresCounterfactualWitness") or "counterfactual" in str(idea.get("lane") or "").lower():
        local_fold = "same-case counterfactual witness fold"
    return {
        "family": family,
        "mechanism": mechanism,
        "shape": shape,
        "localFold": local_fold,
        "onlineFoldRole": "calibrate-after-submission",
        "positiveRecordsToPreserve": positives[-3:],
        "neutralOrDownRecordsToReject": neutral_down[-4:],
        "trustClaim": (
            f"Local evidence is useful only if {local_fold} predicts movement for {family}/{mechanism}/{shape} "
            "without reproducing known online-neutral decoys."
        ),
        "falsifier": (
            "Downgrade this fold/mechanism if the candidate improves locally but ties/regresses online, "
            "or if negative controls rank it above an online-positive baseline."
        ),
    }


def convergence_review(
    ideas: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    scores: dict[str, dict[str, Any]],
    max_lanes: int,
) -> dict[str, Any]:
    selected_lanes = {str(item.get("lane") or "") for item in selected}
    freeform = [item for item in ideas if bool(item.get("freeformDivergence"))]
    template_selected = [
        str(item.get("lane") or "")
        for item in selected
        if not bool(item.get("freeformDivergence"))
    ]
    rejected_freeform: list[dict[str, Any]] = []
    for idea in freeform:
        lane = str(idea.get("lane") or "")
        if lane in selected_lanes:
            continue
        score = scores.get(lane, {})
        rejected_freeform.append(
            {
                "lane": lane,
                "expertRole": idea.get("expertRole"),
                "score": score.get("score", 0),
                "decision": score.get("decision"),
                "whyNotSelected": (
                    "lower convergence score or duplicate family/mechanism after higher-ranked freeform lanes"
                    if score.get("decision") == "selectable"
                    else "failed convergence scoring"
                ),
                "risks": score.get("risks", []),
            }
        )
    rejected_freeform.sort(key=lambda item: item.get("score", 0), reverse=True)
    witness_lanes = [
        str(item.get("lane") or "")
        for item in selected
        if bool(item.get("requiresCounterfactualWitness")) or str(item.get("attackTrack") or "").startswith("witness")
    ]
    risk_sidecars = [
        str(item.get("lane") or "")
        for item in selected
        if str(item.get("attackTrack") or "") == "risk-sidecar"
        or bool(item.get("controlledRiskLane"))
        or bool(item.get("architectureBreakoutLane"))
    ]
    attack_thesis = build_attack_thesis(selected)
    return {
        "policy": "diverge widely first, then converge by online explanation, novelty, non-duplication, smallest decisive test, and harness recoverability",
        "attackThesis": attack_thesis,
        "witnessMainLanes": witness_lanes,
        "riskSidecarLanes": risk_sidecars,
        "convergenceTarget": attack_thesis.get("goal") or "select a coherent portfolio without converting soft guidance into hard gates",
        "freeformPoolCount": len(freeform),
        "selectedFreeformCount": len([item for item in selected if bool(item.get("freeformDivergence"))]),
        "selectedTemplateCount": len(template_selected),
        "selectedTemplateLanes": template_selected,
        "targetFreeformShare": ">=50% of selected lanes when enough freeform candidates exist",
        "maxLanes": max_lanes,
        "rejectedFreeformTop": rejected_freeform[:8],
        "templateUseRule": "Template lanes may provide harness pressure or 044 confirmation, but they should not dominate selectedLanes when viable freeform ideas exist.",
    }


def idea_board_quality_gate(
    selected: list[dict[str, Any]],
    idea_scores: dict[str, dict[str, Any]],
    stagnation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane_names = " ".join(str(idea.get("lane") or "") for idea in selected).lower()
    edit_count = len([idea for idea in selected if str(idea.get("workerType")) in ("edit", "edit-or-proposal")])
    exploit_count = len([idea for idea in selected if idea.get("direction_state") == "exploit"])
    selected_scores = [idea_scores.get(str(idea.get("lane")), {}).get("score", 0) for idea in selected]
    stagnation_active = bool(isinstance(stagnation, dict) and stagnation.get("active"))
    witness_saturated = bool(isinstance(stagnation, dict) and stagnation.get("witnessSaturated"))
    harness_checks = [lane.get("killCondition") and lane.get("smallestDecisiveTest") for lane in selected]
    has_gatekeeper_or_harness = (
        "gatekeeper" in lane_names
        or all(bool(item) for item in harness_checks)
    )
    has_discriminator = "discriminator" in lane_names or "forensics" in lane_names
    has_counterfactual_witness = any(
        bool(idea.get("requiresCounterfactualWitness"))
        or str(idea.get("attackTrack") or "").startswith("witness")
        or "counterfactual" in str(idea.get("lane") or "").lower()
        for idea in selected
    )
    has_dataset_evolution = "dataset_evolution" in lane_names or any(bool(idea.get("datasetEvolutionLane")) for idea in selected)
    if stagnation_active:
        has_discriminator = (
            has_discriminator
            or "adversarial_proxy" in lane_names
            or "small_enumerator" in lane_names
            or has_counterfactual_witness
            or any(bool(idea.get("datasetDecisionLane")) for idea in selected)
        )
    checks = [
        {"name": "has_online_discriminator_or_forensics", "passed": has_discriminator},
        {
            "name": "has_proxy_generator_or_dataset_when_available",
            "passed": "proxy" in lane_names or "generator" in lane_names or has_dataset_evolution or stagnation_active,
        },
        {
            "name": "dataset_lane_optional_but_tracked",
            "passed": True,
            "detail": "dataset-evolution is valuable, but it must not block exploit/architecture search by itself",
        },
        {"name": "harness_guard_present", "passed": has_gatekeeper_or_harness},
        {"name": "edit_lane_budget", "passed": edit_count <= (5 if stagnation_active else 3)},
        {
            "name": "exploit_lanes_allowed_if_distinct",
            "passed": exploit_count <= (3 if stagnation_active else 2),
        },
        {
            "name": "minimum_quality_advisory",
            "passed": bool(selected_scores) and min(selected_scores) >= 18,
            "detail": "Low idea score lowers confidence but is not a hard gate when the lane has a hypothesis, stop condition, isolation, and result contract.",
        },
    ]
    if stagnation_active:
        novel_count = len(
            [
                idea
                for idea in selected
                if bool(idea.get("stagnationLane")) or bool(str(idea.get("noveltyClass") or "").strip())
            ]
        )
        global_perspective = stagnation.get("globalPerspective", {}) if isinstance(stagnation, dict) else {}
        global_active = bool(isinstance(global_perspective, dict) and global_perspective.get("active"))
        selected_lane_blobs = [
            " ".join(
                str(value or "").lower()
                for value in (
                    idea.get("lane"),
                    idea.get("hypothesis"),
                    idea.get("changed_mechanism"),
                    idea.get("hidden_shape"),
                    idea.get("noveltyClass"),
                )
            )
            for idea in selected
        ]
        global_breakout_count = len(
            [text for text in selected_lane_blobs if any(token in text for token in GLOBAL_BREAKOUT_LANE_TOKENS)]
        )
        local_envelope_count = len(
            [
                text
                for text in selected_lane_blobs
                if any(token in text for token in LOCAL_OPTIMUM_LANE_TOKENS)
                and not any(token in text for token in GLOBAL_BREAKOUT_LANE_TOKENS)
            ]
        )
        min_global_breakout = int(global_perspective.get("minGlobalBreakoutLanes") or 0) if isinstance(global_perspective, dict) else 0
        max_local_envelope = int(global_perspective.get("maxLocalEnvelopeLanes") or 99) if isinstance(global_perspective, dict) else 99
        required_novel = max(1, math.ceil(len(selected) * 0.33)) if selected else 1
        artifact_count = len([idea for idea in selected if bool(idea.get("requiresNewArtifact"))])
        controlled_risk_count = len([idea for idea in selected if bool(idea.get("controlledRiskLane")) or bool(idea.get("riskOverride"))])
        architecture_count = len([idea for idea in selected if bool(idea.get("architectureBreakoutLane"))])
        repeated_standard_count = len([idea for idea in selected if str(idea.get("lane") or "") in STAGNATION_REPEATED_LANES])
        gatekeeper_items = [
            idea
            for idea in selected
            if "gatekeeper" in str(idea.get("lane", "")).lower() or str(idea.get("workerType")) == "review"
        ]
        checks.extend(
            [
                {"name": "stagnation_has_novel_lane", "passed": novel_count >= required_novel},
                {
                    "name": "stagnation_has_counterfactual_witness_track",
                    "passed": has_counterfactual_witness or witness_saturated,
                    "detail": (
                        "counterfactual work is useful when it is fresh; when witnessSaturated=true, absence of a witness lane is an intentional pivot signal"
                    ),
                },
                {"name": "stagnation_new_artifact_optional", "passed": True, "detail": f"artifact lanes selected={artifact_count}"},
                {"name": "stagnation_has_mutation_or_architecture_pressure", "passed": controlled_risk_count >= 1 or architecture_count >= 1},
                {"name": "stagnation_architecture_lane_encouraged", "passed": True, "detail": f"architecture lanes selected={architecture_count}"},
                {"name": "stagnation_repeated_standard_lanes_limited", "passed": repeated_standard_count <= 2},
                {
                    "name": "stagnation_gatekeeper_allows_bounded_exploration",
                    "passed": (not gatekeeper_items) or any(bool(idea.get("allowsHighVariance")) for idea in gatekeeper_items),
                },
            ]
        )
        if global_active:
            checks.extend(
                [
                    {
                        "name": "global_perspective_breakout_budget",
                        "passed": global_breakout_count >= min_global_breakout,
                        "detail": f"globalBreakout={global_breakout_count}, required={min_global_breakout}",
                    },
                    {
                        "name": "global_perspective_local_lane_cap",
                        "passed": local_envelope_count <= max_local_envelope,
                        "detail": f"localEnvelope={local_envelope_count}, max={max_local_envelope}",
                    },
                ]
            )
        if int(stagnation.get("escapeLevel") or 0) >= 2:
            checks.append(
                {
                    "name": "stagnation_second_order_escape_lane",
                    "passed": any(bool(idea.get("escapeLane")) for idea in selected),
                }
            )
            dataset_backlog = stagnation.get("datasetDecisionBacklog", {}) if isinstance(stagnation, dict) else {}
            if int(dataset_backlog.get("validatedBacklogCount") or 0) > 0:
                checks.append(
                    {
                        "name": "stagnation_dataset_decision_backlog_lane",
                        "passed": any(bool(idea.get("datasetDecisionLane")) for idea in selected),
                    }
                )
    for check in checks:
        check.setdefault("severity", "advisory")
    hard_checks = [
        {
            "name": "selected_lanes_nonempty",
            "passed": bool(selected),
            "severity": "hard",
            "detail": "An epoch needs at least one owned lane to dispatch and recover.",
        },
        {
            "name": "selected_lanes_have_stop_conditions",
            "passed": all(bool(item) for item in harness_checks) if selected else False,
            "severity": "hard",
            "detail": "Every selected lane needs a smallestDecisiveTest and killCondition so execution is bounded.",
        },
    ]
    checks = hard_checks + checks
    hard_failed = [
        str(item.get("name") or "")
        for item in checks
        if item.get("severity") == "hard" and not bool(item.get("passed"))
    ]
    advisory_failed = [
        str(item.get("name") or "")
        for item in checks
        if item.get("severity") != "hard" and not bool(item.get("passed"))
    ]
    passed = not hard_failed
    return {
        "passed": passed,
        "hardPassed": passed,
        "hardFailed": hard_failed,
        "advisoryWarnings": advisory_failed,
        "checks": checks,
        "scoreRange": {
            "min": round(min(selected_scores), 4) if selected_scores else 0,
            "max": round(max(selected_scores), 4) if selected_scores else 0,
        },
        "ifFailed": "Fix hard harness checks before dispatch. Advisory warnings steer selection but must not block high-variance exploration by themselves.",
    }


def expert_panel_ideas(
    current_id: str,
    online_items: list[dict[str, Any]],
    stagnation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    neutral_shapes = [
        str(item.get("shape") or item.get("attempt") or "")
        for item in online_items
        if item.get("actual") in ("neutral", "down")
    ]
    positive_shapes = [
        str(item.get("shape") or item.get("attempt") or "")
        for item in online_items
        if item.get("actual") == "up"
    ]
    neutral_hint = ", ".join(item for item in neutral_shapes[-3:] if item) or "post-044 neutral branches"
    positive_hint = ", ".join(item for item in positive_shapes[-3:] if item) or "baseline-044 large-sparse residual signal"
    ideas = [
        {
            "expertRole": "Online Forensics Expert",
            "lane": "online_discriminator-positive_vs_neutral",
            "direction_state": "diagnose",
            "affected_family": "hidden_dataset_fit",
            "changed_mechanism": "online_discriminator",
            "hidden_shape": "positive_vs_neutral_delta",
            "hypothesis": f"Contrast online-positive shapes ({positive_hint}) against online-neutral shapes ({neutral_hint}) and identify the smallest feature that predicts transfer.",
            "whyNow": "Recent local gains have repeatedly tied online-best, so the next gain likely needs a discriminator before more code edits.",
            "requiredContext": [
                "docs/optimization-ledger.json onlineEvaluations",
                "docs/online-offline-weights.json",
                ".docs/project-memory recentUpdates",
            ],
            "smallestDecisiveTest": "Build a compact report over baseline-044 positive cases and 046/047/048 neutral cases; no solver edit required.",
            "killCondition": "If the discriminator cannot separate positive from neutral cases, do not open an exploit lane from it.",
            "expectedArtifact": "diagnostic report plus 2-3 new lane hypotheses",
            "workerType": "diagnostic",
        },
        {
            "expertRole": "Algorithm Mechanism Expert",
            "lane": "mechanism_synthesis-non_jobcount_residual_operator",
            "direction_state": "explore",
            "affected_family": "large_sparse_non_jobcount",
            "changed_mechanism": "new_operator",
            "hidden_shape": "residual_conflict_structure",
            "hypothesis": "Create one new residual repair operator based on conflict structure rather than job-count, phase-count, or flow-count guard widening.",
            "whyNow": "Job-count and phase widening produced local gains that were online-neutral; a new mechanism is needed.",
            "requiredContext": [
                "successful large_sparse residual records",
                "failed/neutral post-044 widening records",
                "src/Solution.cpp current selector/repair operators",
            ],
            "smallestDecisiveTest": "Instrument one residual conflict case and compare current chosen assignment to one structure-aware alternative.",
            "killCondition": "Reject if it only changes a threshold/guard or if online_fit_core/large_sparse_forensics are flat.",
            "expectedArtifact": "minimal patch or proposal with one named target case",
            "workerType": "edit-or-proposal",
        },
        {
            "expertRole": "Benchmark/Data Generator Expert",
            "lane": "hidden_proxy_generator-online_neutral_decoys",
            "direction_state": "diagnose",
            "affected_family": "hidden_dataset_fit",
            "changed_mechanism": "proxy_generator",
            "hidden_shape": "neutral_decoy_suite",
            "hypothesis": "Generate PDF-legal proxy cases that intentionally reproduce local-positive but online-neutral post-044 behavior.",
            "whyNow": "Existing proxy suites accept too many neutral branches as promising.",
            "requiredContext": [
                "online-positive baseline-044 record",
                "online-neutral baseline-046/047/048 records",
                "existing benchmark suite definitions",
            ],
            "smallestDecisiveTest": "Add or temporarily generate 3-5 cases that distinguish baseline-044 from 046/047 without editing solver code.",
            "killCondition": "Reject the generated proxy if it fails to rank online-positive baseline-044 above online-neutral variants.",
            "expectedArtifact": "temporary case generator or benchmark design note",
            "workerType": "diagnostic",
        },
        {
            "expertRole": "Dataset Evolution Expert",
            "lane": "dataset_evolution-online_feedback_to_proxy_candidate",
            "direction_state": "diagnose",
            "affected_family": "offline_dataset_fit",
            "changed_mechanism": "dataset_candidate",
            "hidden_shape": "online_feedback_contrast",
            "hypothesis": (
                f"Convert online-positive shapes ({positive_hint}) and online-neutral/down shapes ({neutral_hint}) "
                "into one datasetCandidate that states what new proxy cases should explain, reject, and eventually gate."
            ),
            "whyNow": "Weights alone do not make the offline suite more predictive; neutral feedback must create or freeze dataset candidates.",
            "requiredContext": [
                "docs/dataset-evolution-ledger.json if present",
                "docs/optimization-ledger.json onlineEvaluations",
                "docs/online-offline-weights.json",
                "tools/benchmark.py current suite boundaries",
            ],
            "smallestDecisiveTest": (
                "Write one datasetCandidate with candidateId, sourceOnlineFeedback, caseFamily, caseShape, "
                "explainsPositive, rejectsNeutralOrNegative, artifactPaths or generatedCaseFacts, and promotionGateImpact."
            ),
            "killCondition": "Reject if it cannot name both a positive online record to preserve and a neutral/down record to reject.",
            "expectedArtifact": "datasetCandidate JSON plus generated-case/report evidence",
            "workerType": "diagnostic",
            "datasetEvolutionLane": True,
            "requiresDatasetCandidate": True,
            "requiresNewArtifact": True,
            "noveltyClass": "dataset_evolution",
        },
        {
            "expertRole": "Counterfactual Debugger",
            "lane": "counterfactual_selector-second_best_replay",
            "direction_state": "explore",
            "affected_family": "selector_audit",
            "changed_mechanism": "counterfactual_replay",
            "hidden_shape": "solver_decision_frontier",
            "hypothesis": "Trace key solver selectors and replay the second-best accepted/rejected choice on cases where scorer metrics disagree with internal metrics.",
            "whyNow": "Repeated guard edits suggest the ranking metric, not only the guarded region, may be wrong.",
            "requiredContext": [
                "current Solution.cpp decision points",
                "failed selector/guard attempts",
                "high-value benchmark case reports if present",
            ],
            "smallestDecisiveTest": "Instrument one selector and output top-3 candidate metric deltas on one high-value suite.",
            "killCondition": "Stop if second-best choices never improve scorer metrics on sampled cases.",
            "expectedArtifact": "selector trace and one specific counterfactual mutation candidate",
            "workerType": "diagnostic",
        },
        {
            "expertRole": "Risk/Runtime Gatekeeper",
            "lane": "risk_gatekeeper-duplicate_and_runtime_filter",
            "direction_state": "proposal-only",
            "affected_family": "risk_control",
            "changed_mechanism": "gate",
            "hidden_shape": "epoch_preflight",
            "hypothesis": "Before edit lanes, filter every proposed idea against frozen patterns, active online-unconfirmed branches, and runtime headroom.",
            "whyNow": "The loop has accumulated many failed guard/selector variants and worker churn.",
            "requiredContext": [
                "frozenPatterns",
                "failedExperiments avoidNextTime",
                "doctor/status/active pool state",
            ],
            "smallestDecisiveTest": "Produce a reject/allow matrix for the current idea board; no solver edit.",
            "killCondition": "Any idea without a one-suite kill condition is rejected before dispatch.",
            "expectedArtifact": "preflight matrix",
            "workerType": "review",
        },
        {
            "expertRole": "Exploit Strategist",
            "lane": "exploit_strategist-minimal_confirmed_signal_extension",
            "direction_state": "exploit",
            "affected_family": "large_sparse",
            "changed_mechanism": "minimal_extension",
            "hidden_shape": "confirmed_residual_signal",
            "hypothesis": "Try exactly one minimal extension of the online-confirmed baseline-044 residual signal, but only after a discriminator names the target shape.",
            "whyNow": "baseline-044 is the active online-best and the only recent positive signal.",
            "requiredContext": [
                "best-known online baseline record",
                "online-offline weights",
                "large_sparse successful/neutral attempts",
            ],
            "smallestDecisiveTest": "One named target forensic case plus online_fit_core non-regression.",
            "killCondition": "Reject if the idea broadens job-count/phase-count without a new named target.",
            "expectedArtifact": "single-cause patch candidate or rejection",
            "workerType": "edit",
        },
        {
            "expertRole": "044 Exploit Specialist",
            "lane": "online_confirmed_exploit-044_style_forensic_before_patch",
            "direction_state": "exploit",
            "affected_family": "large_sparse",
            "changed_mechanism": "online_confirmed_exact_neighbor_probe",
            "hidden_shape": "online_positive_neighbor_shape",
            "hypothesis": (
                "Reproduce the baseline-044 success pattern: start from an online-confirmed positive mechanism, "
                "pick one exact neighboring shape, prove with a temporary forensic comparator that the output/scorer moves, "
                "then apply only the minimal single-cause patch."
            ),
            "whyNow": "baseline-044 succeeded because a sharp phase6/4096 forensic probe preceded a one-line exact guard; the loop should keep this exploit path alive while broader architecture lanes explore.",
            "requiredContext": [
                "attempt-104/baseline-044 successful ledger record",
                "baseline-036 online-confirmed large_sparse residual repair record",
                "post-044 neutral boundary records 045/046/047/048 as do-not-broaden lessons",
                "current src/Solution.cpp residual/selector code",
            ],
            "smallestDecisiveTest": (
                "Create a temporary comparator over 3-5 exact target cases for one neighboring shape. "
                "Baseline vs candidate must show scorer movement or concrete conflict reduction before the patch is considered."
            ),
            "killCondition": (
                "Stop as rejected if the forensic comparator is flat, if the candidate broadens more than one dimension, "
                "or if the patch is not single-cause."
            ),
            "expectedArtifact": "temporary forensic comparator/report plus minimal single-cause patch or rejection",
            "workerType": "edit",
            "onlineConfirmedExploitLane": True,
            "forensicBeforePatch": True,
            "sourcePositiveSignal": "baseline-044-large-sparse-phase6-residual-target",
            "exactTargetRule": "one neighboring shape, one mechanism, forensic evidence before patch",
            "doNotBroaden": [
                "phase>=6 without exact target",
                "jobCount boundary widening without online-confirmed discriminator",
                "phase7/job28 neutral branch",
                "job32 phase6 neutral branch",
                "jobs22 leaf-band/capacity-shadow neutral branch",
            ],
            "noveltyClass": "online_confirmed_exploit",
            "riskLevel": "R1",
        },
    ]
    if isinstance(stagnation, dict) and stagnation.get("active"):
        for idea in ideas:
            if idea.get("lane") == "risk_gatekeeper-duplicate_and_runtime_filter":
                idea["allowsHighVariance"] = True
                idea["hypothesis"] = (
                    "Filter duplicates and runtime risks, but must allow at least one bounded high-variance "
                    "new-artifact/enumeration lane instead of vetoing all mutation."
                )
                idea["killCondition"] = (
                    "Reject only lanes that repeat known frozen mechanisms or lack a smallest decisive test; "
                    "do not block every stagnationLane."
                )
        ideas.extend(
            [
                {
                    "expertRole": "Objective Reframe Lead",
                    "lane": "global_objective_reframe-hidden_score_axis_audit",
                    "direction_state": "diagnose",
                    "affected_family": "global_search_policy",
                    "changed_mechanism": "objective_reframe",
                    "hidden_shape": "online_hidden_axis_unknown",
                    "hypothesis": (
                        "Stop assuming the next gain is inside the baseline-044 residual score gradient. Re-rank recent positive, neutral, "
                        "and negative attempts by official scorer components and propose one new non-residual objective axis for the next edit lane."
                    ),
                    "whyNow": "Recent global-looking lanes repeated old names and did not create a promotion path; the coordinator needs a fresh search objective before more code churn.",
                    "requiredContext": [
                        "docs/optimization-ledger.json onlineEvaluations",
                        "docs/search-graph.json recent no-promotion nodes",
                        "docs/failed-diffs-index.json reusable snippets",
                    ],
                    "smallestDecisiveTest": (
                        "Produce a ranking table with at least three candidate hidden axes and pick exactly one next executable target component "
                        "that is not residual_envelope/same_case/counterfactual."
                    ),
                    "killCondition": "Reject if the output only restates large_sparse residual repair or does not name a concrete next target component and first-kill.",
                    "expectedArtifact": "hidden_score_axis_audit.json plus one next mutation row",
                    "workerType": "diagnostic",
                    "stagnationLane": True,
                    "escapeLane": True,
                    "noveltyClass": "objective_reframe",
                    "requiresNewArtifact": True,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Adversarial Fold Validator",
                    "lane": "global_adversarial_proxy-rank_online_records",
                    "direction_state": "diagnose",
                    "affected_family": "hidden_dataset_fit",
                    "changed_mechanism": "adversarial_proxy_ranker",
                    "hidden_shape": "online_record_ordering",
                    "hypothesis": (
                        "Instead of adding more proxy cases, test whether existing and newly materialized PDF/legal cases can rank online-positive "
                        "044/036 above online-neutral 045-051 families. If not, freeze that proxy direction."
                    ),
                    "whyNow": "Proxy generation has produced artifacts, but artifacts have not yet changed selection pressure enough to create promotion candidates.",
                    "requiredContext": [
                        "docs/dataset-evolution-ledger.json promoted/frozen candidates",
                        "docs/optimization-ledger.json online-positive and neutral submissions",
                        "recent metamorphic case artifacts",
                    ],
                    "smallestDecisiveTest": "Create one rank table over at least one positive and two neutral/down online records using available local folds or generated case facts.",
                    "killCondition": "Reject/freeze if the fold cannot rank positives above neutral/down records or if it needs a broad new benchmark run before a rank table exists.",
                    "expectedArtifact": "online_record_proxy_rank_table.json with promote/freeze decision",
                    "workerType": "diagnostic",
                    "stagnationLane": True,
                    "datasetEvolutionLane": True,
                    "noveltyClass": "adversarial_proxy",
                    "requiresNewArtifact": True,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Non-Residual Edit Scout",
                    "lane": "global_nonresidual_edit-leaf_band_or_job_between_probe",
                    "direction_state": "explore",
                    "affected_family": "mechanism_breakout",
                    "changed_mechanism": "nonresidual_leafband_jobbetween_probe",
                    "hidden_shape": "outside_residual_envelope",
                    "hypothesis": (
                        "Make one tiny src/Solution.cpp edit outside the residual acceptance envelope, targeting either leaf-band pressure or job_between/max_global "
                        "rather than phase6 same-case residual movement."
                    ),
                    "whyNow": "The current basin has over-sampled residual selectors and exact neighbors; a small outside-envelope edit can falsify a new subsystem cheaply.",
                    "requiredContext": [
                        "current Solution.cpp non-residual selector or assignment decision point",
                        "failed leaf-band and officialPermutation lessons as negative controls",
                        "baseline-028 hidden_shape positive signal",
                    ],
                    "smallestDecisiveTest": "Patch one non-residual decision point, compile once, and run hidden_shape or online_fit_core as first-kill; run large_sparse only if first-kill moves.",
                    "killCondition": "Reject/revert if the diff touches residual repair acceptance, compiles fail, first-kill is flat/worse, or runtime risk is obvious.",
                    "expectedArtifact": "one non-residual patch or rejected diff lesson",
                    "workerType": "edit",
                    "stagnationLane": True,
                    "architectureBreakoutLane": True,
                    "requiresArchitectureAttempt": True,
                    "riskLevel": "R2",
                    "noveltyClass": "mechanism_breakout",
                    "requiresNewArtifact": False,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Controlled Risk Mutator",
                    "lane": "stagnation_controlled_risk-one_scorer_moving_mutation",
                    "direction_state": "explore",
                    "affected_family": "controlled_risk",
                    "changed_mechanism": "bounded_scorer_moving_mutation",
                    "hidden_shape": "high_variance_micro_patch",
                    "hypothesis": (
                        "Attempt exactly one small src/Solution.cpp mutation that is expected to move a scorer metric, even if Phase A has not "
                        "found a perfect target. Keep the diff tiny, compile once, run one first-kill suite, and return the negative result if it fails."
                    ),
                    "whyNow": "The loop is over-optimized for safe diagnosis; stagnation requires mutation pressure with bounded blast radius.",
                    "requiredContext": [
                        "docs/optimization-ledger.json failedExperiments avoidNextTime",
                        "docs/online-offline-weights.json high-weight families",
                        "current src/Solution.cpp selector/repair decision point chosen by the worker",
                    ],
                    "smallestDecisiveTest": "Patch one decision point, compile, and run exactly one first-kill scorer suite such as online_fit_core or large_sparse_forensics.",
                    "killCondition": "Reject and revert workspace patch if compile fails, the first-kill suite is flat/worse, runtime risk appears, or the diff touches more than one mechanism.",
                    "expectedArtifact": "one attempted mutation diff plus first-kill scorer result",
                    "workerType": "edit",
                    "stagnationLane": True,
                    "controlledRiskLane": True,
                    "riskOverride": True,
                    "requiresMutationAttempt": True,
                    "noveltyClass": "controlled_risk_mutation",
                    "riskBudget": "one-file-one-mechanism-one-suite",
                    "riskLimit": "src/Solution.cpp only; no ledger/package/memory edits; no broad benchmark before first-kill moves",
                    "requiresNewArtifact": False,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Architecture Inventor",
                    "lane": "architecture_breakout-multi_objective_repair_pipeline",
                    "direction_state": "explore",
                    "affected_family": "architecture_breakout",
                    "changed_mechanism": "multi_objective_repair_pipeline",
                    "hidden_shape": "cross_family_hidden_objective",
                    "hypothesis": (
                        "Prototype a different repair pipeline that ranks candidates by a blended scorer surrogate "
                        "(phase-inner, phase-between, max-load, projected global) instead of the current residual-envelope accept/reject cascade."
                    ),
                    "whyNow": "The current cascade is locally optimized around baseline-044 and keeps rediscovering online-neutral guard variants.",
                    "requiredContext": [
                        "current src/Solution.cpp repair pipeline and candidate scoring points",
                        "successful baseline-044 large_sparse residual signal",
                        "failed post-044 guard/selector widening lessons",
                    ],
                    "smallestDecisiveTest": "Change one pipeline decision point, compile, and run one first-kill suite; run a second suite only if the first moves positively.",
                    "killCondition": "Reject and revert if the diff becomes a broad rewrite, touches I/O/scorer, fails compile, or the first-kill suite is flat/worse.",
                    "expectedArtifact": "architectureSummary plus scorer-moving patch or rejected diff lesson",
                    "workerType": "edit",
                    "stagnationLane": True,
                    "architectureBreakoutLane": True,
                    "requiresArchitectureAttempt": True,
                    "riskLevel": "R2",
                    "noveltyClass": "architecture_breakout",
                    "architectureBudget": "one pipeline decision point; up to two first-kill suites if the first is positive",
                    "allowedExperimentScope": "src/Solution.cpp solver internals only; no ledger/package/memory edits; no full/runtime before parent gate",
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Search Policy Hacker",
                    "lane": "architecture_breakout-shadow_assignment_frontier",
                    "direction_state": "explore",
                    "affected_family": "architecture_breakout",
                    "changed_mechanism": "shadow_assignment_frontier",
                    "hidden_shape": "alternative_candidate_frontier",
                    "hypothesis": (
                        "Prototype a small shadow-assignment frontier that keeps 2-3 plausible alternative legal moves before final selection, "
                        "so the solver can escape the current greedy residual choice without another hard-coded shape guard."
                    ),
                    "whyNow": "Several failures suggest the chosen frontier, not only the guard predicate, may be too narrow.",
                    "requiredContext": [
                        "Counterfactual selector lessons",
                        "failed single-flow second-best replay lesson",
                        "current candidate construction and rollback code",
                    ],
                    "smallestDecisiveTest": "Keep the frontier bounded, compile, and run one first-kill suite that can reveal scorer movement.",
                    "killCondition": "Reject and revert if the frontier grows unbounded, runtime risk is obvious, or first-kill score is flat/worse.",
                    "expectedArtifact": "bounded frontier patch or concrete rejection lesson",
                    "workerType": "edit",
                    "stagnationLane": True,
                    "architectureBreakoutLane": True,
                    "requiresArchitectureAttempt": True,
                    "riskLevel": "R2",
                    "noveltyClass": "search_policy_breakout",
                    "architectureBudget": "one bounded frontier, max 3 alternatives, compile once",
                    "allowedExperimentScope": "src/Solution.cpp solver internals only; no generated benchmark artifacts required",
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Moonshot Architect",
                    "lane": "architecture_moonshot-two_stage_solver_variant",
                    "direction_state": "explore",
                    "affected_family": "moonshot_architecture",
                    "changed_mechanism": "two_stage_solver_variant",
                    "hidden_shape": "unknown_hidden_distribution",
                    "hypothesis": (
                        "Build one isolated two-stage solver variant: first produce a legality-safe baseline assignment, then run a bounded local repair pass "
                        "that optimizes the official scorer terms directly rather than patching the existing residual operator."
                    ),
                    "whyNow": "If baseline-044 is a local basin, a moonshot variant is needed to sample a different basin instead of polishing the same one.",
                    "requiredContext": [
                        "official PDF legality rules",
                        "current baseline output legality checks",
                        "runtime_sparse_history_max risk lesson",
                    ],
                    "smallestDecisiveTest": "Implement only a tiny two-stage variant hook, compile, and run quick or hidden_shape as first-kill.",
                    "killCondition": "Reject and revert if compile fails, legality breaks, runtime risk is clear, or first-kill score collapses.",
                    "expectedArtifact": "moonshot architectureSummary with diff, first-kill score, and rollback lesson",
                    "workerType": "edit",
                    "stagnationLane": True,
                    "architectureBreakoutLane": True,
                    "requiresArchitectureAttempt": True,
                    "riskLevel": "R3",
                    "noveltyClass": "moonshot_architecture",
                    "architectureBudget": "one isolated hook or alternate pass; no full rewrite; no parent promotion without full gate",
                    "allowedExperimentScope": "workspace-only src/Solution.cpp; may be ugly/prototype-grade if easy to revert",
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Adversarial Proxy Builder",
                    "lane": "stagnation_adversarial_proxy-new_pdf_legal_cases",
                    "direction_state": "diagnose",
                    "affected_family": "hidden_dataset_fit",
                    "changed_mechanism": "adversarial_proxy_generator",
                    "hidden_shape": "new_pdf_legal_cases",
                    "hypothesis": (
                        "Create a new PDF-legal adversarial generator/report with 3-5 cases that rank the "
                        "online-positive baseline-044 envelope above online-neutral phase7/job32/jobs22 branches."
                    ),
                    "whyNow": "Recent proxy-generator lanes only rediscovered known neutral decoys; stagnation requires a new data artifact.",
                    "requiredContext": [
                        "docs/official-pdf-rules.md legality constraints",
                        "docs/optimization-ledger.json onlineEvaluations for 044/046/047/048",
                        "tools/benchmark.py existing suite definitions only as negative examples",
                    ],
                    "smallestDecisiveTest": (
                        "Produce a temporary generator or report listing 3-5 legal cases, expected baseline ranking, "
                        "and why they are not phase7/job32/jobs22 neutral decoys."
                    ),
                    "killCondition": "Reject if no new generated case exists or if the cases only reuse phase7/job32/jobs22 neutral decoys.",
                    "expectedArtifact": "new proxy generator/report with 3-5 PDF-legal adversarial cases",
                    "workerType": "diagnostic",
                    "stagnationLane": True,
                    "noveltyClass": "new_artifact",
                    "requiresNewArtifact": True,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Small Exhaustive Enumerator",
                    "lane": "stagnation_small_enumerator-dominated_solver_choices",
                    "direction_state": "diagnose",
                    "affected_family": "solver_frontier",
                    "changed_mechanism": "small_exhaustive_enumeration",
                    "hidden_shape": "dominated_choice_microcases",
                    "hypothesis": (
                        "Run a tiny exhaustive/enumerative diagnostic to find PDF-legal microcases where the current "
                        "solver's accepted choice is dominated by another legal assignment under the official scorer."
                    ),
                    "whyNow": "The local optimum may be caused by the solver never seeing a better frontier, not by another guard tweak.",
                    "requiredContext": [
                        "docs/official-pdf-rules.md",
                        "current Solution.cpp selector/repair decision points",
                        "recent failed same-phase/source-adjacent swap lessons",
                    ],
                    "smallestDecisiveTest": "One temp script or report over a very small case space that names at least one dominated decision or proves none in scope.",
                    "killCondition": "Reject if enumeration only reproduces an existing benchmark result or requires broad full-suite runs.",
                    "expectedArtifact": "small enumeration script/report with dominated-choice evidence",
                    "workerType": "diagnostic",
                    "stagnationLane": True,
                    "noveltyClass": "enumeration",
                    "requiresNewArtifact": True,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Mechanism Breakout Expert",
                    "lane": "stagnation_mechanism_breakout-outside_residual_envelope",
                    "direction_state": "explore",
                    "affected_family": "mechanism_breakout",
                    "changed_mechanism": "outside_residual_envelope",
                    "hidden_shape": "non_baseline044_hidden_shape",
                    "hypothesis": (
                        "Explore one mechanism outside the baseline-044 residual envelope, such as officialPermutation "
                        "selector evidence, leaf-band bounded repair, or capacity interaction, only if backed by a new target artifact."
                    ),
                    "whyNow": "Repeated same-envelope Phase A work is safe but no longer creates a new gradient.",
                    "requiredContext": [
                        "frozenPatterns for failed officialPermutation/history/source-recolor variants",
                        "successful baseline-028 hidden_shape and baseline-036/044 large_sparse records",
                        "new artifact produced by adversarial proxy or enumeration lane if available",
                    ],
                    "smallestDecisiveTest": "Name one non-residual target case and run only its first-kill diagnostic before any broad benchmark.",
                    "killCondition": "Reject if the mechanism is just another post-residual selector without new target evidence.",
                    "expectedArtifact": "one bounded mechanism patch/proposal tied to a new target artifact",
                    "workerType": "edit-or-proposal",
                    "stagnationLane": True,
                    "architectureBreakoutLane": True,
                    "requiresArchitectureAttempt": True,
                    "riskLevel": "R2",
                    "noveltyClass": "mechanism_breakout",
                    "architectureBudget": "one non-residual mechanism, first-kill scorer before broad benchmarks",
                    "allowedExperimentScope": "workspace-only src/Solution.cpp; may return architecture proposal only if source safety blocks patching",
                    "requiresNewArtifact": False,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
                {
                    "expertRole": "Promotion Candidate Revalidator",
                    "lane": "stagnation_revalidate-tiny_positive_2140_candidate",
                    "direction_state": "exploit",
                    "affected_family": "large_sparse",
                    "changed_mechanism": "promotion_revalidation",
                    "hidden_shape": "post_residual_smoothing_tiny_positive",
                    "hypothesis": (
                        "Re-open exactly one prior tiny positive candidate from epoch-20260526-2140, require online_fit_core "
                        "baseline delta plus normal parent-gate evidence, and either promote or permanently freeze it."
                    ),
                    "whyNow": "One tiny local positive was rejected as under-evidenced; stagnation should close that loop once instead of rediscovering it.",
                    "requiredContext": [
                        "epoch-20260526-2140-autonomous child_result for exploit_strategist",
                        "baseline-044 source hash and online-best metadata",
                        "parent gate command list",
                    ],
                    "smallestDecisiveTest": "Apply or reconstruct only that candidate, then run online_fit_core and large_sparse_forensics before any broader gate.",
                    "killCondition": "Reject and freeze if online_fit_core is flat/worse, if the diff is not the same single-cause candidate, or if runtime risk rises.",
                    "expectedArtifact": "revalidation report with parent-gate go/no-go, not automatic promotion",
                    "workerType": "edit-or-proposal",
                    "stagnationLane": True,
                    "noveltyClass": "revalidation",
                    "requiresNewArtifact": False,
                    "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                },
            ]
        )
        if int(stagnation.get("escapeLevel") or 0) >= 2:
            dataset_backlog = stagnation.get("datasetDecisionBacklog", {}) if isinstance(stagnation, dict) else {}
            if int(dataset_backlog.get("validatedBacklogCount") or 0) > 0:
                ideas.append(
                    {
                        "expertRole": "Dataset Arbiter",
                        "lane": "stagnation_escape-dataset_candidate_decision_backlog",
                        "direction_state": "diagnose",
                        "affected_family": "hidden_dataset_fit",
                        "changed_mechanism": "candidate_decision",
                        "hidden_shape": "validated_backlog",
                        "hypothesis": (
                            "The loop is stuck because validated dataset candidates are accumulating without being promoted, frozen, rejected, or merged. "
                            "Forcing a decision should sharpen future offline gates more than generating another proxy-only artifact."
                        ),
                        "whyNow": "Validated dataset candidates exist while recent stagnation closeouts produced no parent-gate path.",
                        "requiredContext": [
                            "docs/dataset-evolution-ledger.json",
                            "recent epoch_closeout.json files",
                            "docs/optimization-ledger.json onlineEvaluations",
                        ],
                        "smallestDecisiveTest": (
                            "Cluster validated candidates by causal shape and recommend exactly one action per cluster: promote, freeze, reject, or merge."
                        ),
                        "killCondition": "Reject if the output only restates candidates without a decision table and next command list.",
                        "expectedArtifact": "dataset decision table plus proposed dataset-promote/dataset-promote --freeze commands",
                        "workerType": "review",
                        "stagnationLane": True,
                        "escapeLane": True,
                        "datasetDecisionLane": True,
                        "noveltyClass": "dataset_decision",
                        "requiresNewArtifact": True,
                        "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                    }
                )
            ideas.extend(
                [
                    {
                        "expertRole": "Objective Reframer",
                        "lane": "stagnation_escape-objective_reframe_hidden_objective",
                        "direction_state": "diagnose",
                        "affected_family": "strategy_pivot",
                        "changed_mechanism": "objective_reframe",
                        "hidden_shape": "second_order_stagnation",
                        "hypothesis": (
                            "Reframe the hidden-objective model after stagnation-mode lanes also failed to create a new artifact. "
                            "Name one new proxy family, one online submission/revalidation option, and one family to freeze."
                        ),
                        "whyNow": "Two stagnation-mode epochs without a new artifact means the search problem definition, not only the mutation, is stale.",
                        "requiredContext": [
                            "recent stagnationMode closeouts and their artifact status",
                            "docs/optimization-ledger.json onlineEvaluations",
                            "docs/official-pdf-rules.md",
                        ],
                        "smallestDecisiveTest": "Produce a pivot memo with a new objective model and one concrete next epoch board; no solver edit.",
                        "killCondition": "Reject if the memo only restates baseline-044 residual envelope or repeats standard stagnation lanes.",
                        "expectedArtifact": "objective pivot memo plus next-epoch board sketch",
                        "workerType": "diagnostic",
                        "stagnationLane": True,
                        "escapeLane": True,
                        "noveltyClass": "objective_reframe",
                        "requiresNewArtifact": True,
                        "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                    },
                    {
                        "expertRole": "Online Budget Strategist",
                        "lane": "stagnation_escape-online_submission_revalidation_plan",
                        "direction_state": "proposal-only",
                        "affected_family": "online_budget",
                        "changed_mechanism": "submission_revalidation_plan",
                        "hidden_shape": "second_order_stagnation",
                        "hypothesis": (
                            "Design a minimal online-budget revalidation plan when offline search has no gradient: choose whether to "
                            "resubmit online-best, submit one tiny candidate, or pause submissions until a new artifact exists."
                        ),
                        "whyNow": "Second-order stagnation needs an explicit online-budget decision instead of more local proxy churn.",
                        "requiredContext": [
                            "docs/submission-map.json",
                            "docs/optimization-ledger.json onlineEvaluations",
                            "remaining upload constraints from taskbook/forum notes",
                        ],
                        "smallestDecisiveTest": "Return a yes/no upload recommendation with exact package naming and calibration effect; no package creation.",
                        "killCondition": "Reject if it recommends online spend without a named hypothesis and rollback/calibration rule.",
                        "expectedArtifact": "online revalidation decision memo",
                        "workerType": "review",
                        "stagnationLane": True,
                        "escapeLane": True,
                        "noveltyClass": "online_budget_revalidation",
                        "requiresNewArtifact": True,
                        "allowsHighVariance": True,
                        "forbiddenReuse": stagnation.get("forbiddenReuse", []),
                    },
                ]
            )
    return ideas


def command_idea_board(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    lane_limit = min(int(args.select_lanes), DEFAULT_EPOCH_LANE_LIMIT)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    current_id = str(baseline.get("id", ""))
    counts = failure_counts(ledger)
    space = load_json(mutation_space_path(args.mutation_space))
    frozen_patterns = list(space.get("frozenPatterns", [])) if isinstance(space, dict) else []
    memory_context = project_memory_context(root)
    experience_context = ledger_experience_context(ledger, limit=args.experience_limit)
    search_system = search_system_context(root, limit=args.experience_limit)
    weights = load_or_default_weights(root)
    online_items = recent_online_items(ledger, limit=args.online_limit)
    prefer_044 = bool(getattr(args, "prefer_044_mode", False) or getattr(args, "force_044_mode", False))
    stagnation = stagnation_context(
        root,
        threshold=args.stagnation_threshold,
        force=bool(getattr(args, "force_stagnation", False) or prefer_044),
    )
    ideas = expert_panel_ideas(current_id, online_items, stagnation=stagnation)
    if not getattr(args, "template_only", False):
        ideas = divergent_expert_ideas(
            current_id,
            online_items,
            experience_context,
            stagnation=stagnation,
        ) + cross_branch_fusion_ideas(
            current_id,
            search_system,
            stagnation=stagnation,
        ) + component_ablation_ideas(
            current_id,
            root,
            stagnation=stagnation,
        ) + ideas
    if prefer_044:
        for idea in ideas:
            if bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch")):
                idea["qualityScoreOverrideReason"] = "preferred 044-style online-confirmed exploit mode"
                idea["selectionPriority"] = 100
            elif bool(idea.get("architectureBreakoutLane")) or bool(idea.get("controlledRiskLane")):
                idea["selectionPriority"] = max(int(idea.get("selectionPriority") or 0), 30)
    for idea in ideas:
        idea["based_on"] = current_id
        idea["contextContract"] = {
            "readIfNeeded": [
                ".docs/project-memory/INDEX.md",
                ".docs/project-memory/memory.json",
                ".docs/project-memory/lanes/competition-huawei-nslb.json",
                "docs/optimization-ledger.json",
                "docs/online-offline-weights.json",
                "docs/dataset-evolution-ledger.json",
                "docs/exploration-index.json",
            ],
            "citeIfUsed": idea.get("requiredContext", []),
            "evidenceExpectedWhenAvailable": [
                "which successful lesson this idea builds on, if available in compact context",
                "which failed lesson or frozen pattern it avoids, if available in compact context",
                "which online feedback record it explains, if available in compact context",
                "validation thesis: which local fold should predict online movement and what would falsify it",
                "negative-control check: which online-neutral/down shape this idea should reject or avoid",
            ],
        }
        idea["validationThesis"] = validation_thesis_for_idea(idea, online_items)
        idea["duplicateRisk"] = duplicate_note_for_idea(idea, frozen_patterns, counts)
        idea["whyNotDuplicate"] = (
            "requires a new discriminator/target/proxy before edit"
            if idea["duplicateRisk"] != "no direct duplicate fingerprint"
            else "not a direct repeat of current frozen fingerprints"
        )
        idea["evidenceAnchors"] = evidence_anchors_for_idea(idea, experience_context, online_items)
        idea["allowed_files"] = ["src/Solution.cpp"] if idea["workerType"] in ("edit", "edit-or-proposal") else []
        if not idea.get("commands"):
            idea["commands"] = (
                ["online_fit_core", "hidden_shape", "large_sparse_forensics"]
                if bool(idea.get("architectureBreakoutLane"))
                else ["online_fit_core", "large_sparse_forensics"]
                if idea["workerType"] in ("edit", "edit-or-proposal")
                else ["diagnostic-only"]
            )
    idea_scores = {
        str(idea.get("lane")): idea_quality_score(
            idea,
            counts=counts,
            frozen_patterns=frozen_patterns,
            weights=weights,
            online_items=online_items,
            stagnation=stagnation,
        )
        for idea in ideas
    }
    bandit_signals = bandit_signals_for_ideas(root, ideas)
    for lane_id, signal in bandit_signals.items():
        score_info = dict(idea_scores.get(lane_id, {}))
        if not score_info:
            continue
        score_info["score"] = round(float(score_info.get("score") or 0) + float(signal.get("scoreBoost") or 0), 4)
        score_info["banditSignal"] = signal
        if signal.get("allocationHint") == "exploit-more-workers":
            score_info.setdefault("strengths", []).append("bandit signal favors more workers")
        if signal.get("allocationHint") in ("require-new-causal-variable", "resurrect-with-new-guard"):
            score_info.setdefault("risks", []).append(f"bandit/novelty: {signal.get('allocationHint')}")
        if signal.get("novelty", {}).get("decision") == "duplicate-static-signature":
            score_info["decision"] = "proposal-only"
            score_info.setdefault("hardMissing", []).append("new causal variable for duplicate failed diff signature")
        idea_scores[lane_id] = score_info
    for idea in ideas:
        idea["qualityScore"] = idea_scores.get(str(idea.get("lane")), {})
        idea["banditSignal"] = bandit_signals.get(str(idea.get("lane")), {})
        if prefer_044 and (bool(idea.get("onlineConfirmedExploitLane")) or bool(idea.get("forensicBeforePatch"))):
            boosted_score = dict(idea["qualityScore"])
            boosted_score["score"] = max(float(boosted_score.get("score") or 0), 99.0)
            boosted_score["decision"] = "selectable"
            boosted_score.setdefault("strengths", []).append("preferred 044 mode primary lane")
            idea["qualityScore"] = boosted_score
            idea_scores[str(idea.get("lane"))] = boosted_score
    selected = select_idea_portfolio(
        ideas,
        idea_scores,
        lane_limit,
        stagnation=stagnation,
        freeform_first=not getattr(args, "template_only", False),
    )
    if prefer_044:
        selected = sorted(
            selected,
            key=lambda item: int(item.get("selectionPriority") or 0),
            reverse=True,
        )
    quality_gate = idea_board_quality_gate(selected, idea_scores, stagnation=stagnation)
    review = convergence_review(ideas, selected, idea_scores, lane_limit)
    attack_thesis = review.get("attackThesis", {}) if isinstance(review, dict) else {}
    global_perspective = stagnation.get("globalPerspective", {}) if isinstance(stagnation, dict) else {}
    board = {
        "project": str(root),
        "currentBaseline": current_id,
        "createdAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "principle": "Diverge before dispatch: generate non-template mechanisms first, then converge by evidence and harness safety before worker lanes are opened.",
        "primaryObjective": {
            "name": "Harnessed Grandmaster Exploration",
            "summary": "Explore boldly, execute safely. Constrain execution errors, evidence gaps, shared-state writes, and promotion; do not constrain imagination or mechanism search.",
            "hardConstraints": [
                "source/baseline integrity",
                "isolated worker workspace and absolute patch boundaries",
                "serial shared-state writes",
                "recover every manifest lane",
                "no promotion without current evidence and parent gate",
            ],
            "softConstraints": [
                "role coverage",
                "freeform/template ratio",
                "dataset lane presence",
                "validation thesis clarity",
                "portfolio shape",
                "minimum idea score",
            ],
            "riskEscape": "During stagnation, preserve at least one bounded controlled-risk, architecture, or 044-style exploit lane when source/workspace safety is clean.",
        },
        "mode": "prefer-044-style-online-confirmed-exploit" if prefer_044 else "mutation-matrix-divergent",
        "divergenceMode": {
            "active": not getattr(args, "template_only", False),
            "rule": "Freeform concept-collision ideas are generated before stock lane templates. Selection should keep the search imaginative, then converge using online feedback, duplicate risk, smallest decisive tests, and recoverability.",
            "templateOnly": bool(getattr(args, "template_only", False)),
        },
        "stagnationMode": stagnation,
        "globalPerspective": global_perspective,
        "controlledRiskMode": {
            "active": bool(stagnation.get("active")),
            "rule": "When active, prefer one bounded scorer-moving mutation, architecture, or 044-style exploit lane that may co-dispatch with Phase A diagnostics.",
            "riskLaneBudget": "coordinator choice; one is a safe default, but independent bounded risk lanes may run when workspace/hash/stop-condition/result contracts are clean",
            "riskLimit": "one file, one mechanism, one first-kill scorer suite; no promotion without full parent gate",
        },
        "innovationMode": {
            "active": bool(stagnation.get("active")),
            "rule": "When active, prefer architecture-breakout lanes with R2/R3 risk budgets, but do not let a fixed quota suppress 044-style exploit or controlled-risk lanes.",
            "minArchitectureBreakoutLanes": 0,
            "editLaneBudget": 4 if stagnation.get("active") else 2,
            "riskLevels": {
                "R1": "micro mutation; one first-kill scorer",
                "R2": "architecture prototype; one solver subsystem; one or two first-kill suites",
                "R3": "moonshot architecture variant; isolated workspace only; ugly is acceptable if revertible",
            },
        },
        "attackThesis": attack_thesis,
        "attackDoctrine": {
            "rule": "Divergence is broad, but execution converges on one attack thesis plus one bounded risk sidecar.",
            "mainTrack": attack_thesis.get("mainTrack") or "independent mechanism probes",
            "riskSidecar": attack_thesis.get("sidecarTrack") or "a bounded architecture/mutation lane may run when isolated, reversible, compile-checked, and first-kill scored",
            "antiPattern": (
                "Do not end another epoch with only local empty-witness prose; either produce a new global artifact, prove the searched space is empty, or pivot the thesis."
                if bool(isinstance(global_perspective, dict) and global_perspective.get("active"))
                else "Do not end another epoch with only 'missing witness' prose; either produce the witness artifact, prove the searched space is empty, or pivot the thesis."
            ),
        },
        "maxDispatchPolicy": {
            "defaultEpochLaneLimit": DEFAULT_EPOCH_LANE_LIMIT,
            "requestedSelectLanes": int(args.select_lanes),
            "effectiveSelectLanes": lane_limit,
            "capped": int(args.select_lanes) != lane_limit,
            "rule": "selectedLanes is capped to one dispatch batch so an epoch can launch and close without heldReady tail lanes.",
        },
        "validationDoctrine": VALIDATION_DOCTRINE,
        "memoryContext": memory_context,
        "experienceContext": experience_context,
        "weightContext": weights,
        "searchSystem": search_system,
        "failedDiffContext": failed_diff_context(root, limit=args.experience_limit),
        "banditAllocation": {
            "rule": "Use Beta-style historical signal to tilt worker slots. It changes selection pressure only; hard harness and parent gate still decide.",
            "signals": bandit_signals,
            "topExploitHints": [
                {"lane": lane, **signal}
                for lane, signal in sorted(
                    bandit_signals.items(),
                    key=lambda item: float(item[1].get("posteriorMean") or 0),
                    reverse=True,
                )[:5]
            ],
        },
        "frozenPatterns": frozen_patterns[-12:],
        "onlineContext": online_items,
        "legacyRoleTemplates": list(EXPERT_PANEL_ROLES)
        + (list(STAGNATION_BREAKOUT_ROLES) if stagnation.get("active") else [])
        + (list(ARCHITECTURE_BREAKOUT_ROLES) if stagnation.get("active") else []),
        "ideas": ideas[: args.max_ideas],
        "divergentPool": [idea for idea in ideas if bool(idea.get("freeformDivergence"))],
        "ideaScores": idea_scores,
        "selectedLanes": selected,
        "convergenceReview": review,
        "qualityGate": quality_gate,
        "selectionRules": [
            "Primary objective: constrain execution errors, not imagination.",
            "First produce freeform non-template hypotheses; only then converge to dispatchable lanes.",
            "Converge selected lanes into one attackThesis so workers contribute to the same proof instead of independent paperwork.",
            (
                "In globalPerspective mode, residual/counterfactual witness work is support-only and capped; the main track is the attackThesis mainTrack."
                if bool(isinstance(global_perspective, dict) and global_perspective.get("active"))
                else "In stagnation, include a counterfactual witness main track whenever recent failures say exact same-case evidence is missing."
            ),
            "Keep one bounded risk/architecture sidecar alive when safe; witness search should guide edits, not ban all edits.",
            "At least half of selected lanes should come from freeform divergence when enough viable freeform ideas exist, but this is advisory.",
            "Search is broad by default; harness integrity, not idea conservatism, is the hard gate.",
            "Quality-gate failures are hard only when lane ownership, stop conditions, or recoverability are missing; portfolio-shape failures are advisory.",
            "Multiple exploit lanes may run if their mechanisms or exact target shapes are distinct.",
            "Selected portfolio should include online-discriminator/proxy/data/gatekeeper tension when useful, but no category is a universal blocker.",
            "Dataset-evolution lanes are recommended after neutral/down feedback; they are optional in exploit or architecture-heavy epochs.",
            "Every selected lane must have a smallestDecisiveTest and killCondition.",
            "Idea quality scores rank candidates; low scores warn the coordinator but do not block a bounded lane with clean execution harness.",
            "Risk/Runtime Gatekeeper may veto execution hazards, not imagination.",
            "Every expert should cite at least one successful lesson and one failed/frozen lesson; missing citations reduce confidence but do not block a bounded exploratory lane.",
            "When stagnationMode.active=true, favor novel causal mechanisms, controlled-risk mutation, architecture breakout, or 044-style exploit pressure.",
            "When globalPerspective.active=true, the main budget must leave the residual/same-case local basin: at most one local-envelope support lane, with the rest biased toward outside-envelope, PDF/legal materialization, adversarial proxy, moonshot architecture, fusion, or objective/online reframe.",
            "When globalPerspective.active=true, do not treat another empty same-case witness search as progress unless it directly retires a global pivot or changes the dataset/proxy model.",
            "During stagnation, Risk/Runtime Gatekeeper may bound exploration but must not veto all high-variance lanes.",
            "During stagnation, selectedLanes should keep mutation pressure through controlled-risk, architecture, or 044-style exploit lanes unless the active baseline/source is unsafe.",
                f"During innovation mode, edit lanes may rise up to {DEFAULT_MAX_ACTIVE_WORKERS} active workers when hypotheses are independent. This loosens exploration only; parent promotion still applies one candidate and runs the full gate.",
            "In 044 mode, keep the baseline-044 playbook alive: exact neighboring shape, forensic-before-patch, one single-cause patch or explicit rejection.",
        ],
        "nextCommands": [],
    }
    if args.write:
        out_dir = root / "docs" / "idea-boards"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{args.run_id or time.strftime('idea-board-%Y%m%d-%H%M%S')}.json"
        atomic_write_json(out_path, board)
        board["written"] = str(out_path)
        board["nextCommands"] = [
            f"python {Path(__file__).resolve()} check --project \"{root}\" --hypothesis \"<selected hypothesis>\"",
            f"python {Path(__file__).resolve()} prepare-epoch --project \"{root}\" --idea-board \"{out_path}\" --max-lanes {lane_limit}",
            f"python {Path(__file__).resolve()} dispatch-epoch --run-dir \"<epoch-dir>\" --max-workers {DEFAULT_MAX_ACTIVE_WORKERS} --write",
        ]
    else:
        board["nextCommands"] = [
            f"python {Path(__file__).resolve()} idea-board --project \"{root}\" --write",
            f"python {Path(__file__).resolve()} prepare-epoch --project \"{root}\" --idea-board \"<written idea board>\" --max-lanes {lane_limit}",
            f"python {Path(__file__).resolve()} dispatch-epoch --run-dir \"<epoch-dir>\" --max-workers {DEFAULT_MAX_ACTIVE_WORKERS} --write",
        ]
    write_json(board)
    return 0


def confidence_score(value: str | None) -> float:
    if value is None:
        return 0.0
    label = value.lower()
    if "high" in label:
        return 0.8
    if "medium" in label:
        return 0.45
    if "fragile" in label or "sensitive" in label:
        return 0.2
    if "support" in label:
        return 0.25
    return 0.3


def state_budget(state: str) -> str:
    return {
        "exploit": "high",
        "explore": "medium",
        "diagnose": "medium",
        "freeze": "stop",
    }.get(state, "low")


def command_epoch_board(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    space = load_json(mutation_space_path(args.mutation_space))
    baseline = ledger.get("currentBaseline", {})
    current_id = str(baseline.get("id", ""))
    source_sha = str(baseline.get("sourceSha256", ""))
    counts = failure_counts(ledger)

    lanes: list[dict[str, Any]] = []
    for family in space.get("families", []):
        family_name = str(family.get("family", "unknown"))
        default_state = str(family.get("defaultState", "explore"))
        allowed = family.get("allowedMechanisms", [])
        knobs = family.get("mutationKnobs", [])
        for knob in knobs:
            mechanism = str(knob.get("type") or (allowed[0] if allowed else "unknown"))
            prior_failures = counts.get((family_name, mechanism), 0)
            state = default_state
            if prior_failures >= args.max_prior_failures:
                state = "freeze"
            if state == "freeze" and not args.include_frozen:
                continue
            confidence = confidence_score(str(family.get("onlineConfidence", "")))
            lane = {
                "attempt": f"auto-{family_name}-{knob.get('name')}",
                "lane": f"{family_name}-{knob.get('name')}",
                "knob": str(knob.get("name", "")),
                "based_on": current_id,
                "baseline_sha256": source_sha,
                "direction_state": state,
                "affected_family": family_name,
                "changed_mechanism": mechanism,
                "hypothesis": f"Test one {mechanism} mutation for {family_name}: {knob.get('name')}",
                "uncertainty_reduced": f"Whether {knob.get('name')} transfers without violating {family_name} guardrails.",
                "expected_gain": str(family.get("onlineConfidence", "unknown")),
                "known_risk": "; ".join(knob.get("rejectIf", [])),
                "allowed_files": ["src/Solution.cpp"] if mechanism != "benchmark" else ["tools/benchmark.py", "tmp diagnostics"],
                "commands": knob.get("requiredSuites", []),
                "confirmation_commands": knob.get("confirmationSuites", []),
                "status": "planned",
                "budget": state_budget(state),
                "prior_family_mechanism_failures": prior_failures,
                "rankHint": round(confidence - prior_failures * 0.08, 4),
            }
            lanes.append(lane)

    lanes.sort(key=lambda item: (item["budget"] == "stop", -item["rankHint"], item["lane"]))
    selected = lanes[: args.max_lanes]
    prompt_template = (
        "You are one child agent in a Huawei NSLB score-loop epoch. Work only in your assigned isolated workspace. "
        "Start by verifying src/Solution.cpp SHA256 equals {baseline_sha256}. Keep one primary strategy. "
        "Patch boundary is strict: apply_patch with relative paths can edit the main project; use absolute workspace paths "
        "or do not use apply_patch. Do not edit ledger, memory, dist, or submit online. Return child_result.json with worker, basedOn, "
        "baselineSha256, hypothesis, changedFiles, checksRun, scores, deltasVsBaseline, notableRegressions, "
        "runtimeRisk, promotionCandidate, result, summary, avoidNextTime."
    )
    write_json(make_epoch_board(root, args, selected, current_id, source_sha, prompt_template))
    return 0


def make_epoch_board(
    root: Path,
    args: argparse.Namespace,
    lanes: list[dict[str, Any]],
    current_id: str,
    source_sha: str,
    prompt_template: str,
) -> dict[str, Any]:
    return {
        "project": str(root),
        "currentBaseline": current_id,
        "baselineSha256": source_sha,
        "mutationSpace": str(mutation_space_path(getattr(args, "mutation_space", None))),
        "lanes": lanes,
        "workerPromptTemplate": prompt_template.format(baseline_sha256=source_sha),
    }


def lanes_from_idea_board(
    board: dict[str, Any],
    *,
    board_path: Path,
    current_id: str,
    source_sha: str,
    max_lanes: int,
) -> list[dict[str, Any]]:
    selected = board.get("selectedLanes", [])
    if not isinstance(selected, list) or not selected:
        raise SystemExit(f"idea board has no selectedLanes: {board_path}")
    quality_gate = board.get("qualityGate", {})
    harness_warnings: list[str] = []
    if isinstance(quality_gate, dict) and quality_gate.get("passed") is False:
        hard_failed = quality_gate.get("hardFailed", [])
        if hard_failed:
            raise SystemExit(f"idea board hard harness checks failed ({hard_failed}): {board_path}")
        harness_warnings.append("idea board qualityGate has advisory failures; continuing because hard harness checks passed")
        for item in quality_gate.get("advisoryWarnings", []):
            harness_warnings.append(f"advisory quality warning: {item}")
    stagnation = board.get("stagnationMode", {}) if isinstance(board.get("stagnationMode", {}), dict) else {}
    if stagnation.get("active"):
        required_novel = max(1, math.ceil(len(selected[:max_lanes]) * 0.33))
        selected_slice = [item for item in selected[:max_lanes] if isinstance(item, dict)]
        novel_count = len(
            [
                item
                for item in selected_slice
                if bool(item.get("stagnationLane")) or bool(str(item.get("noveltyClass") or "").strip())
            ]
        )
        controlled_risk_count = len([item for item in selected_slice if bool(item.get("controlledRiskLane")) or bool(item.get("riskOverride"))])
        architecture_count = len([item for item in selected_slice if bool(item.get("architectureBreakoutLane"))])
        online_exploit_count = len(
            [
                item
                for item in selected_slice
                if bool(item.get("onlineConfirmedExploitLane")) or bool(item.get("forensicBeforePatch"))
            ]
        )
        repeated_standard_count = len(
            [item for item in selected_slice if str(item.get("lane") or "") in STAGNATION_REPEATED_LANES]
        )
        if novel_count < required_novel:
            harness_warnings.append(
                f"stagnation advisory: expected at least {required_novel} novel/stagnation lanes; found {novel_count}"
            )
        if controlled_risk_count < 1 and architecture_count < 1 and online_exploit_count < 1:
            harness_warnings.append("stagnation advisory: no controlled-risk, architecture, or 044-style exploit pressure selected")
        witness_count = len(
            [
                item
                for item in selected_slice
                if bool(item.get("requiresCounterfactualWitness"))
                or str(item.get("attackTrack") or "").startswith("witness")
                or "counterfactual" in str(item.get("lane") or "").lower()
            ]
        )
        if witness_count < 1:
            harness_warnings.append("stagnation advisory: no counterfactual witness track selected")
        if repeated_standard_count > 2:
            harness_warnings.append(
                f"stagnation advisory: selected {repeated_standard_count} repeated standard lanes"
            )
        if int(stagnation.get("escapeLevel") or 0) >= 2 and not any(bool(item.get("escapeLane")) for item in selected_slice):
            harness_warnings.append("second-order stagnation advisory: no objective-reframe or online-revalidation escape lane selected")
        dataset_backlog = stagnation.get("datasetDecisionBacklog", {}) if isinstance(stagnation, dict) else {}
        if (
            int(stagnation.get("escapeLevel") or 0) >= 2
            and int(dataset_backlog.get("validatedBacklogCount") or 0) > 0
            and not any(bool(item.get("datasetDecisionLane")) for item in selected_slice)
        ):
            harness_warnings.append("second-order stagnation advisory: validated dataset backlog exists but no dataset decision lane selected")
    board_baseline = str(board.get("currentBaseline") or "")
    if board_baseline and board_baseline != current_id:
        raise SystemExit(
            f"idea board baseline mismatch: board={board_baseline}, current={current_id}; regenerate idea-board"
        )
    lanes: list[dict[str, Any]] = []
    for idx, idea in enumerate(selected[:max_lanes], start=1):
        if not isinstance(idea, dict):
            continue
        lane_id = str(idea.get("lane") or f"idea_lane_{idx}")
        worker_type = str(idea.get("workerType") or "diagnostic")
        direction_state = str(idea.get("direction_state") or ("diagnose" if "diagnostic" in worker_type else "explore"))
        allowed_files = idea.get("allowed_files", [])
        if not isinstance(allowed_files, list):
            allowed_files = [str(allowed_files)]
        if not allowed_files and worker_type in ("edit", "edit-or-proposal"):
            allowed_files = ["src/Solution.cpp"]
        commands = idea.get("commands", [])
        if not isinstance(commands, list):
            commands = [str(commands)]
        if not commands:
            commands = ["diagnostic-only"] if worker_type in ("diagnostic", "review", "proposal-only") else []
        confirmation_commands = idea.get("confirmation_commands", idea.get("confirmationCommands", []))
        if not isinstance(confirmation_commands, list):
            confirmation_commands = [str(confirmation_commands)]
        kill_condition = str(idea.get("killCondition") or "").strip()
        duplicate_risk = str(idea.get("duplicateRisk") or "").strip()
        known_risk_parts = [part for part in (kill_condition, duplicate_risk) if part]
        lane = {
            "attempt": f"auto-{lane_id}",
            "lane": lane_id,
            "knob": str(idea.get("changed_mechanism") or idea.get("changedMechanism") or worker_type),
            "based_on": current_id,
            "baseline_sha256": source_sha,
            "direction_state": direction_state,
            "affected_family": str(idea.get("affected_family") or idea.get("affectedFamily") or "unknown"),
            "changed_mechanism": str(idea.get("changed_mechanism") or idea.get("changedMechanism") or "unknown"),
            "hidden_shape": str(idea.get("hidden_shape") or idea.get("hiddenShape") or "unknown"),
            "hypothesis": str(idea.get("hypothesis") or ""),
            "uncertainty_reduced": str(
                idea.get("smallestDecisiveTest")
                or idea.get("uncertainty_reduced")
                or idea.get("expectedArtifact")
                or ""
            ),
            "expected_gain": str(idea.get("expectedArtifact") or idea.get("expected_gain") or "diagnostic evidence"),
            "known_risk": "; ".join(known_risk_parts) or str(idea.get("known_risk") or "unspecified"),
            "allowed_files": allowed_files,
            "commands": commands,
            "confirmation_commands": confirmation_commands,
            "status": "planned",
            "budget": state_budget(direction_state),
            "prior_family_mechanism_failures": 0,
            "rankHint": 0.85 if direction_state == "exploit" else 0.55 if direction_state == "explore" else 0.35,
            "expertRole": idea.get("expertRole"),
            "workerType": worker_type,
            "whyNow": idea.get("whyNow"),
            "requiredContext": idea.get("requiredContext", []),
            "smallestDecisiveTest": idea.get("smallestDecisiveTest"),
            "killCondition": idea.get("killCondition"),
            "expectedArtifact": idea.get("expectedArtifact"),
            "contextContract": idea.get("contextContract", {}),
            "duplicateRisk": idea.get("duplicateRisk"),
            "whyNotDuplicate": idea.get("whyNotDuplicate"),
            "evidenceAnchors": idea.get("evidenceAnchors", {}),
            "qualityScore": idea.get("qualityScore", {}),
            "banditSignal": idea.get("banditSignal", {}),
            "recoveredDiffIds": idea.get("recoveredDiffIds", []),
            "recoveredDiffs": idea.get("recoveredDiffs", []),
            "validationThesis": idea.get("validationThesis", {}),
            "stagnationLane": bool(idea.get("stagnationLane")),
            "escapeLane": bool(idea.get("escapeLane")),
            "controlledRiskLane": bool(idea.get("controlledRiskLane")),
            "architectureBreakoutLane": bool(idea.get("architectureBreakoutLane")),
            "onlineConfirmedExploitLane": bool(idea.get("onlineConfirmedExploitLane")),
            "forensicBeforePatch": bool(idea.get("forensicBeforePatch")),
            "sourcePositiveSignal": idea.get("sourcePositiveSignal"),
            "exactTargetRule": idea.get("exactTargetRule"),
            "riskOverride": bool(idea.get("riskOverride")),
            "requiresMutationAttempt": bool(idea.get("requiresMutationAttempt")),
            "requiresArchitectureAttempt": bool(idea.get("requiresArchitectureAttempt")),
            "datasetEvolutionLane": bool(idea.get("datasetEvolutionLane")),
            "requiresDatasetCandidate": bool(idea.get("requiresDatasetCandidate")),
            "riskLevel": idea.get("riskLevel"),
            "riskBudget": idea.get("riskBudget"),
            "riskLimit": idea.get("riskLimit"),
            "architectureBudget": idea.get("architectureBudget"),
            "allowedExperimentScope": idea.get("allowedExperimentScope"),
            "noveltyClass": idea.get("noveltyClass"),
            "requiresNewArtifact": bool(idea.get("requiresNewArtifact")),
            "requiresCounterfactualWitness": bool(idea.get("requiresCounterfactualWitness")),
            "counterfactualWitnessSchema": idea.get("counterfactualWitnessSchema", []),
            "attackTrack": idea.get("attackTrack"),
            "attackThesisRole": idea.get("attackThesisRole"),
            "forbiddenReuse": idea.get("forbiddenReuse", []),
            "allowsHighVariance": bool(idea.get("allowsHighVariance")),
            "harnessWarnings": list(harness_warnings),
            "ideaBoardPath": str(board_path),
        }
        lane["phase"] = lane_phase(lane)
        lane["phasePrerequisites"] = phase_prerequisites_for_lane(lane)
        lane["commandBudget"], lane["timeBudgetMinutes"] = command_budget_for_lane(lane)
        lane["allowedCommands"] = allowed_commands_for_lane(lane)
        lanes.append(lane)
    if not lanes:
        raise SystemExit(f"idea board selectedLanes could not be converted: {board_path}")
    return lanes


def copy_workspace(root: Path, destination: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in EXCLUDED_COPY_NAMES}
        ignored.update(name for name in names if name.endswith(".pyc"))
        return ignored

    shutil.copytree(root, destination, ignore=ignore)
    (destination / "build").mkdir(exist_ok=True)
    (destination / "dist").mkdir(exist_ok=True)


def lane_prompt(board: dict[str, Any], lane: dict[str, Any]) -> str:
    commands = lane.get("commands", [])
    confirmation_commands = lane.get("confirmation_commands", [])
    normalized_commands = []
    diagnostic_only = any(str(command) == "diagnostic-only" for command in commands)
    benchmark_commands = [str(command) for command in commands if command not in ("run_regression", "diagnostic-only")]
    if controlled_risk_lane(lane):
        first_kill_choices = ", ".join(benchmark_commands) or "online_fit_core or large_sparse_forensics"
        normalized_commands.append("g++ -std=c++17 -O2 -pipe src\\Solution.cpp -o build\\score_loop_candidate.exe")
        normalized_commands.append(
            f"Run exactly one first-kill scorer suite chosen from: {first_kill_choices}; stop after that suite."
        )
    elif architecture_breakout_lane(lane):
        first_kill_choices = ", ".join(benchmark_commands) or "online_fit_core, hidden_shape, or large_sparse_forensics"
        normalized_commands.append("g++ -std=c++17 -O2 -pipe src\\Solution.cpp -o build\\score_loop_candidate.exe")
        normalized_commands.append(
            f"Run one first-kill scorer suite chosen from: {first_kill_choices}; run a second listed suite only if the first moves positively."
        )
    elif benchmark_commands:
        normalized_commands.append("g++ -std=c++17 -O2 -pipe src\\Solution.cpp -o build\\score_loop_candidate.exe")
    if not controlled_risk_lane(lane) and not architecture_breakout_lane(lane):
        for command in commands:
            if command == "run_regression":
                normalized_commands.append("python tools\\run_regression.py")
            elif command == "diagnostic-only":
                normalized_commands.append("No fixed benchmark suite. Run the smallest diagnostic command needed; do not edit solver code unless allowed_files permits it.")
            else:
                normalized_commands.append(
                    f"python tools\\benchmark.py --suite {command} --exe build\\score_loop_candidate.exe --discard-case-files"
                )
    command_text = "\n".join(f"{idx + 1}. {command}" for idx, command in enumerate(normalized_commands))
    if not command_text:
        command_text = "1. Run the smallest checks needed for this proposal-only lane."
    confirmation_text = "\n".join(
        f"- python tools\\benchmark.py --suite {command} --exe build\\score_loop_candidate.exe --discard-case-files"
        for command in confirmation_commands
    ) or "- none"
    workspace = str(lane.get("workspace") or "<assigned isolated workspace>")
    project_root_text = str(board["project"])
    workspace_solution = str(Path(workspace) / "src" / "Solution.cpp")
    main_solution = str(Path(project_root_text) / "src" / "Solution.cpp")
    context_path = str(lane.get("context_path") or lane.get("contextPath") or "")
    allowed_files = lane.get("allowed_files", [])
    allowed_files_text = ", ".join(allowed_files) if allowed_files else "none; diagnostic/proposal-only"
    command_budget = lane.get("commandBudget") or command_budget_for_lane(lane)[0]
    time_budget = lane.get("timeBudgetMinutes") or command_budget_for_lane(lane)[1]
    phase = lane.get("phase") or lane_phase(lane)
    allowed_commands_text = "\n".join(f"- {command}" for command in lane.get("allowedCommands", allowed_commands_for_lane(lane)))
    evidence_anchors_text = json.dumps(lane.get("evidenceAnchors", {}), ensure_ascii=False, indent=2)
    quality_score_text = json.dumps(lane.get("qualityScore", {}), ensure_ascii=False, indent=2)
    validation_thesis_text = json.dumps(lane.get("validationThesis", {}), ensure_ascii=False, indent=2)
    validation_doctrine_text = json.dumps(board.get("validationDoctrine", VALIDATION_DOCTRINE), ensure_ascii=False, indent=2)
    recovered_diffs = recovery_records_for_lane(Path(project_root_text), lane, limit=4)
    recovered_diffs_text = json.dumps(recovered_diffs, ensure_ascii=False, indent=2)
    context_contract = lane.get("contextContract", {}) if isinstance(lane.get("contextContract", {}), dict) else {}
    read_if_needed = context_contract.get("readIfNeeded", context_contract.get("mustRead", []))
    cite_if_used = context_contract.get("citeIfUsed", context_contract.get("mustUse", lane.get("requiredContext", [])))
    evidence_expected = context_contract.get(
        "evidenceExpectedWhenAvailable",
        context_contract.get("evidenceRequiredInOutput", []),
    )
    contract_lines: list[str] = []
    if lane.get("workerType") or context_contract:
        contract_lines.extend(
            [
                "Mutation Row Execution Contract:",
                f"- Worker type: {lane.get('workerType') or 'unspecified'}",
                f"- Why now: {lane.get('whyNow') or 'unspecified'}",
                f"- Smallest decisive test: {lane.get('smallestDecisiveTest') or 'unspecified'}",
                f"- Kill condition: {lane.get('killCondition') or 'unspecified'}",
                f"- Expected artifact: {lane.get('expectedArtifact') or 'child_result.json'}",
                f"- Duplicate risk: {lane.get('duplicateRisk') or 'not recorded'}",
                f"- Why not duplicate: {lane.get('whyNotDuplicate') or 'not recorded'}",
                "- Validation thesis is advisory for test selection, not a substitute for code/diff evidence:",
                validation_thesis_text,
            ]
        )
        if lane.get("stagnationLane") or lane.get("noveltyClass") or lane.get("requiresNewArtifact"):
            contract_lines.extend(
                [
                    "- Stagnation-mode lane: yes",
                    f"  - Second-order escape lane: {bool(lane.get('escapeLane'))}",
                    f"  - Controlled-risk mutation lane: {controlled_risk_lane(lane)}",
                    f"  - Architecture-breakout lane: {architecture_breakout_lane(lane)}",
                    f"  - Risk level: {lane.get('riskLevel') or 'standard'}",
                    f"  - Novelty class: {lane.get('noveltyClass') or 'unspecified'}",
                    f"  - Requires new artifact/case/enumeration: {bool(lane.get('requiresNewArtifact'))}",
                    f"  - Forbidden reuse: {', '.join(str(item) for item in lane.get('forbiddenReuse', [])) or 'none'}",
                ]
            )
            if lane.get("requiresNewArtifact"):
                contract_lines.extend(
                    [
                        "  - Artifact proof required: child_result.json must include artifactPaths, generatedArtifacts/newArtifacts, or currentEvidence entries with artifact/report paths.",
                        "  - Any relative artifact/report path should point to a file under the assigned workspace.",
                        "  - If no new artifact is produced, set result to rejected/proposal-only and explain the failed kill condition.",
                    ]
                )
            if lane.get("attackTrack") or lane.get("attackThesisRole"):
                contract_lines.extend(
                    [
                        f"  - Attack track: {lane.get('attackTrack') or 'unspecified'}",
                        f"  - Attack thesis role: {lane.get('attackThesisRole') or 'contribute evidence to the shared thesis'}",
                    ]
                )
            if lane.get("requiresCounterfactualWitness"):
                schema = lane.get("counterfactualWitnessSchema") or []
                schema_text = ", ".join(str(item) for item in schema) if isinstance(schema, list) else str(schema)
                contract_lines.extend(
                    [
                        "  - Counterfactual witness proof required: do not merely state that a witness is missing.",
                        "  - Search for exact same-case alternatives and emit a table/report under the workspace.",
                        f"  - Witness schema: {schema_text or 'caseId, flowId, baselinePort, alternativePort, componentDeltas, scoreDelta, legality'}",
                        "  - If no witness exists in the searched space, report the bounded search space, count attempted alternatives, and the component reason every alternative failed.",
                    ]
                )
            if lane.get("datasetEvolutionLane") or lane.get("requiresDatasetCandidate"):
                contract_lines.extend(
                    [
                        "  - Dataset evolution proof: include datasetCandidate when you claim dataset progress.",
                        "  - datasetCandidate fields: candidateId, sourceOnlineFeedback, caseFamily, caseShape, hypothesis, explainsPositive, rejectsNeutralOrNegative, artifactPaths or generatedCaseFacts, promotionGateImpact.",
                        "  - The candidate should say which online-positive record it preserves and which neutral/down record it rejects.",
                        "  - If no datasetCandidate can be supported, close as diagnostic/no-progress with currentEvidence; do not block unrelated exploit or architecture lanes.",
                    ]
                )
            if controlled_risk_lane(lane):
                contract_lines.extend(
                    [
                        f"  - Risk budget: {lane.get('riskBudget') or 'one-file-one-mechanism-one-suite'}",
                        f"  - Risk limit: {lane.get('riskLimit') or 'tiny diff, first-kill scorer suite, no promotion without parent gate'}",
                        "  - Mutation proof required: child_result.json must include mutationAttempted=true and attemptedDiffSummary or mutationSummary.",
                    ]
                )
            if architecture_breakout_lane(lane):
                contract_lines.extend(
                    [
                        f"  - Architecture budget: {lane.get('architectureBudget') or 'one subsystem, bounded prototype, first-kill scorer'}",
                        f"  - Experiment scope: {lane.get('allowedExperimentScope') or 'workspace-only src/Solution.cpp; no package/ledger/memory edits'}",
                        "  - Architecture proof required when an executable target exists: child_result.json should include architectureAttempted=true and architectureSummary or attemptedDiffSummary.",
                        "  - If the lane depends on a concrete witness/target case and none exists, stop cleanly with promotionCandidate=false, result=needs-more-evidence or blocked-by-missing-witness, and currentEvidence explaining the missing artifact. This is a valid learning outcome, not an invalid dispatch.",
                    ]
                )
        if read_if_needed:
            contract_lines.append("- Durable context available if compact context is insufficient:")
            contract_lines.extend(f"  - {item}" for item in read_if_needed)
        if cite_if_used:
            contract_lines.append("- Context to cite only if used:")
            contract_lines.extend(f"  - {item}" for item in cite_if_used)
        if evidence_expected:
            contract_lines.append("- Evidence expected when available in compact/current context:")
            contract_lines.extend(f"  - {item}" for item in evidence_expected)
    if recovered_diffs:
        contract_lines.extend(
            [
                "- Failed-diff recovery material is attached below. For edit/architecture/fusion lanes, apply, recreate, or deliberately supersede one recovered patch before first-kill unless a hard blocker prevents it.",
                "- If no recovered patch can be used, write child_result.json with result=blocked-by-missing-target or needs-more-evidence and cite the exact missing target/witness.",
                recovered_diffs_text,
            ]
        )
    contract_text = "\n".join(contract_lines) if contract_lines else "Mutation Row Execution Contract: compact lane only; no role/prose obligations."
    return f"""You are one child agent in a Huawei NSLB autonomous score-loop epoch.

Main project root, read-only reference: {project_root_text}
Assigned isolated workspace, use this as your working directory: {workspace}
Workspace Solution.cpp absolute path: {workspace_solution}
Main Solution.cpp must remain unchanged: {main_solution}
Compact worker context JSON: {context_path or '<missing; invalid dispatch for mutation epoch>'}
Assigned lane: {lane["lane"]}
Attempt id: {lane["attempt"]}
Epoch phase: {phase}
Based on baseline: {board["currentBaseline"]}
Expected src/Solution.cpp SHA256: {board["baselineSha256"]}

Hypothesis:
{lane["hypothesis"]}

Uncertainty reduced:
{lane["uncertainty_reduced"]}

Direction state: {lane["direction_state"]}
Affected family: {lane["affected_family"]}
Changed mechanism: {lane["changed_mechanism"]}
Hidden shape label: {lane_shape(lane)}
Known risk: {lane["known_risk"]}
Allowed files: {allowed_files_text}

{contract_text}

Idea quality score:
{quality_score_text}

Evidence anchors to cite:
{evidence_anchors_text}

Validation doctrine:
{validation_doctrine_text}

Rules:
- No essay mode: your lane output is code/diff plus current evidence, or a hard blocker with an artifact. Do not finish edit/architecture/controlled-risk/fusion lanes with prose-only analysis.
- Primary objective: explore boldly, execute safely. You may try unusual mechanisms, rough architecture variants, and high-variance local probes when they are bounded by this lane's workspace, stop condition, and result contract.
- Hard limits protect execution only: do not touch the main workspace, do not write shared ledgers/memory/packages, do not fake evidence, and do not recommend promotion without current evidence.
- Soft guidance such as validation thesis, negative controls, role coverage, or dataset evolution should shape your reasoning, but missing polish should not stop a bounded exploratory attempt. It should lower confidence and be recorded honestly.
- First read only the compact worker context JSON above. Do not open full SKILL.md, full optimization ledger, full project memory, or large source ranges unless the compact context is insufficient for this lane.
- Work only inside the assigned isolated workspace above.
- Do not edit or run implementation commands in the main project root.
- Shell commands must pass the assigned workspace as `workdir`.
- Search output must be bounded: never run recursive `rg` over tmp/score-loop-epochs, workspaces, build, dist, or the whole project root. Use a named file or narrow directory with `--glob '!tmp/**' --glob '!build/**' --glob '!dist/**' --max-count 20`; read the compact context, exploration index, ledger, or one named epoch file for historical evidence.
- `apply_patch` does not inherit shell `workdir`. If you use `apply_patch`, every file header must be an absolute path under the assigned workspace, for example `*** Update File: {workspace_solution}`.
- Never use relative `apply_patch` headers such as `*** Update File: src/Solution.cpp`; that can modify the main project and invalidates the lane.
- Start by verifying src/Solution.cpp SHA256 equals the expected hash. Stop if it differs.
- After any patch, verify the main Solution.cpp hash still equals the expected hash. If it changed, stop and report main-workspace drift immediately.
- Keep exactly one primary strategy.
- Do not edit docs/optimization-ledger.json, project memory, dist packages, or submit online.
- Do not spawn other agents.
- If the lane is diagnose/proposal-only, prefer evidence and a patch proposal over code edits. If the lane is edit, controlled-risk, architecture, fusion, risk-resurrection, or 044-style forensic-before-patch, make the smallest safe mutation attempt instead of turning the lane into paperwork unless the execution harness is actually missing.
- If this prompt lacks lane id, assigned workspace, baseline hash, smallest decisive test, or kill condition, stop and report invalid dispatch instead of inventing a broad task. Missing role labels or imperfect context citation is advisory unless it breaks the execution harness.
- Startup observability is mandatory. Your first filesystem action in the assigned workspace is to write `{workspace}\\worker_started.json` with worker/lane/attempt/startTime/promptPath, before long analysis or benchmarks.
- After baseline hash verification and after each major command, update `{workspace}\\worker_heartbeat.json` with step/status/updatedAt/lastCommand/nextAction. This lets the controller distinguish real runtime from prompt-delivery failure.
- If you are interrupted by the controller, read the launch instruction again, update worker_heartbeat.json immediately, then either continue the bounded lane or write child_result.json with blocker/currentEvidence.
- Cite the successful lesson you build on, the failed/frozen lesson you avoid, and the online feedback record this lane explains when available. If you cannot cite them, record the gap in evidenceNotes; do not claim promotion from uncited history.
- Treat online score as an expensive extra validation fold, not an oracle. Your current task is to produce trustworthy local evidence or a calibrated negative lesson.
- State which local fold/case/suite should predict online movement for this lane, and which online-positive and online-neutral/down records make that validation believable.
- If local evidence is not representative of the hidden objective, say so. You may still return a controlled-risk negative lesson, but not a promotionCandidate.
- Old epoch child results are priorEvidence only. They cannot replace this epoch's currentEvidence or smallestDecisiveTestResult.
- If currentEvidence is empty and your conclusion relies only on older epochs, set result to proposal-only or rejected and promotionCandidate=false.
- If recovered failed diffs are present in the compact context or contract, do not merely discuss them. Apply/recreate/supersede one recovered patch in the isolated workspace, or return a hard blocker explaining why no recovered patch maps to the current target.
- If this is a requiresNewArtifact lane, produce an auditable artifact or report in the workspace and list it in artifactPaths/generatedArtifacts/newArtifacts or currentEvidence. If you cannot, the lane may still close as a negative lesson, but not as artifact progress.
- If this is a counterfactual-witness lane, produce exact same-case evidence with caseId/flowId/baselinePort/alternativePort/componentDeltas/scoreDelta/legality, or prove the bounded searched space was empty with attempted alternative counts. Missing witness is a learning result, not a reason to fabricate or broaden blindly.
- If this is a dataset-evolution lane, return datasetCandidate with candidateId, sourceOnlineFeedback, caseFamily, caseShape, hypothesis, explainsPositive, rejectsNeutralOrNegative, artifactPaths or generatedCaseFacts, and promotionGateImpact when you claim dataset progress. If you cannot, close as diagnostic without blocking unrelated exploit or architecture lanes.
- If this is a controlled-risk mutation lane, you must attempt exactly one small src/Solution.cpp mutation. Return `mutationAttempted=true`, `attemptedDiffSummary`, and the first-kill scorer result even when the mutation is reverted or rejected.
- If this is an architecture-breakout lane, attempt a real solver-architecture change in the isolated workspace when the compact context gives enough executable target evidence. It can be rough, but it must be revertible, compile-checked, and first-kill scored. Return `architectureAttempted=true`, `architectureSummary`, and the scorer result. If the lane's own hypothesis requires a concrete witness/target and none is available, stop cleanly with `promotionCandidate=false`, `result=needs-more-evidence` or `blocked-by-missing-witness`, `architectureAttempted=false`, and currentEvidence explaining what artifact is missing.

Required checks:
{command_text}

Confirmation suites are coordinator-only unless the target evidence already moved:
{confirmation_text}

Speed protocol:
- Command budget: at most {command_budget} shell commands and roughly {time_budget} minutes. When exhausted, stop and write child_result.json as inconclusive/rejected/proposal-only with the best reusable lesson.
- Allowed command whitelist for this lane:
{allowed_commands_text}
- Compile once with `g++ -std=c++17 -O2 -pipe src\\Solution.cpp -o build\\score_loop_candidate.exe`, then reuse `--exe build\\score_loop_candidate.exe` for every benchmark suite.
- Benchmark commands should add `--discard-case-files` after report.json is written unless the lane explicitly needs the raw `.in`/`.out` for diagnosis.
- Do not run `--compare-baselines` inside worker lanes; broad baseline comparisons are parent-gate or coordinator diagnostics only.
- For diagnostic-only lanes, do not run a fake `diagnostic-only` benchmark suite. Use targeted reading, instrumentation, or a temporary report artifact and explain the exact evidence gathered.
- The string `diagnostic-only` is never a valid value for `python tools\\benchmark.py --suite`.
- Fail fast: run the smallest target or diagnostic suite first. If the target evidence is flat or worse and the lane is not proposal-only, stop, revert any solver edit in the workspace, and write a rejected child_result.
- Do not run full/official/pdfstress/runtime as early exploration. These are confirmation gates for a candidate that already moved the target evidence.
- After parsing report.json, ensure large per-case `.in`/`.out` benchmark files are deleted in the assigned workspace unless they are needed for diagnosis. Keep report.json and child_result.json.
- If a benchmark command is repeated only to compare the baseline, use one exact target case or a coordinator-provided snapshot; do not rerun broad baseline comparisons inside every worker.

Return child_result.json at the workspace root with:
worker, laneId, attemptId, basedOn, baselineSha256, affectedFamily, changedMechanism,
hiddenShape, hypothesis, changedFiles, checksRun, scores,
deltasVsBaseline, notableRegressions, runtimeRisk, promotionCandidate, result,
summary, avoidNextTime, currentEvidence, priorEvidence, budgetUsed, budgetExceeded. For controlled-risk lanes include mutationAttempted and attemptedDiffSummary. For architecture-breakout lanes include architectureAttempted and architectureSummary, or architectureAttempted=false plus a missing-witness/currentEvidence explanation when the lane cannot be executed rationally. For requiresNewArtifact lanes also include artifactPaths or generatedArtifacts/newArtifacts. For counterfactual-witness lanes also include counterfactualWitnesses or a witnessSearchSummary. Include evidenceNotes with: successfulLessonUsed,
failedOrFrozenLessonAvoided, onlineFeedbackExplained, smallestDecisiveTestResult,
validationThesis, localFoldTrust, onlineFoldInterpretation,
and killConditionOutcome. For dataset-evolution lanes also include datasetCandidate.
"""


def command_prepare_epoch(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    lane_limit = min(int(args.max_lanes), DEFAULT_EPOCH_LANE_LIMIT)
    if lane_limit < 1:
        raise SystemExit("--max-lanes must be at least 1")
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    source_path = root / str(baseline.get("sourcePath", "src/Solution.cpp"))
    source_hash = sha256_file(source_path) if source_path.exists() else None
    expected_hash = str(baseline.get("sourceSha256", "")).lower()
    drift_info: dict[str, Any] | None = None
    if source_hash and source_hash.lower() != expected_hash:
        if not args.allow_drift:
            raise SystemExit("source hash drift; run drift before preparing an epoch")
        if not args.drift_classification:
            raise SystemExit("source hash drift with --allow-drift requires --drift-classification")
        drift_info = {
            "expectedSourceSha256": expected_hash,
            "actualSourceSha256": source_hash.lower(),
            "classification": args.drift_classification,
            "note": args.drift_note,
        }

    epoch_args = argparse.Namespace(
        project=str(root),
        mutation_space=args.mutation_space,
        max_lanes=lane_limit,
        max_prior_failures=args.max_prior_failures,
        include_frozen=args.include_frozen,
    )

    current_id = str(baseline.get("id", ""))
    source_sha = str(baseline.get("sourceSha256", ""))
    if getattr(args, "idea_board", ""):
        idea_board_path = Path(args.idea_board).resolve()
        loaded_board = load_json(idea_board_path)
        if not isinstance(loaded_board, dict):
            raise SystemExit(f"idea board is not a JSON object: {idea_board_path}")
        lanes = lanes_from_idea_board(
            loaded_board,
            board_path=idea_board_path,
            current_id=current_id,
            source_sha=source_sha,
            max_lanes=lane_limit,
        )
        board = dict(loaded_board)
        selected_count = len(loaded_board.get("selectedLanes", [])) if isinstance(loaded_board.get("selectedLanes", []), list) else 0
        board["project"] = str(root)
        board["currentBaseline"] = current_id
        board["baselineSha256"] = source_sha
        board["ideaBoardPath"] = str(idea_board_path)
        board["lanes"] = lanes
        board["maxDispatchPolicy"] = {
            "defaultEpochLaneLimit": DEFAULT_EPOCH_LANE_LIMIT,
            "requestedMaxLanes": int(args.max_lanes),
            "effectiveMaxLanes": lane_limit,
            "sourceSelectedLanes": selected_count,
            "overflowLaneCount": max(0, selected_count - lane_limit),
            "capped": int(args.max_lanes) != lane_limit or selected_count > lane_limit,
            "rule": "prepare-epoch materializes at most one bounded dispatch batch; overflow selected lanes are not added to the manifest.",
        }
        board["workerPromptTemplate"] = (
            "Mutation-matrix epoch: prompts must preserve lane id, workspace, baseline hash, "
            "smallestDecisiveTest, killCondition, recovered failed-diff material, and child_result.json contract. "
            "Edit/architecture/fusion lanes must produce a solver diff or a hard blocker, not prose-only analysis."
        )
    else:
        space = load_json(mutation_space_path(args.mutation_space))
        counts = failure_counts(ledger)
        lanes = []
        for family in space.get("families", []):
            family_name = str(family.get("family", "unknown"))
            default_state = str(family.get("defaultState", "explore"))
            for knob in family.get("mutationKnobs", []):
                mechanism = str(knob.get("type") or "unknown")
                prior_failures = counts.get((family_name, mechanism), 0)
                state = "freeze" if prior_failures >= args.max_prior_failures else default_state
                if state == "freeze" and not args.include_frozen:
                    continue
                lane = {
                        "attempt": f"auto-{family_name}-{knob.get('name')}",
                        "lane": f"{family_name}-{knob.get('name')}",
                        "knob": str(knob.get("name", "")),
                        "based_on": current_id,
                        "baseline_sha256": source_sha,
                        "direction_state": state,
                        "affected_family": family_name,
                        "changed_mechanism": mechanism,
                        "hypothesis": f"Test one {mechanism} mutation for {family_name}: {knob.get('name')}",
                        "uncertainty_reduced": f"Whether {knob.get('name')} transfers without violating {family_name} guardrails.",
                        "expected_gain": str(family.get("onlineConfidence", "unknown")),
                        "known_risk": "; ".join(knob.get("rejectIf", [])),
                        "allowed_files": ["src/Solution.cpp"] if mechanism != "benchmark" else ["tools/benchmark.py", "tmp diagnostics"],
                        "commands": knob.get("requiredSuites", []),
                        "confirmation_commands": knob.get("confirmationSuites", []),
                        "status": "planned",
                        "budget": state_budget(state),
                        "prior_family_mechanism_failures": prior_failures,
                        "rankHint": round(confidence_score(str(family.get("onlineConfidence", ""))) - prior_failures * 0.08, 4),
                    }
                lane["phase"] = lane_phase(lane)
                lane["phasePrerequisites"] = phase_prerequisites_for_lane(lane)
                lane["commandBudget"], lane["timeBudgetMinutes"] = command_budget_for_lane(lane)
                lane["allowedCommands"] = allowed_commands_for_lane(lane)
                lanes.append(lane)
        lanes.sort(key=lambda item: (item["budget"] == "stop", -item["rankHint"], item["lane"]))
        lanes = lanes[: lane_limit]
        prompt_template = (
            "You are one child agent in a Huawei NSLB score-loop epoch. Work only in your assigned isolated workspace. "
            "Start by verifying src/Solution.cpp SHA256 equals {baseline_sha256}. Keep one primary strategy. "
            "Patch boundary is strict: apply_patch with relative paths can edit the main project; use absolute workspace paths "
            "or do not use apply_patch. Do not edit ledger, memory, dist, or submit online. Return child_result.json."
        )
        board = make_epoch_board(root, epoch_args, lanes, current_id, source_sha, prompt_template)

    run_id = args.run_id or time.strftime("epoch-%Y%m%d-%H%M%S")
    run_dir = Path(args.output).resolve() if args.output else root / "tmp" / "score-loop-epochs" / run_id
    if run_dir.exists():
        if not args.force:
            raise SystemExit(f"run directory exists: {run_dir}; use --force to replace")
        shutil.rmtree(run_dir)
    prompts_dir = run_dir / "prompts"
    workspaces_dir = run_dir / "workspaces"
    contexts_dir = run_dir / "contexts"
    prompts_dir.mkdir(parents=True)
    workspaces_dir.mkdir(parents=True)
    contexts_dir.mkdir(parents=True)
    for lane in lanes:
        base_attempt = str(lane["attempt"])
        lane["attempt"] = f"{run_id}-{base_attempt}"
        workspace = workspaces_dir / lane["lane"]
        if not args.no_copy:
            copy_workspace(root, workspace)
        else:
            workspace.mkdir(parents=True, exist_ok=True)
        lane["workspace"] = str(workspace)
        lane["phase"] = lane.get("phase") or lane_phase(lane)
        lane["phasePrerequisites"] = lane.get("phasePrerequisites") or phase_prerequisites_for_lane(lane)
        lane["commandBudget"] = lane.get("commandBudget") or command_budget_for_lane(lane)[0]
        lane["timeBudgetMinutes"] = lane.get("timeBudgetMinutes") or command_budget_for_lane(lane)[1]
        lane["allowedCommands"] = lane.get("allowedCommands") or allowed_commands_for_lane(lane)
        context_path = contexts_dir / f"{lane['lane']}.worker_context.json"
        lane["context_path"] = str(context_path)
        lane["contextPath"] = str(context_path)
        atomic_write_json(context_path, build_worker_context(root, board, ledger, lane))
        prompt = lane_prompt(board, lane)
        prompt_path = prompts_dir / f"{lane['lane']}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        lane["prompt_path"] = str(prompt_path)
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "board": board,
        "lanes": lanes,
        "drift": drift_info,
        "phasePolicy": {
            "defaultDispatchPhase": "auto",
            "phaseA": "diagnostic/review/proposal lanes that produce current evidence and target selection",
            "phaseB": "edit/exploit lanes; blocked until Phase A has schema-valid current evidence or coordinator uses --phase all",
            "staleEvidenceRule": "prior epoch child results may be cited as priorEvidence but cannot replace currentEvidence",
        },
        "next_steps": [
            "Review prompts under prompts/.",
            "Run dispatch-epoch --phase auto --write; launch only Phase A first unless the queue explicitly says Phase B is ready.",
            "After workers finish, run score_loop_tools.py collect-epoch --run-dir <epoch-dir> --write.",
            "Only after Phase A evidence is collected, dispatch Phase B or regenerate a narrower board.",
            "Then run score_loop_tools.py rank-children --run-dir <epoch-dir> and close-epoch --run-dir <epoch-dir> --write.",
            "Apply at most one candidate in the main workspace and run Promotion Gate.",
        ],
    }
    (run_dir / "epoch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_json({"runDir": str(run_dir), "manifest": str(run_dir / "epoch_manifest.json"), "lanes": lanes})
    return 0


def command_gate_decision(args: argparse.Namespace) -> int:
    child_path = Path(args.child_result).resolve()
    loaded_result = load_json(child_path)
    _run_dir, manifest = epoch_manifest_for_child(child_path)
    result = apply_lane_metadata(loaded_result, lane_for_child_path(child_path, manifest))
    weights = load_or_default_weights(project_root(args.project)) if args.project else {}
    rank_score, strengths, risks = score_child(result, weights)
    result_text = json.dumps(result, ensure_ascii=False).lower()
    high_weight_regression = any(
        phrase in result_text
        for phrase in (
            "online_fit_core regresses",
            "onlinefitcoreweighted negative",
            "hiddenshapeweighted negative",
            "hidden_shape regresses",
            "runtime risk",
            "timeout",
        )
    )
    row_decision = decision_for_ranked(
        {
            "promotionCandidate": result.get("promotionCandidate"),
            "rankScore": rank_score,
            "risks": risks,
        },
        args.min_rank_score,
    )
    if high_weight_regression:
        decision = "reject"
    else:
        decision = row_decision
    parent_gate = [
        "python tools\\run_regression.py",
        "python tools\\benchmark.py --suite quick",
        "python tools\\benchmark.py --suite full",
        "python tools\\benchmark.py --suite official_seed_sweep",
        "python tools\\benchmark.py --suite online_fit_core",
    ]
    if "runtime" in result_text or "loop" in result_text:
        parent_gate.append("python tools\\benchmark.py --suite runtime")
    if "leaf" in result_text or "leafband" in result_text:
        parent_gate.append("python tools\\benchmark.py --suite hidden_leaf_band_forensics")
    if "official" in result_text or "permutation" in result_text:
        parent_gate.append("python tools\\benchmark.py --suite hidden_shape")
    write_json(
        {
            "childResult": str(Path(args.child_result).resolve()),
            "rankScore": round(rank_score, 4),
            "decision": decision,
            "strengths": strengths,
            "risks": risks,
            "requiredParentGate": parent_gate,
            "rule": "Apply at most one eligible candidate to the main workspace, then run every parent gate command before promotion.",
        }
    )
    return 0 if decision == "eligible-for-parent-gate" else 1


def rank_child_results(run_dir: Path, weights: dict[str, Any] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    manifest: dict[str, Any] | None = None
    cancelled_lanes: set[str] = set()
    pool_path = run_dir / "pool_state.json"
    if pool_path.exists():
        try:
            pool = load_json(pool_path)
            workers = pool.get("workers", []) if isinstance(pool, dict) else []
            cancelled_lanes = {
                str(worker.get("lane"))
                for worker in workers
                if isinstance(worker, dict)
                and worker.get("status") == "cancelled"
                and str(worker.get("blocker") or "").strip()
            }
        except Exception:  # noqa: BLE001
            cancelled_lanes = set()
    if (run_dir / "epoch_manifest.json").exists():
        loaded_manifest = load_json(run_dir / "epoch_manifest.json")
        if isinstance(loaded_manifest, dict):
            manifest = loaded_manifest
    if manifest:
        lane_paths = [
            (lane, Path(str(lane.get("workspace", ""))).resolve() / "child_result.json")
            for lane in manifest.get("lanes", [])
            if isinstance(lane, dict) and lane.get("workspace")
        ]
    elif (run_dir / "workspaces").is_dir():
        search_dir = run_dir / "workspaces"
        lane_paths = [(None, path) for path in sorted(search_dir.rglob("child_result.json"))]
    else:
        search_dir = run_dir
        lane_paths = [(None, path) for path in sorted(search_dir.rglob("child_result.json"))]
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for lane, result_path in lane_paths:
        if not result_path.exists():
            if manifest and lane:
                if str(lane.get("lane") or "") not in cancelled_lanes:
                    missing.append(str(Path(str(lane.get("workspace", ""))).resolve()))
            continue
        try:
            loaded_result = load_json(result_path)
            result = apply_lane_metadata(loaded_result, lane)
        except Exception as exc:  # noqa: BLE001
            rows.append({"path": str(result_path), "error": str(exc), "rankScore": -999})
            continue
        rank_score, strengths, risks = score_child(result, weights or {})
        schema_errors, schema_warnings = validate_child_result(result)
        if lane:
            lane_errors, lane_warnings = validate_child_against_lane(result, lane, strict=False)
            schema_errors.extend(lane_errors)
            schema_warnings.extend(lane_warnings)
        if schema_errors:
            rank_score -= 100
            risks.extend(schema_errors)
        elif schema_warnings:
            rank_score -= 5 * len(schema_warnings)
            risks.extend(schema_warnings)
        rows.append(
            {
                "worker": result.get("worker") or result_path.parent.name,
                "path": str(result_path),
                "rankScore": round(rank_score, 4),
                "promotionCandidate": result.get("promotionCandidate"),
                "result": result.get("result"),
                "summary": result.get("summary"),
                "strengths": strengths,
                "risks": risks,
                "schemaValid": not schema_errors,
                "schemaWarnings": schema_warnings,
            }
        )
    if not manifest:
        if (run_dir / "workspaces").is_dir():
            search_dir = run_dir / "workspaces"
        else:
            search_dir = run_dir
        if search_dir.exists():
            missing = [str(path) for path in search_dir.iterdir() if path.is_dir() and not (path / "child_result.json").exists()]
    rows.sort(key=lambda item: item.get("rankScore", -999), reverse=True)
    return missing, rows


def decision_for_ranked(row: dict[str, Any], min_rank_score: float) -> str:
    risks = " ".join(str(item).lower() for item in row.get("risks", []))
    if row.get("promotionCandidate") is not True:
        return "reject-or-needs-more-evidence"
    if "negative" in risks or "runtime risk" in risks or "regression" in risks:
        return "reject"
    if float(row.get("rankScore", -999)) >= min_rank_score:
        return "eligible-for-parent-gate"
    return "needs-more-evidence"


def command_close_epoch(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    weights = load_or_default_weights(project_root(args.project)) if args.project else {}
    missing, ranked = rank_child_results(run_dir, weights)
    top = ranked[0] if ranked else None
    close_blockers: list[str] = []
    collection_path = run_dir / "epoch_collection.json"
    collection: dict[str, Any] | None = None
    protocol_warnings: list[str] = []
    if collection_path.exists():
        loaded_collection = load_json(collection_path)
        if isinstance(loaded_collection, dict):
            collection = loaded_collection
            protocol_warnings.extend(str(item) for item in collection.get("protocolWarnings", []) if item)
            if collection.get("complete") is not True:
                close_blockers.append("epoch_collection.json is not complete")
            guard = collection.get("mainWorkspaceGuard")
            if isinstance(guard, dict) and guard.get("sourceHashMatches") is not True:
                close_blockers.append("main workspace source hash drift detected")
    else:
        close_blockers.append("missing epoch_collection.json; run collect-epoch --write first")
    try:
        manifest = load_epoch_manifest(run_dir)
        pool_path = run_dir / "pool_state.json"
        if pool_path.exists():
            pool = load_json(pool_path)
            if isinstance(pool, dict):
                protocol_warnings.extend(protocol_warnings_for_pool(pool, manifest))
        else:
            protocol_warnings.append("missing pool_state.json; dispatch/pool lifecycle was not recorded")
    except Exception as exc:  # noqa: BLE001
        protocol_warnings.append(f"could not audit phase protocol: {exc}")
    protocol_warnings = list(dict.fromkeys(protocol_warnings))
    top_decision = "invalid-epoch" if close_blockers else (decision_for_ranked(top, args.min_rank_score) if top else "no-results")
    summary = {
        "runDir": str(run_dir),
        "collection": str(collection_path) if collection_path.exists() else "",
        "collectionComplete": collection.get("complete") if collection else False,
        "validCloseout": not close_blockers,
        "closeBlockers": close_blockers,
        "protocolWarnings": protocol_warnings,
        "missingChildResults": missing,
        "ranked": ranked,
        "topCandidate": top,
        "topDecision": top_decision,
        "nextAction": (
            "continue-current-thread; finish valid collection before closing: dispatch ready/missing lanes, wait for active lanes, fix invalid child results, or explicitly pool-update unused lanes to cancelled with a blocker and rerun collect-epoch --write"
            if top_decision == "invalid-epoch"
            else
            "inspect diff and run gate-decision, then parent Promotion Gate"
            if top_decision == "eligible-for-parent-gate"
            else "record lessons, keep active baseline, and start diagnose/explore epoch"
        ),
    }
    if args.write:
        output = run_dir / "epoch_closeout.json"
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["written"] = str(output)
    write_json(summary)
    return 1 if top_decision == "invalid-epoch" else 0


def load_epoch_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "epoch_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"missing epoch_manifest.json: {manifest_path}")
    return load_json(manifest_path)


def load_or_infer_epoch_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "epoch_manifest.json"
    if manifest_path.exists():
        return load_json(manifest_path)
    workspaces = run_dir / "workspaces"
    lanes = []
    if workspaces.exists():
        for workspace in sorted(path for path in workspaces.iterdir() if path.is_dir()):
            lanes.append(
                {
                    "lane": workspace.name,
                    "attempt": workspace.name,
                    "workspace": str(workspace),
                    "prompt_path": "",
                    "baseline_sha256": "",
                }
            )
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "inferred": True,
        "lanes": lanes,
        "board": {},
    }


def child_result_has_current_evidence(path: Path, lane: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    try:
        result = load_json(path)
        errors, _warnings = validate_child_result(result)
        lane_errors, _lane_warnings = validate_child_against_lane(result, lane, strict=False)
        if errors or lane_errors:
            return False
        evidence_notes = result.get("evidenceNotes", {}) if isinstance(result.get("evidenceNotes", {}), dict) else {}
        return bool(result.get("currentEvidence") or evidence_notes.get("smallestDecisiveTestResult"))
    except Exception:  # noqa: BLE001
        return False


def cancelled_lane_names(pool: dict[str, Any] | None) -> set[str]:
    workers = pool.get("workers", []) if isinstance(pool, dict) else []
    return {
        str(worker.get("lane"))
        for worker in workers
        if isinstance(worker, dict)
        and worker.get("status") == "cancelled"
        and str(worker.get("blocker") or "").strip()
    }


def phase_a_complete(manifest: dict[str, Any], pool: dict[str, Any] | None = None) -> bool:
    phase_a_lanes = [lane for lane in manifest.get("lanes", []) if str(lane.get("phase") or lane_phase(lane)).upper() == "A"]
    if not phase_a_lanes:
        return True
    cancelled = cancelled_lane_names(pool)
    for lane in phase_a_lanes:
        if str(lane.get("lane") or "") in cancelled:
            continue
        workspace = Path(str(lane.get("workspace", ""))).resolve()
        if not child_result_has_current_evidence(workspace / "child_result.json", lane):
            return False
    return True


def selected_dispatch_phase(args_phase: str, manifest: dict[str, Any], pool: dict[str, Any] | None = None) -> str:
    requested = str(args_phase or "auto").upper()
    if requested == "ALL":
        return "ALL"
    if requested in ("A", "B"):
        return requested
    return "B" if phase_a_complete(manifest, pool) else "A"


def worker_phase(worker: dict[str, Any], manifest: dict[str, Any]) -> str:
    explicit = str(worker.get("phase") or "").upper()
    if explicit in ("A", "B"):
        return explicit
    lane_name = str(worker.get("lane") or "")
    for lane in manifest.get("lanes", []):
        if str(lane.get("lane") or "") == lane_name:
            return str(lane.get("phase") or lane_phase(lane)).upper()
    return ""


def protocol_warnings_for_pool(pool: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    workers = pool.get("workers", []) if isinstance(pool, dict) else []
    transitions = pool.get("phaseTransitions", []) if isinstance(pool, dict) else []
    dispatch_phase = str(pool.get("dispatchPhase") or "").upper() if isinstance(pool, dict) else ""
    has_phase_b_transition = dispatch_phase in ("B", "ALL") or any(
        isinstance(item, dict) and str(item.get("toPhase") or "").upper() in ("B", "ALL")
        for item in transitions
    )
    phase_b_started = False
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        status = str(worker.get("status") or "")
        phase = worker_phase(worker, manifest)
        if phase == "B" and status in ("active", "completed", "completed-invalid", "retired"):
            if not bool(
                worker.get("riskOverride")
                or worker.get("controlledRiskLane")
                or worker.get("architectureBreakoutLane")
                or worker.get("onlineConfirmedExploitLane")
                or worker.get("onlineExploitOverride")
            ):
                phase_b_started = True
        if status in ("active", "completed", "completed-invalid", "retired") and str(worker.get("blocker") or "").strip():
            warnings.append(f"worker {worker.get('lane')} is {status} but still has blocker: {worker.get('blocker')}")
    if phase_b_started and not has_phase_b_transition:
        warnings.append("Phase B worker started/completed without recorded phase-transition or dispatchPhase=B/ALL")
    return warnings


def command_dispatch_epoch(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    manifest = load_epoch_manifest(run_dir)
    pool_path = run_dir / "pool_state.json"
    existing_pool = load_json(pool_path) if pool_path.exists() else {}
    dispatch_phase = selected_dispatch_phase(args.phase, manifest, existing_pool if isinstance(existing_pool, dict) else None)
    phase_a_done = phase_a_complete(manifest, existing_pool if isinstance(existing_pool, dict) else None)
    risk_mode_active = controlled_risk_active(manifest)
    innovation_mode_active = innovation_active(manifest)
    tasks: list[dict[str, Any]] = []
    for lane in manifest.get("lanes", []):
        lane_phase_value = str(lane.get("phase") or lane_phase(lane)).upper()
        lane_risk_override = bool(risk_mode_active and controlled_risk_lane(lane) and dispatch_phase == "A" and lane_phase_value == "B")
        lane_architecture_override = bool(
            innovation_mode_active and architecture_breakout_lane(lane) and dispatch_phase == "A" and lane_phase_value == "B"
        )
        lane_online_exploit_override = bool(
            online_confirmed_exploit_lane(lane) and dispatch_phase == "A" and lane_phase_value == "B"
        )
        prompt_path = Path(str(lane.get("prompt_path", ""))).resolve()
        workspace = Path(str(lane.get("workspace", ""))).resolve()
        source_path = workspace / "src" / "Solution.cpp"
        expected_child_result = workspace / "child_result.json"
        started_path = workspace / "worker_started.json"
        heartbeat_path = workspace / "worker_heartbeat.json"
        observed_hash = sha256_file(source_path) if source_path.exists() else ""
        expected_hash = str(lane.get("baseline_sha256") or manifest.get("board", {}).get("baselineSha256") or "")
        workspace_solution = str(workspace / "src" / "Solution.cpp")
        infra_ready = bool(prompt_path.exists() and workspace.exists() and observed_hash.lower() == expected_hash.lower())
        phase_selected = (
            dispatch_phase == "ALL"
            or lane_phase_value == dispatch_phase
            or lane_risk_override
            or lane_architecture_override
            or lane_online_exploit_override
        )
        phase_blocker = ""
        if not phase_selected:
            phase_blocker = f"phase {lane_phase_value} held; current dispatch phase is {dispatch_phase}"
        elif lane_phase_value == "B" and not phase_a_done and dispatch_phase != "ALL" and not (
            lane_risk_override or lane_architecture_override or lane_online_exploit_override
        ):
            phase_blocker = "phase B blocked until Phase A child_result files contain currentEvidence"
        ready = bool(infra_ready and not phase_blocker)
        launch_message = (
            f"Read and execute this prompt file now: {prompt_path}\n"
            f"Use this assigned workspace as workdir: {workspace}\n"
            f"First write startup artifact: {started_path}\n"
            f"Then update heartbeat after each major step: {heartbeat_path}\n"
            f"Finish by writing child_result.json here: {expected_child_result}\n"
            "Do not edit the main project workspace."
        )
        tasks.append(
            {
                "lane": lane.get("lane"),
                "attempt": lane.get("attempt"),
                "phase": lane_phase_value,
                "riskOverride": lane_risk_override,
                "controlledRiskLane": controlled_risk_lane(lane),
                "onlineConfirmedExploitLane": online_confirmed_exploit_lane(lane),
                "forensicBeforePatch": bool(lane.get("forensicBeforePatch")),
                "sourcePositiveSignal": lane.get("sourcePositiveSignal"),
                "exactTargetRule": lane.get("exactTargetRule"),
                "architectureBreakoutLane": architecture_breakout_lane(lane),
                "datasetEvolutionLane": bool(lane.get("datasetEvolutionLane")),
                "requiresDatasetCandidate": bool(lane.get("requiresDatasetCandidate")),
                "architectureOverride": lane_architecture_override,
                "onlineExploitOverride": lane_online_exploit_override,
                "riskLevel": lane.get("riskLevel"),
                "contextPath": lane.get("contextPath") or lane.get("context_path", ""),
                "commandBudget": lane.get("commandBudget"),
                "timeBudgetMinutes": lane.get("timeBudgetMinutes"),
                "agentType": "worker",
                "spawnAgent": {
                    "agent_type": "worker",
                    "messagePath": str(prompt_path),
                    "launchMessage": launch_message,
                    "workspace": str(workspace),
                    "contextPath": lane.get("contextPath") or lane.get("context_path", ""),
                    "expectedArtifact": str(expected_child_result),
                    "stopCondition": "child_result.json written with schema-valid evidence, or baseline hash mismatch reported",
                    "startupContract": {
                        "firstArtifact": str(started_path),
                        "heartbeatArtifact": str(heartbeat_path),
                        "firstAction": "write worker_started.json before long analysis or benchmarks",
                        "heartbeatRule": "update worker_heartbeat.json after hash check and every major command",
                        "stallRecovery": "if pending_init or no startup artifact after 3-5 minutes, resend launchMessage once; if still unchanged, cancel lane with blocker",
                    },
                    "patchBoundary": {
                        "applyPatchAllowed": "absolute-workspace-paths-only",
                        "workspaceSolution": workspace_solution,
                        "forbiddenRelativeHeaders": ["src/Solution.cpp"],
                    },
                },
                "workspace": str(workspace),
                "workspaceSolution": workspace_solution,
                "promptPath": str(prompt_path),
                "launchMessage": launch_message,
                "startedPath": str(started_path),
                "heartbeatPath": str(heartbeat_path),
                "prompt": prompt_path.read_text(encoding="utf-8") if prompt_path.exists() and args.include_prompts else "",
                "expectedBaselineSha256": expected_hash,
                "observedWorkspaceSha256": observed_hash,
                "readyToDispatch": ready,
                "phaseSelected": phase_selected,
                "blocker": "" if ready else (phase_blocker or "missing prompt/workspace or workspace source hash mismatch"),
                "expectedChildResult": str(expected_child_result),
                "ownerState": "ready" if ready else "blocked",
                "retireAfter": "collect-epoch captures child_result.json or blocker is recorded",
                "stallPolicy": "No worker_started.json/worker_heartbeat.json/child_result.json after 3-5 minutes of active assignment means prompt delivery or startup stall; resend launchMessage once, then cancel with blocker if unchanged.",
            }
        )
    duplicate_lanes = sorted(
        lane
        for lane in {str(task["lane"]) for task in tasks}
        if len([task for task in tasks if str(task["lane"]) == lane]) > 1
    )
    existing_workers = {
        str(worker.get("lane")): worker
        for worker in existing_pool.get("workers", [])
        if isinstance(worker, dict)
    } if isinstance(existing_pool, dict) else {}
    workers: list[dict[str, Any]] = []
    for task in tasks:
        old = existing_workers.get(str(task["lane"]), {})
        old_status = str(old.get("status", ""))
        if old_status in ("active", "completed", "completed-invalid", "cancelled", "retired"):
            status = old_status
        else:
            status = "ready" if task["readyToDispatch"] else "blocked"
        workers.append(
            {
                "lane": task["lane"],
                "attempt": task["attempt"],
                "phase": task["phase"],
                "riskOverride": task.get("riskOverride", False),
                "controlledRiskLane": task.get("controlledRiskLane", False),
                "onlineConfirmedExploitLane": task.get("onlineConfirmedExploitLane", False),
                "forensicBeforePatch": task.get("forensicBeforePatch", False),
                "sourcePositiveSignal": task.get("sourcePositiveSignal"),
                "exactTargetRule": task.get("exactTargetRule"),
                "architectureBreakoutLane": task.get("architectureBreakoutLane", False),
                "datasetEvolutionLane": task.get("datasetEvolutionLane", False),
                "requiresDatasetCandidate": task.get("requiresDatasetCandidate", False),
                "architectureOverride": task.get("architectureOverride", False),
                "onlineExploitOverride": task.get("onlineExploitOverride", False),
                "riskLevel": task.get("riskLevel"),
                "workerId": old.get("workerId", ""),
                "status": status,
                "workspace": task["workspace"],
                "promptPath": task["promptPath"],
                "launchMessage": task["launchMessage"],
                "startedPath": task["startedPath"],
                "heartbeatPath": task["heartbeatPath"],
                "contextPath": task["contextPath"],
                "expectedChildResult": task["expectedChildResult"],
                "expectedBaselineSha256": task["expectedBaselineSha256"],
                "observedWorkspaceSha256": task["observedWorkspaceSha256"],
                "assignedAt": old.get("assignedAt"),
                "completedAt": old.get("completedAt"),
                "retiredAt": old.get("retiredAt"),
                "lastHeartbeatAt": old.get("lastHeartbeatAt", ""),
                "lastWorkspaceActivityAt": old.get("lastWorkspaceActivityAt", ""),
                "monitorStatus": old.get("monitorStatus", ""),
                "blocker": task["blocker"],
                "resultStatus": old.get("resultStatus", ""),
                "rankScore": old.get("rankScore"),
            }
        )
    max_workers = min(int(args.max_workers), DEFAULT_MAX_ACTIVE_WORKERS)
    if max_workers < 1:
        raise SystemExit("--max-workers must be at least 1")
    active_count = len([worker for worker in workers if worker["status"] == "active"])
    ready_count = len([worker for worker in workers if worker["status"] == "ready"])
    active_slots = max(0, max_workers - active_count)
    dispatchable_ready_lanes: list[str] = []
    dispatchable_ready_set: set[str] = set()
    if active_slots > 0:
        for worker in workers:
            if worker["status"] == "ready":
                lane_name = str(worker["lane"])
                dispatchable_ready_lanes.append(lane_name)
                dispatchable_ready_set.add(lane_name)
                if len(dispatchable_ready_lanes) >= active_slots:
                    break
    dispatch_tasks = [
        task
        for task in tasks
        if str(task["lane"]) in dispatchable_ready_set
    ]
    held_ready_lanes = [
        str(worker["lane"])
        for worker in workers
        if worker["status"] == "ready" and str(worker["lane"]) not in dispatchable_ready_set
    ]
    pool_state = {
        "version": 1,
        "runId": manifest.get("run_id"),
        "updatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "dispatchPhase": dispatch_phase,
        "phaseAComplete": phase_a_done,
        "controlledRiskModeActive": risk_mode_active,
        "innovationModeActive": innovation_mode_active,
        "maxActiveWorkers": max_workers,
        "requestedMaxWorkers": int(args.max_workers),
        "maxWorkersCapped": int(args.max_workers) != max_workers,
        "workers": workers,
        "active": [worker["lane"] for worker in workers if worker["status"] == "active"],
        "blocked": [worker["lane"] for worker in workers if worker["status"] == "blocked"],
        "completed": [worker["lane"] for worker in workers if worker["status"].startswith("completed")],
        "cancelled": [worker["lane"] for worker in workers if worker["status"] == "cancelled"],
        "retired": [worker["lane"] for worker in workers if worker["status"] == "retired"],
        "ready": [worker["lane"] for worker in workers if worker["status"] == "ready"],
        "dispatchableReady": dispatchable_ready_lanes,
        "heldReady": held_ready_lanes,
        "newWorkersAllowed": min(active_slots, ready_count),
        "duplicatesToClose": duplicate_lanes,
        "laneOwners": existing_pool.get("laneOwners", {}) if isinstance(existing_pool, dict) else {},
    }
    output = {
        "runDir": str(run_dir),
        "runId": manifest.get("run_id"),
        "dispatchPhase": dispatch_phase,
        "phaseAComplete": phase_a_done,
        "ready": bool(dispatchable_ready_lanes),
        "tasks": dispatch_tasks,
        "allTasks": tasks,
        "heldReady": held_ready_lanes,
        "poolState": pool_state,
        "maxWorkerPolicy": {
            "defaultMaxActiveWorkers": DEFAULT_MAX_ACTIVE_WORKERS,
            "effectiveMaxActiveWorkers": max_workers,
            "requestedMaxWorkers": int(args.max_workers),
            "capped": int(args.max_workers) != max_workers,
            "rule": "Normal epochs should have no heldReady lanes because idea-board/prepare-epoch are capped. If heldReady appears, do not launch it; finish or cancel active lanes first.",
        },
        "dispatchRule": "Spawn only tasks listed in tasks. Normal epochs should have tasks == all ready lanes and heldReady == []; if heldReady is non-empty, treat it as overflow from manual manifest edits or existing active slots, not as an immediate backlog. Every manifest lane must end as completed/completed-invalid, retired, or cancelled-with-blocker before close-epoch can be final.",
    }
    if args.write:
        path = run_dir / "dispatch_queue.json"
        atomic_write_json(path, output)
        atomic_write_json(pool_path, pool_state)
        output["written"] = str(path)
        output["poolWritten"] = str(pool_path)
    write_json(output)
    return 0 if output["ready"] else 1


def command_collect_epoch(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    manifest = load_or_infer_epoch_manifest(run_dir)
    root = project_root(args.project) if args.project else None
    weights = load_or_default_weights(root) if root else {}
    main_guard = main_workspace_guard(root) if root else None
    pool_path = run_dir / "pool_state.json"
    pool_state = load_json(pool_path) if pool_path.exists() else {}
    pool_workers = {
        str(worker.get("lane")): dict(worker)
        for worker in pool_state.get("workers", [])
        if isinstance(worker, dict)
    } if isinstance(pool_state, dict) else {}
    lanes: list[dict[str, Any]] = []
    now_dt = datetime.now(timezone.utc).astimezone()
    now = now_dt.isoformat(timespec="seconds")
    for lane in manifest.get("lanes", []):
        workspace = Path(str(lane.get("workspace", ""))).resolve()
        result_path = workspace / "child_result.json"
        row: dict[str, Any] = {
            "lane": lane.get("lane"),
            "attempt": lane.get("attempt"),
            "workspace": str(workspace),
            "childResult": str(result_path),
            "status": "missing",
        }
        worker = pool_workers.get(str(lane.get("lane")), {})
        if not worker:
            worker = {
                "lane": lane.get("lane"),
                "attempt": lane.get("attempt"),
                "phase": lane.get("phase") or lane_phase(lane),
                "riskOverride": bool(lane.get("riskOverride")),
                "controlledRiskLane": controlled_risk_lane(lane),
                "architectureBreakoutLane": architecture_breakout_lane(lane),
                "riskLevel": lane.get("riskLevel"),
                "workerId": "",
                "workspace": str(workspace),
                "promptPath": str(lane.get("prompt_path", "")),
                "launchMessage": "",
                "startedPath": str(workspace / "worker_started.json"),
                "heartbeatPath": str(workspace / "worker_heartbeat.json"),
                "contextPath": str(lane.get("contextPath") or lane.get("context_path", "")),
                "expectedChildResult": str(result_path),
                "expectedBaselineSha256": lane.get("baseline_sha256", ""),
                "observedWorkspaceSha256": "",
                "assignedAt": None,
                "completedAt": None,
                "retiredAt": None,
                "lastHeartbeatAt": "",
                "lastWorkspaceActivityAt": "",
                "monitorStatus": "",
                "blocker": "",
                "resultStatus": "",
                "rankScore": None,
            }
        expected_hash = str(
            worker.get("expectedBaselineSha256")
            or lane.get("baseline_sha256")
            or manifest.get("board", {}).get("baselineSha256")
            or ""
        )
        monitor = worker_progress_monitor(worker, workspace, now_dt)
        partial_evidence = workspace_partial_evidence(workspace, expected_hash)
        row["monitor"] = monitor
        row["partialEvidence"] = partial_evidence
        if result_path.exists():
            try:
                loaded_result = load_json(result_path)
                if isinstance(loaded_result, dict) and args.write:
                    if augment_compile_failure_result(loaded_result, workspace):
                        atomic_write_json(result_path, loaded_result)
                result = apply_lane_metadata(loaded_result, lane)
                errors, warnings = validate_child_result(result)
                lane_errors, lane_warnings = validate_child_against_lane(result, lane, strict=False)
                errors.extend(lane_errors)
                warnings.extend(lane_warnings)
                rank_score, strengths, risks = score_child(result, weights)
                if errors:
                    rank_score -= 100
                    risks.extend(errors)
                row.update(
                    {
                        "status": "completed-invalid" if errors else "completed",
                        "rankScore": round(rank_score, 4),
                        "promotionCandidate": result.get("promotionCandidate"),
                        "result": result.get("result"),
                        "summary": result.get("summary"),
                        "schemaErrors": errors,
                        "schemaWarnings": warnings,
                        "strengths": strengths,
                        "risks": risks,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                row.update({"status": "unreadable", "error": str(exc), "rankScore": -999})
        elif partial_evidence.get("hasPartial"):
            row.update(
                {
                    "status": "partial-needs-recovery",
                    "result": "missing-child-result",
                    "summary": "Workspace has source/compile/benchmark/heartbeat evidence but no child_result.json.",
                    "rankScore": -500,
                    "schemaErrors": [],
                    "schemaWarnings": ["partial worker evidence must be recovered before close-epoch"],
                    "strengths": [],
                    "risks": [
                        "do not cancel as no-worker; recover artifacts into child_result.json or rerun smallest decisive test"
                    ],
                }
            )
        elif str(worker.get("status") or "") == "cancelled" and str(worker.get("blocker") or "").strip():
            row.update(
                {
                    "status": "cancelled",
                    "result": "cancelled-no-worker",
                    "summary": str(worker.get("blocker")),
                    "rankScore": -999,
                    "schemaErrors": [],
                    "schemaWarnings": [],
                    "strengths": [],
                    "risks": ["lane explicitly cancelled by coordinator"],
                }
            )
        lanes.append(row)
        if row["status"].startswith("completed"):
            worker["status"] = row["status"]
            worker["completedAt"] = worker.get("completedAt") or now
            worker["resultStatus"] = row.get("result", "")
            worker["rankScore"] = row.get("rankScore")
            worker["blocker"] = ""
        elif row["status"] == "cancelled":
            worker["status"] = "cancelled"
        elif row["status"] == "partial-needs-recovery":
            worker["status"] = "blocked"
            worker["blocker"] = "partial workspace evidence exists without child_result.json; recover before close"
        elif row["status"] == "missing" and worker.get("status") not in ("active", "retired", "cancelled"):
            worker["status"] = "ready"
        elif row["status"] == "unreadable":
            worker["status"] = "blocked"
            worker["blocker"] = row.get("error", "unreadable child_result")
        worker["startedPath"] = worker.get("startedPath") or str(workspace / "worker_started.json")
        worker["heartbeatPath"] = worker.get("heartbeatPath") or str(workspace / "worker_heartbeat.json")
        worker["lastHeartbeatAt"] = monitor.get("lastHeartbeatAt", "")
        worker["lastWorkspaceActivityAt"] = monitor.get("lastWorkspaceActivity", {}).get("updatedAt", "")
        worker["monitorStatus"] = monitor.get("state", "")
        pool_workers[str(lane.get("lane"))] = worker
    completed = [lane for lane in lanes if lane.get("status") == "completed"]
    cancelled = [lane for lane in lanes if lane.get("status") == "cancelled"]
    invalid = [lane for lane in lanes if lane.get("status") == "completed-invalid"]
    partial = [lane for lane in lanes if lane.get("status") == "partial-needs-recovery"]
    ranked = sorted(completed, key=lambda item: item.get("rankScore", -999), reverse=True)
    workers = list(pool_workers.values())
    max_workers = int(pool_state.get("maxActiveWorkers", 4)) if isinstance(pool_state, dict) else 4
    active_count = len([worker for worker in workers if worker.get("status") == "active"])
    ready_count = len([worker for worker in workers if worker.get("status") == "ready"])
    next_pool = {
        "version": 1,
        "runId": manifest.get("run_id"),
        "updatedAt": now,
        "dispatchPhase": pool_state.get("dispatchPhase", "") if isinstance(pool_state, dict) else "",
        "phaseAComplete": phase_a_complete(manifest, pool_state if isinstance(pool_state, dict) else None),
        "phaseTransitions": pool_state.get("phaseTransitions", []) if isinstance(pool_state, dict) else [],
        "maxActiveWorkers": max_workers,
        "workers": workers,
        "active": [worker.get("lane") for worker in workers if worker.get("status") == "active"],
        "blocked": [worker.get("lane") for worker in workers if worker.get("status") == "blocked"],
        "completed": [worker.get("lane") for worker in workers if str(worker.get("status", "")).startswith("completed")],
        "cancelled": [worker.get("lane") for worker in workers if worker.get("status") == "cancelled"],
        "retired": [worker.get("lane") for worker in workers if worker.get("status") == "retired"],
        "ready": [worker.get("lane") for worker in workers if worker.get("status") == "ready"],
        "retireCandidates": [worker.get("lane") for worker in workers if str(worker.get("status", "")).startswith("completed")],
        "newWorkersAllowed": min(max(0, max_workers - active_count), ready_count),
        "duplicatesToClose": pool_state.get("duplicatesToClose", []) if isinstance(pool_state, dict) else [],
        "laneOwners": pool_state.get("laneOwners", {}) if isinstance(pool_state, dict) else {},
    }
    protocol_warnings = protocol_warnings_for_pool(next_pool, manifest)
    stalled = [
        lane
        for lane in lanes
        if lane.get("status") == "missing"
        and lane.get("monitor", {}).get("state") in ("not-started-or-prompt-not-consumed", "started-no-heartbeat")
    ]
    output = {
        "runDir": str(run_dir),
        "runId": manifest.get("run_id"),
        "complete": len(completed) + len(cancelled) == len(lanes) and all(lane.get("status") in ("completed", "cancelled") for lane in lanes),
        "lanes": lanes,
        "ranked": ranked,
        "cancelledLanes": cancelled,
        "partialRecoveryLanes": partial,
        "stalledOrUnobservableLanes": stalled,
        "poolState": next_pool,
        "protocolWarnings": protocol_warnings,
        "nextAction": (
            "close-epoch"
            if len(completed) + len(cancelled) == len(lanes) and ranked
            else "recover-partial-workers-into-child-result"
            if partial
            else "recover-or-cancel-stalled-workers"
            if stalled
            else "fix-invalid-child-results-or-reject-epoch-before-close"
            if invalid
            else "continue-current-thread-dispatch-wait-or-cancel-open-lanes"
        ),
    }
    if main_guard is not None:
        output["mainWorkspaceGuard"] = main_guard
        if not main_guard["sourceHashMatches"]:
            output["complete"] = False
            output["nextAction"] = "stop-and-classify-main-workspace-drift"
            for lane in output["ranked"]:
                lane.setdefault("risks", []).append("main workspace source drift detected during collect-epoch")
    if args.write:
        path = run_dir / "epoch_collection.json"
        atomic_write_json(path, output)
        atomic_write_json(pool_path, next_pool)
        output["written"] = str(path)
        output["poolWritten"] = str(pool_path)
    write_json(output)
    return 0 if output["complete"] else 1


def command_pool_update(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    pool_path = run_dir / "pool_state.json"
    with file_lock(pool_path):
        if not pool_path.exists():
            raise SystemExit(f"missing pool_state.json: {pool_path}; run dispatch-epoch --write first")
        pool = load_json(pool_path)
        workers = pool.get("workers", [])
        if not isinstance(workers, list):
            raise SystemExit("pool_state.json workers must be a list")
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        matched = False
        for worker in workers:
            if not isinstance(worker, dict) or str(worker.get("lane")) != args.lane:
                continue
            matched = True
            if args.status == "cancelled" and not (args.blocker or str(worker.get("blocker") or "").strip()):
                raise SystemExit("cancelled lanes require --blocker explaining why the manifest lane will not produce child_result.json")
            worker["status"] = args.status
            if args.worker_id:
                worker["workerId"] = args.worker_id
            if args.blocker:
                worker["blocker"] = args.blocker
            if args.clear_blocker:
                worker["blocker"] = ""
            if args.status == "active":
                worker["assignedAt"] = worker.get("assignedAt") or now
            elif args.status.startswith("completed"):
                worker["completedAt"] = worker.get("completedAt") or now
            elif args.status == "retired":
                worker["retiredAt"] = worker.get("retiredAt") or now
            break
        if not matched:
            raise SystemExit(f"lane not found in pool_state.json: {args.lane}")
        max_workers = int(pool.get("maxActiveWorkers", 4))
        active_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"])
        ready_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"])
        pool.update(
            {
                "updatedAt": now,
                "workers": workers,
                "active": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"],
                "blocked": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "blocked"],
                "completed": [
                    worker.get("lane")
                    for worker in workers
                    if isinstance(worker, dict) and str(worker.get("status", "")).startswith("completed")
                ],
                "cancelled": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "cancelled"],
                "retired": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "retired"],
                "ready": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"],
                "newWorkersAllowed": min(max(0, max_workers - active_count), ready_count),
            }
        )
        if args.write:
            atomic_write_json(pool_path, pool)
    write_json({"pool": str(pool_path), "write": args.write, "lane": args.lane, "status": args.status, "poolState": pool})
    return 0


def command_phase_transition(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    manifest = load_epoch_manifest(run_dir)
    pool_path = run_dir / "pool_state.json"
    with file_lock(pool_path):
        if not pool_path.exists():
            raise SystemExit(f"missing pool_state.json: {pool_path}; run dispatch-epoch --write first")
        pool = load_json(pool_path)
        workers = pool.get("workers", [])
        if not isinstance(workers, list):
            raise SystemExit("pool_state.json workers must be a list")
        to_phase = str(args.to_phase).upper()
        phase_a_done = phase_a_complete(manifest, pool)
        if to_phase == "B" and not phase_a_done and not args.force:
            raise SystemExit("Phase A is not complete; use --force only with an explicit coordinator reason")
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        changed: list[str] = []
        for worker in workers:
            if not isinstance(worker, dict):
                continue
            phase = worker_phase(worker, manifest)
            if to_phase != "ALL" and phase != to_phase:
                continue
            status = str(worker.get("status") or "")
            if status == "cancelled":
                continue
            if status in ("completed", "completed-invalid", "retired"):
                worker["blocker"] = ""
                continue
            blocker = str(worker.get("blocker") or "")
            if status == "blocked" and blocker.startswith("phase"):
                worker["status"] = "ready"
                worker["blocker"] = ""
                changed.append(str(worker.get("lane")))
            elif status in ("ready", "active"):
                worker["blocker"] = ""
                changed.append(str(worker.get("lane")))
        max_workers = int(pool.get("maxActiveWorkers", 4))
        active_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"])
        ready_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"])
        transitions = pool.get("phaseTransitions", [])
        if not isinstance(transitions, list):
            transitions = []
        transitions.append(
            {
                "at": now,
                "toPhase": to_phase,
                "phaseAComplete": phase_a_done,
                "force": bool(args.force),
                "reason": args.reason,
                "changedLanes": changed,
            }
        )
        pool.update(
            {
                "updatedAt": now,
                "dispatchPhase": to_phase,
                "phaseAComplete": phase_a_done,
                "phaseTransitions": transitions,
                "workers": workers,
                "active": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"],
                "blocked": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "blocked"],
                "completed": [
                    worker.get("lane")
                    for worker in workers
                    if isinstance(worker, dict) and str(worker.get("status", "")).startswith("completed")
                ],
                "retired": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "retired"],
                "ready": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"],
                "newWorkersAllowed": min(max(0, max_workers - active_count), ready_count),
            }
        )
        warnings = protocol_warnings_for_pool(pool, manifest)
        if args.write:
            atomic_write_json(pool_path, pool)
    write_json(
        {
            "pool": str(pool_path),
            "write": args.write,
            "toPhase": to_phase,
            "phaseAComplete": phase_a_done,
            "changedLanes": changed,
            "protocolWarnings": warnings,
            "poolState": pool,
        }
    )
    return 0


def command_pool_retire(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    pool_path = run_dir / "pool_state.json"
    with file_lock(pool_path):
        if not pool_path.exists():
            raise SystemExit(f"missing pool_state.json: {pool_path}")
        pool = load_json(pool_path)
        workers = pool.get("workers", [])
        if not isinstance(workers, list):
            raise SystemExit("pool_state.json workers must be a list")
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        targets = set(args.lane or [])
        if args.completed:
            targets.update(
                str(worker.get("lane"))
                for worker in workers
                if isinstance(worker, dict) and str(worker.get("status", "")).startswith("completed")
            )
        if not targets:
            targets.update(str(item) for item in pool.get("retireCandidates", []) if item)
        retired: list[str] = []
        for worker in workers:
            if not isinstance(worker, dict) or str(worker.get("lane")) not in targets:
                continue
            if worker.get("status") == "active" and not args.force:
                continue
            worker["status"] = "retired"
            worker["blocker"] = ""
            worker["retiredAt"] = worker.get("retiredAt") or now
            retired.append(str(worker.get("lane")))
        max_workers = int(pool.get("maxActiveWorkers", 4))
        active_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"])
        ready_count = len([worker for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"])
        pool.update(
            {
                "updatedAt": now,
                "workers": workers,
                "active": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "active"],
                "blocked": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "blocked"],
                "completed": [
                    worker.get("lane")
                    for worker in workers
                    if isinstance(worker, dict) and str(worker.get("status", "")).startswith("completed")
                ],
                "retired": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "retired"],
                "ready": [worker.get("lane") for worker in workers if isinstance(worker, dict) and worker.get("status") == "ready"],
                "retireCandidates": [],
                "newWorkersAllowed": min(max(0, max_workers - active_count), ready_count),
            }
        )
        if args.write:
            atomic_write_json(pool_path, pool)
    write_json({"pool": str(pool_path), "write": args.write, "retired": retired, "poolState": pool})
    return 0


def child_result_paths(run_dir: Path) -> list[Path]:
    search_dir = run_dir / "workspaces" if (run_dir / "workspaces").is_dir() else run_dir
    if run_dir.is_file():
        return [run_dir]
    return sorted(search_dir.rglob("child_result.json"))


def result_record(result: dict[str, Any], path: Path) -> dict[str, Any]:
    _run_dir, manifest = epoch_manifest_for_child(path.resolve())
    result = apply_lane_metadata(result, lane_for_child_path(path.resolve(), manifest))
    fp = fingerprint(
        {
            "id": result.get("worker") or path.parent.name,
            "basedOn": result.get("basedOn"),
            "hypothesis": result.get("hypothesis"),
            "affectedFamily": result_family(result),
            "changedMechanism": result_mechanism(result),
            "parameter_or_rule": result.get("knob") or result_shape(result),
            "direction": result.get("direction") or direction_from(json.dumps(result, ensure_ascii=False).lower()),
            "summary": result.get("summary"),
            "avoidNextTime": result.get("avoidNextTime"),
        }
    )
    rank_score, strengths, risks = score_child(result)
    return {
        "id": result.get("worker") or path.parent.name,
        "source": str(path),
        "fingerprint": fp,
        "fingerprintKey": fingerprint_key(fp),
        "family": fp["affected_family"],
        "mechanism": fp["changed_mechanism"],
        "shape": result_shape(result),
        "rankScore": round(rank_score, 4),
        "promotionCandidate": result.get("promotionCandidate"),
        "result": result.get("result"),
        "summary": result.get("summary"),
        "avoidNextTime": result.get("avoidNextTime"),
        "strengths": strengths,
        "risks": risks,
    }


def lesson_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def command_learn_from_children(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    run_dir = Path(args.run_dir).resolve()
    write_failed_diffs = bool(args.write_failed_diffs or args.write_index or args.write_search_graph)
    rows: list[dict[str, Any]] = []
    frozen_to_add: list[str] = []
    positive_patterns: list[dict[str, Any]] = []
    negative_patterns: list[dict[str, Any]] = []
    failed_diff_updates: list[dict[str, Any]] = []
    for result_path in child_result_paths(run_dir):
        try:
            result = load_json(result_path)
        except Exception as exc:  # noqa: BLE001
            rows.append({"source": str(result_path), "error": str(exc)})
            continue
        row = result_record(result, result_path)
        rows.append(row)
        try:
            failed_diff_updates.append(
                archive_failed_diff_for_child(root, run_dir, result_path, result, write=write_failed_diffs)
            )
        except Exception as exc:  # noqa: BLE001
            failed_diff_updates.append({"source": str(result_path), "error": str(exc), "archived": False})
        lessons = lesson_items(row.get("avoidNextTime"))
        if lessons and row.get("promotionCandidate") is not True:
            frozen_to_add.extend(lessons)
            negative_patterns.append(row)
        elif row.get("promotionCandidate") is True and row.get("rankScore", 0) >= args.min_rank_score:
            positive_patterns.append(row)
    attempt_cards: list[dict[str, Any]] = []
    graph_updates: list[dict[str, Any]] = []
    for result_path in child_result_paths(run_dir):
        try:
            card = attempt_card_from_child_result(root, result_path)
            attempt_cards.append(card)
            graph_updates.append(update_search_graph_from_card(root, card, write=args.write_search_graph))
        except Exception as exc:  # noqa: BLE001
            graph_updates.append({"source": str(result_path), "error": str(exc)})
    space_path = mutation_space_path(args.mutation_space)
    mutation_patch: dict[str, Any] = {
        "sourceMutationSpace": str(space_path),
        "addFrozenPatterns": sorted(set(frozen_to_add)),
        "positivePatterns": positive_patterns,
        "negativePatterns": negative_patterns,
    }
    index_path = root / "docs" / "exploration-index.json"
    index = {"version": 1, "updatedAt": None, "entries": []}
    if index_path.exists():
        index = load_json(index_path)
    existing_keys = {
        str(item.get("fingerprintKey", ""))
        for item in index.get("entries", [])
        if isinstance(item, dict)
    }
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    new_entries = []
    for row in rows:
        key = str(row.get("fingerprintKey", ""))
        if not key or key in existing_keys:
            continue
        entry = {
            "attempt": row.get("id"),
            "source": row.get("source"),
            "fingerprint": row.get("fingerprint"),
            "fingerprintKey": key,
            "result": row.get("result"),
            "promotionCandidate": row.get("promotionCandidate"),
            "rankScore": row.get("rankScore"),
            "lesson": lesson_items(row.get("avoidNextTime")) or row.get("summary"),
            "retryPolicy": "only-with-new-guard" if lesson_items(row.get("avoidNextTime")) else "allowed",
            "recordedAt": now,
        }
        new_entries.append(entry)
        existing_keys.add(key)
    if args.write_index:
        index.setdefault("entries", []).extend(new_entries)
        index["updatedAt"] = now
        atomic_write_json(index_path, index)
    if args.write_mutation_space and frozen_to_add:
        space = load_json(space_path)
        current = list(space.get("frozenPatterns", []))
        for item in sorted(set(frozen_to_add)):
            if item not in current:
                current.append(item)
        space["frozenPatterns"] = current
        atomic_write_json(space_path, space)
    write_json(
        {
            "runDir": str(run_dir),
            "childResults": rows,
            "mutationSpacePatch": mutation_patch,
            "explorationIndex": {
                "path": str(index_path),
                "write": args.write_index,
                "newEntries": new_entries,
            },
            "attemptCards": {
                "dir": str(attempt_cards_dir(root)),
                "write": args.write_search_graph,
                "cards": attempt_cards,
            },
            "searchGraph": {
                "path": str(search_graph_path(root)),
                "write": args.write_search_graph,
                "updates": graph_updates,
            },
            "failedDiffs": {
                "indexPath": str(failed_diffs_index_path(root)),
                "dir": str(failed_diffs_dir(root)),
                "write": write_failed_diffs,
                "updates": failed_diff_updates,
            },
            "writeMutationSpace": args.write_mutation_space,
        }
    )
    return 0


def command_archive_attempt(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger_file = ledger_path(root)
    ledger = load_json(ledger_file)
    child_path = Path(args.child_result).resolve()
    loaded_child = load_json(child_path)
    _run_dir, manifest = epoch_manifest_for_child(child_path)
    lane = lane_for_child_path(child_path, manifest)
    child = apply_lane_metadata(loaded_child, lane)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    bucket = args.bucket
    if bucket == "auto":
        bucket = "successfulExperiments" if child.get("promotionCandidate") is True and args.accepted else "failedExperiments"
    if bucket not in ("successfulExperiments", "failedExperiments"):
        raise SystemExit("bucket must be successfulExperiments, failedExperiments, or auto")
    closeout_path, closeout = closeout_for_child(child_path)
    override: dict[str, Any] | None = None
    if args.accepted and bucket == "successfulExperiments" and closeout_path is not None:
        top_decision = str(closeout.get("topDecision", "") if isinstance(closeout, dict) else "")
        eligible = top_decision == "eligible-for-parent-gate"
        if not eligible and not args.manual_override:
            raise SystemExit(
                f"epoch closeout decision is {top_decision or 'missing'}; "
                "refuse accepted archive without --manual-override --override-reason"
            )
        if args.manual_override:
            if not args.override_reason.strip():
                raise SystemExit("--manual-override requires --override-reason")
            override = {
                "type": "manual-closeout-override",
                "closeoutPath": str(closeout_path),
                "previousTopDecision": top_decision or "missing",
                "reason": args.override_reason.strip(),
            }
    attempt_id = (
        args.attempt
        or str(child.get("attemptId") or child.get("attempt") or child.get("laneId") or child_path.parent.name)
    )
    existing = [
        item
        for item in ledger.get(bucket, [])
        if isinstance(item, dict) and str(item.get("id") or item.get("attempt")) == attempt_id
    ]
    if existing and not args.force:
        raise SystemExit(f"{bucket} already contains attempt {attempt_id}; use --force to append anyway")
    record = {
        "id": attempt_id,
        "createdAt": now,
        "basedOn": child.get("basedOn"),
        "baselineSha256": child.get("baselineSha256"),
        "hypothesis": child.get("hypothesis"),
        "affectedFamily": result_family(child),
        "changedMechanism": result_mechanism(child),
        "hiddenShape": result_shape(child),
        "parameter_or_rule": result_shape(child),
        "changedFiles": child.get("changedFiles", []),
        "checksRun": child.get("checksRun", []),
        "scores": child.get("scores", {}),
        "deltasVsBaseline": child.get("deltasVsBaseline", {}),
        "notableRegressions": child.get("notableRegressions", []),
        "runtimeRisk": child.get("runtimeRisk"),
        "promotionCandidate": child.get("promotionCandidate"),
        "result": args.result or child.get("result"),
        "summary": child.get("summary"),
        "failureReason": args.failure_reason or (child.get("summary") if bucket == "failedExperiments" else ""),
        "avoidNextTime": child.get("avoidNextTime"),
        "sourceChildResult": str(child_path),
        "archivedBy": "score_loop_tools.py archive-attempt",
    }
    if override:
        record["manualOverride"] = override
    patched = dict(ledger)
    patched.setdefault(bucket, []).append(record)
    patched["updatedAt"] = now
    attempt_card = attempt_card_from_child_result(root, child_path)
    attempt_card["ledgerBucket"] = bucket
    attempt_card["ledgerRecord"] = record
    search_graph_update = update_search_graph_from_card(root, attempt_card, write=args.write_search_graph)
    if args.write:
        atomic_write_json(ledger_file, patched)
    write_json(
        {
            "ledger": str(ledger_file),
            "write": args.write,
            "bucket": bucket,
            "record": record,
            "attemptCard": attempt_card,
            "searchGraph": search_graph_update,
        }
    )
    return 0


def command_attempt_card(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    child_path = Path(args.child_result).resolve()
    card = attempt_card_from_child_result(root, child_path)
    graph_update = update_search_graph_from_card(root, card, write=args.write_search_graph)
    if args.write:
        attempt_cards_dir(root).mkdir(parents=True, exist_ok=True)
        atomic_write_json(attempt_card_path(root, str(card.get("id") or child_path.parent.name)), card)
    write_json(
        {
            "card": card,
            "cardPath": str(attempt_card_path(root, str(card.get("id") or child_path.parent.name))),
            "write": args.write,
            "searchGraph": graph_update,
        }
    )
    return 0


def command_search_graph(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    graph = load_or_default_search_graph(root)
    rebuilt_cards: list[dict[str, Any]] = []
    if args.rebuild_from:
        source = Path(args.rebuild_from).resolve()
        for result_path in child_result_paths(source):
            try:
                card = attempt_card_from_child_result(root, result_path)
                rebuilt_cards.append(card)
                update_search_graph_from_card(root, card, write=args.write)
            except Exception as exc:  # noqa: BLE001
                rebuilt_cards.append({"source": str(result_path), "error": str(exc)})
        graph = load_or_default_search_graph(root)
    context = search_system_context(root, limit=args.limit)
    nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    write_json(
        {
            "graphPath": str(search_graph_path(root)),
            "exists": search_graph_path(root).exists(),
            "write": args.write,
            "nodeCount": len(nodes),
            "edgeCount": len([item for item in graph.get("edges", []) if isinstance(item, dict)]),
            "recentNodes": nodes[-args.limit :],
            "fusionCandidates": context.get("fusionCandidates", [])[: args.limit],
            "rebuiltCards": rebuilt_cards,
            "rule": "Use this as a search-memory surface: revive, ablate, or fuse branches only as named hypotheses with first-kill evidence.",
        }
    )
    return 0


def command_failed_diffs(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    rebuild_updates: list[dict[str, Any]] = []
    if args.rebuild_from:
        source = Path(args.rebuild_from).resolve()
        run_dir = source if source.is_dir() else source.parent
        for result_path in child_result_paths(source):
            try:
                loaded = load_json(result_path)
                rebuild_updates.append(archive_failed_diff_for_child(root, run_dir, result_path, loaded, write=args.write))
            except Exception as exc:  # noqa: BLE001
                rebuild_updates.append({"source": str(result_path), "error": str(exc), "archived": False})
    index = load_or_default_failed_diffs_index(root)
    records = [item for item in index.get("records", []) if isinstance(item, dict)]
    filtered = records
    if args.family:
        filtered = [item for item in filtered if str(item.get("family") or "") == args.family]
    if args.mechanism:
        filtered = [item for item in filtered if str(item.get("mechanism") or "") == args.mechanism]
    if args.target_function:
        filtered = [
            item
            for item in filtered
            if args.target_function in [str(value) for value in item.get("targetFunctions", [])]
        ]
    if args.control_tag:
        filtered = [
            item
            for item in filtered
            if args.control_tag in [str(value) for value in item.get("controlTags", [])]
        ]
    novelty = None
    if args.hypothesis or args.target_function or args.control_tag:
        signature = static_diff_signature(
            args.hypothesis,
            {
                "hypothesis": args.hypothesis,
                "affectedFamily": args.family,
                "changedMechanism": args.mechanism,
            },
            None,
        )
        if args.target_function and args.target_function not in signature["targetFunctions"]:
            signature["targetFunctions"].append(args.target_function)
        if args.control_tag and args.control_tag not in signature["controlTags"]:
            signature["controlTags"].append(args.control_tag)
        novelty = novelty_assessment_for_signature(index, signature, args.family or "unknown", args.mechanism or "unknown")
    write_json(
        {
            "indexPath": str(failed_diffs_index_path(root)),
            "failedDiffsDir": str(failed_diffs_dir(root)),
            "write": args.write,
            "rebuildFrom": args.rebuild_from,
            "rebuildUpdates": rebuild_updates,
            "recordCount": len(records),
            "filteredCount": len(filtered),
            "records": filtered[-args.limit :],
            "noveltyAssessment": novelty,
            "riskResurrectionCandidates": [
                item
                for item in filtered
                if item.get("compilation") == "SUCCESS"
                and item.get("firstKillResult") in ("MOVED_POSITIVE", "FAILED_REGRESSION", "FLAT", "UNKNOWN")
            ][-args.limit :],
        }
    )
    return 0


def load_or_default_weights(root: Path) -> dict[str, Any]:
    path = root / "docs" / "online-offline-weights.json"
    if path.exists():
        return load_json(path)
    return {"version": 1, "updatedAt": None, "families": {}, "history": []}


def online_actual_from_delta(delta: Any, status: str = "") -> str:
    if status and status.lower() not in ("success", "accepted", "ok"):
        return "down"
    value = as_float(delta)
    if value is None:
        return "neutral"
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "neutral"


def family_from_online_record(record: dict[str, Any]) -> str:
    text = " ".join(str(record.get(key, "")) for key in ("baseline", "decision", "note", "submittedPackage")).lower()
    return classify(text, FAMILY_KEYWORDS, "unknown")


def mechanism_from_online_record(record: dict[str, Any]) -> str:
    text = " ".join(str(record.get(key, "")) for key in ("baseline", "decision", "note", "submittedPackage")).lower()
    return classify(text, MECHANISM_KEYWORDS, "unknown")


def update_weight_node(
    node: dict[str, Any],
    actual: str,
    *,
    confirm_step: float,
    contradict_step: float,
    neutral_step: float = 0.0,
    now: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    old_weight = float(node.get("current_weight", 0.5))
    if actual == "up":
        new_weight = min(1.0, old_weight + confirm_step)
        node["online_confirmed"] = int(node.get("online_confirmed", 0)) + 1
        calibration = "confirmed-positive"
    elif actual == "down":
        new_weight = max(0.0, old_weight - contradict_step)
        node["online_contradicted"] = int(node.get("online_contradicted", 0)) + 1
        calibration = "contradicted-negative"
    else:
        new_weight = max(0.0, min(1.0, old_weight + neutral_step))
        calibration = "neutral"
    node["current_weight"] = round(new_weight, 4)
    node["evidence_count"] = int(node.get("evidence_count", 0)) + 1
    if now:
        node["last_update"] = now
    if reason:
        node["reason"] = reason
    return {
        "calibration_result": calibration,
        "offline_weight_update": {"old": round(old_weight, 4), "new": round(new_weight, 4)},
        "node": node,
    }


def update_family_weight_from_online(
    families: dict[str, Any],
    family_name: str,
    actual: str,
    *,
    confirm_step: float,
    contradict_step: float,
) -> dict[str, Any]:
    family = families.setdefault(
        family_name,
        {
            "current_weight": 0.5,
            "evidence_count": 0,
            "online_confirmed": 0,
            "online_contradicted": 0,
            "last_update": None,
            "reason": "",
        },
    )
    update = update_weight_node(
        family,
        actual,
        confirm_step=confirm_step,
        contradict_step=contradict_step,
    )
    return {
        "calibration_result": update["calibration_result"],
        "offline_weight_update": update["offline_weight_update"],
        "family": family,
    }


def ledger_online_eval_record(
    args: argparse.Namespace,
    baseline: dict[str, Any],
    online_score: float,
    online_delta: float | None,
    actual: str,
    calibration: str,
    next_action: str,
    now: str,
    weight_history_id: str,
) -> dict[str, Any]:
    best = as_float(baseline.get("scores", {}).get("bestKnownOnlineScore"))
    if actual == "up":
        status = "confirmed-better"
    elif actual == "down":
        status = "rejected-after-online-submission"
    elif actual == "neutral":
        status = "neutral"
    else:
        status = "diagnostic"
    return {
        "baseline": args.attempt,
        "basedOn": args.based_on or baseline.get("id"),
        "submittedPackage": args.submitted_package,
        "submittedAt": args.submitted_at or now,
        "reportedAt": now,
        "status": status,
        "score": online_score,
        "previousBestOnlineScore": best,
        "bestKnownOnlineScoreAtSubmit": best,
        "delta": online_delta,
        "firstPlaceScoreSnapshot": baseline.get("scores", {}).get("firstPlaceScoreSnapshot"),
        "gapToFirstPlace": (
            baseline.get("scores", {}).get("firstPlaceScoreSnapshot") - online_score
            if isinstance(baseline.get("scores", {}).get("firstPlaceScoreSnapshot"), (int, float))
            else None
        ),
        "decision": next_action,
        "affected_family": args.family,
        "changed_mechanism": args.mechanism,
        "hidden_shape": args.shape,
        "predicted_direction": args.predicted_direction,
        "actual_direction": actual,
        "calibration_result": calibration,
        "local_quick_delta": args.local_quick_delta,
        "local_full_delta": args.local_full_delta,
        "hidden_dataset_hypothesis": args.hidden_hypothesis,
        "next_action": next_action,
        "source": "score_loop_tools.py online-update",
        "weightHistoryId": weight_history_id,
        "note": args.reason,
    }


def normalize_submission_attempt(package_name: str) -> str:
    stem = Path(package_name).name
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    if stem.startswith("submission_"):
        stem = stem[len("submission_") :]
    stem = re.split(r"_(?:q|f|off|pdf)\d+_", stem, maxsplit=1, flags=re.IGNORECASE)[0]
    return stem.strip("_") or Path(package_name).stem


def load_submission_map(root: Path) -> dict[str, Any]:
    path = submission_map_path(root)
    if path.exists():
        return load_json(path)
    return {"version": 1, "updatedAt": None, "submissions": []}


def submission_lookup_keys(package_name: str, attempt: str = "") -> set[str]:
    name = Path(package_name).name if package_name else ""
    stem = Path(name).stem if name else ""
    normalized = normalize_submission_attempt(name) if name else ""
    keys = {item for item in (name, stem, normalized, attempt) if item}
    keys.update({item.lower() for item in list(keys) if item})
    return keys


def lookup_submission_mapping(root: Path, package_name: str, attempt: str = "") -> dict[str, Any]:
    mapping = load_submission_map(root)
    keys = submission_lookup_keys(package_name, attempt)
    for record in reversed(mapping.get("submissions", [])):
        if not isinstance(record, dict):
            continue
        record_keys: set[str] = set()
        for package_field in ("packageName", "submittedPackage", "sourcePackage", "packagePath"):
            record_keys.update(submission_lookup_keys(str(record.get(package_field) or ""), str(record.get("attempt") or "")))
        record_keys.update(submission_lookup_keys("", str(record.get("attempt") or "")))
        if keys & record_keys:
            return record
        package_attempt = normalize_submission_attempt(package_name) if package_name else ""
        record_attempt = str(record.get("attempt") or "")
        if package_attempt and record_attempt and (package_attempt in record_attempt or record_attempt in package_attempt):
            return record
    return {}


def command_register_submission(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    package_name = Path(args.package).name
    if not package_name.lower().endswith(".zip"):
        raise SystemExit("submission package must be a .zip file")
    if len(package_name) > args.max_name_length:
        raise SystemExit(
            f"submission filename too long ({len(package_name)} > {args.max_name_length}): {package_name}; "
            "use a short name such as sub047.zip and keep metadata in submission-map.json"
        )
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    mapping_path = submission_map_path(root)
    mapping = load_submission_map(root)
    record = {
        "packageName": package_name,
        "packagePath": str(Path(args.package).resolve()) if args.package else "",
        "attempt": args.attempt,
        "basedOn": args.based_on,
        "family": args.family,
        "mechanism": args.mechanism,
        "shape": args.shape,
        "predictedDirection": args.predicted_direction,
        "sourcePackage": args.source_package,
        "note": args.note,
        "createdAt": now,
    }
    existing = [
        item
        for item in mapping.get("submissions", [])
        if isinstance(item, dict) and str(item.get("packageName")) == package_name
    ]
    if existing and not args.force:
        raise SystemExit(f"submission-map already contains {package_name}; use --force to append/update")
    if args.force and existing:
        mapping["submissions"] = [
            item
            for item in mapping.get("submissions", [])
            if not (isinstance(item, dict) and str(item.get("packageName")) == package_name)
        ]
    mapping.setdefault("submissions", []).append(record)
    mapping["updatedAt"] = now
    if args.write:
        atomic_write_json(mapping_path, mapping)
    write_json({"submissionMap": str(mapping_path), "write": args.write, "record": record})
    return 0


def infer_shape_from_text(text: str) -> str:
    lowered = text.lower().replace("_", "-")
    job = re.search(r"\bjob[- ]?(\d+)\b", lowered)
    phase = re.search(r"\bphase[- ]?(\d+)\b", lowered)
    if job and phase:
        return f"job{job.group(1)}_phase{phase.group(1)}"
    return classify(text.lower(), SHAPE_KEYWORDS, "")


def parse_online_feedback_text(text: str, ledger: dict[str, Any], root: Path, *, neutral_delta: float = 0.0) -> dict[str, Any]:
    package_match = re.search(r"([^\s\"']+\.zip)\b", text)
    package_name = package_match.group(1) if package_match else ""
    attempt = normalize_submission_attempt(package_name) if package_name else ""
    submitted_at_match = re.search(r"\b(20\d\d-\d\d-\d\d[ T]\d\d:\d\d:\d\d)\b", text)
    submitted_at = submitted_at_match.group(1).replace("T", " ") if submitted_at_match else ""
    status_match = re.search(r"\b(success|accepted|ok|failed|failure|error|compile\s*error|runtime\s*error)\b", text, re.IGNORECASE)
    status = status_match.group(1).lower().replace(" ", "-") if status_match else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    numeric_lines = [line for line in lines if re.fullmatch(r"\d+(?:\.\d+)?", line)]
    score_text = numeric_lines[-1] if numeric_lines else ""
    if not score_text:
        candidates = re.findall(r"\b\d{6,12}(?:\.\d+)?\b", text)
        if candidates:
            score_text = candidates[-1]
    online_score = as_float(score_text)
    if not attempt:
        baseline_match = re.search(r"\b(baseline-\d+[A-Za-z0-9_-]*)\b", text)
        attempt = baseline_match.group(1) if baseline_match else ""
    if not attempt:
        raise SystemExit("could not parse attempt/package from online feedback")
    if online_score is None:
        raise SystemExit("could not parse numeric online score from online feedback")
    label_text = " ".join([package_name, attempt]).replace("_", " ").lower()
    mapping = lookup_submission_mapping(root, package_name, attempt)
    family = classify(label_text, FAMILY_KEYWORDS, "unknown")
    mechanism = classify(label_text, MECHANISM_KEYWORDS, "unknown")
    shape = infer_shape_from_text(label_text)
    if mapping:
        attempt = str(mapping.get("attempt") or attempt)
        family = str(mapping.get("family") or family)
        mechanism = str(mapping.get("mechanism") or mechanism)
        shape = str(mapping.get("shape") or shape)
    best_id, best_score = best_online_baseline(ledger)
    delta = online_score - best_score if best_score is not None else None
    accept_best = bool(delta is not None and delta > neutral_delta and status not in ("failed", "failure", "error", "compile-error", "runtime-error"))
    return {
        "attempt": attempt,
        "submittedPackage": package_name,
        "submittedAt": submitted_at,
        "status": status,
        "onlineScore": online_score,
        "family": family,
        "mechanism": mechanism,
        "shape": shape,
        "basedOn": mapping.get("basedOn") if mapping else None,
        "predictedDirection": mapping.get("predictedDirection") if mapping else None,
        "submissionMapping": mapping,
        "bestKnownOnlineBaseline": best_id,
        "bestKnownOnlineScore": best_score,
        "deltaVsBest": delta,
        "autoAcceptBestEligible": accept_best,
    }


def command_online_feedback(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    if args.text:
        feedback_text = args.text
    elif args.file:
        feedback_text = Path(args.file).read_text(encoding="utf-8-sig")
    else:
        feedback_text = sys.stdin.read()
    parsed = parse_online_feedback_text(feedback_text, ledger, root, neutral_delta=args.neutral_delta)
    update_args = argparse.Namespace(
        project=args.project,
        attempt=args.attempt or parsed["attempt"],
        online_score=str(args.online_score if args.online_score is not None else parsed["onlineScore"]),
        family=args.family or parsed["family"],
        mechanism=args.mechanism or parsed["mechanism"],
        shape=args.shape if args.shape is not None and args.shape != "" else parsed["shape"],
        predicted_direction=args.predicted_direction if args.predicted_direction != "auto" else str(parsed.get("predictedDirection") or "up"),
        based_on=args.based_on or parsed.get("basedOn"),
        local_quick_delta=args.local_quick_delta,
        local_full_delta=args.local_full_delta,
        hidden_hypothesis=args.hidden_hypothesis or str((parsed.get("submissionMapping") or {}).get("note") or ""),
        reason=args.reason or f"parsed raw online feedback; status={parsed['status'] or 'unknown'}",
        submitted_package=args.submitted_package or parsed["submittedPackage"],
        submitted_at=args.submitted_at or parsed["submittedAt"],
        neutral_delta=args.neutral_delta,
        confirm_step=args.confirm_step,
        contradict_step=args.contradict_step,
        neutral_step=args.neutral_step,
        write=args.write,
        write_ledger=args.write_ledger,
        accept_best_update=args.accept_best_update or (args.auto_accept_best and parsed["autoAcceptBestEligible"]),
        force_ledger=args.force_ledger,
        parsed_online_feedback=parsed,
    )
    return command_online_update(update_args)


def command_online_update(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    weights = load_or_default_weights(root)
    families = weights.setdefault("families", {})
    history = weights.setdefault("history", [])
    baseline = ledger.get("currentBaseline", {})
    best = as_float(baseline.get("scores", {}).get("bestKnownOnlineScore"))
    online_score = as_float(args.online_score)
    if online_score is None:
        raise SystemExit("online score must be numeric")
    online_delta = online_score - best if best is not None else None
    predicted = args.predicted_direction or "unknown"
    if online_delta is None or abs(online_delta) <= args.neutral_delta:
        actual = "neutral"
    elif online_delta > 0:
        actual = "up"
    else:
        actual = "down"
    confirmed = predicted not in ("unknown", "neutral") and predicted == actual
    contradicted = predicted not in ("unknown", "neutral") and actual != "neutral" and predicted != actual
    family = families.setdefault(
        args.family,
        {
            "current_weight": 0.5,
            "evidence_count": 0,
            "online_confirmed": 0,
            "online_contradicted": 0,
            "last_update": None,
            "reason": "",
        },
    )
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    reason = args.reason or f"{args.attempt}: predicted {predicted}, actual {actual}"
    if confirmed:
        calibration = "confirmed"
        next_action = "exploit" if actual == "up" else "freeze"
    elif contradicted:
        calibration = "contradicted"
        next_action = "restore-online-best" if actual == "down" else "diagnose"
    else:
        calibration = "inconclusive"
        next_action = "diagnose"
    family_update = update_weight_node(
        family,
        actual if (confirmed or contradicted) else "neutral",
        confirm_step=args.confirm_step,
        contradict_step=args.contradict_step,
        neutral_step=args.neutral_step,
        now=now,
        reason=reason,
    )
    mechanisms = family.setdefault("mechanisms", {})
    mechanism = mechanisms.setdefault(
        args.mechanism,
        {
            "current_weight": family_update["offline_weight_update"]["old"],
            "evidence_count": 0,
            "online_confirmed": 0,
            "online_contradicted": 0,
            "last_update": None,
            "reason": "",
            "shapes": {},
        },
    )
    mechanism_update = update_weight_node(
        mechanism,
        actual if (confirmed or contradicted) else "neutral",
        confirm_step=args.confirm_step * 0.9,
        contradict_step=args.contradict_step * 0.9,
        neutral_step=args.neutral_step,
        now=now,
        reason=reason,
    )
    shape_update: dict[str, Any] | None = None
    if args.shape:
        shapes = mechanism.setdefault("shapes", {})
        shape = shapes.setdefault(
            args.shape,
            {
                "current_weight": mechanism_update["offline_weight_update"]["old"],
                "evidence_count": 0,
                "online_confirmed": 0,
                "online_contradicted": 0,
                "last_update": None,
                "reason": "",
            },
        )
        shape_update = update_weight_node(
            shape,
            actual if (confirmed or contradicted) else "neutral",
            confirm_step=args.confirm_step * 0.8,
            contradict_step=args.contradict_step * 0.8,
            neutral_step=args.neutral_step,
            now=now,
            reason=reason,
        )
    weight_history_id = f"{args.attempt}@{now}"
    record = {
        "id": weight_history_id,
        "submitted_attempt": args.attempt,
        "based_on": args.based_on or baseline.get("id"),
        "online_score": online_score,
        "online_delta_vs_best": online_delta,
        "local_quick_delta": args.local_quick_delta,
        "local_full_delta": args.local_full_delta,
        "affected_family": args.family,
        "changed_mechanism": args.mechanism,
        "hidden_shape": args.shape,
        "predicted_direction": predicted,
        "actual_direction": actual,
        "calibration_result": calibration,
        "offline_weight_update": family_update["offline_weight_update"],
        "mechanism_weight_update": mechanism_update["offline_weight_update"],
        "shape_weight_update": shape_update["offline_weight_update"] if shape_update else None,
        "hidden_dataset_hypothesis": args.hidden_hypothesis,
        "next_action": next_action,
        "updated_at": now,
    }
    history.append(record)
    weights["updatedAt"] = now
    output_path = root / "docs" / "online-offline-weights.json"
    ledger_file = ledger_path(root)
    ledger_patch: dict[str, Any] | None = None
    if args.write_ledger:
        existing = [
            item
            for item in ledger.get("onlineEvaluations", [])
            if isinstance(item, dict) and str(item.get("baseline")) == args.attempt
        ]
        if existing and not args.force_ledger:
            raise SystemExit(f"online evaluation already exists for attempt {args.attempt}; use --force-ledger to append anyway")
        eval_record = ledger_online_eval_record(
            args,
            baseline,
            online_score,
            online_delta,
            actual,
            calibration,
            next_action,
            now,
            weight_history_id,
        )
        ledger.setdefault("onlineEvaluations", []).append(eval_record)
        ledger["updatedAt"] = now
        scores = baseline.setdefault("scores", {})
        if args.accept_best_update and actual == "up":
            scores["bestKnownOnlineScore"] = online_score
            scores["bestKnownOnlineBaseline"] = args.attempt
            scores["gapToFirstPlaceUsingBestKnownOnline"] = eval_record.get("gapToFirstPlace")
        ledger_patch = {
            "wouldWrite": str(ledger_file),
            "appendOnlineEvaluation": eval_record,
            "acceptBestUpdate": args.accept_best_update,
        }
    if args.write:
        if args.write_ledger:
            atomic_write_json(output_path, weights)
            atomic_write_json(ledger_file, ledger)
        else:
            atomic_write_json(output_path, weights)
    search_graph_online = attach_online_result_to_search_graph(root, record, write=args.write)
    write_json(
        {
            "wouldWrite": str(output_path),
            "write": args.write,
            "ledgerPatchPreview": ledger_patch,
            "writeLedger": args.write_ledger,
            "record": record,
            "family": family,
            "mechanism": mechanism,
            "shape": shape_update["node"] if shape_update else None,
            "parsedOnlineFeedback": getattr(args, "parsed_online_feedback", None),
            "searchGraphOnlineUpdate": search_graph_online,
        }
    )
    return 0


def command_dataset_status(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    dataset_ledger = load_or_default_dataset_ledger(root)
    candidates = [item for item in dataset_ledger.get("candidates", []) if isinstance(item, dict)]
    promoted = [item for item in dataset_ledger.get("promoted", []) if isinstance(item, dict)]
    frozen = [item for item in dataset_ledger.get("frozen", []) if isinstance(item, dict)]
    pending = [
        item
        for item in candidates
        if str(item.get("status", "candidate")) not in ("validated", "promoted", "frozen")
    ]
    validated_backlog = [
        item
        for item in candidates
        if str(item.get("status", "candidate")) == "validated"
    ]
    write_json(
        {
            "datasetEvolutionLedger": str(dataset_evolution_path(root)),
            "exists": dataset_evolution_path(root).exists(),
            "updatedAt": dataset_ledger.get("updatedAt"),
            "counts": {
                "candidates": len(candidates),
                "pending": len(pending),
                "validatedBacklog": len(validated_backlog),
                "promoted": len(promoted),
                "frozen": len(frozen),
                "history": len(dataset_ledger.get("history", [])),
            },
            "recentCandidates": candidates[-args.limit :],
            "validatedBacklog": validated_backlog[-args.limit :],
            "promoted": promoted[-args.limit :],
            "frozen": frozen[-args.limit :],
            "nextActions": [
                "Use dataset-suggest after online-feedback when a local proxy gain is online-neutral/down.",
                "Use dataset-validate before treating any generated proxy as a promotion gate.",
                "Do not let validated candidates accumulate: promote, freeze, reject, or merge them before opening another same-shape proxy lane.",
                "Use dataset-promote or dataset-promote --freeze to make the lesson durable.",
            ],
        }
    )
    return 0


def command_dataset_suggest(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    source_child = Path(args.source_child_result).resolve() if args.source_child_result else None
    child_candidate: dict[str, Any] = {}
    if source_child:
        child_result = load_json(source_child)
        child_candidate = dataset_candidate_from_child_result(child_result) or {}
        if not child_candidate:
            raise SystemExit("source child_result does not contain datasetCandidate")
    source_online_query = args.source_online_feedback or str(child_candidate.get("sourceOnlineFeedback") or "")
    source_online = (
        find_online_feedback_record(ledger, source_online_query)
        if source_online_query
        else latest_online_feedback_record(ledger)
    )
    source_online_label = source_online_query or (online_record_label(source_online) if source_online else "")
    family = args.family or str(child_candidate.get("family") or child_candidate.get("caseFamily") or "")
    mechanism = args.mechanism or str(child_candidate.get("mechanism") or child_candidate.get("changedMechanism") or "dataset_candidate")
    case_family = args.case_family or str(child_candidate.get("caseFamily") or family or "hidden_dataset_fit")
    case_shape = args.case_shape or args.shape or str(child_candidate.get("caseShape") or child_candidate.get("shape") or "")
    candidate_id = args.candidate_id or str(child_candidate.get("candidateId") or "")
    if not candidate_id:
        candidate_id = f"dataset-{time.strftime('%Y%m%d-%H%M%S')}-{candidate_id_slug(case_family, case_shape)}"
    candidate = {
        **child_candidate,
        "candidateId": candidate_id,
        "createdAt": child_candidate.get("createdAt") or now,
        "updatedAt": now,
        "status": args.status,
        "sourceOnlineFeedback": args.source_online_feedback
        or child_candidate.get("sourceOnlineFeedback")
        or source_online_label
        or "latest-online-feedback",
        "sourceOnlineRecord": source_online or child_candidate.get("sourceOnlineRecord") or {},
        "family": family or "hidden_dataset_fit",
        "mechanism": mechanism,
        "caseFamily": case_family,
        "caseShape": case_shape or "unspecified_hidden_shape",
        "hypothesis": args.hypothesis or str(child_candidate.get("hypothesis") or ""),
        "explainsPositive": normalize_string_list(args.explains_positive)
        or normalize_string_list(child_candidate.get("explainsPositive")),
        "rejectsNeutralOrNegative": normalize_string_list(args.rejects_neutral_negative)
        or normalize_string_list(child_candidate.get("rejectsNeutralOrNegative")),
        "artifactPaths": normalize_string_list(args.artifact_path)
        or normalize_string_list(child_candidate.get("artifactPaths")),
        "generatedCaseFacts": normalize_string_list(args.case_fact)
        or normalize_string_list(child_candidate.get("generatedCaseFacts") or child_candidate.get("caseFacts")),
        "promotionGateImpact": args.promotion_gate_impact or str(child_candidate.get("promotionGateImpact") or ""),
        "recommendedGate": args.recommended_gate or str(child_candidate.get("recommendedGate") or "candidate-only until dataset-validate passes"),
        "sourceChildResult": str(source_child) if source_child else str(child_candidate.get("sourceChildResult") or ""),
        "note": args.note or str(child_candidate.get("note") or ""),
    }
    validation = validate_dataset_candidate_against_online(
        candidate,
        ledger_online_evaluations(ledger),
        strict=False,
    )
    candidate["validation"] = validation
    dataset_file = dataset_evolution_path(root)
    if args.write:
        dataset_file.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(dataset_file):
            dataset_ledger = load_or_default_dataset_ledger(root)
            upsert_dataset_candidate(dataset_ledger, candidate, force=args.force)
            dataset_ledger["updatedAt"] = now
            dataset_ledger.setdefault("history", []).append(
                {"at": now, "action": "suggest", "candidateId": candidate_id, "source": "dataset-suggest"}
            )
            atomic_write_json(dataset_file, dataset_ledger)
    write_json(
        {
            "datasetEvolutionLedger": str(dataset_file),
            "write": args.write,
            "candidate": candidate,
            "validationPreview": validation,
        }
    )
    return 0


def command_dataset_validate(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    dataset_file = dataset_evolution_path(root)
    source_child = Path(args.child_result).resolve() if args.child_result else None
    dataset_ledger = load_or_default_dataset_ledger(root)
    if source_child:
        child_result = load_json(source_child)
        candidate = dataset_candidate_from_child_result(child_result)
        if not candidate:
            raise SystemExit("child_result does not contain datasetCandidate")
    else:
        candidate = find_dataset_candidate(dataset_ledger, args.candidate_id)
        if not candidate:
            raise SystemExit(f"dataset candidate not found: {args.candidate_id}")
    validation = validate_dataset_candidate_against_online(
        candidate,
        ledger_online_evaluations(ledger),
        strict=args.strict,
    )
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if args.write and not source_child:
        with file_lock(dataset_file):
            dataset_ledger = load_or_default_dataset_ledger(root)
            target = find_dataset_candidate(dataset_ledger, str(candidate.get("candidateId")))
            if not target:
                raise SystemExit(f"dataset candidate not found during write: {candidate.get('candidateId')}")
            target["validation"] = validation
            target["status"] = "validated" if validation["valid"] else "needs-work"
            target["updatedAt"] = now
            dataset_ledger["updatedAt"] = now
            dataset_ledger.setdefault("history", []).append(
                {
                    "at": now,
                    "action": "validate",
                    "candidateId": target.get("candidateId"),
                    "valid": validation["valid"],
                }
            )
            atomic_write_json(dataset_file, dataset_ledger)
    write_json(
        {
            "datasetEvolutionLedger": str(dataset_file),
            "write": args.write,
            "candidateId": candidate.get("candidateId"),
            "validation": validation,
        }
    )
    return 0 if validation["valid"] else 1


def command_dataset_promote(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    dataset_file = dataset_evolution_path(root)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    dataset_ledger = load_or_default_dataset_ledger(root)
    candidate = find_dataset_candidate(dataset_ledger, args.candidate_id)
    if not candidate:
        raise SystemExit(f"dataset candidate not found: {args.candidate_id}")
    validation = candidate.get("validation", {}) if isinstance(candidate.get("validation", {}), dict) else {}
    if not args.force and not args.freeze and validation.get("status") != "validated":
        raise SystemExit("dataset candidate must pass dataset-validate before promotion; use --force only for a documented manual override")
    updated = dict(candidate)
    updated["updatedAt"] = now
    updated["status"] = "frozen" if args.freeze else "promoted"
    updated["decisionReason"] = args.reason
    updated["targetSuite"] = args.target_suite
    updated["integrationStatus"] = (
        "frozen-pattern; do not use as positive promotion evidence"
        if args.freeze
        else "metadata-promoted; integrate into benchmark/proxy code only after coordinator review"
    )
    if args.write:
        with file_lock(dataset_file):
            dataset_ledger = load_or_default_dataset_ledger(root)
            dataset_ledger["candidates"] = [
                item
                for item in dataset_ledger.get("candidates", [])
                if not (isinstance(item, dict) and str(item.get("candidateId")) == args.candidate_id)
            ]
            bucket = "frozen" if args.freeze else "promoted"
            dataset_ledger[bucket] = [
                item
                for item in dataset_ledger.get(bucket, [])
                if not (isinstance(item, dict) and str(item.get("candidateId")) == args.candidate_id)
            ]
            dataset_ledger.setdefault(bucket, []).append(updated)
            dataset_ledger["updatedAt"] = now
            dataset_ledger.setdefault("history", []).append(
                {
                    "at": now,
                    "action": "freeze" if args.freeze else "promote",
                    "candidateId": args.candidate_id,
                    "targetSuite": args.target_suite,
                    "reason": args.reason,
                    "force": args.force,
                }
            )
            atomic_write_json(dataset_file, dataset_ledger)
    write_json(
        {
            "datasetEvolutionLedger": str(dataset_file),
            "write": args.write,
            "bucket": "frozen" if args.freeze else "promoted",
            "candidate": updated,
        }
    )
    return 0


def known_baseline_sources(root: Path) -> list[dict[str, Any]]:
    baselines_dir = root / "docs" / "baselines"
    rows: list[dict[str, Any]] = []
    if not baselines_dir.exists():
        return rows
    for source in sorted(baselines_dir.glob("*/Solution.cpp")):
        try:
            rows.append(
                {
                    "baseline": source.parent.name,
                    "path": str(source),
                    "sha256": sha256_file(source),
                    "bytes": source.stat().st_size,
                }
            )
        except OSError:
            continue
    return rows


def best_online_baseline(ledger: dict[str, Any]) -> tuple[str, float | None]:
    baseline = ledger.get("currentBaseline", {})
    scores = baseline.get("scores", {}) if isinstance(baseline, dict) else {}
    best_id = str(scores.get("bestKnownOnlineBaseline") or baseline.get("id") or "")
    best_score = as_float(scores.get("bestKnownOnlineScore"))
    return best_id, best_score


def baseline_record_for_id(root: Path, ledger: dict[str, Any], baseline_id: str) -> dict[str, Any]:
    current = ledger.get("currentBaseline", {})
    if isinstance(current, dict) and current.get("id") == baseline_id:
        return dict(current)
    for record in ledger.get("successfulExperiments", []):
        if not isinstance(record, dict):
            continue
        if record.get("promotedAs") == baseline_id or record.get("id") == baseline_id:
            snapshot = root / "docs" / "baselines" / baseline_id / "Solution.cpp"
            source_hash = sha256_file(snapshot).lower() if snapshot.exists() else record.get("sourceSha256", "")
            scores = record.get("scores", {}) if isinstance(record.get("scores", {}), dict) else {}
            current_scores = current.get("scores", {}) if isinstance(current, dict) else {}
            if current_scores:
                scores = {**scores, **{k: v for k, v in current_scores.items() if k.startswith("bestKnown") or k.startswith("gapToFirst") or k == "firstPlaceScoreSnapshot"}}
            return {
                "id": baseline_id,
                "createdAt": record.get("createdAt"),
                "description": record.get("summary") or record.get("hypothesis") or record.get("description", ""),
                "sourcePath": "src/Solution.cpp",
                "snapshotPath": str(Path("docs") / "baselines" / baseline_id / "Solution.cpp"),
                "sourceSha256": source_hash,
                "scores": scores,
            }
    snapshot = root / "docs" / "baselines" / baseline_id / "Solution.cpp"
    if snapshot.exists():
        current_scores = current.get("scores", {}) if isinstance(current, dict) else {}
        return {
            "id": baseline_id,
            "createdAt": None,
            "description": "Restored from baseline snapshot; ledger record was reconstructed by restore-online-best.",
            "sourcePath": "src/Solution.cpp",
            "snapshotPath": str(Path("docs") / "baselines" / baseline_id / "Solution.cpp"),
            "sourceSha256": sha256_file(snapshot).lower(),
            "scores": current_scores,
        }
    raise SystemExit(f"cannot find baseline record or snapshot for {baseline_id}")


def command_restore_online_best(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    source_rel = str(baseline.get("sourcePath", "src/Solution.cpp"))
    source_path = root / source_rel
    best_id, best_score = best_online_baseline(ledger)
    if args.baseline:
        best_id = args.baseline
    snapshot = root / "docs" / "baselines" / best_id / "Solution.cpp"
    if not snapshot.exists():
        raise SystemExit(f"missing baseline snapshot: {snapshot}")
    expected_snapshot_hash = sha256_file(snapshot).lower()
    current_hash = sha256_file(source_path).lower() if source_path.exists() else ""
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    backup_path = None
    if current_hash and current_hash != expected_snapshot_hash:
        backup_dir = root / "docs" / "drift-backups"
        backup_path = backup_dir / f"{now.replace(':', '').replace('+', '_')}-{current_hash[:12]}-Solution.cpp"
    output = {
        "project": str(root),
        "bestKnownOnlineBaseline": best_id,
        "bestKnownOnlineScore": best_score,
        "sourcePath": str(source_path),
        "currentSourceSha256": current_hash,
        "snapshotPath": str(snapshot),
        "snapshotSha256": expected_snapshot_hash,
        "alreadyRestored": current_hash == expected_snapshot_hash,
        "backupPath": str(backup_path) if backup_path else None,
        "updateLedger": args.update_ledger,
        "write": args.write,
    }
    restored_record = baseline_record_for_id(root, ledger, best_id)
    output["ledgerCurrentBaselinePreview"] = restored_record if args.update_ledger else None
    if args.write:
        if backup_path:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, backup_path)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot, source_path)
        if args.update_ledger:
            ledger["currentBaseline"] = restored_record
            ledger["updatedAt"] = now
            atomic_write_json(ledger_path(root), ledger)
        output["restoredSourceSha256"] = sha256_file(source_path).lower()
    write_json(output)
    return 0


def command_drift(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    source_path = root / str(baseline.get("sourcePath", "src/Solution.cpp"))
    expected_hash = str(baseline.get("sourceSha256", "")).lower()
    actual_hash = sha256_file(source_path).lower() if source_path.exists() else ""
    known = known_baseline_sources(root)
    actual_matches = [row for row in known if row["sha256"].lower() == actual_hash]
    expected_matches = [row for row in known if row["sha256"].lower() == expected_hash]
    if actual_hash == expected_hash and actual_hash:
        classification = "clean-active-baseline"
        risk = "none"
        next_action = "safe to prepare an epoch"
    elif actual_matches:
        classification = "matches-known-baseline-snapshot"
        risk = "medium"
        next_action = "update ledger only if this baseline is intentionally active; otherwise restore currentBaseline snapshot"
    else:
        classification = "unrecorded-source-drift"
        risk = "high"
        next_action = "backup or record this source as an attempt before any edit lane; do not stack new experiments"
    output = {
        "project": str(root),
        "currentBaseline": baseline.get("id"),
        "sourcePath": str(source_path),
        "expectedSourceSha256": expected_hash,
        "actualSourceSha256": actual_hash,
        "classification": classification,
        "risk": risk,
        "actualMatchesKnownBaseline": actual_matches,
        "expectedBaselineSnapshot": expected_matches,
        "restoreCandidate": expected_matches[0] if expected_matches else None,
        "nextAction": next_action,
    }
    write_json(output)
    return 0 if classification == "clean-active-baseline" else 1


def command_init_weights(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    online = ledger_online_evaluations(ledger)
    weights = {"version": 1, "updatedAt": None, "families": {}, "history": []}
    families = weights["families"]
    history = weights["history"]
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for record in online:
        status = str(record.get("status", ""))
        actual = online_actual_from_delta(record.get("delta"), status)
        family_name = str(record.get("affected_family") or family_from_online_record(record))
        mechanism = str(record.get("changed_mechanism") or mechanism_from_online_record(record))
        update = update_family_weight_from_online(
            families,
            family_name,
            actual,
            confirm_step=args.confirm_step,
            contradict_step=args.contradict_step,
        )
        item = {
            "submitted_attempt": record.get("baseline"),
            "based_on": record.get("baseline"),
            "online_score": record.get("score"),
            "online_delta_vs_best": record.get("delta"),
            "affected_family": family_name,
            "changed_mechanism": mechanism,
            "predicted_direction": "unknown",
            "actual_direction": actual,
            "calibration_result": update["calibration_result"],
            "offline_weight_update": update["offline_weight_update"],
            "hidden_dataset_hypothesis": record.get("note", ""),
            "next_action": "exploit" if actual == "up" else ("freeze" if actual == "down" else "diagnose"),
            "updated_at": record.get("reportedAt") or record.get("submittedAt") or now,
        }
        history.append(item)
        families[family_name]["last_update"] = item["updated_at"]
        families[family_name]["reason"] = f"initialized from ledger onlineEvaluations; latest={item['submitted_attempt']}"
    weights["updatedAt"] = now
    output_path = root / "docs" / "online-offline-weights.json"
    if args.write:
        atomic_write_json(output_path, weights)
    write_json(
        {
            "sourceOnlineEvaluations": len(online),
            "wouldWrite": str(output_path),
            "write": args.write,
            "families": families,
            "historyCount": len(history),
        }
    )
    return 0


def command_run_epoch(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    ledger = load_json(ledger_path(root))
    baseline = ledger.get("currentBaseline", {})
    online_state = online_best_state(baseline)
    if (
        online_state["severity"] in ("yellow", "red")
        and not args.allow_online_unconfirmed
        and not args.from_online_best
    ):
        queue = {
            "project": str(root),
            "mode": "diagnostic-only",
            "reason": f"online-best yellow/red gate: {online_state['state']}",
            "onlineBestState": online_state,
            "recommendedCommands": [
                f"python {Path(__file__).resolve()} status --project \"{root}\"",
                f"python {Path(__file__).resolve()} restore-online-best --project \"{root}\"",
                f"python {Path(__file__).resolve()} restore-online-best --project \"{root}\" --write --update-ledger",
                f"python {Path(__file__).resolve()} run-epoch --project \"{root}\"",
                f"python {Path(__file__).resolve()} run-epoch --project \"{root}\" --allow-online-unconfirmed --max-lanes 2",
            ],
        }
        write_json(queue)
        return 1
    doctor_args = argparse.Namespace(
        project=str(root),
        mutation_space=args.mutation_space,
        min_score=args.min_doctor_score,
        max_duplicate_keys=args.max_duplicate_keys,
        allow_online_unconfirmed=args.allow_online_unconfirmed,
    )
    doctor_code = command_doctor(doctor_args)
    hard_doctor_failure = False
    if doctor_code != 0:
        try:
            doctor_capture = capture_json_output(command_doctor, doctor_args)
            failed_names = [
                str(item.get("name") or "")
                for item in doctor_capture.get("checks", [])
                if isinstance(item, dict) and not bool(item.get("passed"))
            ]
            hard_doctor_failure = any(
                name
                in {
                    "ledger-readable",
                    "source-hash-matches-currentBaseline",
                    "baseline-snapshot-present",
                }
                for name in failed_names
            )
        except Exception:  # noqa: BLE001
            hard_doctor_failure = True
    if doctor_code != 0 and hard_doctor_failure and not args.allow_dirty:
        queue = {
            "project": str(root),
            "mode": "diagnostic-only",
            "reason": "hard doctor gate failed; rerun with --allow-dirty only after classifying drift/source integrity",
            "recommendedCommands": [
                f"python {Path(__file__).resolve()} drift --project \"{root}\"",
                f"python {Path(__file__).resolve()} init-weights --project \"{root}\" --write",
                f"python {Path(__file__).resolve()} doctor --project \"{root}\"",
            ],
        }
        write_json(queue)
        return 1
    idea_board_path = args.idea_board
    if not idea_board_path and not getattr(args, "mutation_space_only", False):
        idea_id = f"{args.run_id or time.strftime('epoch-%Y%m%d-%H%M%S')}-board"
        idea_args = argparse.Namespace(
            project=str(root),
            mutation_space=args.mutation_space,
            max_ideas=18,
            select_lanes=args.max_lanes,
            online_limit=8,
            experience_limit=12,
            stagnation_threshold=2,
            force_stagnation=False,
            prefer_044_mode=False,
            force_044_mode=False,
            template_only=False,
            run_id=idea_id,
            write=True,
        )
        idea_output = capture_json_output(command_idea_board, idea_args)
        idea_board_path = str(idea_output.get("written") or "")
        if not idea_board_path:
            raise SystemExit("run-epoch failed to create an idea-board; rerun idea-board --write manually")

    prep_args = argparse.Namespace(
        project=str(root),
        mutation_space=args.mutation_space,
        idea_board=idea_board_path,
        run_id=args.run_id,
        output=args.output,
        max_lanes=args.max_lanes,
        max_prior_failures=args.max_prior_failures,
        include_frozen=args.include_frozen,
        allow_drift=args.allow_dirty,
        drift_classification=args.drift_classification,
        drift_note=args.drift_note,
        force=args.force,
        no_copy=args.no_copy,
    )
    return command_prepare_epoch(prep_args)


def add_doctor_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    weight: float,
    detail: str,
    fix: str = "",
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "weight": weight,
            "detail": detail,
            "fix": fix,
        }
    )


def command_doctor(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    checks: list[dict[str, Any]] = []
    ledger_file = ledger_path(root)
    mutation_file = mutation_space_path(args.mutation_space)
    source_hash_matches = False
    ledger: dict[str, Any] = {}
    mutation_space: dict[str, Any] = {}

    try:
        ledger = load_json(ledger_file)
        add_doctor_check(checks, "ledger-readable", True, 1.0, str(ledger_file))
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports all failures.
        add_doctor_check(checks, "ledger-readable", False, 1.0, str(exc), "Repair docs/optimization-ledger.json.")

    baseline = ledger.get("currentBaseline", {}) if isinstance(ledger, dict) else {}
    source_path = root / str(baseline.get("sourcePath", "src/Solution.cpp"))
    expected_hash = str(baseline.get("sourceSha256", "")).lower()
    actual_hash = sha256_file(source_path).lower() if source_path.exists() else ""
    source_hash_matches = bool(expected_hash and actual_hash == expected_hash)
    add_doctor_check(
        checks,
        "active-baseline-locked",
        source_hash_matches,
        1.4,
        f"expected={expected_hash or 'missing'} actual={actual_hash or 'missing'}",
        "Classify source drift before editing or restore the active baseline.",
    )

    scores = baseline.get("scores", {}) if isinstance(baseline, dict) else {}
    online_best = scores.get("bestKnownOnlineBaseline")
    add_doctor_check(
        checks,
        "online-best-known",
        bool(scores.get("bestKnownOnlineScore") is not None and online_best),
        0.8,
        f"bestKnownOnlineBaseline={online_best}, bestKnownOnlineScore={scores.get('bestKnownOnlineScore')}",
        "Record best-known online score/baseline in the ledger.",
    )
    online_state = online_best_state(baseline)
    add_doctor_check(
        checks,
        "online-best-active-or-acknowledged",
        online_state["severity"] == "green" or args.allow_online_unconfirmed,
        0.9,
        f"state={online_state['state']}, current={online_state['currentBaseline']}, best={online_state['bestKnownOnlineBaseline']}",
        "Restore online-best before exploit lanes, or rerun doctor/run-epoch with --allow-online-unconfirmed for diagnosis only.",
    )

    try:
        mutation_space = load_json(mutation_file)
        families = mutation_space.get("families", [])
        add_doctor_check(
            checks,
            "mutation-space-readable",
            bool(families),
            0.9,
            f"{len(families)} families in {mutation_file}",
            "Populate references/mutation_space.json with bounded families and knobs.",
        )
    except Exception as exc:  # noqa: BLE001
        add_doctor_check(checks, "mutation-space-readable", False, 0.9, str(exc), "Repair mutation_space.json.")
        families = []

    frozen_patterns = mutation_space.get("frozenPatterns", []) if isinstance(mutation_space, dict) else []
    add_doctor_check(
        checks,
        "frozen-patterns-present",
        len(frozen_patterns) >= 5,
        0.6,
        f"{len(frozen_patterns)} frozen patterns",
        "Add repeated online-regressive or proxy-only patterns to frozenPatterns.",
    )

    records = ledger_records(ledger) if isinstance(ledger, dict) else []
    failed_with_lessons = [
        rec for rec in records if rec.get("_bucket") == "failedExperiments" and rec.get("avoidNextTime")
    ]
    failed_total = len([rec for rec in records if rec.get("_bucket") == "failedExperiments"])
    lesson_ratio = (len(failed_with_lessons) / failed_total) if failed_total else 1.0
    add_doctor_check(
        checks,
        "failed-attempt-lessons",
        lesson_ratio >= 0.8,
        0.8,
        f"{len(failed_with_lessons)}/{failed_total} failed attempts include avoidNextTime",
        "Backfill concrete avoidNextTime lessons for failed attempts.",
    )

    weights_path = root / "docs" / "online-offline-weights.json"
    weights = load_or_default_weights(root)
    weight_history = weights.get("history", []) if isinstance(weights, dict) else []
    online_evaluations = ledger_online_evaluations(ledger) if isinstance(ledger, dict) else []
    add_doctor_check(
        checks,
        "online-offline-calibration",
        weights_path.exists() or bool(weight_history) or bool(online_evaluations),
        1.0,
        f"weights_path_exists={weights_path.exists()}, weight_history={len(weight_history)}, ledger_online_evaluations={len(online_evaluations)}",
        "After the next real online score, run online-update --write to maintain explicit family weights.",
    )
    dataset_path = dataset_evolution_path(root)
    dataset_ledger = load_or_default_dataset_ledger(root)
    dataset_candidates = dataset_ledger.get("candidates", []) if isinstance(dataset_ledger, dict) else []
    dataset_promoted = dataset_ledger.get("promoted", []) if isinstance(dataset_ledger, dict) else []
    dataset_frozen = dataset_ledger.get("frozen", []) if isinstance(dataset_ledger, dict) else []
    dataset_backlog = dataset_decision_backlog(root)
    add_doctor_check(
        checks,
        "dataset-evolution-ledger-ready",
        dataset_path.exists(),
        0.5,
        (
            f"path={dataset_path}; exists={dataset_path.exists()}; candidates={len(dataset_candidates)}, "
            f"validatedBacklog={dataset_backlog['validatedBacklogCount']}, promoted={len(dataset_promoted)}, frozen={len(dataset_frozen)}"
        ),
        "Initialize docs/dataset-evolution-ledger.json with dataset-suggest --write after online feedback.",
    )
    add_doctor_check(
        checks,
        "dataset-candidate-decisions-controlled",
        int(dataset_backlog["validatedBacklogCount"]) <= 8 or bool(dataset_promoted or dataset_frozen),
        0.6,
        (
            f"validatedBacklog={dataset_backlog['validatedBacklogCount']}, pending={dataset_backlog['pendingCount']}, "
            f"promoted={len(dataset_promoted)}, frozen={len(dataset_frozen)}"
        ),
        "Before more proxy-only epochs, promote/freeze/reject/merge validated dataset candidates so they change future gates.",
    )
    families_with_mechanisms = [
        name
        for name, item in weights.get("families", {}).items()
        if isinstance(item, dict) and isinstance(item.get("mechanisms"), dict) and item.get("mechanisms")
    ] if isinstance(weights, dict) else []
    add_doctor_check(
        checks,
        "mechanism-calibration-ready",
        bool(families_with_mechanisms) or bool(weight_history),
        0.5,
        f"families_with_mechanism_weights={families_with_mechanisms}",
        "Use online-update --mechanism and --shape after online feedback to build fine-grained weights.",
    )
    exploration_index = root / "docs" / "exploration-index.json"
    add_doctor_check(
        checks,
        "child-learning-index-ready",
        exploration_index.exists(),
        0.4,
        f"index_path={exploration_index}; exists={exploration_index.exists()}; created by learn-from-children --write-index",
        "Run learn-from-children after epochs to persist child_result lessons.",
    )
    search_graph_file = search_graph_path(root)
    cards_dir = attempt_cards_dir(root)
    search_context = search_system_context(root)
    add_doctor_check(
        checks,
        "search-graph-infrastructure-ready",
        search_graph_file.exists() or bool(search_context.get("nodeCount")) or exploration_index.exists(),
        0.5,
        (
            f"graph_path={search_graph_file}; exists={search_graph_file.exists()}; "
            f"nodes={search_context.get('nodeCount')}; cards_dir_exists={cards_dir.exists()}; "
            f"bootstrap_from_exploration_index={exploration_index.exists()}"
        ),
        "Run learn-from-children --write-search-graph or archive-attempt --write-search-graph after the next epoch.",
    )

    duplicate_summary = duplicate_risk_summary(ledger) if isinstance(ledger, dict) else {"risky": {}, "historical": {}}
    risky_duplicates = duplicate_summary["risky"]
    duplicate_controlled = bool(frozen_patterns) and lesson_ratio >= 0.8
    add_doctor_check(
        checks,
        "duplicate-index-controlled",
        len(risky_duplicates) <= args.max_duplicate_keys or duplicate_controlled,
        0.7,
        (
            f"{len(risky_duplicates)} current-risk duplicate fingerprints, {len(duplicate_summary['historical'])} historical duplicates; "
            f"controlled_by_lessons_and_frozen_patterns={duplicate_controlled}"
        ),
        "Use check before new lanes; freeze or rename repeated current-baseline causal mechanisms.",
    )

    required_commands = {
        "status",
        "index",
        "check",
        "suggest-lanes",
        "idea-board",
        "epoch-board",
        "prepare-epoch",
        "rank-children",
        "gate-decision",
        "close-epoch",
        "register-submission",
        "online-feedback",
        "online-update",
        "dataset-status",
        "dataset-suggest",
        "dataset-validate",
        "dataset-promote",
        "search-graph",
        "failed-diffs",
        "attempt-card",
        "drift",
        "init-weights",
        "run-epoch",
        "dispatch-epoch",
        "collect-epoch",
        "pool-update",
        "phase-transition",
        "pool-retire",
        "learn-from-children",
        "archive-attempt",
        "restore-online-best",
        "validate-child",
        "audit-skill",
        "reweight-mutations",
        "doctor",
    }
    script_commands = parser_command_names()
    missing_commands = sorted(required_commands - script_commands)
    add_doctor_check(
        checks,
        "router-command-coverage",
        not missing_commands,
        0.8,
        f"missing={missing_commands}",
        "Add missing subcommands to score_loop_tools.py and SKILL.md router.",
    )

    total_weight = sum(float(item["weight"]) for item in checks)
    earned = sum(float(item["weight"]) for item in checks if item["passed"])
    score_10 = round((earned / total_weight) * 10.0, 2) if total_weight else 0.0
    output = {
        "project": str(root),
        "score10": score_10,
        "grade": "9.5-ready" if score_10 >= 9.5 else "needs-hardening",
        "activeBaseline": baseline.get("id"),
        "sourceHashMatches": source_hash_matches,
        "duplicateRisk": duplicate_summary,
        "checks": checks,
        "nextFixes": [item for item in checks if not item["passed"]],
    }
    write_json(output)
    return 0 if score_10 >= args.min_score else 1


def ledger_online_evaluations(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    values = ledger.get("onlineEvaluations", [])
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def command_index_preview(ledger: dict[str, Any]) -> dict[str, list[str]]:
    current_id = str(ledger.get("currentBaseline", {}).get("id", ""))
    seen: dict[str, list[str]] = {}
    for record in ledger_records(ledger):
        fp = fingerprint(record, default_based_on=current_id)
        key = fingerprint_key(fp)
        if "unknown" in key:
            continue
        seen.setdefault(key, []).append(str(record.get("id") or record.get("baseline") or "unknown"))
    return {key: ids for key, ids in seen.items() if len(ids) > 1}


def duplicate_risk_summary(ledger: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    current_id = str(ledger.get("currentBaseline", {}).get("id", ""))
    all_duplicates = command_index_preview(ledger)
    risky: dict[str, list[str]] = {}
    historical: dict[str, list[str]] = {}
    for key, ids in all_duplicates.items():
        if key.startswith(f"{current_id}|"):
            risky[key] = ids
        else:
            historical[key] = ids
    return {"risky": risky, "historical": historical}


def parser_command_names() -> set[str]:
    return set(build_parser()._subparsers._group_actions[0].choices.keys())  # type: ignore[attr-defined]


def skill_router_mentions() -> set[str]:
    parts = []
    for path in (SKILL_MD, PROFILE_MD):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8-sig"))
    text = "\n".join(parts).lower()
    return {name for name in parser_command_names() if name in text}


def command_audit_skill(args: argparse.Namespace) -> int:
    parser_commands = parser_command_names()
    router_mentions = skill_router_mentions()
    missing_in_skill = sorted(parser_commands - router_mentions)
    required_files = [
        SKILL_ROOT / "SKILL.md",
        PROFILE_MD,
        SKILL_ROOT / "agents" / "openai.yaml",
        SKILL_ROOT / "scripts" / "score_loop_tools.py",
        DEFAULT_MUTATION_SPACE,
    ]
    missing_files = [str(path) for path in required_files if not path.exists()]
    output = {
        "skillRoot": str(SKILL_ROOT),
        "valid": not missing_in_skill and not missing_files,
        "parserCommands": sorted(parser_commands),
        "commandsMentionedInSkill": sorted(router_mentions),
        "missingInSkillText": missing_in_skill,
        "missingFiles": missing_files,
    }
    write_json(output)
    return 0 if output["valid"] else 1


def command_reweight_mutations(args: argparse.Namespace) -> int:
    root = project_root(args.project)
    weights = load_or_default_weights(root)
    space_path = mutation_space_path(args.mutation_space)
    space = load_json(space_path)
    families = weights.get("families", {}) if isinstance(weights, dict) else {}
    adjusted = dict(space)
    adjusted_families: list[dict[str, Any]] = []
    for family in space.get("families", []):
        item = dict(family)
        name = str(item.get("family", "unknown"))
        weight = family_weight(weights, name)
        original_state = str(item.get("defaultState", "explore"))
        confidence = str(item.get("onlineConfidence", "")).lower()
        if "support" in confidence:
            state = original_state
        elif weight >= args.exploit_threshold:
            state = "exploit"
        elif weight <= args.freeze_threshold:
            state = "freeze"
        else:
            state = original_state
        item["defaultState"] = state
        item["onlineWeight"] = round(weight, 4)
        item["reweightReason"] = f"from docs/online-offline-weights.json family weight; originalState={original_state}"
        mechanisms = families.get(name, {}).get("mechanisms", {}) if isinstance(families.get(name, {}), dict) else {}
        adjusted_knobs: list[dict[str, Any]] = []
        for knob in item.get("mutationKnobs", []):
            knob_item = dict(knob)
            mechanism_name = str(knob_item.get("type") or "unknown")
            mech_weight = mechanism_weight(weights, name, mechanism_name)
            knob_item["onlineMechanismWeight"] = round(mech_weight, 4)
            if mechanism_name in mechanisms and mech_weight <= args.freeze_threshold:
                reject_if = list(knob_item.get("rejectIf", []))
                guard = f"mechanism weight {mechanism_name}={mech_weight:.2f} is below freeze threshold"
                if guard not in reject_if:
                    reject_if.append(guard)
                knob_item["rejectIf"] = reject_if
                knob_item["reweightState"] = "mechanism-freeze"
            elif mechanism_name in mechanisms and mech_weight >= args.exploit_threshold:
                knob_item["reweightState"] = "mechanism-exploit"
            else:
                knob_item["reweightState"] = "family-default"
            adjusted_knobs.append(knob_item)
        item["mutationKnobs"] = adjusted_knobs
        adjusted_families.append(item)
    adjusted["families"] = adjusted_families
    output_path = Path(args.output).resolve() if args.output else space_path
    if args.write:
        atomic_write_json(output_path, adjusted)
    write_json(
        {
            "source": str(space_path),
            "wouldWrite": str(output_path),
            "write": args.write,
            "families": [
                {
                    "family": item.get("family"),
                    "defaultState": item.get("defaultState"),
                    "onlineWeight": item.get("onlineWeight"),
                    "reweightReason": item.get("reweightReason"),
                }
                for item in adjusted_families
            ],
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Validate active baseline and online score state.")
    status.add_argument("--project", help="Project root. Defaults to current directory.")
    status.set_defaults(func=command_status)

    index = sub.add_parser("index", help="Build an exploration fingerprint index from the ledger.")
    index.add_argument("--project", help="Project root. Defaults to current directory.")
    index.add_argument("--verbose", action="store_true", help="Print all entries instead of the latest 20.")
    index.set_defaults(func=command_index)

    check = sub.add_parser("check", help="Check whether a candidate idea duplicates prior attempts.")
    check.add_argument("--project", help="Project root. Defaults to current directory.")
    check.add_argument("--hypothesis", required=True)
    check.add_argument("--based-on")
    check.add_argument("--family")
    check.add_argument("--mechanism")
    check.add_argument("--direction")
    check.set_defaults(func=command_check)

    rank = sub.add_parser("rank-children", help="Rank child_result.json files from a parallel run.")
    rank.add_argument("--run-dir", required=True)
    rank.add_argument("--project", help="Project root for online/offline weights.")
    rank.set_defaults(func=command_rank_children)

    validate_child = sub.add_parser("validate-child", help="Validate one child_result.json against the required schema.")
    validate_child.add_argument("--child-result", required=True)
    validate_child.add_argument("--run-dir", help="Optional epoch directory for manifest-aware validation.")
    validate_child.add_argument("--project", help="Accepted for command-shape compatibility; validate-child does not mutate project state.")
    validate_child.add_argument("--strict", action="store_true", help="Treat missing lane-required checks as errors.")
    validate_child.set_defaults(func=command_validate_child)

    dataset_status = sub.add_parser("dataset-status", help="Show offline dataset-evolution candidates and decisions.")
    dataset_status.add_argument("--project", help="Project root. Defaults to current directory.")
    dataset_status.add_argument("--limit", type=int, default=8)
    dataset_status.set_defaults(func=command_dataset_status)

    dataset_suggest = sub.add_parser("dataset-suggest", help="Create a dataset-evolution candidate from online feedback or a child result.")
    dataset_suggest.add_argument("--project", help="Project root. Defaults to current directory.")
    dataset_suggest.add_argument("--candidate-id", default="")
    dataset_suggest.add_argument("--source-online-feedback", default="", help="Attempt/baseline/id of the online feedback this candidate explains. Defaults to latest.")
    dataset_suggest.add_argument("--source-child-result", default="", help="child_result.json containing datasetCandidate.")
    dataset_suggest.add_argument("--family", default="")
    dataset_suggest.add_argument("--mechanism", default="dataset_candidate")
    dataset_suggest.add_argument("--shape", default="")
    dataset_suggest.add_argument("--case-family", default="")
    dataset_suggest.add_argument("--case-shape", default="")
    dataset_suggest.add_argument("--hypothesis", default="")
    dataset_suggest.add_argument("--explains-positive", action="append", default=[])
    dataset_suggest.add_argument("--rejects-neutral-negative", action="append", default=[])
    dataset_suggest.add_argument("--artifact-path", action="append", default=[])
    dataset_suggest.add_argument("--case-fact", action="append", default=[])
    dataset_suggest.add_argument("--promotion-gate-impact", default="")
    dataset_suggest.add_argument("--recommended-gate", default="")
    dataset_suggest.add_argument("--status", default="candidate")
    dataset_suggest.add_argument("--note", default="")
    dataset_suggest.add_argument("--force", action="store_true")
    dataset_suggest.add_argument("--write", action="store_true")
    dataset_suggest.set_defaults(func=command_dataset_suggest)

    dataset_validate = sub.add_parser("dataset-validate", help="Validate a dataset candidate against historical online feedback.")
    dataset_validate.add_argument("--project", help="Project root. Defaults to current directory.")
    dataset_validate.add_argument("--candidate-id", default="")
    dataset_validate.add_argument("--child-result", default="")
    dataset_validate.add_argument("--strict", action="store_true")
    dataset_validate.add_argument("--write", action="store_true")
    dataset_validate.set_defaults(func=command_dataset_validate)

    dataset_promote = sub.add_parser("dataset-promote", help="Promote or freeze a validated dataset candidate.")
    dataset_promote.add_argument("--project", help="Project root. Defaults to current directory.")
    dataset_promote.add_argument("--candidate-id", required=True)
    dataset_promote.add_argument("--target-suite", default="")
    dataset_promote.add_argument("--reason", required=True)
    dataset_promote.add_argument("--freeze", action="store_true", help="Freeze the candidate as a negative/proxy trap instead of promoting.")
    dataset_promote.add_argument("--force", action="store_true")
    dataset_promote.add_argument("--write", action="store_true")
    dataset_promote.set_defaults(func=command_dataset_promote)

    suggest = sub.add_parser("suggest-lanes", help="Suggest a small non-duplicate lane board.")
    suggest.add_argument("--project", help="Project root. Defaults to current directory.")
    suggest.add_argument(
        "--max-prior-failures",
        type=int,
        default=4,
        help="Freeze family/mechanism pairs with at least this many prior failed attempts.",
    )
    suggest.set_defaults(func=command_suggest_lanes)

    idea = sub.add_parser("idea-board", help="Generate a mutation-matrix divergent idea board before opening worker lanes.")
    idea.add_argument("--project", help="Project root. Defaults to current directory.")
    idea.add_argument("--mutation-space", help="Path to mutation_space.json.")
    idea.add_argument("--max-ideas", type=int, default=18)
    idea.add_argument("--select-lanes", type=int, default=DEFAULT_EPOCH_LANE_LIMIT)
    idea.add_argument("--online-limit", type=int, default=8)
    idea.add_argument("--experience-limit", type=int, default=12)
    idea.add_argument("--stagnation-threshold", type=int, default=2, help="Recent closed epochs without parent-gate/promotion before stagnation mode activates.")
    idea.add_argument("--force-stagnation", action="store_true", help="Force stagnation-mode idea selection for validation or manual escape from a local optimum.")
    idea.add_argument("--prefer-044-mode", action="store_true", help="Prefer baseline-044 style online-confirmed exploit selection: exact neighbor, forensic before patch.")
    idea.add_argument("--template-only", action="store_true", help="Disable freeform divergence and use only legacy mutation templates.")
    idea.add_argument("--force-044-mode", action="store_true", help=argparse.SUPPRESS)
    idea.add_argument("--run-id", default="", help="Optional output id under docs/idea-boards when --write is used.")
    idea.add_argument("--write", action="store_true", help="Write the idea board to docs/idea-boards/<id>.json.")
    idea.set_defaults(func=command_idea_board)

    epoch = sub.add_parser("epoch-board", help="Generate an epoch board from the mutation search space.")
    epoch.add_argument("--project", help="Project root. Defaults to current directory.")
    epoch.add_argument("--mutation-space", help="Path to mutation_space.json.")
    epoch.add_argument("--max-lanes", type=int, default=5)
    epoch.add_argument("--max-prior-failures", type=int, default=4)
    epoch.add_argument("--include-frozen", action="store_true")
    epoch.set_defaults(func=command_epoch_board)

    prep = sub.add_parser("prepare-epoch", help="Prepare isolated workspaces and prompts from an idea board or the mutation search space.")
    prep.add_argument("--project", help="Project root. Defaults to current directory.")
    prep.add_argument("--mutation-space", help="Path to mutation_space.json.")
    prep.add_argument("--idea-board", default="", help="Path to docs/idea-boards/*.json; selectedLanes become canonical epoch lanes.")
    prep.add_argument("--run-id", default="")
    prep.add_argument("--output", default="", help="Run directory. Defaults to project tmp/score-loop-epochs/<run-id>.")
    prep.add_argument("--max-lanes", type=int, default=DEFAULT_EPOCH_LANE_LIMIT)
    prep.add_argument("--max-prior-failures", type=int, default=4)
    prep.add_argument("--include-frozen", action="store_true")
    prep.add_argument("--allow-drift", action="store_true")
    prep.add_argument("--drift-classification", default="", help="Required when --allow-drift is used.")
    prep.add_argument("--drift-note", default="", help="Short evidence note for classified drift.")
    prep.add_argument("--force", action="store_true")
    prep.add_argument("--no-copy", action="store_true", help="Create prompts/manifest without copying project workspaces.")
    prep.set_defaults(func=command_prepare_epoch)

    gate = sub.add_parser("gate-decision", help="Classify one child_result.json before parent gate.")
    gate.add_argument("--child-result", required=True)
    gate.add_argument("--project", help="Project root for online/offline weights.")
    gate.add_argument("--min-rank-score", type=float, default=10.0)
    gate.set_defaults(func=command_gate_decision)

    close = sub.add_parser("close-epoch", help="Summarize a prepared epoch after child agents finish.")
    close.add_argument("--run-dir", required=True)
    close.add_argument("--project", help="Project root for online/offline weights.")
    close.add_argument("--min-rank-score", type=float, default=10.0)
    close.add_argument("--write", action="store_true", help="Write epoch_closeout.json in the run directory.")
    close.set_defaults(func=command_close_epoch)

    dispatch = sub.add_parser("dispatch-epoch", help="Create a dispatch queue from an epoch manifest.")
    dispatch.add_argument("--run-dir", required=True)
    dispatch.add_argument("--phase", choices=["auto", "A", "B", "all"], default="auto", help="Dispatch phase. auto sends Phase A first, then Phase B after Phase A current evidence exists.")
    dispatch.add_argument("--include-prompts", action="store_true")
    dispatch.add_argument("--max-workers", type=int, default=DEFAULT_MAX_ACTIVE_WORKERS)
    dispatch.add_argument("--write", action="store_true")
    dispatch.set_defaults(func=command_dispatch_epoch)

    collect = sub.add_parser("collect-epoch", help="Collect child_result status and rank completed lanes.")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--project", help="Project root for online/offline weights.")
    collect.add_argument("--write", action="store_true")
    collect.set_defaults(func=command_collect_epoch)

    pool = sub.add_parser("pool-update", help="Update one lane status in an epoch pool_state.json.")
    pool.add_argument("--run-dir", required=True)
    pool.add_argument("--lane", required=True)
    pool.add_argument("--status", required=True, choices=["ready", "active", "blocked", "completed", "completed-invalid", "cancelled", "retired"])
    pool.add_argument("--worker-id", default="")
    pool.add_argument("--blocker", default="")
    pool.add_argument("--clear-blocker", action="store_true", help="Clear any stale blocker text for this lane.")
    pool.add_argument("--write", action="store_true")
    pool.set_defaults(func=command_pool_update)

    phase_transition = sub.add_parser("phase-transition", help="Record a coordinator phase transition and unblock ready lanes.")
    phase_transition.add_argument("--run-dir", required=True)
    phase_transition.add_argument("--to-phase", required=True, choices=["B", "all"], help="Phase to open after prerequisite evidence is collected.")
    phase_transition.add_argument("--reason", required=True, help="Current-evidence reason for opening the next phase.")
    phase_transition.add_argument("--force", action="store_true", help="Allow transition even if Phase A current evidence is incomplete.")
    phase_transition.add_argument("--write", action="store_true")
    phase_transition.set_defaults(func=command_phase_transition)

    pool_retire = sub.add_parser("pool-retire", help="Retire completed or selected lanes in an epoch pool_state.json.")
    pool_retire.add_argument("--run-dir", required=True)
    pool_retire.add_argument("--lane", action="append", help="Lane to retire. May be repeated.")
    pool_retire.add_argument("--completed", action="store_true", help="Retire every completed/completed-invalid lane.")
    pool_retire.add_argument("--force", action="store_true", help="Allow retiring active lanes.")
    pool_retire.add_argument("--write", action="store_true")
    pool_retire.set_defaults(func=command_pool_retire)

    learn = sub.add_parser("learn-from-children", help="Extract reusable lessons and mutation-space/index patches from child_result files.")
    learn.add_argument("--run-dir", required=True, help="Epoch directory, workspaces directory, or one child_result.json.")
    learn.add_argument("--project", help="Project root. Defaults to current directory.")
    learn.add_argument("--mutation-space", help="Path to mutation_space.json.")
    learn.add_argument("--min-rank-score", type=float, default=10.0)
    learn.add_argument("--write-index", action="store_true", help="Append new entries to docs/exploration-index.json.")
    learn.add_argument("--write-mutation-space", action="store_true", help="Append rejected avoidNextTime lessons to frozenPatterns.")
    learn.add_argument("--write-search-graph", action="store_true", help="Write docs/search-graph.json and docs/attempt-cards/*.json.")
    learn.add_argument("--write-failed-diffs", action="store_true", help="Write rejected solver diffs to docs/failed_diffs and docs/failed-diffs-index.json.")
    learn.set_defaults(func=command_learn_from_children)

    archive = sub.add_parser("archive-attempt", help="Archive a child_result as a ledger successful/failed experiment.")
    archive.add_argument("--project", help="Project root. Defaults to current directory.")
    archive.add_argument("--child-result", required=True)
    archive.add_argument("--attempt", default="")
    archive.add_argument("--bucket", choices=["auto", "successfulExperiments", "failedExperiments"], default="auto")
    archive.add_argument("--accepted", action="store_true", help="With --bucket auto, archive promotion candidates as successful experiments.")
    archive.add_argument("--result", default="")
    archive.add_argument("--failure-reason", default="")
    archive.add_argument("--manual-override", action="store_true", help="Allow accepted archive when epoch closeout was not eligible.")
    archive.add_argument("--override-reason", default="", help="Required reason for --manual-override.")
    archive.add_argument("--force", action="store_true")
    archive.add_argument("--write", action="store_true")
    archive.add_argument("--write-search-graph", action="store_true", help="Also write/update docs/search-graph.json and docs/attempt-cards/*.json.")
    archive.set_defaults(func=command_archive_attempt)

    attempt_card = sub.add_parser("attempt-card", help="Render one child_result.json as a durable attempt card.")
    attempt_card.add_argument("--project", help="Project root. Defaults to current directory.")
    attempt_card.add_argument("--child-result", required=True)
    attempt_card.add_argument("--write", action="store_true", help="Write docs/attempt-cards/<attempt>.json.")
    attempt_card.add_argument("--write-search-graph", action="store_true", help="Also update docs/search-graph.json.")
    attempt_card.set_defaults(func=command_attempt_card)

    search_graph = sub.add_parser("search-graph", help="Summarize or rebuild the persistent experiment search graph.")
    search_graph.add_argument("--project", help="Project root. Defaults to current directory.")
    search_graph.add_argument("--limit", type=int, default=10)
    search_graph.add_argument("--rebuild-from", default="", help="Epoch/workspaces directory or child_result.json to ingest.")
    search_graph.add_argument("--write", action="store_true", help="When rebuilding, write graph and cards.")
    search_graph.set_defaults(func=command_search_graph)

    failed_diffs = sub.add_parser("failed-diffs", help="Inspect or rebuild the failed diff furnace index.")
    failed_diffs.add_argument("--project", help="Project root. Defaults to current directory.")
    failed_diffs.add_argument("--limit", type=int, default=10)
    failed_diffs.add_argument("--rebuild-from", default="", help="Epoch/workspaces directory or child_result.json to ingest.")
    failed_diffs.add_argument("--family", default="")
    failed_diffs.add_argument("--mechanism", default="")
    failed_diffs.add_argument("--target-function", default="")
    failed_diffs.add_argument("--control-tag", default="")
    failed_diffs.add_argument("--hypothesis", default="", help="Assess novelty of a proposed mutation text against failed diffs.")
    failed_diffs.add_argument("--write", action="store_true", help="When rebuilding, write docs/failed_diffs and docs/failed-diffs-index.json.")
    failed_diffs.set_defaults(func=command_failed_diffs)

    register = sub.add_parser("register-submission", help="Record metadata for a short upload-safe submission zip name.")
    register.add_argument("--project", help="Project root. Defaults to current directory.")
    register.add_argument("--package", required=True, help="Short zip path/name, e.g. dist/sub047.zip.")
    register.add_argument("--attempt", required=True, help="Full attempt/baseline id represented by the short zip.")
    register.add_argument("--family", required=True)
    register.add_argument("--mechanism", default="unknown")
    register.add_argument("--shape", default="")
    register.add_argument("--based-on", default="")
    register.add_argument("--predicted-direction", choices=["up", "down", "neutral", "unknown"], default="up")
    register.add_argument("--source-package", default="", help="Optional original long/local package name.")
    register.add_argument("--note", default="")
    register.add_argument("--max-name-length", type=int, default=MAX_SUBMISSION_BASENAME_LENGTH)
    register.add_argument("--force", action="store_true")
    register.add_argument("--write", action="store_true")
    register.set_defaults(func=command_register_submission)

    online_feedback = sub.add_parser("online-feedback", help="Parse raw leaderboard feedback text and update online/offline calibration.")
    online_feedback.add_argument("--project", help="Project root. Defaults to current directory.")
    online_feedback.add_argument("--text", default="", help="Raw pasted leaderboard feedback text. Reads stdin when omitted.")
    online_feedback.add_argument("--file", default="", help="Read raw leaderboard feedback text from a file.")
    online_feedback.add_argument("--attempt", default="", help="Override parsed attempt id.")
    online_feedback.add_argument("--online-score", type=float, help="Override parsed online score.")
    online_feedback.add_argument("--family", default="", help="Override inferred family label.")
    online_feedback.add_argument("--mechanism", default="", help="Override inferred mechanism label.")
    online_feedback.add_argument("--shape", default="", help="Override inferred shape label.")
    online_feedback.add_argument("--predicted-direction", choices=["auto", "up", "down", "neutral", "unknown"], default="auto")
    online_feedback.add_argument("--based-on")
    online_feedback.add_argument("--local-quick-delta", type=float)
    online_feedback.add_argument("--local-full-delta", type=float)
    online_feedback.add_argument("--hidden-hypothesis", default="")
    online_feedback.add_argument("--reason", default="")
    online_feedback.add_argument("--submitted-package", default="")
    online_feedback.add_argument("--submitted-at", default="")
    online_feedback.add_argument("--neutral-delta", type=float, default=0.0)
    online_feedback.add_argument("--confirm-step", type=float, default=0.15)
    online_feedback.add_argument("--contradict-step", type=float, default=0.25)
    online_feedback.add_argument("--neutral-step", type=float, default=0.0)
    online_feedback.add_argument("--write", action="store_true")
    online_feedback.add_argument("--write-ledger", action="store_true")
    online_feedback.add_argument("--accept-best-update", action="store_true")
    online_feedback.add_argument("--auto-accept-best", action="store_true", help="Accept as best only when parsed score is strictly above current best.")
    online_feedback.add_argument("--force-ledger", action="store_true")
    online_feedback.set_defaults(func=command_online_feedback)

    online = sub.add_parser("online-update", help="Update online/offline family weights from one online score.")
    online.add_argument("--project", help="Project root. Defaults to current directory.")
    online.add_argument("--attempt", required=True)
    online.add_argument("--online-score", required=True)
    online.add_argument("--family", required=True)
    online.add_argument("--mechanism", default="unknown")
    online.add_argument("--shape", default="", help="Optional hidden-shape / case-shape label for fine-grained calibration.")
    online.add_argument("--predicted-direction", choices=["up", "down", "neutral", "unknown"], default="unknown")
    online.add_argument("--based-on")
    online.add_argument("--local-quick-delta", type=float)
    online.add_argument("--local-full-delta", type=float)
    online.add_argument("--hidden-hypothesis", default="")
    online.add_argument("--reason", default="")
    online.add_argument("--submitted-package", default="")
    online.add_argument("--submitted-at", default="")
    online.add_argument("--neutral-delta", type=float, default=0.0)
    online.add_argument("--confirm-step", type=float, default=0.15)
    online.add_argument("--contradict-step", type=float, default=0.25)
    online.add_argument("--neutral-step", type=float, default=0.0)
    online.add_argument("--write", action="store_true")
    online.add_argument("--write-ledger", action="store_true", help="Also append a normalized onlineEvaluations record to optimization-ledger.json.")
    online.add_argument("--accept-best-update", action="store_true", help="When the online score improves, update bestKnownOnlineScore/Baseline in the current baseline scores.")
    online.add_argument("--force-ledger", action="store_true", help="Allow appending a duplicate attempt online evaluation.")
    online.set_defaults(func=command_online_update)

    drift = sub.add_parser("drift", help="Classify source hash drift against the ledger and baseline snapshots.")
    drift.add_argument("--project", help="Project root. Defaults to current directory.")
    drift.set_defaults(func=command_drift)

    restore = sub.add_parser("restore-online-best", help="Restore src/Solution.cpp from the best-known online baseline snapshot, backing up drift first.")
    restore.add_argument("--project", help="Project root. Defaults to current directory.")
    restore.add_argument("--baseline", default="", help="Override baseline id. Defaults to bestKnownOnlineBaseline.")
    restore.add_argument("--update-ledger", action="store_true", help="Also set optimization-ledger currentBaseline to the restored baseline record.")
    restore.add_argument("--write", action="store_true")
    restore.set_defaults(func=command_restore_online_best)

    init_weights = sub.add_parser("init-weights", help="Initialize online/offline weights from ledger onlineEvaluations.")
    init_weights.add_argument("--project", help="Project root. Defaults to current directory.")
    init_weights.add_argument("--confirm-step", type=float, default=0.12)
    init_weights.add_argument("--contradict-step", type=float, default=0.18)
    init_weights.add_argument("--write", action="store_true")
    init_weights.set_defaults(func=command_init_weights)

    run_epoch = sub.add_parser("run-epoch", help="One-command doctor/status/prepare epoch runner.")
    run_epoch.add_argument("--project", help="Project root. Defaults to current directory.")
    run_epoch.add_argument("--mutation-space", help="Path to mutation_space.json.")
    run_epoch.add_argument("--idea-board", default="", help="Path to docs/idea-boards/*.json; selectedLanes become canonical epoch lanes.")
    run_epoch.add_argument("--run-id", default="")
    run_epoch.add_argument("--output", default="")
    run_epoch.add_argument("--max-lanes", type=int, default=DEFAULT_EPOCH_LANE_LIMIT)
    run_epoch.add_argument("--max-prior-failures", type=int, default=4)
    run_epoch.add_argument("--include-frozen", action="store_true")
    run_epoch.add_argument("--allow-dirty", action="store_true", help="Allow prepared diagnostic/edit lanes after explicit drift classification.")
    run_epoch.add_argument("--drift-classification", default="")
    run_epoch.add_argument("--drift-note", default="")
    run_epoch.add_argument("--force", action="store_true")
    run_epoch.add_argument("--no-copy", action="store_true")
    run_epoch.add_argument("--min-doctor-score", type=float, default=9.5)
    run_epoch.add_argument("--max-duplicate-keys", type=int, default=2)
    run_epoch.add_argument("--allow-online-unconfirmed", action="store_true", help="Allow edit lanes from a local baseline that is not best-known online.")
    run_epoch.add_argument("--from-online-best", action="store_true", help="Compatibility alias: require restoring online-best first; does not mutate by itself.")
    run_epoch.add_argument("--mutation-space-only", action="store_true", help="Legacy fallback: skip automatic divergent idea-board generation and prepare lanes directly from mutation_space.json.")
    run_epoch.set_defaults(func=command_run_epoch)

    audit_skill = sub.add_parser("audit-skill", help="Check CLI/SKILL.md router consistency.")
    audit_skill.set_defaults(func=command_audit_skill)

    reweight = sub.add_parser("reweight-mutations", help="Reweight mutation_space families from online/offline weights.")
    reweight.add_argument("--project", help="Project root. Defaults to current directory.")
    reweight.add_argument("--mutation-space", help="Path to mutation_space.json.")
    reweight.add_argument("--output", default="", help="Output path. Defaults to updating the mutation-space path when --write is used.")
    reweight.add_argument("--exploit-threshold", type=float, default=0.6)
    reweight.add_argument("--freeze-threshold", type=float, default=0.35)
    reweight.add_argument("--write", action="store_true")
    reweight.set_defaults(func=command_reweight_mutations)

    doctor = sub.add_parser("doctor", help="Score loop readiness audit for autonomous 9.5-grade operation.")
    doctor.add_argument("--project", help="Project root. Defaults to current directory.")
    doctor.add_argument("--mutation-space", help="Path to mutation_space.json.")
    doctor.add_argument("--min-score", type=float, default=9.5)
    doctor.add_argument("--max-duplicate-keys", type=int, default=2)
    doctor.add_argument("--allow-online-unconfirmed", action="store_true", help="Allow active baseline to differ from best-known online for diagnostic/proposal work.")
    doctor.set_defaults(func=command_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
