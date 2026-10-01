# LED Odds Board

A Raspberry Pi and a 64x32 RGB LED panel that show live odds and minutes-to-post
for **Saratoga** or **Belmont Park**, and a clock with a 3-day forecast the rest of the time.

## What it shows

**Race board** (from 90 minutes before post)
- Every running horse on its saddle-cloth color, with live odds
- Odds in **red** when bet below the morning line, **green** when above, white when unchanged
- A dot marks the favorite; scratched horses are left off
- Odds ending in /1 show as just the number (6/1 shows as 6)
- Right column: minutes to post, race number (R1), distance (6.5F), surface (DRT brown, TRF green)
- MTP color: white above 10, yellow 4-10, red 3 and under
- More than 10 runners: flips between two pages

**Big MTP view** (toggle in the web UI): race number and minutes to post, filling the panel.

**Idle**: clock, date, temperature and 3-day forecast, from the plane tracker.

Data comes from NYRA's public racing pages. No paid API.

## Web UI

`http://<pi-name>.local:8080`
- **Board**: live picture of the panel, Saratoga/Belmont and Full board/Big MTP toggles
- **Settings**: racing, clock & weather (Tomorrow.io key), brightness and night dimming
- **Logs**: recent service output

## Hardware

Raspberry Pi 3A+, Adafruit RGB Matrix Bonnet, 64x32 HUB75 panel (P4 is about 10x5 in),
5V 4A power supply, microSD card, heatsink, 2x20 header extender.

## Install

See **[SETUP.md](SETUP.md)**: blank SD card to running board, step by step.

## Project layout

| Path | What it is |
|---|---|
| `odds-board.py` | Entry point |
| `install.sh` | Installer and auto-start service |
| `config.py`, `config/` | Settings (`config.json`, `secrets.json` are created on the Pi, not stored in git) |
| `display/` | Main loop: switches between clock/weather and the race board |
| `scenes/race.py` | Race board scene |
| `scenes/clock.py`, `date.py`, `temperature.py`, `daysforecast.py` | Idle screens (from the plane tracker) |
| `utilities/nyra.py` | Reads NYRA's racing pages |
| `utilities/racefeed.py` | Background polling |
| `utilities/race_render.py` | Draws the race screens |
| `web/` | Web UI |

## Credits and license

Built on the plane tracker by **c0wsaysmoo**
([plane-tracker-rgb-pi](https://github.com/c0wsaysmoo/plane-tracker-rgb-pi)), which is based on
**Colin Waddell's** [FlightTracker](https://github.com/ColinWaddell/FlightTracker) (formerly
its-a-plane-python). The idle screens, animation loop, fonts and weather icons come from those
projects. The first commit in this repository is an unmodified import of those files, and later
commits show every change.

Panel driver: [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix), installed
separately during setup.

Released under the **GNU General Public License v3.0**, the same license as FlightTracker.
See [LICENSE](LICENSE).

Race data is read from nyra.com for personal, non-commercial display.
