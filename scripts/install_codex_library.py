import argparse
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
DISABLED_SKILL_FILENAME = "SKILL.md.ccdawn-disabled"
BRT_ACTIVATION_START = "<!-- CCDawn BRT activation: start -->"
BRT_ACTIVATION_END = "<!-- CCDawn BRT activation: end -->"
BRT_ACTIVATION_BLOCK = f"""{BRT_ACTIVATION_START}
## CCDawn BRT Default Routing

- Apply this lightweight BRT gate before the first tool call or downstream skill choice on every user message; users do not need to invoke `/brt`.
- Before development or planning, check `Desired Result / Owning Surface / Acceptance Evidence / Highest-impact Fork`. For `MISSING_CONTEXT`, first use one narrow read-only probe and never ask the user for locally discoverable context. For an unresolved `PRODUCT_FORK` whose outcomes materially differ, load `ccdawn-brt` and answer with explicit `Current Understanding / Evidence / Recommendation / Behavioral Difference / Wrong-decision Impact / Wait for Calibration` fields; end by inviting `按推荐` or a correction. Otherwise proceed with the minimum sufficient workflow.
- If the user states uncertainty, presents materially different alternatives, or uses a broad goal whose plausible meanings change the owning surface, MUST NOT start a broad repository scan or select a downstream owner. Load `ccdawn-brt`, then give one compact alignment turn containing the current understanding, a recommended path, and grouped high-impact questions. Wait for calibration unless one narrow read-only probe can resolve the choice.
- Treat `continue`, `确认`, or `按推荐` as direct continuation only after a `Continuation Health Check` confirms the prior contract is complete and still valid. A missing result/surface/evidence, a new phase, or a new user-visible fork requires a narrow probe or compact alignment, not blind inheritance.
- During execution, if new evidence invalidates the aligned approach or would change user-visible behavior, edit scope, data/API, compatibility, security, or acceptance, stop affected writes, perform only safe diagnosis, and discuss the evidence, impact, and recommended path with the user. Recover safely and report without pausing when the issue stays within the existing contract; never expand scope or force through a contract-changing surprise.
- Select the most specific useful owner after alignment. Preserve existing execution permission across routing and do not stop after each task or stage without a natural gate.
- Before the first write, scope expansion, or merge, run the project coordination `preflight` with `development`, `mechanical`, or `integration` intent when that command is available. Planning artifacts are development writes. Ordinary development on the primary `main/master` checkout must move to a task worktree; mechanical writes require explicit classification; integration requires the matching active claim and a clean target.
- For feature work, silently classify code-efficiency risk as `FAST / CHECK / PROFILE`: keep an already-located N+1 or local inefficiency, its batch fix, and deterministic query/count assertion with the current owner; use `ccdawn-bug-review` only for an observed failure, correctness regression, or unresolved root cause, and load `ccdawn-performance-engineering` only when profiling is needed for a target/regression or material hot-path, scale, concurrency, or resource risk. Do not benchmark routine changes.
- During code-writing work, silently classify file-structure risk as `STAY / CHECK / SPLIT`: keep cohesive files with the current owner; load `ccdawn-code-structure-guard` only when a touched hand-written source file accumulates independently changing responsibilities or its structure materially obstructs navigation, testing, review, or collaboration. Line count alone is a review signal, never a mandatory split; generated, vendored, migration, schema, fixture, and declarative-data files are exempt by default. Do not create abstractions solely to reduce lines.
- On Windows, if `python` or `py` resolves to a failing WindowsApps alias, check `$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` before one broader lookup; do not cycle equivalent aliases or scan unrelated roots.
- After alignment on nontrivial project work, proactively perform one bounded discovery of existing same-project peer threads when native thread tools are available and mutual help could reduce duplicate work, conflict, or integration rework. Discovery sends no messages and never creates subagents. Route sustained peer collaboration to `ccdawn-multi-agent-orchestration`; route one-off advice or conflict to `ccdawn-thread-coordination`. Every peer keeps ownership of its own task. Skip discovery for simple work or unavailable thread capabilities.
- When a nontrivial shared goal would benefit from continuous peer progress, conflict recovery, and verified local-main integration, ask once whether to enable `ccdawn-autonomous-collaboration-loop`. After confirmation, preserve local write/commit/local-main/verification/cleanup permission through completion without stage-by-stage prompts; new threads and remote push/PR/publish still require separate permission.
- When a peer delivery becomes merge-ready and local integration is authorized, check the exclusive `integration/<target-key>` responsibility claim once. If no valid Integration Owner exists, proactively claim the queue even when baseline failures or a dirty main temporarily block integration; if a valid claim exists, do not independently chase main, repeat the full gate, or merge, and only deliver `MERGE_READY` evidence. Take over only after explicit release, handoff, or stale lease.
- When a merge-ready delivery is blocked by a dirty target, load `ccdawn-thread-coordination` and classify blockers once as `SELF_OWNED / PEER_OWNED / UNOWNED / UNKNOWN`. A repeated dirty-target blocker must not continue accumulating implementation batches. Unless the user already enabled the automated loop, this one-off recovery must not load `ccdawn-autonomous-collaboration-loop`.
- After the same task pushes a branch and creates or updates a PR, apply a `Post-PR Closeout Gate` with `PR_OPEN / PR_MERGED / PR_CLOSED_UNMERGED`. `PR_OPEN` records `DEFERRED_INTEGRATION`, closes an implementation claim with no pending writes, and retains branch/worktree recovery resources. `PR_MERGED` must verify the base contains the published head, then load `ccdawn-development-cleanup` and safely remove the clean same-task worktree and local branch. `PR_CLOSED_UNMERGED` preserves unabsorbed work. A request to complete development through PR publication includes this verified local closeout, but remote branch deletion remains separately authorized.
- When the user asks to continue with the latest skill, read the live local `SKILL.md` before claiming that the conversation has been refreshed.
- Do not auto-load generic process frameworks such as `using-superpowers`, brainstorming, planning, strict TDD, worktrees, or subagent workflows unless the user explicitly requests them or a concrete task risk requires their unique method.
- Keep user-visible output Chinese-first unless the user requests another language; do not expose internal routing ledgers or process narration.
{BRT_ACTIVATION_END}"""


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


