#!/usr/bin/env python3
"""Collect today's raw material into a local bundle that Claude works from, with no web access.

Reads the feeds in newspaper.toml ([[news.feeds]]), the Hacker News front page, and Wikipedia's
"on this day" list; downloads the full text of every recent article; writes:

  work/YYYY-MM-DD/index.md        one line per item, grouped by source (what the gatherers scan)
  work/YYYY-MM-DD/index.json      the same, as data
  work/YYYY-MM-DD/text/<id>.txt   header + full article text (or the feed summary if extraction failed)
  work/YYYY-MM-DD/hn.md           Hacker News front page with points and comments, linked to ids
  work/YYYY-MM-DD/onthisday.md    Wikipedia's selected events for today's date
  work/YYYY-MM-DD/report.json     per-source status: items kept, errors

No AI is involved. Every source fails on its own; the report says which ones did.
Usage: python3 scripts/fetch_news.py [--date YYYY-MM-DD]
Needs: Python 3.11+, `pip install trafilatura` (full-text extraction; without it, summaries only).
"""
from __future__ import annotations

import html
import json
import re
import sys
import tomllib
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((ROOT / "newspaper.toml").read_text(encoding="utf-8"))
NEWS = CONFIG["news"]
TZ = ZoneInfo(CONFIG["paper"]["timezone"])
UA = "Mozilla/5.0 (compatible; hadaf-newspaper/1.0; +https://github.com/jondot/hadaf)"
MAX_TEXT = 15000

try:
    import trafilatura  # type: ignore
except ImportError:  # summaries only
    trafilatura = None


def get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(s: str | None) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child(el: ET.Element, *names: str) -> ET.Element | None:
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def text_of(el: ET.Element, *names: str) -> str:
    c = child(el, *names)
    return (c.text or "") if c is not None else ""


