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
- Oct 2 2026: clock & weather picture on the Board page confirmed working on the real Pi.
- Oct 2 2026: auto track (picked Belmont) and today's card confirmed on the real Pi during a live Belmont card.
- Oct 5 2026: hardware assembled (Bonnet + 64x32 panel); the board runs on the real panel. Panel checks below pending.

## Layout

| Path | Role |
|---|---|
| `odds-board.py` | Entry point; single-instance lock (/tmp/odds-board.lock); starts web UI subprocess |
| `config.py` | Reads config/config.json + secrets.json; `DEFAULT_CONFIG`; `reload()` |
| `display/__init__.py` | Main loop (plane tracker Animator). `_data` = `[race]` in race mode, `[]` idle. Watches config mtime, writes status + frame to /dev/shm/odds-board for the web UI |
| `scenes/race.py` | Draws the race board each second via `canvas.SetImage(PIL image)` |
| `scenes/clock.py`, `date.py`, `temperature.py`, `daysforecast.py` | Idle screens from the plane tracker. They step aside when `_data` is non-empty |
| `utilities/nyra.py` | Parses NYRA pages: `current_race()`, `parse_race()`, `minutes_to_post()`, `racing_on()`, `race_numbers()`, `card_states()` |
| `utilities/racefeed.py` | Background polling thread; resolves the "auto" track and reads today's card |
| `utilities/race_render.py` | Pure Pillow drawing of both race views, custom 3x5 pixel font, saddle cloth colors |
| `utilities/idle_render.py` | Web UI picture of the clock & weather screen: idle scenes `record()` what they draw, `render_idle()` redraws it with the panel's .bdf fonts |
| `web/` | Flask app on :8080 — Board, Settings (incl. Wi-Fi, Restart display, Shut down), Logs |
| `web/wifi.py` | Settings → Wi-Fi via NetworkManager `nmcli` (sudo -n): status, scan, add (saves only), forget, switch now with fall-back |
| `install.sh` | Installs packages, systemd service `odds-board`, removes stray crontab autostarts |
| `tests/` | Offline tests with a fake `rgbmatrix`, a synthetic sample page and sample weather (no internet) |
| `tools/preview.py` | Renders preview.png of the race screens and the clock & weather screen |

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
  ("6.5F"; miles converted, 1 1/16M = 8.5F), surface "DRT" in brown, "TRF" in green, "SYN" in blue
  (Synthetic/Poly/Tapeta/All Weather; Joe, Oct 2026); unknown surfaces show nothing.

Big MTP view (revised by Joe, Oct 2026): "RACE 5" top-left in blue, time of day top-right in gray (150,150,150),
12-hour with a/p ("2:47p"); MTP digits at 4x, centered below; "MTP" dim gray bottom-right beside the digits.

Today's card screen (Joe's request, Oct 2026): on race days, when no race is within the window, the panel
alternates clock & weather and the card, `card_seconds` (45) each; 0 = off. Header: track name, "SARATOGA" in
Saratoga red (211,58,44), "BELMONT" in forest green (34,139,34); "TODAY" dim gray. 4 races per page, races still to come only, next race first:
race number blue (right-aligned), post time 12-hour with small lowercase a/p ("1:10p"), distance in furlongs, surface DRT brown / TRF
green. More than 4: pages flip every `page_seconds`,
counted from when the card's turn starts, so it always opens on the first races (Joe, Oct 2026). Same for big
fields on the race board: a race always opens on page 1. Gone once the day's last race is off.

Pick 5 page (Joe, Oct 2026): after the race pages, the card screen shows a page per up-to-4 Pick 5s still to
start: header track name + "PICK 5" dim; one line each: name white (NYRA's word before "Pick 5"; plain "PICK 5";
first word only; MANDATORY -> MAND; shortened to fit), races blue ("5-9"), first post time with a/p. Two or fewer
get roomy spacing. Gone once its first race has gone. Any number per day: Belmont Oct 8 2026 had Early 1-5,
Mandatory Pay 3-7, Late 5-9. Web Today's card: summary line of all Pick 5s + a tag under the first leg's post time.
Source: each race's bets line ("... Late Pick 5 (.50) (5-9)"), listed only on the race a Pick 5 starts with.

MTP colors (both views): white above 10, yellow 4-10, red 3 and under. MTP rounds up and is computed on the
Pi from the page's post time (the site's own text caps at 99). Post times are Eastern; always use
`NYRA_TZ`, never the Pi's local zone.

Modes: race board when next post <= `race_window_minutes` (90); otherwise idle clock/weather, identical
to the plane tracker (NWS alerts kept, FAA and ISS alerts removed).

