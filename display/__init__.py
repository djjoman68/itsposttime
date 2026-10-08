"""Main display loop: idle clock/weather screen, switching to the race board
when the next post is within the race window. Hardware setup and timing are
carried over unchanged from the plane tracker."""
import json
import os
import sys
import tempfile
import time
from datetime import datetime

import config
from setup import frames
from utilities import nyra
from utilities.animator import Animator
from utilities.idle_render import render_idle
from utilities.racefeed import RaceFeed

from scenes.temperature import TemperatureScene
from scenes.clock import ClockScene
from scenes.daysforecast import DaysForecastScene
from scenes.date import DateScene
from scenes.race import RaceScene

from rgbmatrix import graphics
from rgbmatrix import RGBMatrix, RGBMatrixOptions


# Status + latest frame for the web UI. Kept in RAM (/dev/shm) to spare the SD card.
STATUS_DIR = "/dev/shm/odds-board" if os.path.isdir("/dev/shm") else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
os.makedirs(STATUS_DIR, exist_ok=True)
STATUS_FILE = os.path.join(STATUS_DIR, "status.json")
FRAME_FILE = os.path.join(STATUS_DIR, "board.png")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.json")


def _atomic_write(path, write_fn):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    os.close(fd)
    write_fn(tmp)
    os.replace(tmp, path)


def adjust_brightness(matrix):
    if not config.NIGHT_BRIGHTNESS:
        if matrix.brightness != config.BRIGHTNESS:
            matrix.brightness = config.BRIGHTNESS
        return
    now = datetime.now().time().replace(second=0, microsecond=0)
    start = datetime.strptime(config.NIGHT_START, "%H:%M").time()
    end = datetime.strptime(config.NIGHT_END, "%H:%M").time()
    new_brightness = config.BRIGHTNESS if end <= now < start else config.BRIGHTNESS_NIGHT
    if matrix.brightness != new_brightness:
        matrix.brightness = new_brightness


