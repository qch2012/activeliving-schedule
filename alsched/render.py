"""Turn the selected sessions into docs/index.html + docs/schedule.ics.

The page (see docs/adr/0002-week-grid-view.md) is a single static file with two
views — a Week grid and a chronological List — plus an activity filter, all
driven by vanilla JS over localStorage. Every week in the horizon is
pre-rendered; the script just shows one.
"""

from __future__ import annotations

import hashlib
import html
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from icalendar import Calendar, Event

from . import config
from .models import TZ, Session

DOCS = Path(__file__).resolve().parent.parent / "docs"

_SOURCE_LABEL = {
    "pool": "Pool",
    "climbing": "Climbing wall",
    "gym": "Gym",
    "gym_track": "Gym track",
    "oval_running": "Oval running",
    "oval_skate": "Oval skating",
}

def _cat(activity: str) -> tuple[str, str]:
    """activity -> (category slug, emoji)."""
    return config.ACTIVITY_CATEGORY.get(activity, ("other", "•"))


def _disp(activity: str) -> str:
    return config.ACTIVITY_RENAME.get(activity, activity)


def _place(s: Session) -> str:
    """Short venue, with the sub-location appended (venue prefix stripped, SHOUTY
    text de-capsed) when it adds something."""
    venue = config.VENUE_SHORT.get(s.venue, s.venue)
    sub = s.sublocation
    if not sub or sub in config.SUBLOCATION_HIDE:
        return venue
    low = sub.lower()
    for prefix in (venue + " ", s.venue + " "):
        if low.startswith(prefix.lower()):
            sub = sub[len(prefix) :]
            break
    if sub.isupper():
        sub = sub.title()
    if sub in config.SUBLOCATION_STANDALONE:
        return sub
    return f"{venue} / {sub}" if sub else venue


def render(
    sessions: list[Session],
    failures: dict[str, str],
    now: datetime,
    out_dir: Path = DOCS,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        html_page(sessions, failures, now), encoding="utf-8"
    )
    (out_dir / "schedule.ics").write_bytes(ics_feed(sessions, now))
    (out_dir / ".nojekyll").touch()


# ---------------------------------------------------------------------------
def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _tail(place: str, disp: str, sep: str) -> str:
    if not place or place == disp:
        return ""
    return f'<span class="w">{sep}{_esc(place)}</span>'


def _row(s: Session) -> str:
    cat, emoji = _cat(s.activity)
    disp = _disp(s.activity)
    return (
        f'<li data-cat="{cat}">'
        f'<span class="t">{s.start:%H:%M}–{s.end:%H:%M}</span> {emoji} '
        f'<span class="a">{_esc(disp)}</span>{_tail(_place(s), disp, " · ")}</li>'
    )


def _chip(s: Session) -> str:
    cat, _ = _cat(s.activity)
    colour = config.ACTIVITY_COLOR.get(s.activity, cat)
    disp = _disp(s.activity)
    place = _place(s)
    line3 = f'<span class="cv">{_esc(place)}</span>' if place and place != disp else ""
    return (
        f'<div class="chip cat-{colour}" data-cat="{cat}">'
        f'<span class="ca">{_esc(disp)}</span>'
        f'<span class="ct">{s.start:%H:%M}–{s.end:%H:%M}</span>'
        f"{line3}</div>"
    )


def _filters(sessions: list[Session]) -> str:
    present: dict[str, str] = {}
    for s in sessions:
        cat, emoji = _cat(s.activity)
        present.setdefault(cat, emoji)
    toggle = (
        '<span class="views">'
        '<button type="button" class="vbtn" data-view="cal" aria-pressed="true">Calendar</button>'
        '<button type="button" class="vbtn" data-view="list" aria-pressed="false">List</button>'
        "</span>"
    )
    if not present:
        return f'<div class="filters">{toggle}</div>'
    chips = "".join(
        f'<button type="button" class="fchip cat-{c}" data-cat="{c}"'
        f' aria-pressed="true">{present[c]} {_esc(config.CATEGORY_LABEL.get(c, c))}</button>'
        for c in config.CATEGORY_ORDER
        if c in present
    )
    return (
        f'<div class="filters">{toggle}{chips}'
        '<button type="button" class="reset">Reset</button></div>'
    )