def parse_feed(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    entries = [e for e in root.iter() if local(e.tag) in ("item", "entry")]
    out = []
    for e in entries:
        link = ""
        for c in e:
            if local(c.tag) == "link":
                link = c.get("href") or (c.text or "")
                if c.get("rel") in (None, "alternate") and link:
                    break
        out.append({
            "title": clean(text_of(e, "title")),
            "url": link.strip(),
            "published": parse_date(text_of(e, "pubDate", "published", "updated", "date")),
            "summary": clean(text_of(e, "description", "summary", "encoded", "content"))[:1200],
        })
    return [o for o in out if o["title"] and o["url"]]


def extract(url: str) -> str:
    if trafilatura is None:
        return ""
    try:
        raw = get(url, timeout=20)
        txt = trafilatura.extract(raw.decode("utf-8", "replace"), url=url, include_comments=False,
                                  include_tables=False, favor_precision=True) or ""
        return txt[:MAX_TEXT]
    except Exception:  # noqa: BLE001 — a failed article keeps its feed summary
        return ""


def main() -> None:
    args = sys.argv[1:]
    day = date.fromisoformat(args[args.index("--date") + 1]) if "--date" in args else datetime.now(TZ).date()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=NEWS.get("window_hours", 36))
    out_dir = ROOT / "work" / day.isoformat()
    (out_dir / "text").mkdir(parents=True, exist_ok=True)

    report: dict[str, dict] = {}
    items: list[dict] = []
    seen: dict[str, str] = {}

    def add(item: dict) -> str:
        """Add an item unless its URL is already in the bundle; return its id either way."""
        key = item["url"].split("#")[0].rstrip("/")
        if key in seen:
            existing = next(i for i in items if i["id"] == seen[key])
            existing.update({k: v for k, v in item.items() if k == "hn"})
            return seen[key]
        item["id"] = f"s{len(items) + 1:03d}"
        seen[key] = item["id"]
        items.append(item)
        return item["id"]

    # Feeds
    def load(feed: dict) -> tuple[dict, list[dict] | Exception]:
        try:
            return feed, parse_feed(get(feed["url"]))
        except Exception as e:  # noqa: BLE001
            return feed, e

    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(load, NEWS["feeds"]))
    for feed, res in results:
        if isinstance(res, Exception):
            report[feed["name"]] = {"ok": False, "error": f"{type(res).__name__}: {res}"[:200]}
            continue
        recent = [r for r in res if r["published"] is None or r["published"] >= cutoff]
        recent = recent[: NEWS.get("max_per_feed", 30)]
        for r in recent:
            add({"source": feed["name"], "kind": feed.get("kind", "news"), "lang": feed.get("lang", "en"),
                 "title": r["title"], "url": r["url"],
                 "published": r["published"].isoformat() if r["published"] else "",
                 "summary": r["summary"]})
        report[feed["name"]] = {"ok": True, "in_feed": len(res), "kept": len(recent)}

    # Hacker News front page (Algolia API)
    hn_lines = []
    try:
        hn = json.loads(get(f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={NEWS.get('hn_items', 30)}"))
        hits = sorted(hn["hits"], key=lambda h: h.get("points") or 0, reverse=True)
        for h in hits:
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
            hid = add({"source": "Hacker News", "kind": "tech", "lang": "en", "title": h.get("title", ""), "url": url,
                 "published": h.get("created_at", ""), "summary": clean(h.get("story_text"))[:1200],
                 "hn": {"points": h.get("points"), "comments": h.get("num_comments"),
                        "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}"}})
            hn_lines.append(f"- [{hid}] {h.get('points')} points · {h.get('num_comments')} comments · {h.get('title')} — {url}")
        report["Hacker News"] = {"ok": True, "kept": len(hits)}
    except Exception as e:  # noqa: BLE001
        report["Hacker News"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}

    # Full text
    with ThreadPoolExecutor(16) as pool:
        texts = list(pool.map(lambda it: extract(it["url"]) if NEWS.get("fetch_text", True) else "", items))
    for it, txt in zip(items, texts):
        it["has_text"] = bool(txt)
        body = txt or it["summary"] or "(no text available; title only)"
        header = (f"Source: {it['source']}\nTitle: {it['title']}\nURL: {it['url']}\n"
                  f"Published: {it['published'] or 'unknown'}\n"
                  f"Content: {'full article text' if txt else 'feed summary only'}\n\n")
        (out_dir / "text" / f"{it['id']}.txt").write_text(header + body + "\n", encoding="utf-8")
    for name, r in report.items():
        if r.get("ok"):
            src = [i for i in items if i["source"] == name]
            r["with_text"] = sum(1 for i in src if i["has_text"])

    # On this day (Wikipedia)
    otd = []
    try:
        raw = json.loads(get(f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{day.month:02d}/{day.day:02d}"))
        for ev in raw.get("selected", []):
            pages = ev.get("pages") or [{}]
            link = pages[0].get("content_urls", {}).get("desktop", {}).get("page", "")
            otd.append(f"- {ev.get('year')}: {clean(ev.get('text'))} — {link}")
        report["Wikipedia on this day"] = {"ok": True, "kept": len(otd)}
    except Exception as e:  # noqa: BLE001
        report["Wikipedia on this day"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}

    # Write index
    lines = [f"# Bundle for {day.isoformat()}", "",
             f"{len(items)} items from {sum(1 for r in report.values() if r.get('ok'))} sources, "
             f"published after {cutoff.astimezone(TZ):%Y-%m-%d %H:%M} local time. "
             "Each line: [id] time · title — summary. Full text: work/<date>/text/<id>.txt", ""]
    for src in dict.fromkeys(i["source"] for i in items):
        lines += [f"## {src}", ""]
        for i in (x for x in items if x["source"] == src):
            t = i["published"][:16].replace("T", " ") if i["published"] else "?"
            mark = "" if i["has_text"] else " (summary only)"
            lines.append(f"- [{i['id']}] {t} · {i['title']} — {i['summary'][:220]}{mark}")
        lines.append("")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "hn.md").write_text("# Hacker News front page, by points\n\n" + "\n".join(hn_lines) + "\n", encoding="utf-8")
    (out_dir / "onthisday.md").write_text(f"# On this day, {day.isoformat()} (Wikipedia, selected)\n\n" + "\n".join(otd) + "\n",
                                          encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for r in report.values() if r.get("ok"))
    print(f"fetch_news: {len(items)} items, {sum(i['has_text'] for i in items)} with full text, "
          f"{ok}/{len(report)} sources ok -> {out_dir.relative_to(ROOT)}/")
    for name, r in report.items():
        print(f"  {'ok ' if r.get('ok') else 'ERR'} {name}: " + (f"kept {r.get('kept')}, text {r.get('with_text', '-')}"
                                                              if r.get("ok") else r["error"]))
    if len(items) < NEWS.get("min_bundle_items", 60):
        sys.exit(f"fetch_news: only {len(items)} items; too few to make an issue")


if __name__ == "__main__":
    main()
