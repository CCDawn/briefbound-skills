import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SUPERPOWERS_ENTRYPOINTS = (
    "using-superpowers",
    "using-skills-community",
    "brainstorming",
    "test-driven-development",
    "using-git-worktrees",
    "writing-plans",
    "subagent-driven-development",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "systematic-debugging",
    "verification-before-completion",
    "writing-skills",
)
DISABLED_SKILL_FILENAME = "SKILL.md.briefbound-disabled"
LEGACY_DISABLED_SKILL_FILENAME = "SKILL.md.ccdawn-disabled"
ROUTER_SKILL_NAME = "briefbound-router"
LEGACY_SPECIAL_SKILL_NAMES = {
    "briefbound-router": "ccdawn-brt",
    "briefbound-project-memory": "ccdawn-dawn-agent-html-memory",
}
ROUTER_ACTIVATION_START = "<!-- Briefbound Router activation: start -->"
ROUTER_ACTIVATION_END = "<!-- Briefbound Router activation: end -->"
LEGACY_ROUTER_ACTIVATION_START = "<!-- CCDawn BRT activation: start -->"
LEGACY_ROUTER_ACTIVATION_END = "<!-- CCDawn BRT activation: end -->"
ROUTER_ACTIVATION_BLOCK = f"""{ROUTER_ACTIVATION_START}
## Briefbound Router Entry Rules

- Intent gate: a clear goal plus an execution verb (fix/add/change/remove/tune) is permission to act. When the goal, write surface, and acceptance are clear or safely recoverable, proceed directly without asking for extra confirmation.
- Grade uncertainty instead of stopping by default: for low- or medium-risk unknowns, state the assumption and continue. Only a high-impact fork (behavior-changing product decision, irreversible or user-facing change, security, or data loss) gets one compact recommendation-and-alignment turn, then wait for calibration.
- Ask only questions whose answers change the approach, batched into one round. Zero questions is legitimate when intent and scope are already clear; never re-ask what task or project memory already answered.
- Delegation: Briefbound itself creates no subagents. If the runtime provides delegation tools, dispatch independent, parallelizable work directly without asking; keep trivial or single-owner work with the current agent, never block work on a delegation decision, and never invent tool names.
- For cross-skill routing, load `briefbound-router` and follow its gates.
- Support substantive reports or explanations with a diagram from `briefbound-diagram-design` when it materially improves comprehension; short status replies stay text-only.
- User-visible output is Chinese-first and follows `briefbound-plain-talk` by default: lead with the answer in plain language, no code dumps in replies (cite `file:line` instead), and no internal routing ledgers or unexplained enums.
{ROUTER_ACTIVATION_END}"""


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))


def read_skill_name(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"{skill_md} is missing YAML frontmatter.")

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")

    raise SystemExit(f"{skill_md} is missing a frontmatter name field.")


def discover_skills(repo_root: Path) -> list[Path]:
    skills = []
    skill_root = repo_root / "skills"
    for path in skill_root.rglob("SKILL.md"):
        skill_dir = path.parent
        skill_name = read_skill_name(skill_dir)
        if skill_name != skill_dir.name:
            raise SystemExit(
                f"Skill folder name '{skill_dir.name}' must match frontmatter name '{skill_name}' in {path}."
            )
        skills.append(skill_dir)
    return sorted(skills, key=lambda path: path.name)


def destination_roots(home: Path, agent: str) -> list[Path]:
    roots = []
    if agent in {"claude", "all"}:
        roots.append(home / ".claude" / "skills")
    if agent in {"codex", "codex-agents", "codex-grok", "all"}:
        roots.append(home / ".codex" / "skills")
    if agent in {"agents", "codex-agents", "all"}:
        roots.append(home / ".agents" / "skills")
    if agent in {"grok", "codex-grok", "all"}:
        roots.append(home / ".grok" / "skills")
    return roots


def codex_skills_root(home: Path) -> Path:
    return home / ".codex" / "skills"


