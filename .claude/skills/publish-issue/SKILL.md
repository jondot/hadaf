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
3. Find the previous issue (the latest issue `.md` file under `issues/`) and note its `number`.
4. Check whether `issues/YYYY/MM/DD.data.json` exists (the service box data, written by a GitHub
   workflow). Don't read it into your work and never edit it; just note in the commit message if it is
   missing or lists errors.

## 1. Re-check yesterday

Read the previous issue. For each item whose facts could have moved since (casualty figures, vote
outcomes, figures marked preliminary, events still unfolding), search for updates. Draft a correction
for anything now known to be wrong or materially changed. Keep the list for step 4.

## 2. Gather — with gatherer subagents

Don't search the news yourself: gathering is the bulk of the run, and doing it in your own context
makes every later step slower and more expensive. Launch one gatherer subagent per section in
`issue.sections`, all in a single message so they run in parallel, each with the Agent tool and
`model` set to `models.gather` from `newspaper.toml`. Give each one this task:

> Use the gather skill (.claude/skills/gather/SKILL.md). Section: <section>. Today: <YYYY-MM-DD>,
> timezone <paper.timezone>. Coverage window: <schedule.coverage_window_hours> hours. Write your
> candidates to work/<YYYY-MM-DD>/<n>.json (n = the section's position, starting at 1).

In the same message, launch two more gatherers the same way, with `Section: calendar` (write to
`work/<YYYY-MM-DD>/calendar.json`) and `Section: onthisday` (write to `work/<YYYY-MM-DD>/onthisday.json`).

When they have all returned, read the candidate files. `work/` is scratch space and is never committed.
If a section's file is missing or empty, launch that section's gatherer once more; if it fails again,
publish without that section and note it in the commit message.

You may run a few searches of your own to settle a specific doubt about a candidate (a conflicting
figure, a stale-looking date), but not to gather new items.

## 3. Select

Apply the editor skill's three tests and its exclusions to every candidate. Gatherers are cheaper,
faster models: treat their files as leads with sources, not as verified facts, and open a source
yourself whenever a candidate you select looks thin, borderline or surprising. Items younger than
`schedule.settle_hours` go in only on an official primary source. Rank by impact; keep at most
`issue.max_items`. Choose the analysis topic, if any. Pick the calendar lines and the one on-this-day
event from their candidate files, following the editor skill.

## 4. Draft

Write `issues/YYYY/MM/DD.md` in the exact format in the editor skill, with `number` = previous + 1,
the corrections from step 1, and `issues/YYYY/MM/DD.sources.json` with an entry for every factual claim.

## 5. Verify — with a separate agent

Launch a subagent (Agent tool, `model` set to `models.verify` from `newspaper.toml`) with this task,
and nothing about how you wrote the draft or what the gatherers found:

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

Commit only the three issue files (`DD.md`, `DD.sources.json`, `DD.check.md`), then
`git pull --rebase origin main` (the data workflow may have pushed meanwhile) and push to `main`.
Never commit `site/` (the deploy workflow builds it). Commit message:

```
Issue <number> — <YYYY-MM-DD>

<n> items, <analysis: yes/no>, <corrections: n>. Verifier: <result>.
<any judgment calls, one line each>
```

The push triggers the GitHub Pages deploy. End with a short summary: items published, items dropped
and why, verifier result.
