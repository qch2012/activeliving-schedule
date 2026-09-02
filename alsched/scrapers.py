"""One scraper per Source. Parsing is split from fetching so the parsers can be
tested against saved fixtures.

- pool, climbing        -> plain HTML / static config
- gym, gym_track,
  oval_running, oval_skate -> DevExpress ASPxScheduler, rendered with Playwright
  (see docs/adr/0001-playwright-for-devexpress-schedulers.md)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from . import config
from .models import TZ, Session

_UA = "activeliving-schedule/0.1 (personal schedule aggregator; +https://github.com)"


def _fetch(url: str) -> str:
    r = httpx.get(url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return r.text


# ---------------------------------------------------------------------------
# time / date parsing
# ---------------------------------------------------------------------------
_MONTHS = {
    name.lower(): i
    for i, name in enumerate(
        "January February March April May June July August September "
        "October November December".split(),
        start=1,
    )
}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})

_DAY_RE = re.compile(r"([A-Za-z]+),\s*([A-Za-z]+)\s+(\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?", re.I)


def infer_year(month: int, day: int, now: datetime) -> int:
    """Schedules never carry a year; pick the one that lands (month, day)
    closest to `now` so a December run still resolves January correctly."""
    target = now.date()
    return min(
        (now.year - 1, now.year, now.year + 1),
        key=lambda y: abs((date(y, month, day) - target).days),
    )


def _parse_time(tok: str, fallback_period: str | None) -> tuple[int, int, str]:
    m = _TIME_RE.search(tok.strip().lower())
    if not m:
        raise ValueError(f"unparseable time {tok!r}")
    hh, mm = int(m.group(1)), int(m.group(2) or 0)
    period = (m.group(3) or fallback_period or "").replace(".", "").lower()
    if not period:
        raise ValueError(f"no am/pm in {tok!r}")
    if period == "pm" and hh != 12:
        hh += 12
    elif period == "am" and hh == 12:
        hh = 0
    return hh, mm, period


def parse_time_range(text: str, day: date) -> tuple[datetime, datetime] | None:
    """'11 a.m. - 2 p.m.' / '5 - 10 p.m.' / '7:30 - 9:30 a.m.' -> datetimes.
    Returns None for 'Closed' or anything without a range."""
    text = text.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    if "-" not in text:
        return None
    left, right = (part.strip() for part in text.split("-", 1))
    try:
        eh, em, period = _parse_time(right, None)
        try:
            sh, sm, _ = _parse_time(left, None)
        except ValueError:
            sh, sm, _ = _parse_time(left, period)  # bare left borrows right's am/pm
    except ValueError:
        return None
    start = datetime(day.year, day.month, day.day, sh, sm, tzinfo=TZ)
    end = datetime(day.year, day.month, day.day, eh, em, tzinfo=TZ)
    if end <= start:
        return None
    return start, end


# ---------------------------------------------------------------------------
# pool  (static accordion HTML)
# ---------------------------------------------------------------------------
def scrape_pool(html: str, now: datetime) -> list[Session]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Session] = []
    for body in soup.select("div.minimal-accordion-item-body"):
        for p in body.find_all("p"):
            strong = p.find("strong")
            if not strong:
                continue
            activity = strong.get_text(" ", strip=True)
            low = activity.lower()
            if "swim" not in low:
                continue
            if any(x in low for x in config.POOL_EXCLUDE_ACTIVITIES):
                continue
            ul = p.find_next_sibling("ul")
            if not ul:
                continue
            for day_li in ul.find_all("li", recursive=False):
                header = "".join(
                    t for t in day_li.find_all(string=True, recursive=False)
                ).strip()
                dm = _DAY_RE.search(header)
                if not dm or dm.group(2).lower() not in _MONTHS:
                    continue
                month, dnum = _MONTHS[dm.group(2).lower()], int(dm.group(3))
                day = date(infer_year(month, dnum, now), month, dnum)
                slots = day_li.find("ul")
                if not slots:
                    continue
                for slot in slots.find_all("li"):
                    txt = slot.get_text(" ", strip=True)
                    rng = parse_time_range(txt, day)
                    if not rng:
                        continue
                    pool = re.search(r"\b(25m|50m)\b", txt)
                    out.append(
                        Session(
                            activity=activity,
                            venue="Aquatic Centre",
                            start=rng[0],
                            end=rng[1],
                            source="pool",
                            sublocation=pool.group(1) if pool else None,
                        )
                    )
    return out


def run_pool(now: datetime) -> list[Session]:
    return scrape_pool(_fetch(config.POOL_URL), now)


# ---------------------------------------------------------------------------
# climbing wall  (static weekly pattern + closures from config)
# ---------------------------------------------------------------------------
def _closed(day: date) -> bool:
    return any(lo <= day <= hi for lo, hi in config.CLIMBING_CLOSURES)


def scrape_climbing(now: datetime) -> list[Session]:
    from .models import HORIZON_DAYS

    day0 = now.astimezone(TZ).date()
    out: list[Session] = []
    for offset in range(HORIZON_DAYS + 1):
        day = day0 + timedelta(days=offset)
        hours = config.CLIMBING_HOURS.get(day.weekday())
        if not hours or _closed(day):
            continue
        open_t, close_t = hours
        out.append(
            Session(
                activity=config.CLIMBING_ACTIVITY,
                venue=config.CLIMBING_VENUE,
                start=datetime.combine(day, open_t, TZ),
                end=datetime.combine(day, close_t, TZ),
                source="climbing",
            )
        )
    return out


run_climbing = scrape_climbing


# ---------------------------------------------------------------------------
# DevExpress ASPxScheduler "Weeks" view  (Playwright)
# Serves the oval running/skating pages and the KNES open-track page.
# ---------------------------------------------------------------------------
# DOM verified live on 2026-09-02: appointments are `div.dxscApt...` whose text
# reads "<start> - <end><subject>[(<location>)]", e.g.
#   "Noon - 2:00 PMRec. Fit Training(Oval Running Track)"
#   "Noon - 1:00 PMPublic Skating"          <- no location
# They are absolutely positioned, so the date comes from geometry: match each
# appointment's centre-x to a dated day-header cell's x-band, and its y to the
# nearest week-row header above it. Default view shows 2 weeks; a [title=Forward]
# button pages ahead.

_DX_APPT_RE = re.compile(
    r"^(Noon|Midnight|\d{1,2}(?::\d{2})?\s*(?:[AP]M)?)\s*[-–]\s*"
    r"(Noon|Midnight|\d{1,2}(?::\d{2})?\s*[AP]M)"
    r"(.+?)(?:\(([^)]*)\))?\s*$",  # trailing (location) is optional
    re.I,
)

_DX_COLLECT_JS = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const HDR = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*[-–]\s*([A-Z][a-z]{2})\s+(\d{1,2})$/;
  const cells = [];
  document.querySelectorAll('*').forEach(e => {
    const t = clean(e.textContent);
    if (HDR.test(t) && e.querySelectorAll('*').length <= 3) {
      const r = e.getBoundingClientRect();
      if (r.width > 0 && r.height > 0)
        cells.push({date: t.replace(/^.*?[-–]\s*/, ''), x: r.left, y: r.top, w: r.width});
    }
  });
  const appts = [];
  document.querySelectorAll('[class*="dxscApt"]').forEach(e => {
    if (!/(^|\s)dxscApt(\s|$)/.test(e.className)) return;
    const r = e.getBoundingClientRect();
    appts.push({text: clean(e.textContent), cx: r.left + r.width / 2, y: r.top});
  });
  return {cells, appts};
}
"""


