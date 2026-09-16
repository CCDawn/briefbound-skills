import argparse
import json
import re
import sys
from pathlib import Path


BRIEFBOUND_CONTRACT_FIELDS = [
    "Context Boundary",
    "Output Contract",
    "Allowed Action",
    "Success Evidence",
    "Stop Condition",
    "Route Out",
]

ROUTER_CORE_MARKERS = [
    "One-Turn Alignment",
    "Route Contract",
    "Next Action",
    "FAST_PATH",
    "COMPACT_FLOW",
    "FULL_FLOW",
    "briefbound-simplification-review",
    "briefbound-simplification-audit",
    "briefbound-performance-engineering",
    "briefbound-code-structure-guard",
    "briefbound-ai-research-loop",
    "briefbound-research-rigor-review",
    "briefbound-autonomous-collaboration-loop",
    "briefbound-multi-agent-orchestration",
    "briefbound-thread-coordination",
    "briefbound-development-cleanup",
    "默认 `AUTO`",
    "能力感知与阶段折叠",
    "`FAST_PATH` 直接执行并最小验证",
    "Skill Budget",
    "约束用于防错",
    "Superpowers 默认不参与自动路由",
    "## 讨论式意图收敛",
    "Alignment Value Gate",
    "ALIGNMENT_PENDING",
    "CALIBRATED",
    "一次窄范围只读 probe",
    "不得静默替用户决定产品行为",
    "不得询问本地证据已经回答的问题",
    "低置信度不得带着未确认的高影响假设写入",
    "只提出答案会改变走向的问题",
    "Unexpected Issue Gate",
    "停止受影响写入",
    "不得扩大范围或硬做",
    "Collaboration Discovery",
    "PEER_READ_ONLY",
    "PEER_DISJOINT_WRITE",
    "PEER_COLLABORATION_READY",
    "COORDINATE_OVERLAP",
    "PEER_CONTEXT_REVIEW",
    "ASK_CREATE",
    "Silent Conflict Triage",
    "READ / WRITE / REMOTE_WRITE / DESTRUCTIVE",
    "写入可分离且收益高于协调成本才并行",
    "FAST / CHECK / PROFILE",
    "不为每次开发建立 benchmark",
    "STAY / CHECK / SPLIT",
    "preflight --write-kind",
    "ISOLATION_REQUIRED",
    "同一 dirty-target blocker 第二次出现",
    "规划文档属于 development 写入",
    "先说结果",
    "复杂概念会改变用户判断或操作时",
]

UNIFIED_CONTRACT_MARKERS = [
    "## 统一调用契约",
    "用户可见内容默认中文",
    "下一步建议: <一个具体动作>",
    "Route Out 仅以 Briefbound task contract 为准",
]

DIRECT_WRITE_OWNERS = {
    "briefbound-autonomous-collaboration-loop",
    "briefbound-bdd-tdd-development",
    "briefbound-bug-review",
    "briefbound-code-structure-guard",
    "briefbound-design-system",
    "briefbound-frontend-engineering",
    "briefbound-multi-agent-orchestration",
    "briefbound-performance-engineering",
    "briefbound-thread-coordination",
    "briefbound-ui-design",
}

TOKEN_BUDGETS = {
    "briefbound-ai-research-loop": 2200,
    "briefbound-autonomous-collaboration-loop": 2300,
    "briefbound-bdd-tdd-development": 1350,
    "briefbound-router": 2800,
    "briefbound-bug-review": 1200,
    "briefbound-code-structure-guard": 1100,
    "briefbound-competition-research-lifecycle": 2500,
    "briefbound-completion-summary": 2400,
    "briefbound-creative-toolbox": 1400,
    "briefbound-project-memory": 1400,
    "briefbound-development-cleanup": 1900,
    "briefbound-design-system": 1500,
    "briefbound-evaluation": 1000,
    "briefbound-feature-reuse-research": 2100,
    "briefbound-frontend-engineering": 1550,
    "briefbound-goal-loop": 1100,
    "briefbound-huawei-nslb-score-loop": 1200,
    "briefbound-multi-agent-orchestration": 1900,
    "briefbound-performance-engineering": 1500,
    "briefbound-planning": 1850,
    "briefbound-pr-review": 1500,
    "briefbound-project-review": 1500,
    "briefbound-research-rigor-review": 1600,
    "briefbound-score-loop": 2200,
    "briefbound-simplification-audit": 1000,
    "briefbound-simplification-review": 1000,
    "briefbound-thread-coordination": 1700,
    "briefbound-ui-design": 2100,
    "briefbound-ui-review": 1350,
    "briefbound-visual-design": 1850,
}

ROUTER_REFERENCE_BUDGETS = {
    "collaboration-discovery.md": 900,
    "routing-practice.md": 2650,
    "capability-routing.md": 1500,
    "runtime.md": 1800,
    "output-forms.md": 900,
    "ui-preview-approval.md": 1600,
}

ROUTER_REFERENCE_REQUIRED_MARKERS = {
    "collaboration-discovery.md": [
        "只读最多 3 个最相关候选",
        "PEER_DISJOINT_WRITE -> PEER_COLLABORATION_READY",
        "不得把现有会话视为可派发的 worker",
    ],
    "routing-practice.md": [
        "未出现的 skill 不能成为 owner",
        "不完成一个就停下来询问",
        "多个 `SAFE_DIRECT` 项只推荐一个",
    ],
    "runtime.md": [
        "完成一个 task 不构成用户闸门",
        "当前项通过后自动进入下一个已授权项",
    ],
    "capability-routing.md": [
        "Preferred owner（可用时）",
        "同一动作只设一个 primary",
        "不是再次索要许可",
        "Preferred owner 不可用时",
    ],
    "output-forms.md": [
        "已有执行许可时连续推进 `SAFE_DIRECT`",
        "只有自然闸门才提供 2-3 个具体选项",
        "触发 `Alignment Value Gate` 时等待用户回复",
        "提问前先摘要已查到的项目惯例",
        "## 意外问题讨论",
        "原契约内可安全、可逆恢复的问题直接处理",
        "## UI 预览预审",
        "APPROVED / REVISE <反馈> / ABANDON",
        "我理解你要的结果是",
        "换一种做法会",
        "如果理解有误，可能",
    ],
    "ui-preview-approval.md": [
        "PREVIEW_REQUIRED",
        "PREVIEW_SKIPPED",
        "WAITING_USER_REVIEW",
        "APPROVED | REVISE | ABANDON",
        "正式 UI owning surface",
        "外部部署属于独立 `REMOTE_WRITE`",
        "不能代替用户批准",
    ],
}

ROUTER_PROFILE_BUDGETS = {
    "alignment": (["SKILL.md", "references/output-forms.md"], 3600),
    "collaboration": (["SKILL.md", "references/collaboration-discovery.md"], 3500),
    "routing": (["SKILL.md", "references/routing-practice.md"], 5450),
    "long-task": (["SKILL.md", "references/runtime.md"], 4300),
    "maximum": (
        [
            "SKILL.md",
            "references/output-forms.md",
            "references/routing-practice.md",
            "references/runtime.md",
        ],
        7200,
    ),
}

HOT_ROUTE_EXTERNAL_CANDIDATES = {
    "agent-browser",
    "api-and-interface-design",
    "browser-testing-with-devtools",
    "codebase-recon",
    "context-engineering",
    "doubt-driven-development",
    "incremental-implementation",
    "performance-optimization",
    "security-and-hardening",
    "spec-driven-development",
    "webapp-testing",
}

UI_ROUTE_OWNERS = {
    "briefbound-ui-design",
    "briefbound-visual-design",
    "briefbound-frontend-engineering",
    "briefbound-design-system",
    "briefbound-ui-review",
}

UI_METADATA_FORBIDDEN_TERMS = {
    "briefbound-ui-design": ["实施或审查"],
    "briefbound-visual-design": ["审查当前界面", "实现当前前端"],
    "briefbound-frontend-engineering": ["审查当前界面", "建立当前界面的视觉方向"],
    "briefbound-design-system": ["审查当前界面", "建立当前界面的视觉方向"],
    "briefbound-ui-review": ["实现当前前端", "建立当前界面的视觉方向"],
}

UI_PREVIEW_REQUIRED_MARKERS = {
    "briefbound-ui-design": [
        "## 预览批准闸门",
        "PREVIEW_REQUIRED / PREVIEW_SKIPPED",
        "WAITING_USER_REVIEW",
        "APPROVED / REVISE <反馈> / ABANDON",
        "批准前不进入正式实现",
    ],
    "briefbound-visual-design": [
        "## 预览批准闸门",
        "PREVIEW_REQUIRED",
        "PREVIEW_SKIPPED",
        "WAITING_USER_REVIEW",
        "UI Review 的通过建议不能代替用户批准",
    ],
    "briefbound-frontend-engineering": [
        "## 预览证据闸门",
        "PREVIEW_REQUIRED",
        "PREVIEW_SKIPPED",
        "用户已明确批准具体预览或设计稿",
        "不能替代对具体预览的用户批准",
    ],
    "briefbound-ui-review": [
        "## 预览预审",
        "READY_FOR_USER_APPROVAL",
        "REVISE_RECOMMENDED",
        "只有用户对具体预览明确批准",
    ],
}

