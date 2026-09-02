from datetime import datetime, timedelta

from alsched.models import TZ, Session, in_window, select


def s(start, end, activity="X", venue="V", source="src", sub=None):
    return Session(activity, venue, start, end, source, sub)


def dt(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_weekday_needs_to_run_past_3pm():
    # 2026-09-02 is a Wednesday
    assert in_window(s(dt(2026, 9, 2, 12), dt(2026, 9, 2, 14))) is False
    assert in_window(s(dt(2026, 9, 2, 12), dt(2026, 9, 2, 15))) is False  # not strictly after
    assert in_window(s(dt(2026, 9, 2, 14), dt(2026, 9, 2, 17))) is True


def test_weekend_is_unrestricted():
    # 2026-09-05 is a Saturday
    assert in_window(s(dt(2026, 9, 5, 7), dt(2026, 9, 5, 9))) is True


def test_select_drops_past_and_far_future_dedupes_and_sorts():
    now = dt(2026, 9, 2, 10)
    past = s(dt(2026, 9, 2, 6), dt(2026, 9, 2, 8))
    beyond = s(dt(2026, 10, 5, 16), dt(2026, 10, 5, 18))  # > 28 days out
    later = s(dt(2026, 9, 2, 16), dt(2026, 9, 2, 18), activity="B")
    sooner = s(dt(2026, 9, 2, 15, 30), dt(2026, 9, 2, 17), activity="A")

    out = select([past, beyond, later, sooner, sooner], now)

    assert out == [sooner, later]
