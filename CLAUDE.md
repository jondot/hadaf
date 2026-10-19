# This repo is a newspaper

A one-page daily newspaper written, edited and verified by Claude.

- To publish today's issue, use the `publish-issue` skill. It runs unattended.
- Editorial rules: `.claude/skills/editor/SKILL.md`. Gathering (per-section subagents):
  `.claude/skills/gather/SKILL.md`. Verification: `.claude/skills/fact-check/SKILL.md`.
- This paper's preferences: `newspaper.toml`. The public summary of the rules: `POLICY.md`
  (keep it in sync with the editor skill when the rules change).
- Issues live in `issues/YYYY/MM/DD.md` with `DD.sources.json` and `DD.check.md`.
  Never edit a published issue; corrections go in the next issue.
- `python3 scripts/build.py` builds the static site into `site/` (not committed; the Pages workflow builds it).
