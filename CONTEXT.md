# ActiveLiving Schedule

A tool that scrapes the University of Calgary Active Living drop-in schedules into one
filtered, self-hosted view — an HTML page and an `.ics` feed — showing only the sessions
the user can actually attend.

## Language

**Session**:
A single dated, time-bounded block when one activity is available at one venue — the
atomic unit of the schedule. Carries activity, venue, optional sub-location, start, end,
and source.
_Avoid_: Event, slot, class, booking

**Activity**:
The thing you can do in a session: Lane Swim, Open Gym, Badminton, Open Track, RF Running,
Recreational Skating, Climbing Wall. In the data model it keeps the source's own name,
verbatim. The HTML page may show a shorter display name (e.g. "Rec. Fit Training" →
"Oval Running") — that is cosmetic only and lives in a rename map in `config.py`.
_Avoid_: Program, sport

**Category**:
A grouping of Activities the page can be filtered by, shown as one emoji chip: Run, Swim,
Badminton, Gym, Skate, Climb. One Category can span venues — Run covers both the
Kinesiology track and the Olympic Oval. Filtering and colour on the page are by Category,
not by Activity.
_Avoid_: Type, kind, group, tag

**Venue**:
The facility a session happens at: Aquatic Centre, Kinesiology Gym, Kinesiology Track,
Olympic Oval, Outdoor Centre Climbing Wall.
_Avoid_: Location, facility, building

**Sub-location**:
A named space within a venue — Red Gym, Gold Alcove, Kin Track 1-2, 25m pool, 50m pool.
Recorded only when the source states it; used to exclude the Gold Alcove and shown on the
page when present.
_Avoid_: Room, area, court

**Source**:
One upstream schedule page and the scraper that reads it. Six are in scope: pool, gym,
gym track, oval running, oval skating, climbing wall. The tennis/racket court page is not
a Source — it is booking-only and out of scope.
_Avoid_: Scraper, feed, provider

**Availability Window**:
The filter for which sessions are reachable. Weekday: the session ends after 15:00 local
(the user's parking pass starts at 3:00pm). Weekend (Saturday and Sunday): every session,
mornings included. Applied identically to the page and the `.ics` feed.
_Avoid_: Filter, availability, schedule filter

**Horizon**:
The rolling 28 days from the run date. Sessions outside it are dropped even if a source
publishes further ahead.
_Avoid_: Range, period, lookahead

**Run**:
One execution of the tool: scrape every Source, keep sessions inside the Availability
Window and Horizon, render `index.html` and `schedule.ics`, commit them.
_Avoid_: Build, job, refresh
```
