---
name: publish-issue
description: Produce today's issue of the newspaper end to end from the day's news bundle — gather, select, draft, verify, check. Use for every daily run (it runs in GitHub Actions) and when asked to produce today's issue.
allowed-tools: Read, Write, Edit, Glob, Grep, Agent, Task, Bash(python3 scripts/check_issue.py:*), Bash(python3 scripts/build.py), Bash(date:*), Bash(ls:*)
---

# Publish today's issue

This runs unattended in GitHub Actions. Never stop to ask a question: when something is ambiguous,
take the reading the editor skill supports, write it in the run notes, and continue.

## Where the material comes from

Before you start, the workflow has already collected today's raw material into `work/<YYYY-MM-DD>/`
(see `scripts/fetch_news.py`): `index.md` (every item, one line each, grouped by source),
`text/<id>.txt` (each item's full article text, or its feed summary), `hn.md` (the Hacker News
front page), `onthisday.md` (Wikipedia's events for today's date) and `report.json` (which sources
worked). **This bundle is the only source for news.** You have no web access for news, and nothing
that isn't in the bundle can go in the issue. The service box data (`DD.data.json`) is also already
fetched; never write or edit it.

The workflow commits and publishes your files after you finish, but only if
`python3 scripts/check_issue.py` passes. You do not run git.

## 0. Prepare

1. Read `newspaper.toml` and `.claude/skills/editor/SKILL.md` in full.
2. Today's date: the workflow passes it in the task; otherwise `TZ=<paper.timezone> date +%F`.
   If `issues/YYYY/MM/DD.md` already exists, stop.
3. Find the previous issue (the latest `issues/*/*/DD.md`), note its `number` and its headlines.
4. Read `work/<date>/report.json`. Note sources that failed; it doesn't change the work.

## 1. Gather — with gatherer subagents

Launch the gatherers in a single message so they run in parallel, each with the Agent tool and
`model` set to `models.gather` from `newspaper.toml`. One per section in `issue.sections`:

> Use the gather skill (.claude/skills/gather/SKILL.md). Section: <section>. Today: <YYYY-MM-DD>.
> Bundle: work/<YYYY-MM-DD>/. Already published in the previous issue, skip unless there is a new
> decision or outcome: <headlines>. Write your candidates to work/<YYYY-MM-DD>/cand-<n>.json
> (n = the section's position, starting at 1).

For the tech section (`tech.section`), add: "Start from work/<YYYY-MM-DD>/hn.md."

Plus one more with `Section: onthisday` (writes `work/<YYYY-MM-DD>/cand-onthisday.json`) and one
with `Section: calendar` (writes `work/<YYYY-MM-DD>/cand-calendar.json`).

When they return, read the candidate files. If a section's file is missing or empty, launch that
gatherer once more. A section that is still empty is left out.

## 2. Select

Apply the editor skill's tests and exclusions. Gatherers are cheaper models: before you select a
candidate, open its text files yourself and confirm the facts are there. Rank by impact; aim for
`issue.min_items` to `issue.max_items` news items in total, at most `tech.max_items` of them in tech.
A day's news is plentiful in the bundle: if you have fewer than `issue.min_items`, go back to
`index.md` yourself and look again before settling for less. Choose the analysis topic, if any, and
the calendar lines and on-this-day event.

## 3. Draft

Write `issues/YYYY/MM/DD.md` in the exact format in the editor skill (`number` = previous + 1), and
`issues/YYYY/MM/DD.sources.json`: an entry for every factual claim, each with the bundle id and a
short quote copied exactly, character for character, from that text file (see the editor skill).

## 4. Verify — with a separate agent

Launch a subagent (Agent tool, `model` set to `models.verify`) with this task, and nothing about how
you wrote the draft:

> Use the fact-check skill (.claude/skills/fact-check/SKILL.md) to verify issues/YYYY/MM/DD.md
> against issues/YYYY/MM/DD.sources.json and the bundle in work/YYYY-MM-DD/. Write the report to
> issues/YYYY/MM/DD.check.md and return the result line and every required change.

Apply every change. If the result was FAIL, or you removed or rewrote more than one item, run the
verifier once more on the revised draft. Update the check report's result line to the final result.

## 5. Check and build

Run `python3 scripts/check_issue.py YYYY-MM-DD`. It checks the format, the item count against
`issue.publish_floor`, the verifier's result, and that every quote really appears in its bundle file.
Fix whatever it reports and run it again until it passes. If you cannot reach `issue.publish_floor`
with items that pass, stop: the workflow will publish nothing today, and that is the right outcome.

Then run `python3 scripts/build.py`; it must exit 0.

## 6. Run notes

Write `issues/YYYY/MM/DD.notes.md`: items published, items dropped and why (one line each), sources
that failed in `report.json`, and any judgment calls. The workflow uses it as the commit message body.