MIN_SHORT_DESCRIPTION_CHARS = 25
MAX_SHORT_DESCRIPTION_CHARS = 64
MAX_SKILL_LINES = 500
REFERENCE_TOC_THRESHOLD_LINES = 100
REFERENCE_TOC_PATTERN = re.compile(r"(?m)^## (?:目录|Contents|Table of Contents)\s*$")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(skill_md: Path) -> dict[str, str]:
    text = read_text(skill_md)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    values: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def parse_openai_interface(openai_yaml: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_text(openai_yaml).splitlines():
        match = re.match(r'^\s{2}(display_name|short_description|default_prompt):\s*["\'](.*)["\']\s*$', line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def estimated_instruction_tokens(text: str) -> int:
    """Cheap language-aware size proxy; whitespace counts badly undercount Chinese."""
    cjk_chars = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    punctuation = len(re.findall(r"[^\w\s\u3400-\u9fff]", text))
    return cjk_chars + round(latin_words * 1.3) + punctuation // 3


def discover_skill_dirs(repo_root: Path) -> list[Path]:
    return sorted(
        [path.parent for path in (repo_root / "skills").rglob("SKILL.md")],
        key=lambda item: item.name,
    )


def rel_skill_path(repo_root: Path, skill_dir: Path) -> str:
    return "./" + skill_dir.relative_to(repo_root).as_posix()


def validate_briefbound_route_references(
    repo_root: Path,
    skill_names: set[str],
    errors: list[str],
) -> None:
    references: dict[str, list[str]] = {}
    for markdown_path in sorted((repo_root / "skills").rglob("*.md")):
        text = read_text(markdown_path)
        for referenced_name in sorted(set(re.findall(r"\bbriefbound-[a-z0-9-]+\b", text))):
            if referenced_name in skill_names:
                continue
            label = markdown_path.relative_to(repo_root).as_posix()
            references.setdefault(referenced_name, []).append(label)

    for missing_name, paths in sorted(references.items()):
        locations = ", ".join(paths[:3])
        if len(paths) > 3:
            locations += f", and {len(paths) - 3} more"
        errors.append(
            f"unresolved Briefbound route '{missing_name}' referenced by {locations}; "
            "package the skill or remove the route"
        )


def validate_ui_routing_cases(
    repo_root: Path,
    skill_names: set[str],
    errors: list[str],
) -> None:
    cases_path = repo_root / "tests" / "ui_routing_cases.json"
    if not cases_path.exists():
        errors.append("tests/ui_routing_cases.json: missing")
        return

    try:
        cases = json.loads(read_text(cases_path))
    except json.JSONDecodeError as exc:
        errors.append(f"tests/ui_routing_cases.json: invalid JSON: {exc}")
        return

    if not isinstance(cases, list) or not cases:
        errors.append("tests/ui_routing_cases.json: expected a non-empty list")
        return

    seen_ids: set[str] = set()
    primary_coverage: set[str] = set()
    forbidden_coverage: set[str] = set()
    for index, case in enumerate(cases):
        label = f"tests/ui_routing_cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected an object")
            continue

        case_id = case.get("id", "")
        prompt = case.get("prompt", "")
        primary = case.get("primary", "")
        support = case.get("support", [])
        forbidden = case.get("forbidden_primary", [])

        if not case_id or case_id in seen_ids:
            errors.append(f"{label}: id must be non-empty and unique")
        seen_ids.add(case_id)
        if not prompt or not contains_cjk(prompt):
            errors.append(f"{label}: prompt must be Chinese-first")
        if primary not in skill_names:
            errors.append(f"{label}: unknown primary owner '{primary}'")
        else:
            primary_coverage.add(primary)
        if not isinstance(support, list) or len(support) > 1:
            errors.append(f"{label}: support must be a list with at most one owner")
            support = []
        if not isinstance(forbidden, list) or not forbidden:
            errors.append(f"{label}: forbidden_primary must be a non-empty list")
            forbidden = []
        for owner in support + forbidden:
            if owner not in skill_names:
                errors.append(f"{label}: unknown referenced owner '{owner}'")
        if primary in forbidden:
            errors.append(f"{label}: primary owner cannot also be forbidden")
        forbidden_coverage.update(forbidden)

    missing_primary = sorted(UI_ROUTE_OWNERS - primary_coverage)
    if missing_primary:
        errors.append(f"tests/ui_routing_cases.json: missing positive cases for {missing_primary}")
    missing_negative = sorted(UI_ROUTE_OWNERS - forbidden_coverage)
    if missing_negative:
        errors.append(f"tests/ui_routing_cases.json: missing negative cases for {missing_negative}")

    routing_text = read_text(
        repo_root / "skills" / "engineering" / "briefbound-router" / "references" / "routing-practice.md"
    )
    for owner in sorted(UI_ROUTE_OWNERS):
        if f"`{owner}`" not in routing_text:
            errors.append(f"briefbound-router routing-practice: missing UI route owner '{owner}'")

        metadata_path = repo_root / "skills" / "engineering" / owner / "agents" / "openai.yaml"
        metadata = read_text(metadata_path) if metadata_path.exists() else ""
        for forbidden_term in UI_METADATA_FORBIDDEN_TERMS.get(owner, []):
            if forbidden_term in metadata:
                errors.append(
                    f"{metadata_path.relative_to(repo_root)}: stale overlapping UI route term "
                    f"'{forbidden_term}'"
                )


def validate_package_routing_cases(
    repo_root: Path,
    skill_names: set[str],
    errors: list[str],
) -> None:
    cases_path = repo_root / "tests" / "routing_cases.json"
    if not cases_path.exists():
        errors.append("tests/routing_cases.json: missing")
        return

    try:
        cases = json.loads(read_text(cases_path))
    except json.JSONDecodeError as exc:
        errors.append(f"tests/routing_cases.json: invalid JSON: {exc}")
        return

    if not isinstance(cases, list) or len(cases) < len(skill_names):
        errors.append(
            "tests/routing_cases.json: expected at least one routing case per packaged skill"
        )
        return

    seen_ids: set[str] = set()
    primary_coverage: set[str] = set()
    forbidden_coverage: set[str] = set()
    composite_count = 0
    for index, case in enumerate(cases):
        label = f"tests/routing_cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected an object")
            continue

        required_fields = {"id", "prompt", "primary", "support", "forbidden_primary"}
        missing_fields = sorted(required_fields - set(case))
        if missing_fields:
            errors.append(f"{label}: missing fields {missing_fields}")
            continue

        case_id = case["id"]
        prompt = case["prompt"]
        primary = case["primary"]
        support = case["support"]
        forbidden = case["forbidden_primary"]

        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            errors.append(f"{label}: id must be a non-empty unique string")
        seen_ids.add(case_id)
        if not isinstance(prompt, str) or not prompt or not contains_cjk(prompt):
            errors.append(f"{label}: prompt must be Chinese-first")
        if primary not in skill_names:
            errors.append(f"{label}: unknown primary owner '{primary}'")
        else:
            primary_coverage.add(primary)
        if not isinstance(support, list) or len(support) > 1:
            errors.append(f"{label}: support must contain at most one owner")
            support = []
        if support:
            composite_count += 1
        if not isinstance(forbidden, list) or not forbidden:
            errors.append(f"{label}: forbidden_primary must be a non-empty list")
            forbidden = []
        for owner in support + forbidden:
            if owner not in skill_names:
                errors.append(f"{label}: unknown referenced owner '{owner}'")
        if primary in support or primary in forbidden:
            errors.append(f"{label}: primary owner cannot also be support or forbidden")
        forbidden_coverage.update(forbidden)

    missing_primary = sorted(skill_names - primary_coverage)
    if missing_primary:
        errors.append(f"tests/routing_cases.json: missing positive cases for {missing_primary}")
    if composite_count < 2:
        errors.append("tests/routing_cases.json: expected at least two composite routing cases")
    missing_negative = sorted(skill_names - forbidden_coverage)
    if missing_negative:
        errors.append(
            "tests/routing_cases.json: missing negative boundary coverage for "
            f"{missing_negative}"
        )


