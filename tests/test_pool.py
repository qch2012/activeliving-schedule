from datetime import date, datetime
from pathlib import Path

import pytest

from alsched.models import TZ
from alsched.scrapers import parse_time_range, scrape_pool

FIXTURE = (Path(__file__).parent / "fixtures" / "pool.html").read_text(encoding="utf-8")
NOW = datetime(2026, 9, 1, tzinfo=TZ)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("11 a.m. - 2 p.m. 25m", (11, 0, 14, 0)),
        ("5 - 10 p.m. 25m *Limited Lanes", (17, 0, 22, 0)),
        ("7:30 - 9:30 a.m.", (7, 30, 9, 30)),
        ("3:30 - 8:30 p.m.", (15, 30, 20, 30)),
        ("10 a.m. - 4:30 p.m.", (10, 0, 16, 30)),
    ],
)
def test_parse_time_range(text, expected):
    rng = parse_time_range(text, date(2026, 9, 3))
    assert rng is not None
    start, end = rng
    assert (start.hour, start.minute, end.hour, end.minute) == expected


@pytest.mark.parametrize("text", ["Closed", "", "some note with no time"])
def test_parse_time_range_rejects_non_ranges(text):
    assert parse_time_range(text, date(2026, 9, 3)) is None


def test_scrape_pool_extracts_sessions():
    sessions = scrape_pool(FIXTURE, NOW)
    assert sessions, "expected at least one pool session from the fixture"

    known = [
        s
        for s in sessions
        if s.activity == "Adult/Youth Lane Swim"
        and s.start == datetime(2026, 9, 3, 11, 0, tzinfo=TZ)
    ]
    assert known, "missing Thu Sep 3 11am Lane Swim"
    assert known[0].end == datetime(2026, 9, 3, 14, 0, tzinfo=TZ)
    assert known[0].venue == "Aquatic Centre"
    assert known[0].sublocation == "25m"
    assert known[0].source == "pool"


def test_scrape_pool_excludes_inflatable_and_closed_days():
    sessions = scrape_pool(FIXTURE, NOW)
    assert not any("inflatable" in s.activity.lower() for s in sessions)
    assert not any(s.start.date() == date(2026, 8, 31) for s in sessions)  # all "Closed"
