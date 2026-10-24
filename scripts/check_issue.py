#!/usr/bin/env python3
"""Quality gate for an issue. The daily workflow publishes the issue only if this passes.

Checks: the issue parses; date and number are right; at least issue.publish_floor news items;
the verifier's report exists and did not FAIL; every news item has at least one source entry;
every quote in sources.json appears in its bundle file; no links in the issue text; run notes exist.

Usage: python3 scripts/check_issue.py YYYY-MM-DD
Exit 0 = publishable. Exit 1 = not; the problems are printed one per line.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build  # noqa: E402  (parser and config)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[‘’‚‛′׳`´]", "'", s)
    s = re.sub(r"[“”„‟″״«»]", '"', s)
    s = re.sub(r"[‐-―−־]", "-", s)
    s = s.replace(" ", " ").replace("‏", "").replace("‎", "")
    return re.sub(r"\s+", " ", s).strip().casefold()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    day = date.fromisoformat(sys.argv[1])
    base = ROOT / "issues" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    bundle = ROOT / "work" / day.isoformat() / "text"
    problems: list[str] = []
    cfg = build.CONFIG

    md = base.with_suffix(".md")
    if not md.exists():
        sys.exit(f"FAIL: {md.relative_to(ROOT)} does not exist")
    try:
        issue = build.parse_issue(md)
    except SystemExit as e:
        sys.exit(f"FAIL: issue does not parse: {e}")

    if str(issue.meta["date"]) != day.isoformat():
        problems.append(f"frontmatter date {issue.meta['date']} != {day}")
    previous = [i for i in build.load_issues() if i.day < day]
    want = int(previous[-1].meta["number"]) + 1 if previous else 1
    if str(issue.meta["number"]) != str(want):
        problems.append(f"number is {issue.meta['number']}, expected {want}")

    items = [it for s in issue.sections if s.kind == "desk" for it in s.items]
    floor = cfg["issue"].get("publish_floor", 5)
    if len(items) < floor:
        problems.append(f"only {len(items)} news items; publish_floor is {floor}")

    body = md.read_text(encoding="utf-8")
    if re.search(r"https?://|www\.", body):
        problems.append("the issue text contains a link; links are not allowed")

    check = base.with_suffix(".check.md")
    if not check.exists():
        problems.append("no verifier report (DD.check.md)")
    else:
        m = re.search(r"^Result:\s*(.+)$", check.read_text(encoding="utf-8"), re.M)
        if not m:
            problems.append("verifier report has no 'Result:' line")
        elif m.group(1).strip().upper().startswith("FAIL"):
            problems.append(f"verifier result is {m.group(1).strip()}")

    src_path = base.with_suffix(".sources.json")
    try:
        sources = json.loads(src_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sources = []
        problems.append("no sources file (DD.sources.json)")
    except json.JSONDecodeError as e:
        sources = []
        problems.append(f"sources file is not valid JSON: {e}")

    valid_for: dict[str, int] = {}
    cache: dict[str, str] = {}
    for n, s in enumerate(sources, 1):
        sid, quote = s.get("id", ""), s.get("quote", "")
        label = f"source #{n} ({s.get('item', '?')[:40]})"
        if not sid or not quote:
            problems.append(f"{label}: missing id or quote")
            continue
        f = bundle / f"{sid}.txt"
        if not f.exists():
            problems.append(f"{label}: bundle file {sid}.txt not found")
            continue
        if sid not in cache:
            cache[sid] = norm(f.read_text(encoding="utf-8"))
        if norm(quote) not in cache[sid]:
            problems.append(f"{label}: quote not found in {sid}.txt: {quote[:80]!r}")
            continue
        key = norm(s.get("item", ""))
        valid_for[key] = valid_for.get(key, 0) + 1

    for it in items:
        if not valid_for.get(norm(it.headline)):
            problems.append(f"no verified source entry for item: {it.headline[:70]} "
                            "(sources.json 'item' must equal the headline)")

    if not base.with_suffix(".notes.md").exists():
        problems.append("no run notes (DD.notes.md)")

    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for p in problems:
            print(f"- {p}")
        sys.exit(1)
    print(f"PASS: {len(items)} news items, {len(sources)} source entries, all quotes found")


if __name__ == "__main__":
    main()
