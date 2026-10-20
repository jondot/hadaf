#!/usr/bin/env python3
"""Fetch the service-box data for today's issue and write issues/YYYY/MM/DD.data.json.

Weather and sunrise/sunset: Open-Meteo (no key). Exchange rates: Bank of Israel representative
rates (SDMX), falling back to ECB rates via Frankfurter. Shabbat times: Hebcal (Fridays only).

No AI is involved: these numbers come straight from the data sources and are stored with the issue,
so the archive keeps each day's data as it was. Every part fails independently; failures are listed
under "errors" and the box simply leaves that part out.

Usage: python3 scripts/fetch_data.py [--date YYYY-MM-DD]
Standard library only (Python 3.11+).
"""
from __future__ import annotations

import csv
import io
import json
import sys
import tomllib
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((ROOT / "newspaper.toml").read_text(encoding="utf-8"))
SERVICE = CONFIG["service"]
TZ = CONFIG["paper"]["timezone"]
UA = {"User-Agent": "hadaf-newspaper/1.0 (+https://github.com/jondot/hadaf)"}


def get(url: str, params: dict | None = None) -> bytes:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def condition(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 80 <= code <= 82:
        return "showers"
    if code >= 95:
        return "storm"
    return "cloudy"


def fetch_weather(day: date) -> dict:
    cities = []
    for c in SERVICE["cities"]:
        raw = json.loads(get("https://api.open-meteo.com/v1/forecast", {
            "latitude": c["lat"], "longitude": c["lon"], "timezone": TZ,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "start_date": day.isoformat(),
            "end_date": (day + timedelta(days=SERVICE.get("weather_days", 7) - 1)).isoformat(),
        }))
        d = raw["daily"]
        days = []
        for i, t in enumerate(d["time"]):
            days.append({
                "date": t,
                "max": round(d["temperature_2m_max"][i]),
                "min": round(d["temperature_2m_min"][i]),
                "rain": d["precipitation_probability_max"][i],
                "condition": condition(int(d["weather_code"][i])),
                "sunrise": d["sunrise"][i][-5:],
                "sunset": d["sunset"][i][-5:],
            })
        cities.append({"name": c["name"], "days": days})
    return {"source": "Open-Meteo", "cities": cities}


def boi_rate(code: str, day: date) -> tuple[float, float, str]:
    """Last two Bank of Israel representative rates up to `day`: (rate, change, rate_date)."""
    url = f"https://edge.boi.org.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/RER_{code}_ILS"
    body = get(url, {"format": "csv", "startperiod": (day - timedelta(days=14)).isoformat(),
                     "endperiod": day.isoformat()}).decode("utf-8-sig")
    rows = [r for r in csv.DictReader(io.StringIO(body)) if r.get("OBS_VALUE")]
    rows.sort(key=lambda r: r["TIME_PERIOD"])
    if len(rows) < 2:
        raise ValueError(f"BoI returned {len(rows)} observations for {code}")
    last, prev = float(rows[-1]["OBS_VALUE"]), float(rows[-2]["OBS_VALUE"])
    return last, last - prev, rows[-1]["TIME_PERIOD"]


def ecb_rate(code: str, day: date) -> tuple[float, float, str]:
    start = (day - timedelta(days=10)).isoformat()
    raw = json.loads(get(f"https://api.frankfurter.app/{start}..{day.isoformat()}", {"from": code, "to": "ILS"}))
    series = sorted(raw["rates"].items())
    if len(series) < 2:
        raise ValueError(f"ECB returned {len(series)} observations for {code}")
    last, prev = series[-1][1]["ILS"], series[-2][1]["ILS"]
    return last, last - prev, series[-1][0]


def fetch_rates(day: date) -> dict:
    out, sources = [], set()
    for code in SERVICE.get("rates", []):
        try:
            rate, change, as_of = boi_rate(code, day)
            sources.add("בנק ישראל")
        except Exception:  # noqa: BLE001 — fall back to ECB reference rates
            rate, change, as_of = ecb_rate(code, day)
            sources.add("ECB")
        out.append({"code": code, "rate": round(rate, 4), "change": round(change, 4), "as_of": as_of})
    return {"source": ", ".join(sorted(sources)), "rates": out}


def fetch_shabbat() -> dict:
    cities, parasha = [], ""
    for c in SERVICE["cities"]:
        if not c.get("shabbat"):
            continue
        raw = json.loads(get("https://www.hebcal.com/shabbat", {
            "cfg": "json", "geonameid": c["geonameid"], "M": "on", "lg": "he"}))
        entry = {"name": c["name"], "candles": "", "havdalah": ""}
        for item in raw.get("items", []):
            cat = item.get("category")
            if cat in ("candles", "havdalah") and not entry[cat]:
                entry[cat] = item["date"][11:16]
            elif cat == "parashat" and not parasha:
                parasha = item.get("hebrew") or item.get("title", "")
        cities.append(entry)
    return {"source": "Hebcal", "parasha": parasha, "cities": cities}


def latest_issue_date() -> date | None:
    files = sorted((ROOT / "issues").glob("*/*/[0-9][0-9].md"))
    if not files:
        return None
    f = files[-1]
    return date(int(f.parent.parent.name), int(f.parent.name), int(f.stem))


def main() -> None:
    args = sys.argv[1:]
    if "--latest-if-missing" in args:
        # Used by the deploy workflow: fetch data for the newest issue unless it already has some.
        day = latest_issue_date()
        if day is None or (ROOT / "issues" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.data.json").exists():
            print("fetch_data: latest issue already has data; nothing to do")
            return
    elif "--date" in args:
        day = date.fromisoformat(args[args.index("--date") + 1])
    else:
        day = datetime.now(ZoneInfo(TZ)).date()
    out = {"date": day.isoformat(), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "errors": []}

    parts = [("weather", lambda: fetch_weather(day)), ("rates", lambda: fetch_rates(day))]
    if SERVICE.get("shabbat") and day.weekday() == 4:  # Friday
        parts.append(("shabbat", fetch_shabbat))
    for name, fn in parts:
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001 — each part fails on its own
            out["errors"].append(f"{name}: {type(e).__name__}: {e}")

    path = ROOT / "issues" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fetch_data: wrote {path.relative_to(ROOT)}; errors: {out['errors'] or 'none'}")
    if len(out["errors"]) == len(parts):
        sys.exit(1)


if __name__ == "__main__":
    main()
