---
name: publish-issue
description: Produce, verify, build and publish today's issue of the newspaper end to end. Use when asked to publish, run or produce today's issue, and for every scheduled daily run.
---

# Publish today's issue

This runs unattended. Never stop to ask a question: when something is ambiguous, take the reading
the editor skill supports, note it in the commit message, and continue. Never publish an issue the
verifier failed.

## 0. Prepare

1. Read `newspaper.toml` and `.claude/skills/editor/SKILL.md` in full.
2. Get today's date in `paper.timezone` (`TZ=<timezone> date +%F`). If `issues/YYYY/MM/DD.md`
   already exists for today, stop: today's issue is out.
3. Find the previous issue (the latest file under `issues/`) and note its `number`.

## 1. Re-check yesterday

Read the previous issue. For each item whose facts could have moved since (casualty figures, vote
outcomes, figures marked preliminary, events still unfolding), search for updates. Draft a correction
for anything now known to be wrong or materially changed. Keep the list for step 4.

## 2. Gather

For each section in `issue.sections`, search for events in the last `schedule.coverage_window_hours`.
Start broad ("<section topic> news <date>"), then go to primary sources: official announcements,
statistics releases, central bank and court decisions, journals. Prefer `editorial.preferred_sources`;
never use `editorial.avoid_sources`. Fetch the actual pages; search snippets are not sources.

Record each fact you may use with its source, URL, publication date and retrieval time. Check every
page's date against the event: aggregator pages and live blogs often show stale content.

Aim for twice as many candidates as `issue.max_items`, so selection is a real choice.

## 3. Select

Apply the editor skill's three tests and its exclusions to every candidate. Items younger than
`schedule.settle_hours` go in only on an official primary source. Rank by impact; keep at most
`issue.max_items`. Choose the analysis topic, if any.

## 4. Draft

Write `issues/YYYY/MM/DD.md` in the exact format in the editor skill, with `number` = previous + 1,
the corrections from step 1, and `issues/YYYY/MM/DD.sources.json` with an entry for every factual claim.

## 5. Verify — with a separate agent

Launch a subagent (Agent tool) with this task, and nothing about how you wrote the draft:

> Use the fact-check skill (.claude/skills/fact-check/SKILL.md) to verify issues/YYYY/MM/DD.md
> against issues/YYYY/MM/DD.sources.json. Write the report to issues/YYYY/MM/DD.check.md and
> return the result line and every required change.

Apply every change it returns. If the result was FAIL, or you removed or rewrote more than one item,
run the verifier once more on the revised draft. If it fails a second time, remove the failing items
and publish what passed; if fewer than two items remain, publish nothing today and say why in the
run summary.

## 6. Build and check

Run `python3 scripts/build.py`. It must exit 0 and produce `site/index.html`. Open the built file and
confirm the issue's headlines appear in it.

## 7. Publish

Commit only the three issue files (`DD.md`, `DD.sources.json`, `DD.check.md`), then push to `main`.
Never commit `site/` (the deploy workflow builds it). Commit message:

```
Issue <number> — <YYYY-MM-DD>

<n> items, <analysis: yes/no>, <corrections: n>. Verifier: <result>.
<any judgment calls, one line each>
```

The push triggers the GitHub Pages deploy. End with a short summary: items published, items dropped
and why, verifier result.
