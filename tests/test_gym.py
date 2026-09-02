"""Pure-logic tests for the active-living (FullCalendar) event parser. Strings
are real event text captured from the live gym page on 2026-09-02."""

from datetime import datetime

import pytest

from alsched.models import TZ
from alsched.scrapers import parse_fc_event


@pytest.mark.parametrize(
    "text,date,expected",
    [
        ("Open Gym Time6 AM - 7 AMRED GYM", "2026-09-02", (6, 0, 7, 0, "Open Gym", "RED GYM")),
        ("Badminton12 PM - 1 PMRED GYM", "2026-09-02", (12, 0, 13, 0, "Badminton", "RED GYM")),
        ("Open Gym Time1:15 PM - 3:45 PMRED GYM", "2026-09-02", (13, 15, 15, 45, "Open Gym", "RED GYM")),
        ("Open Gym Time10 AM - 11:45 AMGOLD GYM", "2026-09-02", (10, 0, 11, 45, "Open Gym", "GOLD GYM")),
        ("Basketball8 AM - 11 AMJS-EAST", "2026-09-02", (8, 0, 11, 0, "Basketball", "JS-EAST")),
    ],
)
def test_parse_fc_event(text, date, expected):
    start, end, activity, location = parse_fc_event(text, date)
    sh, sm, eh, em, act, loc = expected
    assert (start.hour, start.minute, end.hour, end.minute) == (sh, sm, eh, em)
    assert start.date().isoformat() == date
    assert start.tzinfo == TZ
    assert (activity, location) == (act, loc)


def test_parse_fc_event_rejects_junk():
    assert parse_fc_event("No events", "2026-09-02") is None
    assert parse_fc_event("Open Gym Time6 AM - 7 AMRED GYM", "not-a-date") is None
