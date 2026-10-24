# This repo is a newspaper

A one-page daily newspaper written, edited and verified by Claude.

- The daily run is `.github/workflows/daily.yml`: it builds the news bundle (`scripts/fetch_news.py`),
  runs the `publish-issue` skill via the Claude Code GitHub Action (no web tools, no git), gates on
  `scripts/check_issue.py`, then commits and deploys. Claude works from `work/<date>/` only.
- Editorial rules: `.claude/skills/editor/SKILL.md`. Gathering (per-section subagents):
  `.claude/skills/gather/SKILL.md`. Verification: `.claude/skills/fact-check/SKILL.md`.
- This paper's preferences: `newspaper.toml`. The public summary of the rules: `POLICY.md`
  (keep it in sync with the editor skill when the rules change).
- Issues live in `issues/YYYY/MM/DD.md` with `DD.sources.json`, `DD.check.md`, `DD.notes.md`, `DD.data.json`.
  Never edit a published issue; corrections go in the next issue.
- `python3 scripts/build.py` builds the static site into `site/` (not committed; the Pages workflow builds it).
