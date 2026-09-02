"""Run every scraper best-effort, filter, and render docs/index.html +
docs/schedule.ics. A scraper that raises is reported and skipped; the run still
exits non-zero so CI notices, but the page is written either way.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime

from .models import TZ, Session, select
from .render import render
from .scrapers import SCRAPERS


def collect(now: datetime) -> tuple[list[Session], dict[str, str]]:
    sessions: list[Session] = []
    failures: dict[str, str] = {}
    for name, run in SCRAPERS.items():
        try:
            got = run(now)
            sessions.extend(got)
            print(f"  {name}: {len(got)} sessions", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - best-effort by design
            failures[name] = f"{type(e).__name__}: {e}"
            print(f"  {name}: FAILED - {failures[name]}", file=sys.stderr)
            traceback.print_exc()
    return select(sessions, now), failures


def main() -> int:
    now = datetime.now(TZ)
    sessions, failures = collect(now)
    render(sessions, failures, now)
    print(
        f"wrote docs/ with {len(sessions)} sessions"
        + (f"; {len(failures)} source(s) failed" if failures else ""),
        file=sys.stderr,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
