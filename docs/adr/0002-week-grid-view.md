# The schedule page is a two-view client-side app

`docs/index.html` renders both a **Week grid** (7 day-columns, one week at a time,
default) and the original chronological **List**, with a toggle between them, an
activity filter, week/day navigation, and expandable session chips — all vanilla
JS reading and writing `localStorage`. It is still a single static file with no
network calls: every week in the horizon is pre-rendered and the script just
shows one.

This supersedes the first design's "static chronological agenda" (ADR-implicit,
from the initial grilling). The agenda couldn't meet the "fit the current screen
without scrolling" requirement — 190 sessions over 28 days scroll in any single
layout. Showing one week (or one day on a narrow screen) at a time does fit, at
the cost of turning a zero-JS page into a small client-side app. The `.ics` feed
and the scrapers are unaffected.