def validate_live_routing_cases(
    repo_root: Path,
    skill_names: set[str],
    errors: list[str],
) -> None:
    path = repo_root / "tests" / "live_routing_cases.json"
    label = "tests/live_routing_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot load: {exc}")
        return
    if not isinstance(cases, list) or len(cases) < 3:
        errors.append(f"{label}: expected at least three live cases")
        return

    required = {
        "id",
        "prompt",
        "smoke",
        "expected_skill_reads",
        "forbidden_skill_reads",
        "max_commands",
        "expected_final_any",
        "timeout_seconds",
    }
    seen_ids: set[str] = set()
    smoke_count = 0
    for index, case in enumerate(cases):
        case_label = f"{label}[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{case_label}: expected an object")
            continue
        missing = sorted(required - set(case))
        if missing:
            errors.append(f"{case_label}: missing fields {missing}")
            continue

        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            errors.append(f"{case_label}: id must be a non-empty unique string")
        seen_ids.add(case_id)
        if not isinstance(case["prompt"], str) or not contains_cjk(case["prompt"]):
            errors.append(f"{case_label}: prompt must be Chinese-first")
        if not isinstance(case["smoke"], bool):
            errors.append(f"{case_label}: smoke must be boolean")
        elif case["smoke"]:
            smoke_count += 1

        expected = case["expected_skill_reads"]
        forbidden = case["forbidden_skill_reads"]
        if not isinstance(expected, list):
            errors.append(f"{case_label}: expected_skill_reads must be a list")
            expected = []
        if not isinstance(forbidden, list) or not forbidden:
            errors.append(f"{case_label}: forbidden_skill_reads must be a non-empty list")
            forbidden = []
        for owner in expected + forbidden:
            if not isinstance(owner, str) or owner not in skill_names:
                errors.append(f"{case_label}: unknown skill read '{owner}'")
        overlap = sorted(set(expected) & set(forbidden))
        if overlap:
            errors.append(f"{case_label}: expected and forbidden skill reads overlap: {overlap}")

        max_commands = case["max_commands"]
        if not isinstance(max_commands, int) or not 0 <= max_commands <= 50:
            errors.append(f"{case_label}: max_commands must be an integer from 0 to 50")
        expected_final = case["expected_final_any"]
        if not isinstance(expected_final, list) or not all(
            isinstance(term, str) and term for term in expected_final
        ):
            errors.append(f"{case_label}: expected_final_any must be a string list")
        for field in (
            "expected_final_all",
            "forbidden_final_any",
            "forbidden_delegation_phrases",
        ):
            terms = case.get(field, [])
            if not isinstance(terms, list) or not all(
                isinstance(term, str) and term for term in terms
            ):
                errors.append(f"{case_label}: {field} must be a string list")
        semantic_groups = case.get("expected_final_groups", [])
        if not isinstance(semantic_groups, list) or not all(
            isinstance(group, list)
            and group
            and all(isinstance(term, str) and term for term in group)
            for group in semantic_groups
        ):
            errors.append(f"{case_label}: expected_final_groups must be a list of non-empty string lists")
        min_commands = case.get("min_commands", 0)
        if not isinstance(min_commands, int) or not 0 <= min_commands <= max_commands:
            errors.append(f"{case_label}: min_commands must be an integer from 0 to max_commands")
        for field in ("min_questions", "max_questions"):
            value = case.get(field)
            if value is not None and (not isinstance(value, int) or not 0 <= value <= 10):
                errors.append(f"{case_label}: {field} must be an integer from 0 to 10")
        if case.get("min_questions", 0) > case.get("max_questions", 10):
            errors.append(f"{case_label}: min_questions must not exceed max_questions")
        for field in (
            "require_recommendation",
            "require_wrong_decision_impact",
            "require_wait_for_calibration",
        ):
            value = case.get(field)
            if value is not None and not isinstance(value, bool):
                errors.append(f"{case_label}: {field} must be boolean")
        timeout_seconds = case["timeout_seconds"]
        if not isinstance(timeout_seconds, int) or not 30 <= timeout_seconds <= 600:
            errors.append(f"{case_label}: timeout_seconds must be an integer from 30 to 600")

        workspace_files = case.get("workspace_files")
        if workspace_files is not None:
            if not isinstance(workspace_files, dict) or not workspace_files:
                errors.append(f"{case_label}: workspace_files must be a non-empty object")
            else:
                for relative_name, content in workspace_files.items():
                    normalized = relative_name.replace("\\", "/") if isinstance(relative_name, str) else ""
                    if (
                        not normalized
                        or normalized.startswith("/")
                        or re.match(r"^[A-Za-z]:", normalized)
                        or ".." in normalized.split("/")
                    ):
                        errors.append(f"{case_label}: unsafe workspace fixture path '{relative_name}'")
                    if not isinstance(content, str) or not content:
                        errors.append(f"{case_label}: workspace fixture '{relative_name}' must be non-empty text")

        followups = case.get("followups", [])
        if not isinstance(followups, list):
            errors.append(f"{case_label}: followups must be a list")
            followups = []
        for followup_index, followup in enumerate(followups, start=1):
            followup_label = f"{case_label}.followups[{followup_index - 1}]"
            followup_required = {
                "prompt",
                "expected_skill_reads",
                "forbidden_skill_reads",
                "max_commands",
                "expected_final_any",
            }
            if not isinstance(followup, dict):
                errors.append(f"{followup_label}: expected an object")
                continue
            followup_missing = sorted(followup_required - set(followup))
            if followup_missing:
                errors.append(f"{followup_label}: missing fields {followup_missing}")
                continue
            if not isinstance(followup["prompt"], str) or not contains_cjk(followup["prompt"]):
                errors.append(f"{followup_label}: prompt must be Chinese-first")
            followup_expected = followup["expected_skill_reads"]
            followup_forbidden = followup["forbidden_skill_reads"]
            if not isinstance(followup_expected, list):
                errors.append(f"{followup_label}: expected_skill_reads must be a list")
                followup_expected = []
            if not isinstance(followup_forbidden, list) or not followup_forbidden:
                errors.append(f"{followup_label}: forbidden_skill_reads must be a non-empty list")
                followup_forbidden = []
            for owner in followup_expected + followup_forbidden:
                if not isinstance(owner, str) or owner not in skill_names:
                    errors.append(f"{followup_label}: unknown skill read '{owner}'")
            followup_overlap = sorted(set(followup_expected) & set(followup_forbidden))
            if followup_overlap:
                errors.append(
                    f"{followup_label}: expected and forbidden skill reads overlap: {followup_overlap}"
                )
            followup_max = followup["max_commands"]
            if not isinstance(followup_max, int) or not 0 <= followup_max <= 50:
                errors.append(f"{followup_label}: max_commands must be an integer from 0 to 50")
                followup_max = 0
            followup_min = followup.get("min_commands", 0)
            if not isinstance(followup_min, int) or not 0 <= followup_min <= followup_max:
                errors.append(
                    f"{followup_label}: min_commands must be an integer from 0 to max_commands"
                )
            for field in (
                "expected_final_any",
                "expected_final_all",
                "forbidden_final_any",
                "forbidden_delegation_phrases",
            ):
                terms = followup.get(field, [])
                if not isinstance(terms, list) or not all(
                    isinstance(term, str) and term for term in terms
                ):
                    errors.append(f"{followup_label}: {field} must be a string list")
            followup_groups = followup.get("expected_final_groups", [])
            if not isinstance(followup_groups, list) or not all(
                isinstance(group, list)
                and group
                and all(isinstance(term, str) and term for term in group)
                for group in followup_groups
            ):
                errors.append(
                    f"{followup_label}: expected_final_groups must be a list of non-empty string lists"
                )
            for field in ("min_questions", "max_questions"):
                value = followup.get(field)
                if value is not None and (not isinstance(value, int) or not 0 <= value <= 10):
                    errors.append(f"{followup_label}: {field} must be an integer from 0 to 10")
            if followup.get("min_questions", 0) > followup.get("max_questions", 10):
                errors.append(f"{followup_label}: min_questions must not exceed max_questions")
            for field in (
                "require_recommendation",
                "require_wrong_decision_impact",
                "require_wait_for_calibration",
            ):
                value = followup.get(field)
                if value is not None and not isinstance(value, bool):
                    errors.append(f"{followup_label}: {field} must be boolean")
            followup_timeout = followup.get("timeout_seconds", timeout_seconds)
            if not isinstance(followup_timeout, int) or not 30 <= followup_timeout <= 600:
                errors.append(
                    f"{followup_label}: timeout_seconds must be an integer from 30 to 600"
                )

    if smoke_count != 1:
        errors.append(f"{label}: expected exactly one low-cost smoke case, found {smoke_count}")