def brt_activation_state(path: Path) -> str:
    if not path.exists():
        return "absent"
    text = path.read_text(encoding="utf-8")
    starts = text.count(BRT_ACTIVATION_START)
    ends = text.count(BRT_ACTIVATION_END)
    if starts == 0 and ends == 0:
        return "absent"
    if starts == 1 and ends == 1 and text.index(BRT_ACTIVATION_START) < text.index(BRT_ACTIVATION_END):
        return "active"
    return "conflict"


def _read_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_preserving_newlines(path: Path, text: str, newline: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline))


def install_brt_activation(path: Path) -> bool:
    state = brt_activation_state(path)
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed CCDawn BRT activation markers in {path}.")

    original = _read_preserving_newlines(path) if path.exists() else ""
    newline = "\r\n" if "\r\n" in original else "\n"
    normalized = original.replace("\r\n", "\n")
    if state == "active":
        pattern = re.compile(
            re.escape(BRT_ACTIVATION_START) + r".*?" + re.escape(BRT_ACTIVATION_END),
            re.DOTALL,
        )
        updated = pattern.sub(BRT_ACTIVATION_BLOCK, normalized, count=1)
    else:
        updated = (
            f"{normalized}\n\n{BRT_ACTIVATION_BLOCK}\n"
            if normalized
            else f"{BRT_ACTIVATION_BLOCK}\n"
        )

    if updated == normalized:
        return False
    _write_preserving_newlines(path, updated, newline)
    return True


def remove_brt_activation(path: Path) -> bool:
    state = brt_activation_state(path)
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed CCDawn BRT activation markers in {path}.")
    if state == "absent":
        return False

    original = _read_preserving_newlines(path)
    newline = "\r\n" if "\r\n" in original else "\n"
    normalized = original.replace("\r\n", "\n")
    start = normalized.index(BRT_ACTIVATION_START)
    end = normalized.index(BRT_ACTIVATION_END, start) + len(BRT_ACTIVATION_END)
    prefix_start = start - 2 if start >= 2 and normalized[start - 2 : start] == "\n\n" else start
    suffix_end = end + 1 if normalized[end : end + 1] == "\n" else end
    updated = normalized[:prefix_start] + normalized[suffix_end:]
    _write_preserving_newlines(path, updated, newline)
    return True


def manage_brt_activation_path(
    path: Path,
    surface: str,
    action: str,
    dry_run: bool = False,
) -> None:
    if action == "ignore":
        return

    state = brt_activation_state(path)
    if action == "warn":
        print(f"CCDawn BRT {surface} activation: {state} ({path})")
        return
    if state == "conflict":
        raise SystemExit(f"Refusing to edit malformed CCDawn BRT activation markers in {path}.")

    if dry_run:
        verb = "install/update" if action == "install" else "remove"
        print(f"Planned CCDawn BRT {surface} activation: {verb} ({path}, current={state})")
        return

    changed = install_brt_activation(path) if action == "install" else remove_brt_activation(path)
    result = "installed" if action == "install" else "removed"
    if not changed:
        result = "already active" if action == "install" else "already absent"
    print(f"CCDawn BRT {surface} activation: {result} ({path})")


