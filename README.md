# activeliving-schedule

One filtered view of the University of Calgary Active Living drop-in schedules —
pool, gym, gym track, oval running, oval skating, and the climbing wall — as a
static HTML page and an `.ics` feed.

Only sessions you can actually attend are shown: on weekdays, anything still
running after 15:00 (parking pass starts at 3:00pm); on weekends, everything.
Rolling 4-week horizon.

See [`CONTEXT.md`](CONTEXT.md) for the vocabulary and
[`docs/adr/`](docs/adr/) for design decisions.

## Run

```sh
uv sync
uv run playwright install chromium
uv run python -m alsched.main
```

Output lands in `docs/` (`index.html`, `schedule.ics`), served via GitHub Pages.
