# AGENTS

This repository publishes local Codex skills. Treat slash-command behavior as a packaging problem first, not as a prompt-writing problem.

## Repo rules

- One skill lives under `skills/<bucket>/<briefbound-skill-name>/`.
- The folder name must match the `name` field in `SKILL.md`.
- When the catalog changes, update `README.md`, `README.zh-CN.md`, the bucket `README.md`, and `.claude-plugin/plugin.json` in the same change.
- The default install target is `~/.codex/skills/<briefbound-skill-name>`.
- The native Grok target is `~/.grok/skills/<briefbound-skill-name>` with global activation in `~/.grok/AGENTS.md`.
- Use `~/.agents/skills/<briefbound-skill-name>` only when you explicitly need an extra local catalog copy.
- Do not rely on symlinks or junctions as the default install shape.

## Slash-command lessons learned

- Do not install the same skill into both `.codex/skills` and `.agents/skills` unless the user explicitly wants both copies. Codex can show duplicate slash-command entries when both are present.
- After changing a skill, inspect the installed live copy under `~/.codex/skills/<briefbound-skill-name>`, not just the repo copy. A repo file and the live loaded file can drift.
- After changing install metadata or `agents/openai.yaml`, restart Codex and verify the slash-command entry in a fresh thread.
- Keep `agents/openai.yaml` aligned with the working pattern already used in this repo: a minimal `interface:` block with a distinctive `display_name`, `short_description`, and `default_prompt`.
- If this repository is the active trusted workspace, its `.claude-plugin/plugin.json` can also influence visible skill entries. When debugging duplicates, check both installed global copies and the repo-local manifest.

## Duplicate or missing slash-command checklist

1. Check the live installed copy in `~/.codex/skills/<briefbound-skill-name>`.
2. Check whether an extra `~/.agents/skills/<briefbound-skill-name>` copy exists.
3. Check `agents/openai.yaml` for the live copy, not only the repo copy.
4. Check whether the current workspace is this repo and whether `.claude-plugin/plugin.json` also exposes the same skill.
5. Restart Codex before concluding that a metadata change failed.

## Default verification flow

1. Edit the repo copy.
2. Run `python scripts/install_codex_library.py` unless you intentionally need a different target.
3. Validate the installed live Codex copy when the local validator is available.
4. Inspect the live installed files under `~/.codex/skills/`.
5. Restart Codex and verify the slash-command entry from a fresh thread.
6. For Grok changes, run `grok inspect --json` and verify a fresh session resolves Briefbound skills from `~/.grok/skills`.