class Display(
    RaceScene,
    TemperatureScene,
    ClockScene,
    DaysForecastScene,
    DateScene,
    Animator,
):
    def __init__(self):
        options = RGBMatrixOptions()
        options.hardware_mapping = "adafruit-hat-pwm" if config.HAT_PWM_ENABLED else "adafruit-hat"
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.row_address_type = 0
        options.multiplexing = 0
        options.pwm_bits = 11
        options.brightness = config.BRIGHTNESS
        options.pwm_lsb_nanoseconds = 160
        options.led_rgb_sequence = config.LED_RGB_SEQUENCE
        options.pixel_mapper_config = ""
        options.show_refresh_rate = 0
        options.gpio_slowdown = config.GPIO_SLOWDOWN
        options.disable_hardware_pulsing = True
        options.drop_privileges = True
        options.limit_refresh_rate_hz = 120
        self.matrix = RGBMatrix(options=options)

        self.canvas = self.matrix.CreateFrameCanvas()
        self.canvas.Clear()

        # _data holds [race] during the race window and [] otherwise.
        # Every idle scene already steps aside when _data is non-empty.
        self._data = []
        self.feed = RaceFeed()
        self._config_mtime = self._read_config_mtime()
        self._last_frame = None
        # What the idle scenes last drew, for the web UI's picture (see utilities/idle_render.py)
        self._idle_view = {}
        self._idle_version = 0
        self._screen = None              # "card", a race number, or None (clock)
        self._screen_started = 0.0       # when it appeared; pages count from here

        super().__init__()
        self.delay = frames.PERIOD

    def draw_square(self, x0, y0, x1, y1, colour):
        for x in range(x0, x1):
            _ = graphics.DrawLine(self.canvas, x, y0, x, y1, colour)

    @staticmethod
    def _read_config_mtime():
        try:
            return os.path.getmtime(CONFIG_FILE)
        except OSError:
            return None

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def watch_config(self, count):
        """Pick up web UI changes within a second, no restart needed for race settings."""
        mtime = self._read_config_mtime()
        if mtime == self._config_mtime:
            return
        self._config_mtime = mtime
        old_track = config.RACE_TRACK
        config.reload()
        if config.RACE_TRACK != old_track:
            self.feed.refresh_now()

    @Animator.KeyFrame.add(frames.PER_SECOND * 2)
    def write_status(self, count):
        shown = self._data[0] if self._data else None
        race = shown if shown and "race" in shown else None
        card = list(self.feed.card)
        states = nyra.card_states(card, self.feed.next_race)
        status = {
            "mode": "race" if race else "card" if shown else "idle",
            "track": config.RACE_TRACK,          # the setting: auto, saratoga or belmont
            "track_now": self.feed.track,        # the track being followed today, None if no racing
            "card": [dict(c, state=st, mtp=nyra.minutes_to_post(c["post_time"]) if st == "next" else None)
                     for c, st in zip(card, states)],
            "view": config.RACE_VIEW,
            "race": race["race"] if race else None,
            "post_time": race["post_time"] if race else None,
            "runners": len(nyra.runners(race)) if race else 0,
            "feed_updated": self.feed.last_update.isoformat(timespec="seconds") if self.feed.last_update else None,
            "feed_error": self.feed.last_error,
            "written": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            _atomic_write(STATUS_FILE, lambda p: open(p, "w").write(json.dumps(status)))
            if shown:
                frame = getattr(self, "last_race_image", None)
                if frame is not None and frame is not self._last_frame:
                    _atomic_write(FRAME_FILE, lambda p: frame.save(p, format="PNG"))
                    self._last_frame = frame
            elif self._last_frame != ("idle", self._idle_version):
                idle = render_idle(self._idle_view)
                _atomic_write(FRAME_FILE, lambda p: idle.save(p, format="PNG"))
                self._last_frame = ("idle", self._idle_version)
        except Exception as e:
            print(f"status write failed: {e}")

    @Animator.KeyFrame.add(0)
    def clear_screen(self):
        self.canvas.Clear()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def check_for_race(self, count):
        race = self.feed.race
        card = None if race else self._card_screen()
        new_data = [race] if race else [card] if card else []
        mode_changed = bool(new_data) != bool(self._data)
        # Card screen has no "race", so switching card <-> race board also clears the panel
        race_changed = bool(new_data and self._data) and new_data[0].get("race") != self._data[0].get("race")
        # Note when the card screen or a race appears, so paging starts from its first page
        screen = "card" if card else race["race"] if race else None
        if screen != self._screen:
            self._screen, self._screen_started = screen, time.time()
        self._data = new_data
        if mode_changed:
            # Switching between race board and clock: clear and let the scenes redraw
            self.reset_scene()
            self._redraw_time = True
            self._redraw_forecast = True
            self._redraw_temp = True
            self._redraw_date = True
        elif race_changed:
            self.canvas.Clear()

    def _card_screen(self):
        """Today's card for the panel during its turn in the clock/card alternation, else None.
        Only the races still to come, next race first; nothing once the day's racing is over."""
        secs = config.CARD_SECONDS
        if secs <= 0 or not self.feed.track or int(time.time() // secs) % 2 == 0:
            return None
        card = list(self.feed.card)
        rows = [c for c, st in zip(card, nyra.card_states(card, self.feed.next_race)) if st != "done"]
        if not rows:
            return None
        upcoming = {r["race"] for r in rows}
        # Pick 5s whose first race hasn't gone yet, with that race's post time
        seqs = [dict(p, post_time=c["post_time"]) for c in card for p in c.get("pick5s", [])
                if c["race"] in upcoming]
        return {"card": rows, "track": self.feed.track, "pick5s": seqs}

    @Animator.KeyFrame.add(1)
    def sync(self, count):
        _ = self.matrix.SwapOnVSync(self.canvas)
        adjust_brightness(self.matrix)

    def run(self):
        try:
            print("Press CTRL-C to stop")
            self.play()
        except KeyboardInterrupt:
            print("Exiting\n")
            sys.exit(0)