def manage_brt_activation(home: Path, action: str, dry_run: bool = False) -> None:
    manage_brt_activation_path(codex_agents_path(home), "Codex", action, dry_run)


def manage_selected_brt_activations(
    home: Path,
    roots: list[Path],
    action: str,
    dry_run: bool = False,
) -> None:
    if targets_codex(home, roots):
        manage_brt_activation_path(codex_agents_path(home), "Codex", action, dry_run)
    if targets_grok(home, roots):
        manage_brt_activation_path(grok_agents_path(home), "Grok", action, dry_run)


def process_skill_conflict_state(home: Path) -> list[tuple[str, str]]:
    root = codex_skills_root(home)
    states = []
    for name in SUPERPOWERS_ENTRYPOINTS:
        skill_dir = root / name
        active = (skill_dir / "SKILL.md").exists()
        disabled = (skill_dir / DISABLED_SKILL_FILENAME).exists()
        if active and disabled:
            state = "conflict"
        elif active:
            state = "active"
        elif disabled:
            state = "disabled"
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

        if action == "warn":
            if state == "active":
                changed.append((name, "active"))
            elif state == "conflict":
                blocked.append((name, "both active and disabled entrypoints exist"))
            continue

        if state == "conflict":
            blocked.append((name, "both active and disabled entrypoints exist"))
            continue

        if action == "disable" and state == "active":
            changed.append((name, "would disable" if dry_run else "disabled"))
            if not dry_run:
                active_path.rename(disabled_path)
        elif action == "restore" and state == "disabled":
            changed.append((name, "would restore" if dry_run else "restored"))
            if not dry_run:
                disabled_path.rename(active_path)

    if action == "warn" and changed:
        print("Warning: Superpowers entrypoints can bypass CCDawn BRT routing and add unnecessary workflow context:")
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

    validated = []
    for skill_path in installed_skills:
        subprocess.run([sys.executable, str(validator), str(skill_path)], check=True)
        validated.append(skill_path)
    return validated


def validate_ccdawn_package(repo_root: Path) -> None:
    validator = repo_root / "scripts" / "validate_ccdawn_skills.py"
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
        help="Skip CCDawn package convention validation before install or dry run.",
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
            "Manage local Superpowers entrypoints that can bypass BRT routing. "
            "disable/restore renames only SKILL.md, preserving the original directory and content (default: warn)."
        ),
    )
    parser.add_argument(
        "--brt-activation",
        choices=["warn", "install", "remove", "ignore"],
        default="warn",
        help=(
            "Manage reversible CCDawn BRT blocks in selected Codex/Grok AGENTS.md files. "
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
        validate_ccdawn_package(repo_root)

    roots = destination_roots(home, args.agent)
    if args.dry_run:
        print_install_plan(home, roots, selected_skill_names_list)
        if targets_codex(home, roots):
            manage_process_skill_conflicts(home, args.process_skill_conflicts, dry_run=True)
        if args.brt_activation != "install" or "ccdawn-brt" in selected_skill_names:
            manage_selected_brt_activations(home, roots, args.brt_activation, dry_run=True)
        elif targets_codex(home, roots) or targets_grok(home, roots):
            print("Skipped BRT activation plan because ccdawn-brt is not selected.")
        print("Dry run only; no files changed.")
        return 0

    if args.verify_only:
        installed_skills = verify_installed_skill_copies(roots, selected_skill_names_list)
        if not installed_skills:
            return 1
        print("Verified installed skills:")
        for path in installed_skills:
            print(f"  {path}")
        if targets_codex(home, roots):
            validator = codex_validator_path(home)
            if not validator.exists():
                print(f"Codex validator not found: {validator}")
                return 1
            installed_codex_skills = [codex_skills_root(home) / name for name in selected_skill_names_list]
            validated_codex_skills = validate_installed_codex_skills(home, installed_codex_skills)
            print(f"Validated live Codex skills: {len(validated_codex_skills)}")
            manage_process_skill_conflicts(home, "warn")
        manage_selected_brt_activations(home, roots, "warn")
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
    if targets_codex(home, roots):
        manage_process_skill_conflicts(home, args.process_skill_conflicts)
    if args.brt_activation != "install" or "ccdawn-brt" in selected_skill_names:
        manage_selected_brt_activations(home, roots, args.brt_activation)
    elif targets_codex(home, roots) or targets_grok(home, roots):
        print("Skipped BRT activation because ccdawn-brt was not installed.")

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