def codex_agents_path(home: Path) -> Path:
    return home / ".codex" / "AGENTS.md"


def grok_skills_root(home: Path) -> Path:
    return home / ".grok" / "skills"


def grok_agents_path(home: Path) -> Path:
    return home / ".grok" / "AGENTS.md"


def targets_codex(home: Path, roots: list[Path]) -> bool:
    return codex_skills_root(home) in roots


def targets_grok(home: Path, roots: list[Path]) -> bool:
    return grok_skills_root(home) in roots


def _activation_marker_state(text: str, start_marker: str, end_marker: str) -> str:
    starts = text.count(start_marker)
    ends = text.count(end_marker)
    if starts == 0 and ends == 0:
        return "absent"
    if starts == 1 and ends == 1 and text.index(start_marker) < text.index(end_marker):
        return "active"
    return "conflict"


def router_activation_state(path: Path) -> str:
    if not path.exists():
        return "absent"
    text = path.read_text(encoding="utf-8")
    current = _activation_marker_state(text, ROUTER_ACTIVATION_START, ROUTER_ACTIVATION_END)
    legacy = _activation_marker_state(
        text,
        LEGACY_ROUTER_ACTIVATION_START,
        LEGACY_ROUTER_ACTIVATION_END,
    )
    if "conflict" in {current, legacy} or current == legacy == "active":
        return "conflict"
    if current == "active":
        return "active"
    if legacy == "active":
        return "legacy"
    return "absent"


def _read_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_preserving_newlines(path: Path, text: str, newline: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline))


def _activation_markers_for_state(state: str) -> tuple[str, str]:
    if state == "legacy":
        return LEGACY_ROUTER_ACTIVATION_START, LEGACY_ROUTER_ACTIVATION_END
    return ROUTER_ACTIVATION_START, ROUTER_ACTIVATION_END


