---
name: publish-issue
description: Produce, verify, build and publish today's issue of the newspaper end to end. Use when asked to publish, run or produce today's issue, and for every scheduled daily run.
---

# Publish today's issue

This runs unattended. Never stop to ask a question: when something is ambiguous, take the reading
the editor skill supports, note it in the commit message, and continue. Never publish an issue the
verifier failed.

## Fetching pages in an unattended run

Only fetch (WebFetch) a URL that came from a WebSearch result, from a page already fetched in this
run, or that is written in your task message. Never construct or guess a URL (an API endpoint, a
data feed, a site's search page): fetching one asks the paper's owner for permission, nobody is there
to answer, and the run loses that content. If a fetch is refused or fails, move on with WebSearch.
Put the same rule in every subagent's task (the gather and fact-check skills already carry it).

## 0. Prepare

1. Read `newspaper.toml` and `.claude/skills/editor/SKILL.md` in full.
2. Get today's date in `paper.timezone` (`TZ=<timezone> date +%F`). If `issues/YYYY/MM/DD.md`
   already exists for today, stop: today's issue is out.
3. Find the previous issue (the latest issue `.md` file under `issues/`) and note its `number`
   and its headlines (gatherers use them to skip stories already published).

The service box (weather, exchange rates, sun and Shabbat times) is not your job. The deploy workflow
fetches it from data sources after you push. Never look up those numbers, never fetch the data
sources yourself, and never write `DD.data.json`.

## 1. Gather — with gatherer subagents

Don't search the news yourself: gathering is the bulk of the run, and doing it in your own context
makes every later step slower and more expensive.

**First, the tech lead list.** If `newspaper.toml` has a `[tech]` table, fetch each URL in
`tech.lead_sources` yourself (they are written in your task message, so the fetch needs no approval).
Ask for every story on the page: its title, the URL it links to, its points, comment count and age.
Write the combined list to `work/<YYYY-MM-DD>/hn.md`. If a fetch fails, write what you have; if both
fail, skip the tech section today and note it in the commit message.

**Then launch all gatherers in a single message**, so they run in parallel, each with the Agent tool
and `model` set to `models.gather` from `newspaper.toml`. One per section in `issue.sections`:

> Use the gather skill (.claude/skills/gather/SKILL.md). Section: <section>. Today: <YYYY-MM-DD>,
> timezone <paper.timezone>. Coverage window: <schedule.coverage_window_hours> hours. Already
> published in the previous issue, skip unless there is a new decision or outcome: <headlines>.
> Write your candidates to work/<YYYY-MM-DD>/<n>.json (n = the section's position, starting at 1).

For the tech section (`tech.section`), add to its task: "Lead list: work/<YYYY-MM-DD>/hn.md."

Plus two more with `Section: calendar` (writes `work/<YYYY-MM-DD>/calendar.json`) and
`Section: onthisday` (writes `work/<YYYY-MM-DD>/onthisday.json`).

When they have all returned, read the candidate files. `work/` is scratch space and is never committed.
If a section's file is missing or has no candidates, launch that section's gatherer once more; if it
comes back empty again, publish without that section and say why in the commit message.

You may run a few searches of your own to settle a specific doubt about a candidate (a conflicting
figure, a stale-looking date), but not to gather new items.

## 2. Select

Apply the editor skill's three tests and its exclusions to every candidate. Gatherers are cheaper,
faster models: treat their files as leads with sources, not as verified facts, and open a source
yourself whenever a candidate you select looks thin, borderline or surprising. Items younger than
`schedule.settle_hours` go in only on an official primary source. Rank by impact; keep at most
`issue.max_items` news items in total, of which at most `tech.max_items` in the tech section.
Choose the analysis topic, if any. Pick the calendar lines and the one on-this-day event from their
candidate files, following the editor skill.

If a gatherer happened to find that an item in the previous issue was wrong, add a correction (see
"Corrections" in the editor skill). Don't search for corrections otherwise.

## 3. Draft

Write `issues/YYYY/MM/DD.md` in the exact format in the editor skill, with `number` = previous + 1,
and `issues/YYYY/MM/DD.sources.json` with an entry for every factual claim.

## 4. Verify — with a separate agent

Launch a subagent (Agent tool, `model` set to `models.verify` from `newspaper.toml`) with this task,
and nothing about how you wrote the draft or what the gatherers found:

> Use the fact-check skill (.claude/skills/fact-check/SKILL.md) to verify issues/YYYY/MM/DD.md
> against issues/YYYY/MM/DD.sources.json. Write the report to issues/YYYY/MM/DD.check.md and
> return the result line and every required change.

Apply every change it returns. If the result was FAIL, or you removed or rewrote more than one item,
run the verifier once more on the revised draft. If it fails a second time, remove the failing items
and publish what passed; if fewer than two items remain, publish nothing today and say why in the
run summary.

## 5. Build and check

Run `python3 scripts/build.py`. It must exit 0 and produce `site/index.html`. Open the built file and
confirm the issue's headlines appear in it.

## 6. Publish

Commit only the three issue files (`DD.md`, `DD.sources.json`, `DD.check.md`), then
`git pull --rebase origin main` and push to `main`. Never commit `site/` or `work/`. Commit message:

```
Issue <number> — <YYYY-MM-DD>

<n> items, <analysis: yes/no>, <corrections: n>. Verifier: <result>.
<any judgment calls, one line each>
```

The push triggers the deploy workflow, which adds the service box data and publishes the site.
End with a short summary: items published, items dropped and why, verifier result.