def parse_dx_appointment(
    text: str, day: date
) -> tuple[datetime, datetime, str, str] | None:
    """'Noon - 2:00 PMRec. Fit Training(Oval Running Track)' ->
    (start, end, subject, location)."""
    m = _DX_APPT_RE.match(text.replace("\xa0", " ").strip())
    if not m:
        return None
    start_s, end_s, subject, location = m.groups()
    norm = lambda t: {"noon": "12:00 PM", "midnight": "12:00 AM"}.get(
        t.strip().lower(), t
    )
    rng = parse_time_range(f"{norm(start_s)} - {norm(end_s)}", day)
    if not rng:
        return None
    return rng[0], rng[1], subject.strip(), (location or "").strip()


def _parse_cell_date(text: str, now: datetime) -> date | None:
    """'Aug 31' -> date, with the year inferred from `now`."""
    dm = re.match(r"([A-Za-z]{3,})\s+(\d{1,2})", text.strip())
    if not dm or dm.group(1).lower() not in _MONTHS:
        return None
    month, dnum = _MONTHS[dm.group(1).lower()], int(dm.group(2))
    return date(infer_year(month, dnum, now), month, dnum)


def _dx_sessions(
    appts: list[dict], cells: list[dict], now: datetime, source: str, venue: str
) -> list[Session]:
    parsed: list[tuple[date, float, float, float]] = []
    for c in cells:
        d = _parse_cell_date(c["date"], now)
        if d:
            parsed.append((d, c["x"], c["y"], c["w"]))

    out: list[Session] = []
    for a in appts:
        column = [
            p for p in parsed if p[1] <= a["cx"] < p[1] + p[3] and p[2] < a["y"]
        ]
        if not column:
            continue
        day = max(column, key=lambda p: p[2])[0]  # nearest week-row header above
        got = parse_dx_appointment(a["text"], day)
        if not got:
            continue
        start, end, subject, location = got
        out.append(Session(subject, venue, start, end, source, location or None))
    return out