def validate_capability_routing_cases(
    repo_root: Path,
    skill_names: set[str],
    errors: list[str],
) -> None:
    cases_path = repo_root / "tests" / "capability_routing_cases.json"
    if not cases_path.exists():
        errors.append("tests/capability_routing_cases.json: missing")
        return
    try:
        cases = json.loads(read_text(cases_path))
    except json.JSONDecodeError as exc:
        errors.append(f"tests/capability_routing_cases.json: invalid JSON: {exc}")
        return

    routing_text = read_text(
        repo_root / "skills" / "engineering" / "briefbound-router" / "references" / "capability-routing.md"
    )
    seen_ids: set[str] = set()
    for index, case in enumerate(cases if isinstance(cases, list) else []):
        label = f"tests/capability_routing_cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected an object")
            continue
        case_id = case.get("id", "")
        prompt = case.get("prompt", "")
        preferred = case.get("preferred", "")
        fallback = case.get("fallback", "")
        if not case_id or case_id in seen_ids:
            errors.append(f"{label}: id must be non-empty and unique")
        seen_ids.add(case_id)
        if not prompt or not contains_cjk(prompt):
            errors.append(f"{label}: prompt must be Chinese-first")
        if not preferred or f"`{preferred}`" not in routing_text:
            errors.append(f"{label}: preferred owner '{preferred}' missing from capability routing")
        if fallback not in skill_names:
            errors.append(f"{label}: fallback must be a packaged skill, found '{fallback}'")

    if not isinstance(cases, list) or len(cases) < 10:
        errors.append("tests/capability_routing_cases.json: expected at least ten capability cases")


def validate_conditional_merge_cases(repo_root: Path, errors: list[str]) -> None:
    cases_path = repo_root / "tests" / "conditional_merge_cases.json"
    if not cases_path.exists():
        errors.append("tests/conditional_merge_cases.json: missing")
        return
    try:
        cases = json.loads(read_text(cases_path))
    except json.JSONDecodeError as exc:
        errors.append(f"tests/conditional_merge_cases.json: invalid JSON: {exc}")
        return

    allowed = {
        "CHANGE_FAILURE",
        "BASELINE_FAILURE",
        "ENVIRONMENT_FAILURE",
        "POLICY_FAILURE",
        "UNKNOWN",
    }
    seen_ids: set[str] = set()
    has_positive = False
    has_negative = False
    for index, case in enumerate(cases if isinstance(cases, list) else []):
        label = f"tests/conditional_merge_cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: expected an object")
            continue
        required = {
            "id",
            "prompt",
            "classification",
            "conditional",
            "required_evidence",
            "forbidden_bypass",
        }
        if set(case) != required:
            errors.append(f"{label}: expected fields {sorted(required)}")
            continue
        case_id = case["id"]
        if not case_id or case_id in seen_ids:
            errors.append(f"{label}: id must be non-empty and unique")
        seen_ids.add(case_id)
        if not case["prompt"] or not contains_cjk(case["prompt"]):
            errors.append(f"{label}: prompt must be Chinese-first")
        if case["classification"] not in allowed:
            errors.append(f"{label}: unsupported classification '{case['classification']}'")
        if not isinstance(case["conditional"], bool):
            errors.append(f"{label}: conditional must be boolean")
        has_positive = has_positive or case["conditional"] is True
        has_negative = has_negative or case["conditional"] is False
        if not isinstance(case["required_evidence"], list) or not case["required_evidence"]:
            errors.append(f"{label}: required_evidence must be a non-empty list")
        if not isinstance(case["forbidden_bypass"], list):
            errors.append(f"{label}: forbidden_bypass must be a list")

    if not isinstance(cases, list) or len(cases) < 5 or not has_positive or not has_negative:
        errors.append("tests/conditional_merge_cases.json: expected at least five positive/negative cases")


def validate_feature_reuse_cases(repo_root: Path, errors: list[str]) -> None:
    cases_path = repo_root / "tests" / "feature_reuse_cases.json"
    if not cases_path.exists():
        errors.append("tests/feature_reuse_cases.json: missing")
        return
    try:
        cases = json.loads(read_text(cases_path))
    except json.JSONDecodeError as exc:
        errors.append(f"tests/feature_reuse_cases.json: invalid JSON: {exc}")
        return

    expected_fields = {"id", "prompt", "research", "signal", "route_after"}
    seen_ids: set[str] = set()
    has_positive = False
    has_negative = False
    for index, case in enumerate(cases if isinstance(cases, list) else []):
        label = f"tests/feature_reuse_cases.json[{index}]"
        if not isinstance(case, dict) or set(case) != expected_fields:
            errors.append(f"{label}: expected fields {sorted(expected_fields)}")
            continue
        if not case["id"] or case["id"] in seen_ids:
            errors.append(f"{label}: id must be non-empty and unique")
        seen_ids.add(case["id"])
        if not case["prompt"] or not contains_cjk(case["prompt"]):
            errors.append(f"{label}: prompt must be Chinese-first")
        if not isinstance(case["research"], bool):
            errors.append(f"{label}: research must be boolean")
        has_positive = has_positive or case["research"] is True
        has_negative = has_negative or case["research"] is False
        if not case["signal"] or case["route_after"] not in {
            "original-owner",
            "original-owner-or-planning",
        }:
            errors.append(f"{label}: invalid signal or route_after")
    if not isinstance(cases, list) or len(cases) < 6 or not has_positive or not has_negative:
        errors.append("tests/feature_reuse_cases.json: expected at least six positive/negative cases")


def validate_performance_routing_cases(repo_root: Path, errors: list[str]) -> None:
    path = repo_root / "tests" / "performance_routing_cases.json"
    label = "tests/performance_routing_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read valid JSON: {exc}")
        return

    required = {
        "id", "prompt", "expected_level", "expected_primary",
        "measurement_required", "user_gate",
    }
    levels = {"FAST", "CHECK", "PROFILE"}
    primaries = {"current-owner", "briefbound-performance-engineering", "briefbound-pr-review"}
    seen: set[str] = set()
    seen_levels: set[str] = set()
    has_performance_owner = False
    has_pr_support = False
    for index, case in enumerate(cases if isinstance(cases, list) else []):
        case_label = f"{label}[{index}]"
        if not isinstance(case, dict) or set(case) != required:
            errors.append(f"{case_label}: expected fields {sorted(required)}")
            continue
        if not case["id"] or case["id"] in seen:
            errors.append(f"{case_label}: id must be non-empty and unique")
        seen.add(case["id"])
        if not contains_cjk(case["prompt"]):
            errors.append(f"{case_label}: prompt must be Chinese-first")
        level = case["expected_level"]
        primary = case["expected_primary"]
        if level not in levels:
            errors.append(f"{case_label}: unsupported expected_level '{level}'")
        else:
            seen_levels.add(level)
        if primary not in primaries:
            errors.append(f"{case_label}: unsupported expected_primary '{primary}'")
        if level in {"FAST", "CHECK"} and primary != "current-owner":
            errors.append(f"{case_label}: FAST/CHECK must stay with current-owner")
        if level == "PROFILE" and primary not in {
            "briefbound-performance-engineering", "briefbound-pr-review"
        }:
            errors.append(f"{case_label}: PROFILE must use performance owner or PR review primary")
        if not isinstance(case["measurement_required"], bool):
            errors.append(f"{case_label}: measurement_required must be boolean")
        if level != "PROFILE" and case["measurement_required"] is not False:
            errors.append(f"{case_label}: FAST/CHECK must not require measurement")
        if level == "PROFILE" and case["measurement_required"] is not True:
            errors.append(f"{case_label}: PROFILE must require measurement evidence")
        if case["user_gate"] is not False:
            errors.append(f"{case_label}: efficiency routing must not add a user gate")
        has_performance_owner = has_performance_owner or primary == "briefbound-performance-engineering"
        has_pr_support = has_pr_support or primary == "briefbound-pr-review"

    if (
        not isinstance(cases, list)
        or len(cases) < 7
        or seen_levels != levels
        or not has_performance_owner
        or not has_pr_support
    ):
        errors.append(f"{label}: expected FAST/CHECK/PROFILE plus performance and PR routes")


def validate_peer_collaboration_cases(repo_root: Path, errors: list[str]) -> None:
    path = repo_root / "tests" / "peer_collaboration_cases.json"
    label = "tests/peer_collaboration_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read valid JSON: {exc}")
        return

    routes = {"NONE", "DISCOVER", "PEER_CONTEXT_REVIEW", "PEER_READ_ONLY", "PEER_DISJOINT_WRITE", "COORDINATE_OVERLAP"}
    seen_ids: set[str] = set()
    has_peer_collaboration = False
    has_none = False
    has_create_prompt = False
    for case in cases if isinstance(cases, list) else []:
        required = {
            "id", "prompt", "peer_state", "expected_route", "ask_create_thread",
            "claim_required", "owner_continues",
        }
        if not isinstance(case, dict) or set(case) != required:
            errors.append(f"{label}: every case must use exactly {sorted(required)}")
            continue
        if not case["id"] or case["id"] in seen_ids:
            errors.append(f"{label}: id must be non-empty and unique")
        seen_ids.add(case["id"])
        if not contains_cjk(case["prompt"]) or not contains_cjk(case["peer_state"]):
            errors.append(f"{label}: prompt and peer_state must be Chinese-first")
        if case["expected_route"] not in routes:
            errors.append(f"{label}: invalid expected_route '{case['expected_route']}'")
        for field in ["ask_create_thread", "claim_required", "owner_continues"]:
            if not isinstance(case[field], bool):
                errors.append(f"{label}: {field} must be boolean")
        if case["expected_route"].startswith("PEER_") and case["owner_continues"] is not True:
            errors.append(f"{label}: peer collaboration must preserve each agent's original task progress")
        has_peer_collaboration = has_peer_collaboration or case["expected_route"].startswith("PEER_")
        has_none = has_none or case["expected_route"] == "NONE"
        has_create_prompt = has_create_prompt or case["ask_create_thread"] is True
    if not isinstance(cases, list) or len(cases) < 6 or not (has_peer_collaboration and has_none and has_create_prompt):
        errors.append(f"{label}: expected at least six cases covering peer collaboration, no collaboration, and create-thread prompt")