def _week_grid(sessions: list[Session], now: datetime) -> str:
    by_date: dict = defaultdict(list)
    for s in sessions:
        by_date[s.start.date()].append(s)

    today = now.astimezone(TZ).date()
    monday0 = today - timedelta(days=today.weekday())
    last = max(by_date) if by_date else today
    end = last + timedelta(days=6 - last.weekday())  # that week's Sunday

    weeks = []
    d = monday0
    while d <= end:
        cols = []
        for i in range(7):
            day = d + timedelta(days=i)
            chips = "".join(
                _chip(s)
                for s in sorted(
                    by_date.get(day, []),
                    key=lambda s: (s.start, s.end, s.activity),
                )
            )
            cls = "col is-today" if day == today else "col"
            cols.append(
                f'<div class="{cls}" data-date="{day.isoformat()}">'
                f'<div class="colh">{day:%a %-d}</div>'
                f'<div class="chips">{chips}</div></div>'
            )
        weeks.append(
            f'<div class="week" data-monday="{d.isoformat()}">{"".join(cols)}</div>'
        )
        d += timedelta(days=7)

    nav = (
        '<div class="calnav">'
        '<button type="button" id="nav-prev" aria-label="previous">‹</button>'
        '<span id="nav-label"></span>'
        '<button type="button" id="nav-next" aria-label="next">›</button>'
        '<button type="button" id="nav-today" class="reset" hidden>Today</button>'
        "</div>"
    )
    note = '<p class="empty-note" hidden>Nothing here — try another week or clear filters.</p>'
    return f'<div id="view-cal">{nav}{"".join(weeks)}{note}</div>'


def html_page(
    sessions: list[Session], failures: dict[str, str], now: datetime
) -> str:
    by_day: dict = defaultdict(list)
    for s in sessions:
        by_day[s.start.date()].append(s)
    day_sections = "".join(
        f'<section data-day="{d.isoformat()}"><h2>{d:%A %-d %B}</h2><ul>'
        + "".join(
            _row(s)
            for s in sorted(by_day[d], key=lambda s: (s.start, s.end, s.activity))
        )
        + "</ul></section>"
        for d in sorted(by_day)
    ) or "<p>No sessions in the next 4 weeks.</p>"
    list_view = f'<div id="view-list" hidden>{day_sections}</div>'

    warn = ""
    if failures:
        items = "".join(
            f"<li>{_esc(_SOURCE_LABEL.get(k, k))}: {_esc(v)}</li>"
            for k, v in sorted(failures.items())
        )
        warn = (
            '<div class="warn"><strong>Some sources failed this run</strong>'
            f"<ul>{items}</ul></div>"
        )

    return (
        _PAGE.replace("%%GENERATED%%", now.strftime("%Y-%m-%d %H:%M %Z"))
        .replace("%%FILTERS%%", _filters(sessions))
        .replace("%%WARN%%", warn)
        .replace("%%CAL%%", _week_grid(sessions, now))
        .replace("%%LIST%%", list_view)
    )


