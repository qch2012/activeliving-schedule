# Playwright for the DevExpress scheduler pages

Four of the six sources (gym, gym track, oval running, oval skating) are DevExpress
`ASPxScheduler` widgets that render entirely client-side via AJAX callbacks, with no
static table and no iCal/data export. We drive them with headless Playwright — load the
page, let it render, scrape the DOM — rather than replaying the DevExpress callback POST
(viewstate + `__CALLBACKPARAM`) against the `.aspx` endpoint directly.

The callback approach avoids a browser dependency but is tightly coupled to
server-generated viewstate and breaks on any upstream markup change. Playwright is one
dependency that handles the JavaScript-rendered pages and runs in CI, at the cost of a
heavier install and exposure to bot detection on `schedules.*.ucalgary.ca`. Pool and
climbing stay on plain `httpx` + `beautifulsoup4`.

Update (2026-09-02, from live DOM recon): the four JS pages use three renderers, not one.
The DevExpress ASPxScheduler "Weeks" view described above serves `PublicRunning.aspx`,
`recreationalskating.aspx`, and — despite the different host — `KnesOpenTrackTimes.aspx`.
`alcalendargymtimes.aspx` is FullCalendar (day cells carry `data-date`, so no geometry
needed). All are JavaScript-rendered, so Playwright still applies; there are two DOM
extractors (`_run_dx_scheduler`, `_run_activeliving`).