def validate_autonomous_collaboration_cases(repo_root: Path, errors: list[str]) -> None:
    path = repo_root / "tests" / "autonomous_collaboration_cases.json"
    label = "tests/autonomous_collaboration_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read valid JSON: {exc}")
        return

    required = {
        "id", "situation", "expected_state", "ask_user", "owner_continues",
        "local_main_allowed", "remote_allowed",
    }
    states = {
        "ASK_ENABLE", "DISCOVER", "AGREEMENT", "RUNNING", "NEGOTIATING",
        "RECOVERY_PENDING_EVIDENCE", "MERGE_READY", "INTEGRATING", "INTEGRATED", "CLOSED",
    }
    seen: set[str] = set()
    seen_states: set[str] = set()
    for case in cases if isinstance(cases, list) else []:
        if not isinstance(case, dict) or set(case) != required:
            errors.append(f"{label}: every case must use exactly {sorted(required)}")
            continue
        if not case["id"] or case["id"] in seen:
            errors.append(f"{label}: id must be non-empty and unique")
        seen.add(case["id"])
        if not contains_cjk(case["situation"]):
            errors.append(f"{label}: situation must be Chinese-first")
        if case["expected_state"] not in states:
            errors.append(f"{label}: invalid expected_state '{case['expected_state']}'")
        seen_states.add(case["expected_state"])
        for field in ["ask_user", "owner_continues", "local_main_allowed", "remote_allowed"]:
            if not isinstance(case[field], bool):
                errors.append(f"{label}: {field} must be boolean")
        if case["expected_state"] == "ASK_ENABLE" and case["ask_user"] is not True:
            errors.append(f"{label}: initial enable gate must ask the user")
        if case["expected_state"] != "ASK_ENABLE" and "远程" not in case["situation"] and case["ask_user"] is not False:
            errors.append(f"{label}: normal autonomous states must not add repeated user gates")
        if case["remote_allowed"] and "已单独授权" not in case["situation"]:
            errors.append(f"{label}: remote action requires explicit separate authorization")

    required_states = {
        "ASK_ENABLE", "RUNNING", "NEGOTIATING", "RECOVERY_PENDING_EVIDENCE",
        "MERGE_READY", "INTEGRATING", "CLOSED",
    }
    if not isinstance(cases, list) or len(cases) < 10 or not required_states.issubset(seen_states):
        errors.append(f"{label}: expected at least ten cases covering enable, progress, conflict, integration, and closeout")


def validate_conflict_triage_cases(repo_root: Path, errors: list[str]) -> None:
    path = repo_root / "tests" / "conflict_triage_cases.json"
    label = "tests/conflict_triage_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read valid JSON: {exc}")
        return
    allowed = {"SELF_NARROWED", "CONTINUE_NON_CONFLICTING", "WAIT_SILENTLY", "DISCUSSION_REQUIRED", "PAUSE_REQUIRED", "REUSE_OPEN"}
    seen: set[str] = set()
    message_cases = 0
    silent_cases = 0
    for case in cases if isinstance(cases, list) else []:
        if not isinstance(case, dict) or set(case) != {"id", "situation", "expected", "send_message"}:
            errors.append(f"{label}: invalid case shape")
            continue
        if not case["id"] or case["id"] in seen:
            errors.append(f"{label}: id must be non-empty and unique")
        seen.add(case["id"])
        if not contains_cjk(case["situation"]) or case["expected"] not in allowed:
            errors.append(f"{label}: invalid situation or expected state")
        if not isinstance(case["send_message"], bool):
            errors.append(f"{label}: send_message must be boolean")
        message_cases += case["send_message"] is True
        silent_cases += case["send_message"] is False
    states = {case.get("expected") for case in cases if isinstance(case, dict)} if isinstance(cases, list) else set()
    if not isinstance(cases, list) or len(cases) < 7 or message_cases != 2 or silent_cases < 5:
        errors.append(f"{label}: expected discussion/pause message cases and at least five silent cases")
    if not {"DISCUSSION_REQUIRED", "PAUSE_REQUIRED"}.issubset(states):
        errors.append(f"{label}: must distinguish discussion from maximum-conflict pause")


def validate_peer_advice_message_cases(repo_root: Path, errors: list[str]) -> None:
    path = repo_root / "tests" / "peer_advice_message_cases.json"
    label = "tests/peer_advice_message_cases.json"
    try:
        cases = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read valid JSON: {exc}")
        return

    allowed_expected = {"SEND", "DISCUSS", "SILENT", "CLOSE"}
    allowed_types = {
        "", "ADVICE_AVAILABLE", "ADVICE_UPDATE", "CORRECTION",
        "STATUS_REQUEST", "DISCUSSION_REQUEST",
    }
    seen: set[str] = set()
    expected_states: set[str] = set()
    message_types: set[str] = set()
    silent_cases = 0
    for case in cases if isinstance(cases, list) else []:
        required = {"id", "situation", "prior_state", "expected", "message_type"}
        if not isinstance(case, dict) or set(case) != required:
            errors.append(f"{label}: every case must use exactly {sorted(required)}")
            continue
        if not case["id"] or case["id"] in seen:
            errors.append(f"{label}: id must be non-empty and unique")
        seen.add(case["id"])
        if not contains_cjk(case["situation"]) or not case["prior_state"]:
            errors.append(f"{label}: situation must be Chinese-first and prior_state non-empty")
        if case["expected"] not in allowed_expected or case["message_type"] not in allowed_types:
            errors.append(f"{label}: invalid expected action or message type")
        if case["expected"] in {"SILENT", "CLOSE"} and case["message_type"]:
            errors.append(f"{label}: silent/close cases cannot send a message")
        if case["expected"] in {"SEND", "DISCUSS"} and not case["message_type"]:
            errors.append(f"{label}: send/discuss cases require a message type")
        expected_states.add(case["expected"])
        if case["message_type"]:
            message_types.add(case["message_type"])
        silent_cases += case["expected"] == "SILENT"

    required_types = {
        "ADVICE_AVAILABLE", "ADVICE_UPDATE", "CORRECTION",
        "STATUS_REQUEST", "DISCUSSION_REQUEST",
    }
    if (
        not isinstance(cases, list)
        or len(cases) < 10
        or silent_cases < 4
        or not {"SEND", "DISCUSS", "SILENT", "CLOSE"}.issubset(expected_states)
        or not required_types.issubset(message_types)
    ):
        errors.append(f"{label}: expected dynamic value, aggregation, correction, discussion, silence, and close coverage")

