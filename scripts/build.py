#!/usr/bin/env python3
"""Build the static site from issues/ into site/.

Outputs:
  site/index.html                 latest issue
  site/issues/YYYY-MM-DD.html     every issue
  site/archive.html               all issues, newest first, grouped by month
  site/policy.html                POLICY.md
  site/feed.xml                   RSS (when paper.site_url is set)

Standard library only (Python 3.11+). The issue format is defined in
.claude/skills/editor/SKILL.md; this parser accepts exactly that format.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from email.utils import format_datetime
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "issues"
SITE = ROOT / "site"
TEMPLATE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
CONFIG = tomllib.loads((ROOT / "newspaper.toml").read_text(encoding="utf-8"))
PAPER = CONFIG["paper"]
LABELS = CONFIG["labels"]
SERVICE = CONFIG.get("service", {})


# ---------- parsing ----------

@dataclass
class Item:
    headline: str
    paras: list[str] = field(default_factory=list)
    source: str = ""


SPECIAL = ("analysis", "corrections", "calendar", "onthisday")


@dataclass
class Section:
    label: str
    kind: str = "desk"  # desk | analysis | corrections | calendar | onthisday
    items: list[Item] = field(default_factory=list)
    title: str = ""     # analysis only
    byline: str = ""    # analysis byline; source line for calendar / onthisday
    paras: list[str] = field(default_factory=list)  # body of the special sections
    entries: list[str] = field(default_factory=list)  # calendar lines


@dataclass
class Issue:
    path: Path
    meta: dict
    sections: list[Section]

    @property
    def data(self) -> dict:
        p = self.path.with_name(self.path.stem + ".data.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    @property
    def day(self) -> date:
        return date.fromisoformat(str(self.meta["date"]))

    @property
    def slug(self) -> str:
        return self.day.isoformat()


def fail(path: Path, msg: str) -> None:
    sys.exit(f"build: {path.relative_to(ROOT)}: {msg}")


def parse_issue(path: Path) -> Issue:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        fail(path, "missing frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        if line.strip():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    for key in ("date", "number", "weekday", "summary"):
        if key not in meta:
            fail(path, f"frontmatter missing '{key}'")

    sections: list[Section] = []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", m.group(2)) if b.strip()]
    for block in blocks:
        if block.startswith("## "):
            head = block[3:].strip()
            km = re.match(r"^(.*?)\s*\{(" + "|".join(SPECIAL) + r")\}$", head)
            sections.append(Section(label=km.group(1), kind=km.group(2)) if km else Section(label=head))
            continue
        if not sections:
            fail(path, "content before the first '## ' section")
        sec = sections[-1]
        if block.startswith("### "):
            if sec.kind == "analysis":
                sec.title = block[4:].strip()
            elif sec.kind == "desk":
                sec.items.append(Item(headline=block[4:].strip()))
            else:
                fail(path, "headline inside corrections")
            continue
        if sec.kind == "calendar" and block.startswith("- "):
            sec.entries.extend(l[2:].strip() for l in block.splitlines() if l.startswith("- "))
            continue
        if block.startswith(">"):
            line = " ".join(l.lstrip("> ").strip() for l in block.splitlines())
            if sec.kind in SPECIAL:
                sec.byline = line
            elif sec.items:
                sec.items[-1].source = line
            else:
                fail(path, "source line before any headline")
            continue
        para = " ".join(l.strip() for l in block.splitlines())
        if sec.kind == "desk":
            if not sec.items:
                fail(path, f"paragraph before any headline in '{sec.label}'")
            sec.items[-1].paras.append(para)
        else:
            sec.paras.append(para)

    for sec in sections:
        for it in sec.items:
            if not it.paras:
                fail(path, f"item without body: {it.headline}")
            if not it.source:
                fail(path, f"item without source line: {it.headline}")
    return Issue(path=path, meta=meta, sections=sections)


def load_issues() -> list[Issue]:
    files = sorted(p for p in ISSUES.glob("*/*/*.md") if re.fullmatch(r"\d\d\.md", p.name))
    issues = [parse_issue(p) for p in files]
    issues.sort(key=lambda i: i.day)
    return issues


# ---------- rendering ----------

def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def long_date(d: date) -> str:
    return f"{d.day} ב{LABELS['months'][d.month - 1]} {d.year}" if PAPER["language"] == "he" \
        else f"{d.day} {LABELS['months'][d.month - 1]} {d.year}"


def page(title: str, description: str, content: str, base: str) -> str:
    feed = ""
    if PAPER.get("site_url"):
        feed = f'<link rel="alternate" type="application/rss+xml" title="{html.escape(PAPER["name"])}" href="{base}feed.xml">'
    out = TEMPLATE
    for k, v in {
        "LANG": PAPER["language"], "DIR": PAPER["direction"], "TITLE": html.escape(title),
        "DESCRIPTION": html.escape(description), "FEED_LINK": feed, "CONTENT": content,
    }.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def render_issue(issue: Issue, prev: Issue | None, nxt: Issue | None, base: str) -> str:
    m = issue.meta
    dateline = [f"{m['weekday']}, {long_date(issue.day)}"]
    if m.get("hebrew_date"):
        dateline.append(m["hebrew_date"])
    dateline.append(f"{LABELS['issue_number']} {m['number']}")

    desks, extras, analysis, corrections = [], [], "", ""
    for sec in issue.sections:
        if sec.kind == "desk":
            arts = []
            for it in sec.items:
                body = "".join(f"<p>{inline(p)}</p>" for p in it.paras)
                arts.append(f'<article><h3>{inline(it.headline)}</h3>{body}<p class="src">{inline(it.source)}</p></article>')
            desks.append(f'<section class="desk"><h2 class="label">{inline(sec.label)}</h2>{"".join(arts)}</section>')
        elif sec.kind == "analysis":
            by = f'<p class="by">{inline(sec.byline)}</p>' if sec.byline else ""
            body = "".join(f"<p>{inline(p)}</p>" for p in sec.paras)
            analysis = (f'<section class="analysis" aria-labelledby="an-title"><div class="head">'
                        f'<h2 class="label">{inline(sec.label)}</h2><h3 id="an-title">{inline(sec.title)}</h3>{by}</div>{body}</section>')
        elif sec.kind == "corrections":
            body = " ".join(inline(p) for p in sec.paras)
            corrections = f"<p><strong>{inline(sec.label)}:</strong> {body}</p>"
        elif sec.kind == "calendar" and sec.entries:
            src = f'<p class="src">{inline(sec.byline)}</p>' if sec.byline else ""
            lis = "".join(f"<li>{inline(e)}</li>" for e in sec.entries)
            extras.append(f'<section class="extra"><h2 class="label">{inline(sec.label)}</h2><ul class="cal">{lis}</ul>{src}</section>')
        elif sec.kind == "onthisday" and sec.paras:
            src = f'<p class="src">{inline(sec.byline)}</p>' if sec.byline else ""
            body = "".join(f"<p>{inline(p)}</p>" for p in sec.paras)
            extras.append(f'<section class="extra"><h2 class="label">{inline(sec.label)}</h2>{body}{src}</section>')
    extras_html = f'<div class="extras">{"".join(extras)}</div>' if extras else ""
    data = issue.data
    strip, service = render_today_strip(data), render_service(data)

    def link(target: Issue | None, label: str) -> str:
        if target is None:
            return f"<span>{html.escape(label)}</span>"
        return f'<a href="{base}issues/{target.slug}.html">{html.escape(label)}</a>'

    nav = (f'<nav aria-label="ניווט בין גיליונות">{link(prev, LABELS["previous"])}'
           f'<a href="{base}archive.html">{html.escape(LABELS["archive"])}</a>'
           f'<a href="{base}policy.html">{html.escape(LABELS["policy"])}</a>'
           f'{link(nxt, LABELS["next"])}</nav>')

    content = f"""<div class="page">
