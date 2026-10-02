# CLAUDE.md — It's Post Time (LED odds board)

Read this first every session. It holds the decisions already made so we don't redo them.

## Who you're working with

Joe owns this project. He doesn't write code: you do all the coding, and he makes the design calls.
- Explain changes in plain language. Lead with what changes on the panel or web page.
- Show visual changes before he has to imagine them: run `python3 tools/preview.py` and share the image.
- Ask before pushing to GitHub. Commit freely with clear messages.
- Don't change an agreed design rule (below) unless Joe asks. If a rule causes a problem, explain it and offer options.

## What it is

Raspberry Pi 3A+ + 64x32 RGB LED panel. Shows clock + 3-day forecast when idle, and switches to a live
race board for Saratoga or Belmont Park when the next post is within 90 minutes. Built on the plane
tracker (c0wsaysmoo/plane-tracker-rgb-pi), which is based on ColinWaddell/FlightTracker (GPL-3.0).
Repo: https://github.com/djjoman68/itsposttime

## Status (Oct 2026)

- Software complete and tested offline: race board, idle screens, web UI, installer, setup guide.
- Hardware bought (Oct 1 2026): Pi 3A+ and microSD in hand; Bonnet, 64x32 4mm panel, 5V 4A supply,
  extra-tall header and heatsink ordered from Adafruit, in the mail. Nothing has run on a real panel or
  against live NYRA polling yet.
- Oct 2 2026: SETUP.md steps 1, 3, 4 and 6 done on the real Pi, powered by micro-USB with no Bonnet or
  panel attached. install.sh worked; the service runs and the web UI loads at oddsboard.local:8080.
  Next: step 7 settings now; when the Adafruit parts arrive, steps 2 and 5 (assembly, panel test).

## Layout

| Path | Role |
|---|---|
| `odds-board.py` | Entry point; single-instance lock (/tmp/odds-board.lock); starts web UI subprocess |
| `config.py` | Reads config/config.json + secrets.json; `DEFAULT_CONFIG`; `reload()` |
| `display/__init__.py` | Main loop (plane tracker Animator). `_data` = `[race]` in race mode, `[]` idle. Watches config mtime, writes status + frame to /dev/shm/odds-board for the web UI |
| `scenes/race.py` | Draws the race board each second via `canvas.SetImage(PIL image)` |
| `scenes/clock.py`, `date.py`, `temperature.py`, `daysforecast.py` | Idle screens from the plane tracker. They step aside when `_data` is non-empty |
| `utilities/nyra.py` | Parses NYRA pages: `current_race()`, `parse_race()`, `minutes_to_post()` |
| `utilities/racefeed.py` | Background polling thread |
| `utilities/race_render.py` | Pure Pillow drawing of both race views, custom 3x5 pixel font, saddle cloth colors |
| `web/` | Flask app on :8080 — Board, Settings, Logs |
| `install.sh` | Installs packages, systemd service `odds-board`, removes stray crontab autostarts |
| `tests/` | Offline tests with a fake `rgbmatrix` and a synthetic sample page |
| `tools/preview.py` | Renders preview.png of the race screens |

## Agreed design rules

Full board (64x32):
- Two columns x 5 rows = 10 horses per page; right sidebar 13px wide (x 51-63).
- Each horse: 7x5 saddle-cloth badge, gap, favorite-dot slot, gap, odds.
- Saddle cloths use the standard US colors 1-20 (`SADDLE` in race_render.py). In badges 10-19 the
  leading "1" is a 1px stroke so #12 etc. stay legible.
- Scratched horses are omitted entirely (don't count toward the 10).
- More than 10 active horses: two pages, first 10 in program order on page 1, flip every
  `page_seconds` (default 5). Sidebar stays on both pages.
- Favorite = lowest current odds across the whole field, marked by one white dot before its odds.
- Odds color vs morning line: red if lower than ML (bet down), green if higher, white if equal or unparseable.
- Odds ending in "/1" display without it (6/1 shows as 6). All other formats unchanged (9/2, 3/10).
- Sidebar top to bottom: MTP in 2x digits, race number "R1"/"R10" in blue, distance in furlongs
  ("6.5F"; miles converted, 1 1/16M = 8.5F), surface "DRT" in brown or "TRF" in green (other: white).

Big MTP view: header "RACE 5   MTP" centered (race blue, MTP dim gray); MTP digits at 4x, centered below.

MTP colors (both views): white above 10, yellow 4-10, red 3 and under. MTP rounds up and is computed on the
Pi from the page's post time (the site's own text caps at 99). Post times are Eastern; always use
`NYRA_TZ`, never the Pi's local zone.

Modes: race board when next post <= `race_window_minutes` (90); otherwise idle clock/weather, identical
to the plane tracker (NWS alerts kept, FAA and ISS alerts removed).

Web UI: amber plane-tracker style. Track toggle (Saratoga/Belmont) and view toggle (Full/Big MTP) on the
Board page. Race settings apply live within ~1s; weather/clock/hardware settings need Restart.

## Data source (NYRA, no API)

- Track page `https://www.nyra.com/{track}/racing/`: header `span.mtp-badge[data-mtp-variant=header]`
  has the next race's post time; the sibling span before it says "Race N - ".
- Race detail: `/{track}/rdl/race/?race=N` (lightweight fragment the site loads), fallback
  `/{track}/racing/?race=N`. Block with `span.mtp-badge[data-mtp-variant=default]`; distance is the first
  div with a `title`, surface the next div; horses: `div[title="Current Odds"]`,
  `div[title="Morning Line Odds"]` ("ML 12/1"), program number in the row's `order-1` div.
- Live odds ARE in the raw HTML (verified by Joe with Ctrl+U during a live Belmont card, Oct 1 2026).
- Polling etiquette (keep it gentle): idle, track page at most every 5 min; in the window, odds every
  `poll_seconds` (20, minimum 10) and the track page once a minute. Don't make it faster.

## Not yet verified (check once hardware is running)

- The /rdl/race/ fragment on the live site (fallback exists).
- Saratoga's page layout matches Belmont's (same NYRA site; expected yes, confirm next summer).
- How NYRA writes even money and other odd formats (unparseable odds show white).
- What the header shows between races and after the last race (board should fall back to clock).
- Colors on the real panel: brown DRT, #15 khaki badge, single-LED favorite dot.

## Working rules

- Test before committing: `python3 -m unittest discover tests` (no panel or internet needed).
- Visual changes: `python3 tools/preview.py` (or pass a page saved from nyra.com) and show Joe.
- Never commit `config/*.json` (secrets, Pi settings); .gitignore covers it.
- Don't commit pages saved from nyra.com; the test fixture is synthetic on purpose.
- License is GPL-3.0. Keep credits in README.md. When changing a file that came from the plane
  tracker, keep or add the "Modified for the LED odds board" note at the top.
- The Pi runs one copy only (lock file + systemd). If Joe reports flicker or GPIO errors, check for a
  second process first.
- Service name `odds-board`; logs via `journalctl -u odds-board`; web on port 8080.