Web UI: Saratoga style (Joe's call, Oct 2026; replaced the amber plane-tracker look): header in the
Saratoga logo's red (#d33a2c) with flared capitals and a small white canopy, red-and-white scalloped awning
valance, red controls; the panel picture framed in tote-board green, the only green on the page. All in web/static/style.css; purely visual.
Track toggle (Auto/Saratoga/Belmont) and view toggle (Full/Big MTP) on the Board page. Auto (the default) follows
whichever track's page is counting down to a race today, Saratoga checked first, and sticks with it for the day.
"Today's card" section lists every race (post ET, distance, surface, field size), next race highlighted with
"in 3h 43m" or "23 MTP"; next race comes from the header countdown (a late race stays next), else post times. "On the panel now" shows a picture in both modes, like the plane tracker's display mirror: the
race board image, or the clock & weather screen redrawn from what the idle scenes recorded. Race settings apply live within ~1s; weather/clock/hardware settings need Restart.

## Data source (NYRA, no API)

- Track page `https://www.nyra.com/{track}/racing/`: header `span.mtp-badge[data-mtp-variant=header]`
  has the next race's post time; the sibling span before it says "Race N - ".
- Race detail: `/{track}/rdl/race/?race=N` (lightweight fragment the site loads), fallback
  `/{track}/racing/?race=N`. Block with `span.mtp-badge[data-mtp-variant=default]`; distance is the first
  div with a `title`, surface the next div; horses: `div[title="Current Odds"]`,
  `div[title="Morning Line Odds"]` ("ML 12/1"), program number in the row's `order-1` div.
- Live odds ARE in the raw HTML (verified by Joe with Ctrl+U during a live Belmont card, Oct 1 2026).
- Race tabs on the track page: `a[hx-get="/{track}/rdl/race/?race=N"]`, numbers only, no post times. Today's card
  comes from each race's fragment. A track not racing today has no header badge (Saratoga, Oct 2 2026).
- Verified live Oct 2 2026 (Belmont, 9 races): /rdl/race/ fragments, parse_race, auto track, today's card.
- Race lifecycle (watched Belmont races 1-4, Oct 2 2026): later races show odds = morning line all day;
  betting on a race opens only after the race before it is over. Countdown sits at 0 from post time;
  nothing marks the off. ~2 min after the off the post time is rewritten to the off time (13:43:00 ->
  13:45:20), but delays also show passing post times (race 3: 2:16 -> 2:31:48) and switching on that moved
  the board on ~2 min before race 3 started, so it's not used. ~5-7 min after the off the NEXT race's odds
  go live (race 4 ~2:38:30): the board moves on then (`nyra.odds_live`, checked every 40s once the current
  race is past post time; Joe's call, surest signal). ~10 min after the off (official) the race page drops
  its countdown (`nyra.race_finished`, also moves on) and the header follows within ~1 min. An "OFF"
  display was tried and dropped (Joe's call): the site never says OFF.
- Polling etiquette (keep it gentle): idle, track page at most every 5 min; in the window, odds every
  `poll_seconds` (20, minimum 10) and the track page once a minute. Today's card: one fragment per race,
  1s apart, once a day then every 30 min. After post time, the next race's page every 40s until its odds go live. Auto with no racing anywhere: both track pages every 5 min.
  Don't make it faster.

## Not yet verified (check once hardware is running)

- The word NYRA uses for a synthetic race (short_surface covers Synthetic/Poly/Tapeta/All Weather); a blank surface
  on a synthetic race means it needs another word.
- What the header shows after the last race (board should fall back to clock). Between races: see above.
- Saratoga's page layout matches Belmont's (same NYRA site; expected yes, confirm next summer).
- How NYRA writes even money and other odd formats (unparseable odds show white).
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
- Settings → Wi-Fi (Joe's call: "add a network" + "switch now", no hotspot yet): adding only saves a network, the Pi
  joins it when in range. Switch now runs in the background and rejoins the previous network if joining fails
  (45s). Never forget the network in use. SSIDs are untrusted (neighbors'): the page only ever sets them as text.
  Not yet tried on the real Pi; assumes Raspberry Pi OS's NetworkManager (the page says so if nmcli is missing).
- Root actions from the web page (Restart display, Shut down, Wi-Fi) go through /etc/sudoers.d/odds-board, written
  by install.sh step 6: NOPASSWD for exactly `systemctl restart odds-board`, `systemctl poweroff` and `nmcli`.
  Joe's Pi asks for a sudo password otherwise (don't assume passwordless sudo; Restart silently failed until Oct
  2026). The app checks with `sudo -n -l <cmd>` and tells Joe to re-run install.sh if the rule is missing.
- Settings → Shut down powers the Pi off (`sudo -n systemctl poweroff`). Joe unplugged
  it while running once (Oct 5); it survived. Startup takes ~2 min: no RTC, so the clock starts at the last saved
  time and jumps when it syncs; the board settles a minute after.