<header>
<div class="dateline">{"".join(f"<span>{html.escape(x)}</span>" for x in dateline)}</div>
<h1 class="mast"><a href="{base}index.html">{html.escape(PAPER["name"])}</a></h1>
<div class="double" aria-hidden="true"></div>
<p class="tag">{html.escape(PAPER["tagline"])} · {html.escape(m["summary"])}</p>
{strip}
</header>
<main class="cols">{"".join(desks)}</main>
{analysis}
{extras_html}
{service}
<footer>
{corrections}
<p class="colophon">{html.escape(LABELS["colophon"])}</p>
{nav}
</footer>
</div>"""
    title = f"{PAPER['name']} · {LABELS['issue_number']} {m['number']}"
    return page(title, f"{m['weekday']}, {long_date(issue.day)}", content, base)


def signed(x: float, digits: int) -> str:
    """A signed number, isolated left-to-right so the sign stays put in RTL text."""
    s = f"{abs(x):.{digits}f}"
    s = f"+{s}" if x > 0 else (f"−{s}" if x < 0 else s)
    return f'<bdi dir="ltr">{s}</bdi>'


def temps(d: dict) -> str:
    """Low–high range, isolated left-to-right so it reads the same in RTL text."""
    return f'<bdi dir="ltr" class="num">{d["min"]}°–{d["max"]}°</bdi>'


def render_today_strip(data: dict) -> str:
    """One line under the masthead: today's highs/lows per city and the exchange rates."""
    parts = []
    for c in data.get("weather", {}).get("cities", []):
        if c["days"]:
            d = c["days"][0]
            parts.append(f'<span class="pair">{html.escape(c["name"])} {temps(d)}</span>')
    for r in data.get("rates", {}).get("rates", []):
        name = LABELS["currency_names"].get(r["code"], r["code"])
        parts.append(f'<span class="pair">{html.escape(name)} <span class="num">{r["rate"]:.3f}</span></span>')
    return f'<p class="today">{" · ".join(parts)}</p>' if parts else ""


