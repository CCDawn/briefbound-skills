Skills are organized into bucket folders under `skills/`:

- `engineering/` - code work and implementation workflows
- `research/` - research planning, evidence synthesis, and paper-readiness workflows

Every skill in `engineering/` or `research/` must have:

- a reference in the top-level `README.md`
- an entry in `.claude-plugin/plugin.json`

Published skills in this repository must also follow the live-install rules:

- the skill folder name must match the `name` field in `SKILL.md`
- the default local install target is `~/.codex/skills/<briefbound-skill-name>`
- use `~/.agents/skills/<briefbound-skill-name>` only when you explicitly need an extra local catalog copy
- installing the same skill into both `.codex/skills` and `.agents/skills` can produce duplicate slash-command entries
- the default install shape is a real directory, not a symlink or junction
- after updating a skill, validate the installed live Codex copy before treating the change as done
- after updating install metadata or `agents/openai.yaml`, inspect the installed live copy and restart Codex before concluding that the slash-command change failed
- keep `agents/openai.yaml` aligned with the minimal working shape already used in this repo: an `interface:` block with a distinctive `display_name`, `short_description`, and `default_prompt`
- if the current trusted workspace is this repository, remember that `.claude-plugin/plugin.json` can also influence visible skill entries during slash-command debugging

Each bucket folder should have a `README.md` that lists every skill in the bucket with a one-line description, and each skill name should link to its `SKILL.md`.
