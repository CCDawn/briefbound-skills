import argparse
import shutil
from pathlib import Path


SKILL_NAME = "briefbound-project-memory"


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the briefbound-project-memory skill into Codex.")
    parser.add_argument(
        "--home",
        default=str(Path.home()),
        help="Home directory containing .codex (default: current user home).",
    )
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve()
    skill_root = Path(__file__).resolve().parents[1]

    skill_src = skill_root

    codex_skill_dst = home / ".codex" / "skills" / SKILL_NAME

    codex_skill_dst.parent.mkdir(parents=True, exist_ok=True)

    copy_tree(skill_src, codex_skill_dst)

    print("Installed Codex skill:")
    print(f"  {codex_skill_dst}")
    print("Restart Codex so it reloads the updated skill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