def install_router_activation(path: Path) -> bool:
    state = router_activation_state(path)
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed Briefbound Router activation markers in {path}.")

    original = _read_preserving_newlines(path) if path.exists() else ""
    newline = "\r\n" if "\r\n" in original else "\n"
    normalized = original.replace("\r\n", "\n")
    if state in {"active", "legacy"}:
        start_marker, end_marker = _activation_markers_for_state(state)
        pattern = re.compile(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        updated = pattern.sub(ROUTER_ACTIVATION_BLOCK, normalized, count=1)
    else:
        updated = (
            f"{normalized}\n\n{ROUTER_ACTIVATION_BLOCK}\n"
            if normalized
            else f"{ROUTER_ACTIVATION_BLOCK}\n"
        )

    if updated == normalized:
        return False
    _write_preserving_newlines(path, updated, newline)
    return True


def remove_router_activation(path: Path) -> bool:
    state = router_activation_state(path)
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed Briefbound Router activation markers in {path}.")
    if state == "absent":
        return False

    original = _read_preserving_newlines(path)
    newline = "\r\n" if "\r\n" in original else "\n"
    normalized = original.replace("\r\n", "\n")
    start_marker, end_marker = _activation_markers_for_state(state)
    start = normalized.index(start_marker)
    end = normalized.index(end_marker, start) + len(end_marker)
    prefix_start = start - 2 if start >= 2 and normalized[start - 2 : start] == "\n\n" else start
    suffix_end = end + 1 if normalized[end : end + 1] == "\n" else end
    updated = normalized[:prefix_start] + normalized[suffix_end:]
    _write_preserving_newlines(path, updated, newline)
    return True


def manage_router_activation_path(
    path: Path,
    surface: str,
    action: str,
    dry_run: bool = False,
) -> None:
    if action == "ignore":
        return

    state = router_activation_state(path)
    if action == "warn":
        print(f"Briefbound Router {surface} activation: {state} ({path})")
        return
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed Briefbound Router activation markers in {path}.")

    if dry_run:
        verb = "install/update" if action == "install" else "remove"
        print(f"Planned Briefbound Router {surface} activation: {verb} ({path}, current={state})")
        return

    changed = install_router_activation(path) if action == "install" else remove_router_activation(path)
    result = "installed" if action == "install" else "removed"
    if not changed:
        result = "already active" if action == "install" else "already absent"
    print(f"Briefbound Router {surface} activation: {result} ({path})")


def manage_router_activation(home: Path, action: str, dry_run: bool = False) -> None:
    manage_router_activation_path(codex_agents_path(home), "Codex", action, dry_run)


def manage_selected_router_activations(
    home: Path,
    roots: list[Path],
    action: str,
    dry_run: bool = False,
) -> None:
    if targets_codex(home, roots):
        manage_router_activation_path(codex_agents_path(home), "Codex", action, dry_run)
    if targets_grok(home, roots):
        manage_router_activation_path(grok_agents_path(home), "Grok", action, dry_run)


def process_skill_conflict_state(home: Path) -> list[tuple[str, str]]:
    root = codex_skills_root(home)
    states = []
    for name in SUPERPOWERS_ENTRYPOINTS:
        skill_dir = root / name
        active = (skill_dir / "SKILL.md").exists()
        disabled = (skill_dir / DISABLED_SKILL_FILENAME).exists()
        legacy_disabled = (skill_dir / LEGACY_DISABLED_SKILL_FILENAME).exists()
        present = sum((active, disabled, legacy_disabled))
        if present > 1:
            state = "conflict"
        elif active:
            state = "active"
        elif disabled:
            state = "disabled"
        elif legacy_disabled:
            state = "legacy-disabled"
        else:
            state = "absent"
        states.append((name, state))
    return states


def manage_process_skill_conflicts(home: Path, action: str, dry_run: bool = False) -> None:
    if action == "ignore":
        return

    root = codex_skills_root(home)
    changed = []
    blocked = []
    for name, state in process_skill_conflict_state(home):
        skill_dir = root / name
        active_path = skill_dir / "SKILL.md"
        disabled_path = skill_dir / DISABLED_SKILL_FILENAME
        legacy_disabled_path = skill_dir / LEGACY_DISABLED_SKILL_FILENAME

        if action == "warn":
            if state == "active":
                changed.append((name, "active"))
            elif state == "conflict":
                blocked.append((name, "multiple active or disabled entrypoints exist"))
            continue

        if state == "conflict":
            blocked.append((name, "multiple active or disabled entrypoints exist"))
            continue

        if action == "disable" and state == "active":
            changed.append((name, "would disable" if dry_run else "disabled"))
            if not dry_run:
                active_path.rename(disabled_path)
        elif action == "disable" and state == "legacy-disabled":
            changed.append((name, "would migrate disabled marker" if dry_run else "migrated disabled marker"))
            if not dry_run:
                legacy_disabled_path.rename(disabled_path)
        elif action == "restore" and state in {"disabled", "legacy-disabled"}:
            changed.append((name, "would restore" if dry_run else "restored"))
            if not dry_run:
                source = disabled_path if state == "disabled" else legacy_disabled_path
                source.rename(active_path)

    if action == "warn" and changed:
        print("Warning: Superpowers entrypoints can bypass Briefbound Router and add unnecessary workflow context:")
        for name, _ in changed:
            print(f"  {root / name / 'SKILL.md'}")
        print("To disable only their auto-discovery entrypoints, rerun with --process-skill-conflicts disable.")
    elif changed:
        verb = "Planned process skill conflict changes" if dry_run else "Process skill conflict changes"
        print(f"{verb}:")
        for name, state in changed:
            print(f"  {name}: {state}")

    if blocked:
        print("Process skill conflict entries requiring manual inspection:")
        for name, reason in blocked:
            print(f"  {root / name}: {reason}")


def codex_validator_path(home: Path) -> Path:
    return codex_skills_root(home) / ".system" / "skill-creator" / "scripts" / "quick_validate.py"


def validate_installed_codex_skills(home: Path, installed_skills: list[Path]) -> list[Path]:
    validator = codex_validator_path(home)
    if not validator.exists():
        return []

    validation_env = os.environ.copy()
    validation_env["PYTHONUTF8"] = "1"
    validation_env["PYTHONIOENCODING"] = "utf-8"
    validated = []
    for skill_path in installed_skills:
        subprocess.run(
            [sys.executable, str(validator), str(skill_path)],
            check=True,
            env=validation_env,
        )
        validated.append(skill_path)
    return validated


def validate_briefbound_package(repo_root: Path) -> None:
    validator = repo_root / "scripts" / "validate_briefbound_skills.py"
    if validator.exists():
        subprocess.run([sys.executable, str(validator), "--repo-root", str(repo_root)], check=True)


def verify_installed_skill_copies(roots: list[Path], skill_names: list[str]) -> list[Path]:
    installed = [root / name for root in roots for name in skill_names]
    missing = [path for path in installed if not (path / "SKILL.md").exists()]
    if missing:
        print("Missing installed skill(s):")
        for path in missing:
            print(f"  {path}")
        return []
    for path in installed:
        if read_skill_name(path) != path.name:
            raise SystemExit(f"Installed skill name mismatch: {path}")
    return installed


def print_available_skills(available_skills: list[Path]) -> None:
    print("Available skills:")
    for skill_path in available_skills:
        print(f"  {skill_path.name}")


def print_install_plan(home: Path, roots: list[Path], skill_names: list[str]) -> None:
    print("Install plan:")
    print(f"  Home: {home}")
    print("  Targets:")
    for root in roots:
        print(f"    {root}")
    print("  Skills:")
    for name in skill_names:
        print(f"    {name}")
    if targets_codex(home, roots):
        validator = codex_validator_path(home)
        print(f"  Codex validator: {validator if validator.exists() else 'not found'}")


def warn_duplicate_agents_copy(home: Path, selected_skill_names: set[str], roots: list[Path]) -> None:
    codex_root = codex_skills_root(home)
    agents_root = home / ".agents" / "skills"
    if codex_root not in roots or agents_root in roots or not agents_root.exists():
        return

    duplicates = sorted(name for name in selected_skill_names if (agents_root / name).exists())
    if duplicates:
        print("Warning: matching .agents skill copies already exist and may create duplicate slash-command entries:")
        for name in duplicates:
            print(f"  {agents_root / name}")


def warn_grok_compat_copies(home: Path, selected_skill_names: set[str], roots: list[Path]) -> None:
    if not targets_grok(home, roots):
        return
    claude_root = home / ".claude" / "skills"
    duplicates = sorted(name for name in selected_skill_names if (claude_root / name / "SKILL.md").exists())
    if not duplicates:
        return
    print("Note: Grok also discovers these Claude-compatible copies; native ~/.grok/skills copies are installed:")
    for name in duplicates:
        print(f"  {claude_root / name}")


def legacy_skill_name(skill_name: str) -> str:
    if skill_name in LEGACY_SPECIAL_SKILL_NAMES:
        return LEGACY_SPECIAL_SKILL_NAMES[skill_name]
    prefix = "briefbound-"
    if not skill_name.startswith(prefix):
        raise SystemExit(f"Cannot derive a legacy skill name for {skill_name}.")
    return f"ccdawn-{skill_name.removeprefix(prefix)}"


def _legacy_path_kind(path: Path) -> str:
    is_junction = getattr(path, "is_junction", lambda: False)()
    if is_junction:
        return "junction"
    if path.is_symlink():
        return "symlink"
    return "directory"


def inspect_legacy_skill_copies(
    roots: list[Path],
    skill_names: list[str],
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    removable = []
    blocked = []
    for root in roots:
        for skill_name in skill_names:
            expected_legacy_name = legacy_skill_name(skill_name)
            legacy_path = root / expected_legacy_name
            path_kind = _legacy_path_kind(legacy_path)
            if not legacy_path.exists() and path_kind == "directory":
                continue
            if path_kind in {"junction", "symlink"}:
                expected_target = (root / skill_name).resolve()
                try:
                    actual_target = legacy_path.resolve(strict=True)
                    actual_name = read_skill_name(expected_target)
                except (OSError, UnicodeError, SystemExit) as exc:
                    blocked.append((legacy_path, f"cannot verify link target: {exc}"))
                    continue
                if actual_target != expected_target or actual_name != skill_name:
                    blocked.append(
                        (legacy_path, f"link target is {actual_target}, expected verified {expected_target}")
                    )
                    continue
                removable.append((legacy_path, path_kind))
                continue
            try:
                actual_name = read_skill_name(legacy_path)
            except (OSError, UnicodeError, SystemExit) as exc:
                blocked.append((legacy_path, f"cannot verify ownership: {exc}"))
                continue
            if actual_name != expected_legacy_name:
                blocked.append(
                    (legacy_path, f"frontmatter name is {actual_name!r}, expected {expected_legacy_name!r}")
                )
                continue
            removable.append((legacy_path, path_kind))
    return removable, blocked


def manage_legacy_skill_copies(
    roots: list[Path],
    skill_names: list[str],
    *,
    remove: bool = False,
    dry_run: bool = False,
) -> None:
    removable, blocked = inspect_legacy_skill_copies(roots, skill_names)
    if removable:
        if remove and not dry_run:
            print("Removed verified legacy skill copies:")
            for path, path_kind in removable:
                if path_kind == "junction":
                    path.rmdir()
                elif path_kind == "symlink":
                    path.unlink()
                else:
                    shutil.rmtree(path)
                print(f"  {path}")
        else:
            label = "Legacy skill copies planned for removal" if dry_run else "Legacy skill copies still installed"
            print(f"{label}:")
            for path, _ in removable:
                print(f"  {path}")
    if blocked:
        print("Legacy-named directories requiring manual inspection (not removed):")
        for path, reason in blocked:
            print(f"  {path}: {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install this local skill library into Codex, Grok, optional .agents, and Claude skill directories."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available skills and exit without installing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the install plan without copying files.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate currently installed skills for the selected agent without copying files.",
    )
    parser.add_argument(
        "--skip-package-validate",
        action="store_true",
        help="Skip Briefbound package convention validation before install or dry run.",
    )
    parser.add_argument(
        "--home",
        default=str(Path.home()),
        help="Home directory containing .claude, .codex, .grok, and optional .agents (default: current user home).",
    )
    parser.add_argument(
        "--agent",
        choices=["claude", "codex", "grok", "agents", "codex-agents", "codex-grok", "all"],
        default="codex",
        help=(
            "Which local skill directories to populate (default: codex). "
            "Use grok for ~/.grok/skills, codex-grok for both runtimes, or codex-agents only when both Codex catalogs are required."
        ),
    )
    parser.add_argument(
        "--skill",
        dest="skills",
        action="append",
        help="Install only the named skill. Repeat for multiple skills. Defaults to all skills in the repository.",
    )
    parser.add_argument(
        "--process-skill-conflicts",
        choices=["warn", "disable", "restore", "ignore"],
        default="warn",
        help=(
            "Manage local Superpowers entrypoints that can bypass Briefbound Router. "
            "disable/restore renames only SKILL.md, preserving the original directory and content (default: warn)."
        ),
    )
    parser.add_argument(
        "--router-activation",
        choices=["warn", "install", "remove", "ignore"],
        default="warn",
        help=(
            "Manage reversible Briefbound Router blocks in selected Codex/Grok AGENTS.md files. "
            "The Python installer defaults to warn; install.ps1/install.sh default to install."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    home = Path(args.home).expanduser().resolve()

    available_skills = discover_skills(repo_root)
    if args.list:
        print_available_skills(available_skills)
        return 0

    available_skill_names = {path.name for path in available_skills}
    selected_skill_names = set(args.skills or sorted(available_skill_names))
    unknown = sorted(selected_skill_names - available_skill_names)
    if unknown:
        known = ", ".join(sorted(available_skill_names))
        raise SystemExit(f"Unknown skill(s): {', '.join(unknown)}\nKnown skills: {known}")

    selected_skill_names_list = sorted(selected_skill_names)

    if not args.skip_package_validate:
        validate_briefbound_package(repo_root)

    roots = destination_roots(home, args.agent)
    if args.dry_run:
        print_install_plan(home, roots, selected_skill_names_list)
        manage_legacy_skill_copies(roots, selected_skill_names_list, remove=True, dry_run=True)
        if targets_codex(home, roots):
            manage_process_skill_conflicts(home, args.process_skill_conflicts, dry_run=True)
        if args.router_activation != "install" or ROUTER_SKILL_NAME in selected_skill_names:
            manage_selected_router_activations(home, roots, args.router_activation, dry_run=True)
        elif targets_codex(home, roots) or targets_grok(home, roots):
            print(f"Skipped Briefbound Router activation plan because {ROUTER_SKILL_NAME} is not selected.")
        print("Dry run only; no files changed.")
        return 0

    if args.verify_only:
        installed_skills = verify_installed_skill_copies(roots, selected_skill_names_list)
        if not installed_skills:
            return 1
        print("Verified installed skills:")
        for path in installed_skills:
            print(f"  {path}")
        manage_legacy_skill_copies(roots, selected_skill_names_list)
        if targets_codex(home, roots):
            validator = codex_validator_path(home)
            if not validator.exists():
                print(f"Codex validator not found: {validator}")
                return 1
            installed_codex_skills = [codex_skills_root(home) / name for name in selected_skill_names_list]
            validated_codex_skills = validate_installed_codex_skills(home, installed_codex_skills)
            print(f"Validated live Codex skills: {len(validated_codex_skills)}")
            manage_process_skill_conflicts(home, "warn")
        manage_selected_router_activations(home, roots, "warn")
        return 0

    installed_skills = []
    installed_codex_skills = []
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        for skill_path in available_skills:
            if skill_path.name not in selected_skill_names:
                continue
            destination = root / skill_path.name
            copy_tree(skill_path, destination)
            installed_skills.append(destination)
            if root == home / ".codex" / "skills":
                installed_codex_skills.append(destination)

    validated_codex_skills = validate_installed_codex_skills(home, installed_codex_skills)
    verified_installed_skills = verify_installed_skill_copies(roots, selected_skill_names_list)
    if not verified_installed_skills:
        raise SystemExit("Installed skill verification failed; legacy copies were not removed.")
    manage_legacy_skill_copies(roots, selected_skill_names_list, remove=True)
    if targets_codex(home, roots):
        manage_process_skill_conflicts(home, args.process_skill_conflicts)
    if args.router_activation != "install" or ROUTER_SKILL_NAME in selected_skill_names:
        manage_selected_router_activations(home, roots, args.router_activation)
    elif targets_codex(home, roots) or targets_grok(home, roots):
        print(f"Skipped Briefbound Router activation because {ROUTER_SKILL_NAME} was not installed.")

    print(f"Repository: {repo_root}")
    print(f"Home: {home}")
    print("Installed skills:")
    for path in installed_skills:
        print(f"  {path}")
    if validated_codex_skills:
        print("Validated live Codex skills:")
        for path in validated_codex_skills:
            print(f"  {path}")
    elif installed_codex_skills:
        print("Codex validator not found; skipped live validation.")
    warn_duplicate_agents_copy(home, selected_skill_names, roots)
    warn_grok_compat_copies(home, selected_skill_names, roots)
    print("Restart the client so it reloads the updated local skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