_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Active Living schedule</title>
<style>
  *{box-sizing:border-box}
  [hidden]{display:none!important}
  body{font:16px/1.5 system-ui,-apple-system,sans-serif;margin:0;padding:0 1rem 2rem;
       max-width:60rem;margin-inline:auto;color:#111}
  h1{font-size:1.2rem;margin:.8rem 0 .1rem}
  .sub{color:#666;font-size:.8rem;margin:0 0 .5rem}
  .filters{position:sticky;top:0;z-index:2;background:#fff;padding:.5rem 0;
           border-bottom:1px solid #ddd;display:flex;flex-wrap:wrap;gap:.35rem;align-items:center}
  .filters button{font:inherit;font-size:.78rem;padding:.2rem .55rem;border-radius:1rem;
                  border:1px solid #bbb;background:#f2f2f2;color:#444;cursor:pointer}
  .views{display:flex;gap:.25rem;margin-right:.25rem}
  .vbtn[aria-pressed="true"]{background:#111;border-color:#111;color:#fff}
  .cat-run,.cat-run-oval{--c:#e0574a}
  .cat-run-track{--c:#7a1f1f}
  .cat-swim{--c:#2f7fd1}
  .cat-badminton{--c:#c26a00}
  .cat-gym{--c:#1f9d63}
  .cat-skate{--c:#8b5cf6}
  .cat-climb{--c:#0e8fa8}
  .cat-other{--c:#999}
  .fchip{border-left:3px solid var(--c,#bbb)}
  .fchip[aria-pressed="true"]{background:#111;border-color:#111;border-left-color:var(--c,#111);color:#fff}
  .filters .reset{margin-left:auto;border-style:dashed;background:none}
  .calnav{display:flex;gap:.5rem;align-items:center;padding:.5rem 0;font-size:.9rem}
  .calnav button{font:inherit;padding:.15rem .6rem;border:1px solid #bbb;border-radius:.3rem;
                 background:#f2f2f2;cursor:pointer}
  #nav-label{font-weight:600}
  .week{display:grid;grid-template-columns:repeat(7,1fr);gap:.35rem;align-items:start}
  .col{border:1px solid #e5e5e5;border-radius:.4rem;display:flex;flex-direction:column;
       max-height:calc(100vh - 210px)}  /* keeps the page from scrolling on wide screens */
  .colh{font-size:.78rem;font-weight:600;padding:.3rem .4rem;border-bottom:1px solid #eee;
        position:sticky;top:0;background:#fafafa;border-radius:.4rem .4rem 0 0}
  .col.is-today .colh{color:#3b82f6}
  .chips{overflow-y:auto;padding:.25rem;display:flex;flex-direction:column;gap:.25rem}
  .chip{font-size:.72rem;line-height:1.25;padding:.3rem .4rem;border:1px solid #ddd;
        border-left:3px solid var(--c,#999);border-radius:.3rem;background:#fafafa;color:#222;
        display:flex;flex-direction:column}
  .chip .ca{font-weight:600}
  .chip .ct{font-variant-numeric:tabular-nums;color:#555}
  .chip .cv,#view-list .w{color:#666}
  .empty-note{color:#666;font-size:.9rem;padding:1rem 0}
  #view-list h2{font-size:1rem;margin:1.1rem 0 .3rem;border-bottom:1px solid #ddd;padding-bottom:.2rem}
  #view-list ul{list-style:none;margin:0;padding:0}
  #view-list li{display:flex;flex-wrap:wrap;gap:.5rem;padding:.35rem 0}
  #view-list .t{font-variant-numeric:tabular-nums;color:#333;min-width:6.5rem}
  #view-list .a{font-weight:600}
  .warn{background:#fff3cd;border:1px solid #ffe69c;padding:.6rem .8rem;border-radius:.4rem;
        font-size:.9rem;margin:.75rem 0}
  .warn ul{list-style:disc;padding-left:1.2rem;margin:.3rem 0 0}
  @media(max-width:700px){
    body{max-width:32rem}
    .week{grid-template-columns:1fr}
    .col{max-height:none}
    .chips{overflow:visible}
  }
  @media(prefers-color-scheme:dark){
    body{background:#111;color:#eee}
    .sub,.chip .ct,.chip .cv,.empty-note,#view-list .w{color:#999}
    .filters,.colh{background:#111}
    .filters{border-color:#333}
    .filters button,.calnav button{background:#222;border-color:#444;color:#ccc}
    .vbtn[aria-pressed="true"],.fchip[aria-pressed="true"]{background:#eee;border-color:#eee;color:#111}
    .col{border-color:#333}.colh{background:#1b1b1b;border-color:#333}
    .chip{background:#1b1b1b;border-color:#333;color:#ddd}
    #view-list h2{border-color:#333}#view-list .t{color:#bbb}
    .warn{background:#332b00;border-color:#665600}
  }
</style>
<h1>UCalgary Active Living</h1>
<p class="sub">Weekdays after 3pm and all weekend, next 4 weeks &middot; generated %%GENERATED%%</p>
%%FILTERS%%
%%WARN%%
%%CAL%%
%%LIST%%
<script>
(function () {
  var KEY = "al-view-state";
  var st = {hidden: [], view: "cal", anchor: null};
  try {
    var saved = JSON.parse(localStorage.getItem(KEY));
    if (saved) { st.hidden = saved.hidden || []; st.view = saved.view || "cal"; st.anchor = saved.anchor || null; }
  } catch (e) {}
  var hidden = new Set(st.hidden);  // hidden category slugs

  var weeks = [].slice.call(document.querySelectorAll("#view-cal .week"));
  var cols = [].slice.call(document.querySelectorAll("#view-cal .col"));
  var allDates = cols.map(function (c) { return c.getAttribute("data-date"); });
  var todayCol = document.querySelector("#view-cal .col.is-today");
  var today = todayCol ? todayCol.getAttribute("data-date") : (allDates[0] || null);
  var minDate = allDates[0], maxDate = allDates[allDates.length - 1];
  if (!st.anchor || allDates.indexOf(st.anchor) < 0) st.anchor = today || minDate;

  function narrow() { return window.matchMedia("(max-width: 700px)").matches; }
  function mondayOf(iso) {
    var d = new Date(iso + "T00:00");
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d.toISOString().slice(0, 10);
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify({hidden: Array.from(hidden), view: st.view, anchor: st.anchor})); } catch (e) {}
  }

  function applyFilter() {
    document.querySelectorAll("li[data-cat], .chip[data-cat]").forEach(function (el) {
      el.hidden = hidden.has(el.getAttribute("data-cat"));
    });
    document.querySelectorAll("#view-list section[data-day]").forEach(function (sec) {
      sec.hidden = !sec.querySelector("li[data-cat]:not([hidden])");
    });
    document.querySelectorAll(".fchip").forEach(function (b) {
      b.setAttribute("aria-pressed", hidden.has(b.getAttribute("data-cat")) ? "false" : "true");
    });
  }

  function render() {
    document.getElementById("view-cal").hidden = st.view !== "cal";
    document.getElementById("view-list").hidden = st.view !== "list";
    document.querySelectorAll(".vbtn").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-view") === st.view ? "true" : "false");
    });

    var nd = narrow(), mon = mondayOf(st.anchor);
    weeks.forEach(function (w) { w.hidden = w.getAttribute("data-monday") !== mon; });
    cols.forEach(function (c) {
      c.hidden = nd && c.getAttribute("data-date") !== st.anchor;
    });

    var scope = nd
      ? document.querySelector('#view-cal .col[data-date="' + st.anchor + '"]')
      : weeks.filter(function (w) { return !w.hidden; })[0];
    var note = document.querySelector(".empty-note");
    if (note) note.hidden = st.view !== "cal" || !!(scope && scope.querySelector(".chip:not([hidden])"));

    var lbl = document.getElementById("nav-label");
    if (lbl) {
      var opt = {month: "short", day: "numeric"};
      lbl.textContent = nd
        ? new Date(st.anchor + "T00:00").toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"})
        : "Week of " + new Date(mon + "T00:00").toLocaleDateString(undefined, opt);
    }
    var tb = document.getElementById("nav-today");
    if (tb) tb.hidden = st.view !== "cal" || st.anchor === (today || minDate);
  }

  function step(dir) {
    var d = new Date(st.anchor + "T00:00");
    d.setDate(d.getDate() + dir * (narrow() ? 1 : 7));
    var iso = d.toISOString().slice(0, 10);
    if (iso < minDate) iso = minDate;
    if (iso > maxDate) iso = maxDate;
    st.anchor = iso; save(); render();
  }

  document.querySelectorAll(".fchip").forEach(function (b) {
    b.addEventListener("click", function () {
      var c = b.getAttribute("data-cat");
      hidden.has(c) ? hidden.delete(c) : hidden.add(c);
      save(); applyFilter(); render();
    });
  });
  var reset = document.querySelector(".filters .reset");
  if (reset) reset.addEventListener("click", function () { hidden.clear(); save(); applyFilter(); render(); });
  document.querySelectorAll(".vbtn").forEach(function (b) {
    b.addEventListener("click", function () { st.view = b.getAttribute("data-view"); save(); render(); });
  });
  var prev = document.getElementById("nav-prev"), next = document.getElementById("nav-next"),
      tday = document.getElementById("nav-today");
  if (prev) prev.addEventListener("click", function () { step(-1); });
  if (next) next.addEventListener("click", function () { step(1); });
  if (tday) tday.addEventListener("click", function () { st.anchor = today || minDate; save(); render(); });
  var t;
  window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(render, 150); });

  applyFilter();
  render();
})();
</script>
"""


# ---------------------------------------------------------------------------
def _uid(s: Session) -> str:
    key = f"{s.start.isoformat()}|{s.end.isoformat()}|{s.activity}|{s.venue}|{s.sublocation}"
    return hashlib.md5(key.encode()).hexdigest() + "@activeliving-schedule"


def ics_feed(sessions: list[Session], now: datetime) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//activeliving-schedule//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "UCalgary Active Living")
    for s in sessions:
        ev = Event()
        ev.add("uid", _uid(s))
        ev.add("dtstamp", now)
        ev.add("dtstart", s.start)
        ev.add("dtend", s.end)
        ev.add("summary", f"{s.activity} · {s.venue}")
        ev.add("location", s.sublocation or s.venue)
        ev.add("categories", [s.activity])
        cal.add_component(ev)
    try:
        cal.add_missing_timezones()  # emit VTIMEZONE for America/Edmonton
    except Exception:  # noqa: BLE001 - older icalendar; feed is still valid
        pass
    return cal.to_ical()
