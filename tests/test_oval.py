"""Pure-logic tests for the oval (DevExpress) extractor: the appointment-text
regex and the geometry -> date mapping. Numbers are real values captured from
the live PublicRunning page on 2026-09-02."""

from datetime import date, datetime

from alsched.models import TZ
from alsched.scrapers import _dx_sessions, parse_dx_appointment


def test_parse_dx_appointment_noon_start():
    got = parse_dx_appointment(
        "Noon - 2:00 PMRec. Fit Training(Oval Running Track)", date(2026, 9, 8)
    )
    assert got == (
        datetime(2026, 9, 8, 12, 0, tzinfo=TZ),
        datetime(2026, 9, 8, 14, 0, tzinfo=TZ),
        "Rec. Fit Training",
        "Oval Running Track",
    )


def test_parse_dx_appointment_evening_and_subject():
    start, end, subject, location = parse_dx_appointment(
        "9:00 PM - 10:00 PMHP Running(Oval Running Track)", date(2026, 9, 8)
    )
    assert (start.hour, end.hour) == (21, 22)
    assert subject == "HP Running"
    assert location == "Oval Running Track"


def test_parse_dx_appointment_rejects_junk():
    assert parse_dx_appointment("No Public Running", date(2026, 9, 8)) is None


def test_parse_dx_appointment_without_location():
    # oval skate subjects carry no "(location)" — regression for the bug where
    # every location-less appointment was silently dropped.
    got = parse_dx_appointment("Noon - 1:00 PMPublic Skating", date(2026, 9, 15))
    assert got == (
        datetime(2026, 9, 15, 12, 0, tzinfo=TZ),
        datetime(2026, 9, 15, 13, 0, tzinfo=TZ),
        "Public Skating",
        "",
    )


def test_dx_sessions_location_none_when_absent():
    cells = [{"date": "Sep 15", "x": 145, "y": 500, "w": 169}]
    appts = [{"text": "2:00 PM - 5:00 PMPublic Skating", "cx": 200, "y": 600}]
    sessions = _dx_sessions(
        appts, cells, datetime(2026, 9, 1, tzinfo=TZ), "oval_skate", "Olympic Oval"
    )
    assert len(sessions) == 1
    assert sessions[0].activity == "Public Skating"
    assert sessions[0].sublocation is None


def test_geometry_maps_appointment_to_second_week_column():
    # 7-column grid, week rows at y=507 and y=696; appt centre-x 398 sits in the
    # Sep 1 / Sep 8 column, y=726 puts it under the second week's header.
    cells = [
        {"date": "Aug 31", "x": 145, "y": 507, "w": 169},
        {"date": "Sep 1", "x": 314, "y": 507, "w": 169},
        {"date": "Sep 7", "x": 145, "y": 696, "w": 169},
        {"date": "Sep 8", "x": 314, "y": 696, "w": 169},
    ]
    appts = [
        {"text": "Noon - 2:00 PMRec. Fit Training(Oval Running Track)", "cx": 398, "y": 726}
    ]
    sessions = _dx_sessions(
        appts, cells, datetime(2026, 9, 1, tzinfo=TZ), "oval_running", "Olympic Oval"
    )
    assert len(sessions) == 1
    s = sessions[0]
    assert s.start == datetime(2026, 9, 8, 12, 0, tzinfo=TZ)
    assert s.activity == "Rec. Fit Training"
    assert s.sublocation == "Oval Running Track"
    assert s.source == "oval_running"
