from datetime import datetime

from alsched.models import TZ
from alsched.scrapers import scrape_climbing


def test_expands_weekly_pattern():
    sessions = scrape_climbing(datetime(2026, 9, 15, tzinfo=TZ))  # after summer closure
    assert sessions

    monday = next(s for s in sessions if s.start.weekday() == 0)
    assert (monday.start.hour, monday.start.minute) == (11, 30)
    assert (monday.end.hour, monday.end.minute) == (18, 30)

    thursday = next(s for s in sessions if s.start.weekday() == 3)
    assert (thursday.end.hour, thursday.end.minute) == (17, 0)

    assert all(s.source == "climbing" for s in sessions)


def test_summer_closure_suppresses_everything():
    # 2026-07-01 .. +28d sits entirely inside the Jun 22 - Sep 8 closure
    assert scrape_climbing(datetime(2026, 7, 1, tzinfo=TZ)) == []