def render_service(data: dict) -> str:
    """The service band: weekly weather table, rates, sun times, Shabbat times."""
    blocks = []
    weather = data.get("weather", {}).get("cities", [])
    if weather and weather[0]["days"]:
        days = weather[0]["days"]
        head = "".join(
            f'<th scope="col">{LABELS["weekdays_short"][date.fromisoformat(d["date"]).weekday()]} '
            f'<span class="num">{date.fromisoformat(d["date"]).day}.{date.fromisoformat(d["date"]).month}</span></th>'
            for d in days)
        rows = []
        for c in weather:
            cells = []
            for d in c["days"]:
                rain = (f'<span class="rain">{LABELS["rain"]} {d["rain"]}%</span>'
                        if d.get("rain") is not None and d["rain"] >= 40 else "")
                cells.append(f'<td>{temps(d)}{rain}</td>')
            rows.append(f'<tr><th scope="row">{html.escape(c["name"])}</th>{"".join(cells)}</tr>')
        blocks.append(
            f'<section class="wx"><h2 class="label">{LABELS["weather"]}</h2>'
            f'<div class="scroll"><table><thead><tr><td></td>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

    side = []
    rates = data.get("rates", {}).get("rates", [])
    if rates:
        lines = "".join(
            f'<li><span>{html.escape(LABELS["currency_names"].get(r["code"], r["code"]))}</span>'
            f'<span class="num">{r["rate"]:.3f} <span class="chg">({signed(r["change"], 3)})</span></span></li>'
            for r in rates)
        side.append(f'<div><h3 class="sub">{LABELS["rates_title"]}</h3><ul class="kv">{lines}</ul></div>')
    sun_city = next((c for c in weather if c["name"] == SERVICE.get("sun_city")), weather[0] if weather else None)
    if sun_city and sun_city["days"]:
        d = sun_city["days"][0]
        side.append(f'<div><h3 class="sub">{LABELS["sun"]} · {html.escape(sun_city["name"])}</h3><ul class="kv">'
                    f'<li><span>{LABELS["sunrise"]}</span><span class="num">{d["sunrise"]}</span></li>'
                    f'<li><span>{LABELS["sunset"]}</span><span class="num">{d["sunset"]}</span></li></ul></div>')
    shabbat = data.get("shabbat")
    if shabbat and shabbat.get("cities"):
        title = LABELS["shabbat_title"] + (f' · {html.escape(shabbat["parasha"])}' if shabbat.get("parasha") else "")
        lines = "".join(
            f'<li><span>{html.escape(c["name"])}</span><span class="num"><bdi>{c["candles"]}</bdi> · <bdi>{c["havdalah"]}</bdi></span></li>'
            for c in shabbat["cities"])
        side.append(f'<div><h3 class="sub">{title}</h3><p class="hint">{LABELS["candles"]} · {LABELS["havdalah"]}</p>'
                    f'<ul class="kv">{lines}</ul></div>')
    if side:
        blocks.append(f'<div class="side">{"".join(side)}</div>')
    if not blocks:
        return ""
    return (f'<section class="service" aria-label="{LABELS["weather"]}">{"".join(blocks)}'
            f'<p class="src svc-src">{html.escape(LABELS["service_sources"])}</p></section>')


def small_header(base: str, subtitle: str) -> str:
    return (f'<header><div class="double" aria-hidden="true"></div>'
            f'<p class="mast small"><a href="{base}index.html">{html.escape(PAPER["name"])}</a></p>'
            f'<p class="tag">{html.escape(subtitle)}</p></header>')


def render_archive(issues: list[Issue]) -> str:
    groups: dict[tuple[int, int], list[Issue]] = {}
    for i in reversed(issues):
        groups.setdefault((i.day.year, i.day.month), []).append(i)
    parts = []
    for (y, mo), items in groups.items():
        rows = "".join(
            f'<li><a href="issues/{i.slug}.html"><span>{html.escape(i.meta["weekday"])}, {long_date(i.day)}'
            f'{" · " + html.escape(i.meta["hebrew_date"]) if i.meta.get("hebrew_date") else ""}</span>'
            f'<span class="meta">{html.escape(LABELS["issue_number"])} {i.meta["number"]} · {html.escape(i.meta["summary"])}</span></a></li>'
            for i in items)
        parts.append(f'<h2 class="label">{LABELS["months"][mo - 1]} {y}</h2><ul>{rows}</ul>')
    content = f"""<div class="page narrow archive">
{small_header("", LABELS["archive_title"])}
<main>{"".join(parts)}<p class="note">{html.escape(LABELS["archive_note"])}</p></main>
<footer><nav><a href="index.html">{html.escape(LABELS["today"])}</a><a href="policy.html">{html.escape(LABELS["policy"])}</a>{'<a href="feed.xml">RSS</a>' if PAPER.get("site_url") else ""}</nav></footer>
</div>"""
    return page(f"{PAPER['name']} · {LABELS['archive']}", LABELS["archive_title"], content, "")


def render_markdown(md: str) -> str:
    """Headings, paragraphs, '-' lists and **bold**. Enough for POLICY.md."""
    out = []
    for block in [b.strip() for b in re.split(r"\n\s*\n", md) if b.strip()]:
        if block.startswith("# "):
            out.append(f"<h1>{inline(block[2:])}</h1>")
        elif block.startswith("## "):
            out.append(f"<h2>{inline(block[3:])}</h2>")
        elif all(l.startswith("- ") for l in block.splitlines()):
            out.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in block.splitlines()) + "</ul>")
        else:
            out.append(f"<p>{inline(' '.join(block.splitlines()))}</p>")
    return "".join(out)