def validate_skill(
    repo_root: Path,
    skill_dir: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    skill_md = skill_dir / "SKILL.md"
    text = read_text(skill_md)
    frontmatter = parse_frontmatter(skill_md)
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    license_id = frontmatter.get("license", "")
    label = str(skill_md.relative_to(repo_root))

    skill_line_count = len(text.splitlines())
    if skill_line_count > MAX_SKILL_LINES:
        errors.append(
            f"{label}: {skill_line_count} lines exceeds the {MAX_SKILL_LINES}-line progressive-disclosure limit"
        )

    extra_root_markdown = sorted(
        path.name for path in skill_dir.glob("*.md") if path.name != "SKILL.md"
    )
    if extra_root_markdown:
        errors.append(
            f"{skill_dir.relative_to(repo_root)}: move root documentation into references/: {extra_root_markdown}"
        )

    references_dir = skill_dir / "references"
    if references_dir.exists():
        for reference_path in sorted(references_dir.rglob("*.md")):
            reference_text = read_text(reference_path)
            reference_label = str(reference_path.relative_to(repo_root))
            if reference_text.startswith("---\n") or reference_text.startswith("---\r\n"):
                errors.append(f"{reference_label}: reference files must not duplicate SKILL.md frontmatter")
            reference_line_count = len(reference_text.splitlines())
            if (
                reference_line_count > REFERENCE_TOC_THRESHOLD_LINES
                and not REFERENCE_TOC_PATTERN.search(reference_text)
            ):
                errors.append(
                    f"{reference_label}: {reference_line_count} lines requires a top-level contents section"
                )

    if not name:
        errors.append(f"{label}: missing frontmatter name")
    elif name != skill_dir.name:
        errors.append(f"{label}: frontmatter name '{name}' does not match folder '{skill_dir.name}'")

    if not description:
        errors.append(f"{label}: missing frontmatter description")
    else:
        if not description.startswith("Use when"):
            errors.append(f"{label}: description must start with 'Use when'")
        if len(description) > 500:
            warnings.append(f"{label}: description is {len(description)} chars; consider shortening")

    if license_id != "MIT":
        errors.append(f"{label}: frontmatter license must be 'MIT'")

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not openai_yaml.exists():
        errors.append(f"{skill_dir.relative_to(repo_root)}: missing agents/openai.yaml")
    else:
        interface = parse_openai_interface(openai_yaml)
        metadata_label = str(openai_yaml.relative_to(repo_root))
        for field in ["display_name", "short_description", "default_prompt"]:
            value = interface.get(field, "")
            if not value:
                errors.append(f"{metadata_label}: missing interface field '{field}'")
            elif name.startswith("briefbound-") and not contains_cjk(value):
                errors.append(f"{metadata_label}: '{field}' must be Chinese-first")
        short_description = interface.get("short_description", "")
        if short_description and not (
            MIN_SHORT_DESCRIPTION_CHARS
            <= len(short_description)
            <= MAX_SHORT_DESCRIPTION_CHARS
        ):
            errors.append(
                f"{metadata_label}: short_description must be "
                f"{MIN_SHORT_DESCRIPTION_CHARS}-{MAX_SHORT_DESCRIPTION_CHARS} characters, "
                f"found {len(short_description)}"
            )
        prompt = interface.get("default_prompt", "")
        if name and f"${name}" not in prompt:
            errors.append(f"{metadata_label}: default_prompt must invoke '${name}'")

    if name.startswith("briefbound-") and name != "briefbound-router":
        if "## Briefbound task contract" not in text:
            errors.append(f"{label}: missing '## Briefbound task contract'")
        for field in BRIEFBOUND_CONTRACT_FIELDS:
            if field not in text:
                errors.append(f"{label}: missing Briefbound task contract field '{field}'")

        for marker in UNIFIED_CONTRACT_MARKERS:
            if marker not in text:
                errors.append(f"{label}: unified call contract missing marker '{marker}'")

        route_out_count = len(re.findall(r"(?m)^- Route Out:", text))
        if route_out_count != 1:
            errors.append(
                f"{label}: expected exactly one canonical Briefbound task contract Route Out, found {route_out_count}"
            )
        example_route_outs = re.findall(r"(?m)^Route Out:[^\r\n]*", text)
        if any(line.strip() not in {"Route Out:", "Route Out: <沿用 Briefbound task contract>"} for line in example_route_outs):
            errors.append(f"{label}: output examples must not redefine the canonical Route Out")
        if re.search(r"(?m)^默认路由：<(?!从 Briefbound task contract)[^>]+>", text):
            errors.append(f"{label}: default route examples must select from the Briefbound task contract")

        if name in DIRECT_WRITE_OWNERS:
            route_out = re.search(r"(?m)^- Route Out:.*$", text)
            if route_out is None or "briefbound-development-cleanup" not in route_out.group(0):
                errors.append(f"{label}: direct write owner must route verified residue to briefbound-development-cleanup")

        if re.search(r"(?m)^Route Out: .*暂停", text):
            errors.append(f"{label}: Route Out should use BLOCKED or a concrete owner, not generic pause")
        if re.search(r"(?m)^A\. ", text):
            warnings.append(f"{label}: top-level A/B/C option menu found; ensure it is behind a natural gate")

    if name == "briefbound-router":
        for marker in ROUTER_CORE_MARKERS:
            if marker not in text:
                errors.append(f"{label}: Router missing core marker '{marker}'")

    if name in UI_PREVIEW_REQUIRED_MARKERS:
        for marker in UI_PREVIEW_REQUIRED_MARKERS[name]:
            if marker not in text:
                errors.append(f"{label}: UI preview approval contract missing marker '{marker}'")

    if name == "briefbound-autonomous-collaboration-loop":
        for marker in [
            "询问一次明确列出项目、既有参与会话、integration target 和本地集成范围的授权",
            "不在每个阶段、task、普通冲突或恢复动作后询问是否继续",
            "Loop Owner",
            "Recovery Dispatcher",
            "send_message_to_thread",
            "不得保存 outbox",
            "`takeover`",
            "消息默认只发差量",
            "From/Task / Changed Fact / Action Impact / Evidence Pointer / Reply Needed",
            "不等待 stable main",
            "不反复 closeout",
            "全部预期交付合入本地 `main` 后只运行一次完整集成 gate",
            "可原子认领",
            "INTEGRATION_CLAIMED",
            "integration/<target-key>",
            "不得因无关漂移重跑整套门禁",
            "不能继承证据所有权",
            "MERGE_READY_RECOVERED",
            "RECOVERY_PENDING_EVIDENCE",
            "聊天中的采纳、计划、进度或草稿",
            "测试缓存不阻塞 `MERGE_READY`",
            "不更换多种命令追查",
            "resumePendingAgentIds",
            "MERGE_READY",
            "合入本地 `main`",
            "远程 push",
            "同一 blocker 经两轮不同恢复策略仍失败",
            "最后只做一次整体汇报",
            "BRT_DIRECT_USER_TURN_V1",
            "BRT_TRANSPORT_DISABLED",
            "BLOCKED_TRANSPORT",
            "WAITING_FOR_CLEAN_TARGET",
            "TRANSPORT_EXPIRED",
        ]:
            if marker not in text:
                errors.append(f"{label}: autonomous collaboration contract missing marker '{marker}'")

    if name == "briefbound-bdd-tdd-development":
        for marker in ["## 紧凑 TDD", "只有预期行为和 owning surface 已明确", "默认不派发子代理", "分数下降"]:
            if marker not in text:
                errors.append(f"{label}: compact TDD profile missing marker '{marker}'")

    if name == "briefbound-bug-review":
        for marker in ["不要求展示固定阶段", "根因状态", "只有 `CONFIRMED`", "Bug 修复不转交 TDD owner", "明显低效留给当前 owner"]:
            if marker not in text:
                errors.append(f"{label}: compact debugging owner missing marker '{marker}'")

    if name == "briefbound-ui-design":
        for marker in ["## 界面契约", "## 单 owner 贯穿", "响应式边界", "浏览器验证", "现有设计系统"]:
            if marker not in text:
                errors.append(f"{label}: UI owner missing marker '{marker}'")

    if name == "briefbound-ui-review":
        for marker in ["findings 优先", "## 审查面", "真实用户任务", "浏览器能力", "briefbound-frontend-engineering"]:
            if marker not in text:
                errors.append(f"{label}: UI review owner missing marker '{marker}'")

    if name == "briefbound-frontend-engineering":
        for marker in ["## 生产实现", "最终写入 owner 执行一次", "关键状态", "响应式", "真实浏览器", "briefbound-ui-design"]:
            if marker not in text:
                errors.append(f"{label}: frontend implementation owner missing marker '{marker}'")

    if name == "briefbound-performance-engineering":
        for marker in [
            "## 三档边界",
            "FAST / CHECK / PROFILE",
            "不加载本 skill、不建 benchmark",
            "不因“发现问题”切到 bug owner",
            "## 最小测量循环",
            "一个主要限制点",
            "只撤销本轮自己的优化",
            "目标达到即停止",
            "不默认生成性能报告",
        ]:
            if marker not in text:
                errors.append(f"{label}: lightweight performance contract missing marker '{marker}'")

    if name == "briefbound-code-structure-guard":
        for marker in [
            "## 三档结构闸门",
            "STAY",
            "CHECK",
            "SPLIT",
            "不能单独触发 `SPLIT`",
            "不扫描全仓排行榜",
            "没有降低耦合、认知负担或未来冲突",
            "不默认生成规划文档",
        ]:
            if marker not in text:
                errors.append(f"{label}: lightweight code-structure contract missing marker '{marker}'")

    if name == "briefbound-design-system":
        for marker in ["## 系统闸门", "## 事实源与契约", "## 渐进迁移", "代表性消费者", "Figma/code"]:
            if marker not in text:
                errors.append(f"{label}: design-system owner missing marker '{marker}'")

    if name == "briefbound-visual-design":
        for marker in ["## 语境判断", "## 单 owner 贯穿", "## 视觉契约", "产品类型", "一个有依据的推荐方向", "reduced-motion"]:
            if marker not in text:
                errors.append(f"{label}: visual-design owner missing marker '{marker}'")

    if name == "briefbound-score-loop":
        for marker in [
            "## 实验 owner 独占",
            "不是 TDD RED",
            "## Protocol Freeze",
            "## Search Policy",
            "EXPLOIT",
            "EXPLORE",
            "DIAGNOSE",
            "## ASK -> FILTER -> TELL",
            "smallestDecisiveEvaluation",
            "PRUNE",
            "默认不创建 worker",
        ]:
            if marker not in text:
                errors.append(f"{label}: experiment/TDD boundary missing marker '{marker}'")

    if name == "briefbound-huawei-nslb-score-loop":
        for marker in [
            "不得把 skill 内的旧分数、hash",
            "## Live-State Gate",
            "EXPLOIT",
            "EXPLORE",
            "DIAGNOSE",
            "代理测试",
            "旧 ledger、search graph、attempt cards 和 failed diffs 是可选事实源",
        ]:
            if marker not in text:
                errors.append(f"{label}: live adaptive NSLB contract missing marker '{marker}'")

    if name == "briefbound-creative-toolbox":
        for marker in [
            "## Method Router",
            "一次默认只用一个方法",
            "## Anti-Obvious Gate",
            "拒绝前 3 个显而易见",
            "真实失败方式",
            "用户选中后停止继续发散",
        ]:
            if marker not in text:
                errors.append(f"{label}: routed anti-obvious creative contract missing marker '{marker}'")

    if name == "briefbound-ai-research-loop":
        for marker in ["## Baseline Gate", "## 内层实验循环", "## 外层综合与转向", "briefbound-score-loop"]:
            if marker not in text:
                errors.append(f"{label}: AI research loop missing marker '{marker}'")

    if name == "briefbound-research-rigor-review":
        for marker in ["## 触发闸门", "## 审查方法", "ACCEPT", "QUALIFY", "REJECT", "BLOCKED"]:
            if marker not in text:
                errors.append(f"{label}: research rigor gate missing marker '{marker}'")

    if name == "briefbound-competition-research-lifecycle":
        for marker in ["全项目协调层", "不默认创建 3-6 lanes", "普通 candidate gate 不经过 Rigor Review"]:
            if marker not in text:
                errors.append(f"{label}: competition lifecycle ownership boundary missing marker '{marker}'")

    if name == "briefbound-thread-coordination":
        thread_contract_text = (
            text
            + "\n"
            + read_text(skill_dir / "references" / "proactive-collaboration.md")
            + "\n"
            + read_text(skill_dir / "references" / "integration-ownership.md")
        )
        for marker in [
            "CONFLICT_PAUSE_REQUEST",
            "`preflight`",
            "--write-kind development|mechanical|integration",
            "`ISOLATION_REQUIRED`",
            "`CLEAR/PEERS_NO_OVERLAP`",
            "`PAUSE_REQUEST` 不等于 `PAUSED`",
            "经 trusted relay 发送一次 `CONFLICT_RESOLVED`",
            "DISCUSSION_REQUEST",
            "MERGE_READY",
            "MERGE_READY_CONDITIONAL",
            "CHANGE_FAILURE / BASELINE_FAILURE / ENVIRONMENT_FAILURE / POLICY_FAILURE / UNKNOWN",
            "sync_project_memory.py --coordination-id",
            "send_message_to_thread",
            "read_thread",
            "首次 proposal 的目标必须 idle",
            "不重试催促",
            "Target Validity Gate",
            "ACK Gate",
            "ACK_OWNER / NOT_OWNER / DEFER_UNTIL",
            "无回复不等于接受",
            "Coordination Closeout Gate",
            "不得保留假 open、假 active 或重复集成队列",
            "resumePendingAgentIds",
            "`takeover`",
            "不把消息本身当作修复证据",
            "`heartbeat`",
            "## 受控跨任务投递（`BRT_TRUSTED_RELAY_V1`）",
            "permissionMode=receiver_existing_scope_only",
            "自动闭环仅在用户另行明确启用时",
            "各方继续各自非冲突工作",
            "双方保留各自 owner",
            "非 owner 停止自身冲突写入",
            "validate_thread_transport.py",
            "BRT_TRUSTED_RELAY_V1",
            "MISDELIVERED_DELEGATION",
            "迟到回复不能恢复旧 agreement",
            "Silent Conflict Triage",
            "DISCUSSION_REQUIRED",
            "PAUSE_REQUIRED",
            "合入排队或 gate 可能 stale 不属于 `PAUSE_REQUIRED`",
            "全部进入目标分支后只跑一次完整 gate",
            "WAIT_SILENTLY",
            "存在则复用，不重复发送",
            "讨论优先于暂停",
            "TRUSTED_RELAY_AUTHORIZED",
            "PEER_ACCEPT / PEER_ADAPT / PEER_DECLINE",
            "PEER_CONTEXT_REVIEW",
            "ACTIONABLE_FINDING",
            "CORRECTION",
            "动态消息价值闸门",
            "没有固定总数上限",
            "自然 checkpoint",
            "不定时轮询",
            "COLLABORATION_PROPOSAL",
            "不夺 owner、不强制采纳",
            "SELF_OWNED / PEER_OWNED / UNOWNED / UNKNOWN",
            "不得以“等待 main 清理”继续累积新的实现批次",
            "端口不同不等于数据隔离",
            "PROCESS_OWNER_QUERY",
            "MODEL_RUNTIME_RELEASED",
            "不刷新正式 Launcher",
        ]:
            if marker not in thread_contract_text:
                errors.append(f"{label}: thread coordination contract missing marker '{marker}'")

    if name == "briefbound-multi-agent-orchestration":
        orchestration_text = text + "\n" + read_text(skill_dir / "references" / "team-protocol.md")
        for marker in [
            "## 进入闸门",
            "## 平级协作循环",
            "PEER_COLLABORATION_READY",
            "COLLABORATION_PROPOSAL",
            "PEER_ACCEPT / PEER_ADAPT / PEER_DECLINE",
            "没有主从、派发或隐式任务转移",
            "registry claim 原子占用",
            "用信息价值降低熵",
            "MERGE_READY",
            "integration queue",
            "协同集成而非收编结果",
            "resumePendingAgentIds",
            "不得在未授权时 push",
            "集成验证",
            "一次建议、状态交换或单一冲突只用 `briefbound-thread-coordination`",
            "动态认领集成责任",
            "INTEGRATION_CLAIMED",
            "integration/<target-key>",
        ]:
            if marker not in orchestration_text:
                errors.append(f"{label}: multi-agent orchestration contract missing marker '{marker}'")
        for forbidden in [
            "TEAM_INVITE",
            "TEAM_READY",
            "成员加入 roster",
            "创建 subagent",
            "派发已授权工作",
        ]:
            if forbidden in orchestration_text:
                errors.append(f"{label}: peer collaboration must not restore hierarchical marker '{forbidden}'")

    compact_review_contracts = {
        "briefbound-evaluation": [
            "无需向用户输出“复用检查”",
            "没有 finding 不展示矩阵",
            "最多给 3 个建议",
            "评价 skill 本身不再复制执行流程",
        ],
        "briefbound-project-review": [
            "不逐项询问",
            "不默认生成项目地图、矩阵、ledger",
            "证据足以回答审查目标时停止",
        ],
        "briefbound-pr-review": [
            "findings 优先",
            "由本次变更引入、暴露或会阻塞集成",
            "READY_CONDITIONAL",
            "只做一次限时环境 probe",
            "不把每个 PR 变成性能审计",
            "COVERED / PARTIAL / UNVERIFIED / OUT_OF_SCOPE",
            "CODE / LOCAL_CHECKS / LOCAL_RUNTIME / PACKAGED / REMOTE",
            "FAST / CHECK / PROFILE",
            "OPEN / ADDRESSED / VERIFIED / DEFERRED",
        ],
    }
    for marker in compact_review_contracts.get(name, []):
        if marker not in text:
            errors.append(f"{label}: compact review contract missing marker '{marker}'")

    if name == "briefbound-project-memory":
        for marker in [
            "agent_coordination.py",
            "git-common-dir",
            "coordination registry",
            "--coordination-id",
            "并行 worker 不直接同步 tracked memory",
            "resumePendingAgentIds",
            "takeover",
            "cancel-resume",
            "--confirmed-by-user",
            "Memory 不接管执行循环",
        ]:
            if marker not in text:
                errors.append(f"{label}: live coordination/memory bridge missing marker '{marker}'")

    if name == "briefbound-goal-loop":
        for marker in ["用户明确要求持续/反复迭代", "Goal Loop 是控制策略，不是状态存储", "不在每轮询问是否继续"]:
            if marker not in text:
                errors.append(f"{label}: goal-loop ownership boundary missing marker '{marker}'")

    if name == "briefbound-development-cleanup":
        cleanup_contract_text = (
            text
            + "\n"
            + read_text(skill_dir / "references" / "local-resource-closeout.md")
        )
        for marker in [
            "静默清理检查",
            "不扫描全仓寻找可能的噪音",
            "DEFERRED_INTEGRATION",
            "Post-PR Closeout Gate",
            "PR_OPEN",
            "PR_MERGED",
            "PR_CLOSED_UNMERGED",
            "同一任务",
            "git clean -fdx",
            "git branch -d",
            "git worktree remove",
            "远程分支删除必须单独授权",
            "只停止能证明由本任务启动或依赖的精确进程树",
            "端口不同不等于数据隔离",
            "MODEL_RUNTIME_RELEASED",
        ]:
            if marker not in cleanup_contract_text:
                errors.append(f"{label}: development cleanup safety contract missing marker '{marker}'")

    route_regressions = {
        "briefbound-planning": {
            "required": ["默认 `DIRECT_IMPLEMENTATION`", "在当前方案内使用 `TASK_GRAPH`", "默认连续执行 Critical Path", "只有 Briefbound Router 判为 `PROFILE`"],
            "forbidden": ["briefbound-task-splitting", "默认路由到 `briefbound-completion-summary`"],
        },
        "briefbound-completion-summary": {
            "required": ["普通 FAST_PATH 和有界 COMPACT_FLOW", "不单独加载本 skill", "无持久状态需求时不生成 Ledger"],
            "forbidden": ["总结时必须读取并更新账本", "代码写入型工作尚未做清理检查时"],
        },
        "briefbound-development-cleanup": {
            "required": ["没有已知候选时直接收口", "禁止 force 删除 dirty worktree"],
            "forbidden": ["git clean -fdx --force", "git branch -D"],
        },
    }
    if name in route_regressions:
        contract = route_regressions[name]
        for marker in contract["required"]:
            if marker not in text:
                errors.append(f"{label}: low-noise route contract missing marker '{marker}'")
        for marker in contract["forbidden"]:
            if marker in text:
                errors.append(f"{label}: forced-stage regression marker found '{marker}'")

    estimated_tokens = estimated_instruction_tokens(text)
    budget = TOKEN_BUDGETS.get(name)
    if budget is not None and estimated_tokens > budget:
        warnings.append(
            f"{label}: about {estimated_tokens} instruction tokens exceeds the {budget} hot-route budget"
        )


def validate_catalog(repo_root: Path, skill_dirs: list[Path], errors: list[str]) -> None:
    skill_names = sorted(path.name for path in skill_dirs)
    skill_name_set = set(skill_names)
    expected_plugin_paths = sorted(rel_skill_path(repo_root, path) for path in skill_dirs)

    for skill_dir in skill_dirs:
        metadata_path = skill_dir / "agents" / "openai.yaml"
        if not metadata_path.exists():
            continue
        prompt = parse_openai_interface(metadata_path).get("default_prompt", "")
        referenced = set(re.findall(r"\$(briefbound-[a-z0-9-]+)", prompt))
        stale = sorted(referenced - skill_name_set)
        if stale:
            errors.append(
                f"{metadata_path.relative_to(repo_root)}: default_prompt references missing skills {stale}"
            )

        skill_text = read_text(skill_dir / "SKILL.md")
        referenced_in_skill = set(re.findall(r"`(briefbound-[a-z0-9-]+)`", skill_text))
        stale_in_skill = sorted(referenced_in_skill - skill_name_set)
        if stale_in_skill:
            errors.append(
                f"{(skill_dir / 'SKILL.md').relative_to(repo_root)}: references missing skills {stale_in_skill}"
            )

    plugin_path = repo_root / ".claude-plugin" / "plugin.json"
    if not plugin_path.exists():
        errors.append(".claude-plugin/plugin.json: missing")
    else:
        try:
            plugin_data = json.loads(read_text(plugin_path))
        except json.JSONDecodeError as exc:
            errors.append(f".claude-plugin/plugin.json: invalid JSON: {exc}")
        else:
            actual_paths = sorted(plugin_data.get("skills", []))
            if actual_paths != expected_plugin_paths:
                missing = sorted(set(expected_plugin_paths) - set(actual_paths))
                extra = sorted(set(actual_paths) - set(expected_plugin_paths))
                if missing:
                    errors.append(f".claude-plugin/plugin.json: missing skills {missing}")
                if extra:
                    errors.append(f".claude-plugin/plugin.json: extra skills {extra}")

    for readme_name in ["README.md", "README.zh-CN.md", "README.en.md"]:
        readme_path = repo_root / readme_name
        if not readme_path.exists():
            errors.append(f"{readme_name}: missing")
            continue
        readme_text = read_text(readme_path)
        missing_names = [name for name in skill_names if name not in readme_text]
        if missing_names:
            errors.append(f"{readme_name}: missing skill names {missing_names}")

    router_root = repo_root / "skills" / "engineering" / "briefbound-router"
    router_text = "\n".join(read_text(path) for path in sorted(router_root.rglob("*.md")))
    missing_routes = [name for name in skill_names if name != "briefbound-router" and name not in router_text]
    if missing_routes:
        errors.append(f"briefbound-router: missing package owner routes {missing_routes}")

    for reference_name, budget in ROUTER_REFERENCE_BUDGETS.items():
        reference_path = router_root / "references" / reference_name
        if not reference_path.exists():
            errors.append(f"briefbound-router/references/{reference_name}: missing")
            continue
        estimated = estimated_instruction_tokens(read_text(reference_path))
        if estimated > budget:
            errors.append(
                f"briefbound-router/references/{reference_name}: about {estimated} tokens exceeds {budget}"
            )
        for marker in ROUTER_REFERENCE_REQUIRED_MARKERS.get(reference_name, []):
            if marker not in read_text(reference_path):
                errors.append(
                    f"briefbound-router/references/{reference_name}: missing route regression marker '{marker}'"
                )

    for profile_name, (relative_paths, budget) in ROUTER_PROFILE_BUDGETS.items():
        estimated = 0
        missing_profile_files = []
        for relative_path in relative_paths:
            profile_path = router_root / relative_path
            if not profile_path.exists():
                missing_profile_files.append(relative_path)
                continue
            estimated += estimated_instruction_tokens(read_text(profile_path))
        if missing_profile_files:
            errors.append(f"briefbound-router profile {profile_name}: missing {missing_profile_files}")
        elif estimated > budget:
            errors.append(f"briefbound-router profile {profile_name}: about {estimated} tokens exceeds {budget}")

    hot_route_text = read_text(router_root / "references" / "routing-practice.md")
    leaked_candidates = sorted(
        candidate for candidate in HOT_ROUTE_EXTERNAL_CANDIDATES if f"`{candidate}`" in hot_route_text
    )
    if leaked_candidates:
        errors.append(
            "briefbound-router routing-practice: external install candidates belong in "
            f"github-skill-candidates.md, found {leaked_candidates}"
        )

    huawei_root = repo_root / "skills" / "competition" / "briefbound-huawei-nslb-score-loop"
    for markdown_path in sorted(huawei_root.rglob("*.md")):
        if re.search(r"(?i)[A-Z]:\\Users\\", read_text(markdown_path)):
            errors.append(
                f"{markdown_path.relative_to(repo_root)}: project adapter must not hard-code a user profile path"
            )

    validate_briefbound_route_references(repo_root, set(skill_names), errors)
    validate_package_routing_cases(repo_root, set(skill_names), errors)
    validate_ui_routing_cases(repo_root, set(skill_names), errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Briefbound skill package routing and catalog conventions.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Return nonzero when warnings are found.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    skill_dirs = discover_skill_dirs(repo_root)
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_dirs:
        errors.append("No skills found under skills/")

    for skill_dir in skill_dirs:
        validate_skill(repo_root, skill_dir, errors, warnings)
    validate_catalog(repo_root, skill_dirs, errors)
    validate_capability_routing_cases(repo_root, set(path.name for path in skill_dirs), errors)
    validate_live_routing_cases(repo_root, set(path.name for path in skill_dirs), errors)
    validate_conditional_merge_cases(repo_root, errors)
    validate_feature_reuse_cases(repo_root, errors)
    validate_performance_routing_cases(repo_root, errors)
    validate_peer_collaboration_cases(repo_root, errors)
    validate_autonomous_collaboration_cases(repo_root, errors)
    validate_conflict_triage_cases(repo_root, errors)
    validate_peer_advice_message_cases(repo_root, errors)

    if errors:
        print("Briefbound skill package validation failed:")
        for error in errors:
            print(f"  ERROR: {error}")
    if warnings:
        print("Briefbound skill package validation warnings:")
        for warning in warnings:
            print(f"  WARN: {warning}")

    if errors or (warnings and args.warnings_as_errors):
        return 1

    print(f"Briefbound skill package validation passed: {len(skill_dirs)} skills checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