def _run_dx_scheduler(
    url: str, source: str, now: datetime, venue: str
) -> list[Session]:
    from playwright.sync_api import sync_playwright

    from .models import HORIZON_DAYS

    horizon_end = now.astimezone(TZ).date() + timedelta(days=HORIZON_DAYS)
    seen: set = set()
    sessions: list[Session] = []

    def furthest(cells: list[dict]) -> date | None:
        got = [d for d in (_parse_cell_date(c["date"], now) for c in cells) if d]
        return max(got) if got else None

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Keep Chromium's default UA: DevExpress sniffs it and disables the
        # ViewNavigator callbacks for an unrecognised browser string.
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url, wait_until="networkidle")
        try:
            page.wait_for_selector(".dxscControl_PlasticRed", timeout=15_000)
        except Exception:  # noqa: BLE001 - scheduler container missing; bail below
            pass
        # ponytail: fixed settle so the ASPxScheduler client script finishes
        # wiring its ViewNavigator before we click Forward. Swap for a readiness
        # probe if this proves flaky in CI.
        page.wait_for_timeout(3000)

        prev_furthest: date | None = None
        for _ in range(6):  # safety cap on forward pages
            data = page.evaluate(_DX_COLLECT_JS)
            for s in _dx_sessions(
                data["appts"], data["cells"], now, source, venue
            ):
                key = (s.start, s.end, s.activity, s.sublocation)
                if key not in seen:
                    seen.add(key)
                    sessions.append(s)

            here = furthest(data["cells"])
            if here is None or here == prev_furthest:
                break  # view didn't advance -> no more pages
            prev_furthest = here
            if here >= horizon_end:
                break
            fwd = page.query_selector('[title="Forward"]')
            if not fwd:
                break
            fwd.click()
            page.wait_for_timeout(4000)  # ponytail: fixed dwell for the repaint
        browser.close()
    return sessions


# ---------------------------------------------------------------------------
# active-living pages: a FullCalendar widget  (Playwright)
# ---------------------------------------------------------------------------
# schedules.active-living.ucalgary.ca (gym, gym track) renders FullCalendar.
# Each event is `a.fc-daygrid-event` whose text reads "<title><start> - <end><LOCATION>",
# e.g. "Open Gym Time6 AM - 7 AMRED GYM". The date is the `data-date="YYYY-MM-DD"`
# on the containing day cell. The Month view shows ~6 weeks at once.

_FC_EVENT_RE = re.compile(
    r"^(.+?)(\d{1,2}(?::\d{2})?\s*[AP]M)\s*[-–]\s*(\d{1,2}(?::\d{2})?\s*[AP]M)(.*)$",
    re.I,
)

