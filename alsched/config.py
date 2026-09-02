"""Source URLs, per-source filters, and the climbing-wall pattern.

Everything here is a knob a human turns when a schedule changes shape or a new
semester starts. Nothing here is scraped.
"""

from datetime import date, time

# --- Source URLs ---------------------------------------------------------------
POOL_URL = "https://active-living.ucalgary.ca/facilities/aquatic-centre/pool-schedule-hours"
GYM_URL = "https://schedules.active-living.ucalgary.ca/alcalendargymtimes.aspx"
GYM_TRACK_URL = "https://schedules.active-living.ucalgary.ca/KnesOpenTrackTimes.aspx"
OVAL_RUNNING_URL = "https://schedules.oval.ucalgary.ca/PublicRunning.aspx"
OVAL_SKATE_URL = "https://schedules.oval.ucalgary.ca/recreationalskating.aspx"
CLIMBING_URL = "https://outdoor-centre.ucalgary.ca/climbingbouldering-wall"

# --- Per-source filters ------------------------------------------------------
# Pool: keep every lane/public swim, drop the kids' inflatable event.
POOL_EXCLUDE_ACTIVITIES = ("inflatable",)

# Gym: only these activities, and never the Gold Alcove space.
GYM_ACTIVITIES = ("Open Gym", "Badminton")
GYM_EXCLUDE_SUBLOCATIONS = ("Gold Alcove",)

# Gym track: the KNES page lists "Drop In - Running" (track lanes) and
# "Drop In - Fitness" (infield equipment) — keep only the running lanes.
GYM_TRACK_INCLUDE_SUBJECTS = ("Drop In - Running",)

# Oval running: recreational-fitness stream only, not high-performance intervals.
# The scheduler labels the RF stream "Rec. Fit Training" and the other "HP Running".
OVAL_RUNNING_INCLUDE_SUBJECTS = ("Rec. Fit",)

# Oval ice: the recreationalskating.aspx page also lists hockey / stick-and-puck
# ice and themed skates (e.g. "Pride & Glide"), so keep only the plain public
# drop-in skate. Verified subject strings, 2026-09: "Public Skating", "Public
# Skate". "Pride & Glide" is deliberately excluded.
OVAL_SKATE_INCLUDE_SUBJECTS = ("Public Skating", "Public Skate")

# --- Climbing wall (Outdoor Centre) ----------------------------------------
# No live schedule exists: the wall publishes static weekly hours plus seasonal
# closures as prose at CLIMBING_URL. Re-check both against that page every
# semester (roughly September / January / May).
#
# weekday: 0=Mon .. 6=Sun  ->  (open, close)   (missing key = closed that day)
CLIMBING_HOURS = {
    0: (time(11, 30), time(18, 30)),
    1: (time(11, 30), time(18, 30)),
    2: (time(11, 30), time(18, 30)),
    3: (time(11, 30), time(17, 0)),
    4: (time(11, 30), time(18, 30)),
    5: (time(12, 30), time(17, 30)),
    6: (time(12, 30), time(17, 30)),
}
# inclusive date ranges when the wall is shut
CLIMBING_CLOSURES = [
    (date(2026, 6, 22), date(2026, 9, 8)),  # summer closure
]
CLIMBING_ACTIVITY = "Climbing Wall"
CLIMBING_VENUE = "Outdoor Centre Climbing Wall"

# --- HTML page: filter categories & display names -------------------------
# The page filters by Category (a symbol), not by raw activity. See CONTEXT.md.
# activity  ->  (category slug, emoji)
ACTIVITY_CATEGORY = {
    "Drop In - Running": ("run", "🏃"),
    "Rec. Fit Training": ("run", "🏃"),
    "Adult/Youth Lane Swim": ("swim", "🏊"),
    "Family and Lane Swim": ("swim", "🏊"),
    "Badminton": ("badminton", "🏸"),
    "Open Gym": ("gym", "🤸"),
    "Public Skating": ("skate", "⛸️"),
    "Public Skate": ("skate", "⛸️"),
    "Community Day Public Skate": ("skate", "⛸️"),
    "Climbing Wall": ("climb", "🧗"),
}
CATEGORY_ORDER = ("run", "swim", "badminton", "gym", "skate", "climb", "other")
CATEGORY_LABEL = {
    "run": "Run", "swim": "Swim", "badminton": "Badminton",
    "gym": "Gym", "skate": "Skate", "climb": "Climb", "other": "Other",
}
# raw activity -> shorter name shown on the page
ACTIVITY_RENAME = {
    "Rec. Fit Training": "Oval Running",
    "Adult/Youth Lane Swim": "Lane swim",
    "Family and Lane Swim": "Family lane swim",
    "Drop In - Running": "Track running",
}
VENUE_SHORT = {
    "Aquatic Centre": "Aquatic",
    "Kinesiology Gym": "Kin Gym",
    "Kinesiology Track": "Kin Track",
    "Olympic Oval": "Oval",
    "Outdoor Centre Climbing Wall": "Climbing Wall",
}
# sub-locations that add nothing on the page (only one of them exists)
SUBLOCATION_HIDE = ("Oval Running Track", "Hockey Ice")
# sub-locations that already name their facility -> shown alone, no venue prefix
SUBLOCATION_STANDALONE = ("Red Gym", "Gold Gym")

# activity -> css colour slug, overriding the category colour on calendar chips
# (the filter still groups both under one "Run" toggle)
ACTIVITY_COLOR = {
    "Rec. Fit Training": "run-oval",
    "Drop In - Running": "run-track",
}