def render_policy() -> str:
    body = render_markdown((ROOT / "POLICY.md").read_text(encoding="utf-8"))
    content = f"""<div class="page narrow">
{small_header("", LABELS["policy"])}
<main class="prose">{body}</main>
<footer><nav><a href="index.html">{html.escape(LABELS["today"])}</a><a href="archive.html">{html.escape(LABELS["archive"])}</a></nav></footer>
</div>"""
    return page(f"{PAPER['name']} · {LABELS['policy']}", LABELS["policy"], content, "")


def render_feed(issues: list[Issue]) -> str:
    url = PAPER["site_url"].rstrip("/")
    items = []
    for i in reversed(issues[-30:]):
        heads = "; ".join(it.headline for s in i.sections for it in s.items)
        pub = format_datetime(datetime(i.day.year, i.day.month, i.day.day, 4, 0, tzinfo=timezone.utc))
        items.append(
            f"<item><title>{html.escape(LABELS['issue_number'])} {i.meta['number']} · {html.escape(long_date(i.day))}</title>"
            f"<link>{url}/issues/{i.slug}.html</link><guid>{url}/issues/{i.slug}.html</guid>"
            f"<pubDate>{pub}</pubDate><description>{html.escape(heads)}</description></item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{html.escape(PAPER['name'])}</title><link>{url}/</link>"
            f"<description>{html.escape(PAPER['tagline'])}</description><language>{PAPER['language']}</language>"
            + "".join(items) + "</channel></rss>\n")


def main() -> None:
    issues = load_issues()
    if not issues:
        sys.exit("build: no issues found under issues/")
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "issues").mkdir(parents=True)

    for n, issue in enumerate(issues):
        prev = issues[n - 1] if n > 0 else None
        nxt = issues[n + 1] if n + 1 < len(issues) else None
        (SITE / "issues" / f"{issue.slug}.html").write_text(render_issue(issue, prev, nxt, "../"), encoding="utf-8")
    latest = issues[-1]
    (SITE / "index.html").write_text(
        render_issue(latest, issues[-2] if len(issues) > 1 else None, None, ""), encoding="utf-8")
    (SITE / "archive.html").write_text(render_archive(issues), encoding="utf-8")
    (SITE / "policy.html").write_text(render_policy(), encoding="utf-8")
    if PAPER.get("site_url"):
        (SITE / "feed.xml").write_text(render_feed(issues), encoding="utf-8")
    (SITE / ".nojekyll").write_text("")
    print(f"build: {len(issues)} issue(s), latest {latest.slug} -> {SITE.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
