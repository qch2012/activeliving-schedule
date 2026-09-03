import re
from datetime import datetime

from icalendar import Calendar

from alsched.models import TZ, Session
from alsched.render import html_page, ics_feed

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=TZ)
SESSIONS = [
    Session("Open Gym", "Kinesiology Gym", datetime(2026, 9, 2, 17, 45, tzinfo=TZ),
            datetime(2026, 9, 2, 22, 30, tzinfo=TZ), "gym", "Red Gym"),
    Session("Adult/Youth Lane Swim", "Aquatic Centre", datetime(2026, 9, 3, 19, 30, tzinfo=TZ),
            datetime(2026, 9, 3, 22, 0, tzinfo=TZ), "pool", "25m"),
]


def test_html_lists_by_day_renames_and_shortens_place():
    page = html_page(SESSIONS, {}, NOW)
    assert "Wednesday 2 September" in page
    assert "Thursday 3 September" in page
    assert "17:45–22:30" in page                     # list row keeps the range
    assert ">Red Gym<" in page and "Kin Gym / Red Gym" not in page  # standalone sub-location
    assert ">Lane swim<" in page                     # Adult/Youth Lane Swim renamed
    assert "Adult/Youth Lane Swim" not in page
    assert "generated 2026-09-02 08:00" in page
    assert "failed" not in page.lower()


def test_html_has_category_filter():
    page = html_page(SESSIONS, {}, NOW)
    assert '<div class="filters">' in page
    assert 'data-cat="gym"' in page and 'data-cat="swim"' in page
    assert "🤸 Gym" in page and "🏊 Swim" in page      # emoji + label chips
    assert '<li data-cat="gym">' in page
    assert 'aria-pressed="true"' in page
    assert 'class="reset"' in page
    assert "localStorage" in page
    assert '<section data-day="2026-09-02">' in page


def test_html_week_grid_and_chip_layout():
    page = html_page(SESSIONS, {}, NOW)
    assert 'id="view-cal"' in page and 'id="view-list"' in page
    assert 'data-view="cal"' in page and 'data-view="list"' in page
    assert '<div class="week" data-monday="2026-08-31">' in page
    assert 'data-cat="gym"' in page and 'data-cat="swim"' in page
    assert 'id="nav-prev"' in page and 'id="nav-next"' in page
    # "today" is highlighted in the browser, not baked in at build time
    assert '<div class="col" data-date="2026-09-02">' in page
    assert 'toLocaleDateString("en-CA", {timeZone: "America/Edmonton"})' in page
    assert 'classList.toggle("is-today"' in page

    # calendar chip: three stacked lines, no emoji
    chip = re.search(r'<div class="chip [^"]*" data-cat="gym">(.*?)</div>', page).group(1)
    assert chip == (
        '<span class="ca">Open Gym</span>'
        '<span class="ct">17:45–22:30</span>'
        '<span class="cv">Red Gym</span>'
    )
    assert "🤸" not in chip           # emoji dropped from the chip
    assert "🤸 Gym" in page           # ...but kept on the filter chip


def test_run_category_two_colours_one_filter():
    oval = Session("Rec. Fit Training", "Olympic Oval",
                   datetime(2026, 9, 4, 15, 30, tzinfo=TZ),
                   datetime(2026, 9, 4, 17, 0, tzinfo=TZ), "oval_running", "Oval Running Track")
    track = Session("Drop In - Running", "Kinesiology Track",
                    datetime(2026, 9, 4, 18, 0, tzinfo=TZ),
                    datetime(2026, 9, 4, 20, 0, tzinfo=TZ), "gym_track", "Kin Track 3-6")
    page = html_page([oval, track], {}, NOW)
    # one Run filter toggle, both chips still filter as run
    assert page.count("🏃 Run") == 1
    assert page.count('data-cat="run"') >= 3
    # ...but two different chip colours
    assert '<div class="chip cat-run-oval" data-cat="run">' in page
    assert '<div class="chip cat-run-track" data-cat="run">' in page
    assert ">Oval Running<" in page and "Rec. Fit Training" not in page
    assert ">Track running<" in page
    assert "Kin Track / 3-6" in page
    assert "Oval Running Track" not in page


def test_week_grid_covers_full_horizon_span():
    far = Session("Climbing Wall", "Outdoor Centre Climbing Wall",
                  datetime(2026, 9, 28, 12, 0, tzinfo=TZ),
                  datetime(2026, 9, 28, 18, 0, tzinfo=TZ), "climbing")
    page = html_page(SESSIONS + [far], {}, NOW)
    assert 'data-monday="2026-09-28"' in page
    assert 'data-date="2026-09-28"' in page
    # no sub-location and place == activity -> place omitted, just "🧗 Climbing Wall"
    assert "Climbing Wall / Climbing Wall" not in page


def test_html_shows_failures():
    page = html_page(SESSIONS, {"oval_running": "TimeoutError: boom"}, NOW)
    assert "Some sources failed" in page
    assert "Oval running: TimeoutError: boom" in page


def test_ics_round_trips_with_tz():
    cal = Calendar.from_ical(ics_feed(SESSIONS, NOW))
    events = list(cal.walk("VEVENT"))
    assert len(events) == 2
    starts = sorted(e.decoded("dtstart") for e in events)
    assert starts[0] == datetime(2026, 9, 2, 17, 45, tzinfo=TZ)
    assert any(str(e["summary"]) == "Open Gym · Kinesiology Gym" for e in events)
    assert b"America/Edmonton" in ics_feed(SESSIONS, NOW)


def test_ics_uid_is_stable():
    assert ics_feed(SESSIONS, NOW).count(b"@activeliving-schedule") == 2
    assert ics_feed(SESSIONS, NOW) == ics_feed(SESSIONS, NOW)
