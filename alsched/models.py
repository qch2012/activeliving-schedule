"""The domain model. See CONTEXT.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Edmonton")
HORIZON_DAYS = 28
WEEKDAY_CUTOFF = time(15, 0)  # parking pass starts at 3:00pm


@dataclass(frozen=True)
class Session:
    activity: str
    venue: str
    start: datetime  # tz-aware, America/Edmonton
    end: datetime
    source: str
    sublocation: str | None = None


def in_window(s: Session) -> bool:
    """Availability Window: weekends unrestricted; on weekdays the session must
    still be running after the 15:00 parking-pass cutoff."""
    if s.start.weekday() >= 5:  # Saturday, Sunday
        return True
    # ponytail: compares clock time only, so a session ending after midnight
    # would read as early-morning and be dropped. Rec facilities close well
    # before midnight, so this never bites; revisit if that changes.
    return s.end.time() > WEEKDAY_CUTOFF


def select(sessions: list[Session], now: datetime) -> list[Session]:
    """Apply Horizon + Availability Window, drop anything already finished,
    dedupe, and sort chronologically."""
    day0 = now.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_end = day0 + timedelta(days=HORIZON_DAYS)
    keep = {
        s
        for s in sessions
        if s.end >= now and day0 <= s.start < horizon_end and in_window(s)
    }
    return sorted(keep, key=lambda s: (s.start, s.end, s.activity, s.venue))
