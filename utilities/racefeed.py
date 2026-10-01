"""Background worker that keeps the latest race data ready for the display.

Polling is deliberately gentle:
  - outside the race window it checks NYRA's track page at most every 5 minutes
  - inside the window it re-reads the odds every RACE_POLL_SECONDS (default 20s)
The display thread never waits on the network; it just reads .race.
"""
import logging
import threading
import time
from datetime import datetime

import requests

import config
from utilities import nyra

log = logging.getLogger("racefeed")

HEADERS = {"User-Agent": "Mozilla/5.0 (personal LED odds display)"}
IDLE_CHECK_SECONDS = 300
HEADER_CHECK_SECONDS = 60     # in the race window, re-check which race is next once a minute
ERROR_RETRY_SECONDS = 60


class RaceFeed:
    def __init__(self):
        self._lock = threading.Lock()
        self._race = None            # dict from nyra.parse_race, or None when idle
        self.last_error = None
        self.last_update = None
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._wake = threading.Event()
        self._current = (None, None, None, 0.0)   # (track, race_num, post_time, checked_at)
        threading.Thread(target=self._loop, daemon=True, name="racefeed").start()

    @property
    def race(self):
        with self._lock:
            return dict(self._race) if self._race else None

    def refresh_now(self):
        """Called when the web UI changes the track so the board updates right away."""
        self._current = (None, None, None, 0.0)
        self._wake.set()

    def _set(self, race):
        with self._lock:
            self._race = race
        self.last_update = datetime.now()

    def _get(self, url):
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        return r.text

    def _cycle(self):
        """One check. Returns how many seconds to wait before the next one."""
        config.reload()
        track = config.RACE_TRACK
        window = config.RACE_WINDOW_MINUTES

        cached_track, race_num, post_time, checked = self._current
        if cached_track != track or race_num is None or time.time() - checked >= HEADER_CHECK_SECONDS:
            race_num, post_time = nyra.current_race(self._get(nyra.track_page_url(track)))
            self._current = (track, race_num, post_time, time.time())
        if not race_num:
            self._set(None)                      # track dark or card finished
            return IDLE_CHECK_SECONDS

        mtp = nyra.minutes_to_post(post_time)
        if mtp > window:
            self._set(None)
            self._current = (None, None, None, 0.0)
            # sleep until the window opens, but re-check at least every 5 minutes
            return max(30, min(IDLE_CHECK_SECONDS, (mtp - window) * 60))

        race = None
        for url in (nyra.race_fragment_url(track, race_num), nyra.race_page_url(track, race_num)):
            try:
                race = nyra.parse_race(self._get(url))
            except requests.RequestException as e:
                log.warning(f"fetch failed {url}: {e}")
            if race:
                break
        if race is None:
            raise RuntimeError("race page layout not recognized")

        race["track"] = track
        self._set(race)
        return config.RACE_POLL_SECONDS

    def _loop(self):
        while True:
            try:
                wait = self._cycle()
                self.last_error = None
            except Exception as e:
                # Keep showing the last good odds briefly; the scene drops stale data
                self.last_error = str(e)
                log.error(f"race feed error: {e}")
                wait = ERROR_RETRY_SECONDS
            self._wake.wait(wait)
            self._wake.clear()