_FC_COLLECT_JS = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const events = [];
  document.querySelectorAll('a.fc-daygrid-event').forEach(e => {
    let p = e, d = null;
    while (p) {
      const v = p.getAttribute && p.getAttribute('data-date');
      if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) { d = v; break; }
      p = p.parentElement;
    }
    if (d) events.push({date: d, text: clean(e.textContent)});
  });
  const dd = [...document.querySelectorAll('td[data-date],th[data-date]')]
    .map(e => e.getAttribute('data-date'))
    .filter(v => /^\d{4}-\d{2}-\d{2}$/.test(v)).sort();
  return {events, maxDate: dd.length ? dd[dd.length - 1] : null};
}
"""

_FC_MONTH_JS = (
    "() => { const b = [...document.querySelectorAll('button')]"
    ".find(x => x.textContent.trim() === 'Month' && /SelectorTab/.test(x.className || '')); if (b) b.click(); }"
)
_FC_FORWARD_JS = (
    "() => { const a = [...document.querySelectorAll('button')]"
    ".filter(x => /Adjustor/.test(x.className || '')); if (a.length) a[a.length - 1].click(); }"
)


def parse_fc_event(
    text: str, iso_date: str
) -> tuple[datetime, datetime, str, str] | None:
    """'Open Gym Time6 AM - 7 AMRED GYM' + '2026-09-02' ->
    (start, end, activity, location). The trailing ' Time' is stripped."""
    m = _FC_EVENT_RE.match(text.replace("\xa0", " ").strip())
    if not m:
        return None
    title, start_s, end_s, location = m.groups()
    try:
        day = date.fromisoformat(iso_date)
    except ValueError:
        return None
    rng = parse_time_range(f"{start_s} - {end_s}", day)
    if not rng:
        return None
    activity = re.sub(r"\s+Time$", "", title.strip())
    return rng[0], rng[1], activity, location.strip()


def _run_activeliving(
    url: str, source: str, now: datetime, venue: str
) -> list[Session]:
    from playwright.sync_api import sync_playwright

    from .models import HORIZON_DAYS

    horizon_end = (
        now.astimezone(TZ).date() + timedelta(days=HORIZON_DAYS)
    ).isoformat()
    seen: set = set()
    sessions: list[Session] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1200})
        page.goto(url, wait_until="networkidle")
        try:
            page.wait_for_selector("a.fc-daygrid-event", timeout=20_000)
        except Exception:  # noqa: BLE001 - an empty view has no events
            pass
        page.evaluate(_FC_MONTH_JS)  # Month view ≈ 6 weeks in one grid
        page.wait_for_timeout(3500)

        prev_max: str | None = None
        for _ in range(3):  # month grid usually covers the horizon on its own
            data = page.evaluate(_FC_COLLECT_JS)
            for ev in data["events"]:
                got = parse_fc_event(ev["text"], ev["date"])
                if not got:
                    continue
                start, end, activity, location = got
                key = (start, end, activity, location)
                if key in seen:
                    continue
                seen.add(key)
                sessions.append(
                    Session(activity, venue, start, end, source, location or None)
                )
            mx = data["maxDate"]
            if not mx or mx == prev_max or mx >= horizon_end:
                break
            prev_max = mx
            page.evaluate(_FC_FORWARD_JS)
            page.wait_for_timeout(3500)
        browser.close()
    return sessions


def run_gym(now: datetime) -> list[Session]:
    excluded = tuple(x.casefold() for x in config.GYM_EXCLUDE_SUBLOCATIONS)
    return [
        s
        for s in _run_activeliving(config.GYM_URL, "gym", now, "Kinesiology Gym")
        if s.activity in config.GYM_ACTIVITIES
        and not any(e in (s.sublocation or "").casefold() for e in excluded)
    ]


def run_gym_track(now: datetime) -> list[Session]:
    # KNES track page is the same DevExpress scheduler as the oval.
    return [
        s
        for s in _run_dx_scheduler(
            config.GYM_TRACK_URL, "gym_track", now, "Kinesiology Track"
        )
        if any(
            k.lower() in s.activity.lower()
            for k in config.GYM_TRACK_INCLUDE_SUBJECTS
        )
    ]


def run_oval_running(now: datetime) -> list[Session]:
    return [
        s
        for s in _run_dx_scheduler(
            config.OVAL_RUNNING_URL, "oval_running", now, "Olympic Oval"
        )
        if any(
            k.lower() in s.activity.lower()
            for k in config.OVAL_RUNNING_INCLUDE_SUBJECTS
        )
    ]


def run_oval_skate(now: datetime) -> list[Session]:
    return [
        s
        for s in _run_dx_scheduler(
            config.OVAL_SKATE_URL, "oval_skate", now, "Olympic Oval"
        )
        if any(
            k.lower() in s.activity.lower()
            for k in config.OVAL_SKATE_INCLUDE_SUBJECTS
        )
    ]


# name -> callable(now) -> list[Session]
SCRAPERS = {
    "pool": run_pool,
    "climbing": run_climbing,
    "gym": run_gym,
    "gym_track": run_gym_track,
    "oval_running": run_oval_running,
    "oval_skate": run_oval_skate,
}
