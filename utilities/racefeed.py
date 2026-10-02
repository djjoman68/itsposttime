"""Background worker that keeps the latest race data ready for the display.

Polling is deliberately gentle:
  - outside the race window it checks NYRA's track page at most every 5 minutes
  - inside the window it re-reads the odds every RACE_POLL_SECONDS (default 20s)
  - today's card (post times for every race) is read once, then refreshed every
    30 minutes, one race page per second
  - with the track on "auto" it checks Saratoga, then Belmont, until one is racing
    today, and sticks with that track for the rest of the day
Moving on: NYRA's header stays on a race until it is official, about 10 minutes after
it is run. The board moves to the next race on the card as soon as NYRA rewrites the
race's post time to its off time (about when the race finishes), or failing that when
the race page drops its countdown. See nyra.py for the sequence.
The display thread never waits on the network; it just reads .race, .track and .card.
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
CARD_REFRESH_SECONDS = 1800   # post times can move; re-read the card every 30 minutes
CARD_FETCH_GAP = 1.0          # pause between race pages while reading the card
AUTO_TRACKS = ("saratoga", "belmont")   # Saratoga first: its summer meet takes priority


def _today():
    return datetime.now(nyra.NYRA_TZ).date()


class RaceFeed:
    def __init__(self, start=True):
        self._lock = threading.Lock()
        self._race = None            # dict from nyra.parse_race, or None when idle
        self.last_error = None
        self.last_update = None
        self.track = None            # track being followed today (resolves "auto"); None = no racing
        self.card = []               # today's races: race, post_time, distance, surface, runners
        self.next_race = None        # race number NYRA's header is counting down to
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._wake = threading.Event()
        self._current = (None, None, None, 0.0)   # (track, race_num, post_time, checked_at)
        self._page = (None, None, 0.0)            # (track, html, fetched_at) - last track page
        self._auto = (None, None)                 # (day, track) chosen by "auto"
        self._card_key = (None, None)             # (track, day) the card belongs to
        self._card_checked = 0.0
        self._day_key = (None, None)              # (track, day) the two below belong to
        self._scheduled = {}                      # race -> first post time seen (before any rewrite)
        self._post_seen = {}                      # race -> (latest post time, when it first appeared)
        self.finished = set()                     # races run today; the board has moved past them
        if start:
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

    def _track_page(self, track, max_age=HEADER_CHECK_SECONDS):
        """The track page, re-used if it was fetched within max_age seconds."""
        cached_track, html, fetched = self._page
        if cached_track == track and time.time() - fetched < max_age:
            return html
        html = self._get(nyra.track_page_url(track))
        self._page = (track, html, time.time())
        return html

    def _resolve_track(self, setting):
        """The track to follow today. For "auto", the first of AUTO_TRACKS racing today."""
        if setting != "auto":
            return setting
        today = _today()
        day, track = self._auto
        if day == today and track:
            return track
        for t in AUTO_TRACKS:
            if nyra.racing_on(self._track_page(t, max_age=IDLE_CHECK_SECONDS), today):
                self._auto = (today, t)
                return t
        self._auto = (today, None)
        return None

    def _refresh_card(self, track):
        """Read today's card for the track, then again every CARD_REFRESH_SECONDS."""
        today = _today()
        key = (track, today)
        if self._card_key == key and time.time() - self._card_checked < CARD_REFRESH_SECONDS:
            return
        self._card_checked = time.time()
        html = self._track_page(track)
        if not nyra.racing_on(html, today):
            if self._card_key != key:        # no racing here today; keep a card already read today
                self.card, self._card_key = [], key
            return
        card = []
        for num in nyra.race_numbers(html):
            try:
                race = nyra.parse_race(self._get(nyra.race_fragment_url(track, num)))
            except requests.RequestException as e:
                log.warning(f"card: race {num} fetch failed: {e}")
                race = None
            if race:
                self._scheduled.setdefault(race["race"], race["post_time"])
                card.append({"race": race["race"], "post_time": race["post_time"], "distance": race["distance"],
                             "surface": race["surface"], "runners": len(nyra.runners(race))})
            time.sleep(CARD_FETCH_GAP)
        if card or self._card_key != key:
            self.card, self._card_key = card, key

    def _next_unfinished(self, race_num, post_time):
        """NYRA's header lags behind: if it still points at a race that has been run,
        use the next race on the card instead. (None, None) when the card is done."""
        if race_num not in self.finished:
            return race_num, post_time
        for c in self.card:
            if int(c["race"]) > int(race_num) and c["race"] not in self.finished:
                return c["race"], c["post_time"]
        return None, None

    def _cycle(self):
        """One check. Returns how many seconds to wait before the next one."""
        config.reload()
        window = config.RACE_WINDOW_MINUTES
        track = self._resolve_track(config.RACE_TRACK)
        if track != self.track:
            self._current = (None, None, None, 0.0)
        self.track = track
        if track is None:                        # "auto" and neither track is racing today
            self._set(None)
            self.card, self.next_race = [], None
            return IDLE_CHECK_SECONDS

        day_key = (track, _today())
        if day_key != self._day_key:
            self._day_key, self._scheduled, self._post_seen, self.finished = day_key, {}, {}, set()
        self._refresh_card(track)

        cached_track, race_num, post_time, checked = self._current
        if cached_track != track or race_num is None or time.time() - checked >= HEADER_CHECK_SECONDS:
            race_num, post_time = nyra.current_race(self._track_page(track))
            self._current = (track, race_num, post_time, time.time())
        race_num, post_time = self._next_unfinished(race_num, post_time)
        # After the last race the header may already count down to the next racing day
        today_post = bool(post_time) and nyra.parse_post_time(post_time).date() == _today()
        self.next_race = race_num if today_post else None
        if not race_num:
            self._set(None)                      # track dark or card finished
            return IDLE_CHECK_SECONDS

        mtp = nyra.minutes_to_post(post_time)
        if mtp > window:
            self._set(None)
            self._current = (None, None, None, 0.0)
            # sleep until the window opens, but re-check at least every 5 minutes
            return max(30, min(IDLE_CHECK_SECONDS, (mtp - window) * 60))

        race, official = None, False
        for url in (nyra.race_fragment_url(track, race_num), nyra.race_page_url(track, race_num)):
            try:
                html = self._get(url)
                race = nyra.parse_race(html)
                official = race is None and nyra.race_finished(html)
            except requests.RequestException as e:
                log.warning(f"fetch failed {url}: {e}")
            if race or official:
                break
        went_off = False
        if race:
            self._scheduled.setdefault(race_num, race["post_time"])
            seen = self._post_seen.get(race_num)
            if seen is None or seen[0] != race["post_time"]:
                if seen:
                    log.info(f"race {race_num} post time {seen[0][11:]} -> {race['post_time'][11:]}")
                seen = (race["post_time"], datetime.now(nyra.NYRA_TZ))
                self._post_seen[race_num] = seen
            went_off = nyra.went_off(self._scheduled.get(race_num), race["post_time"], seen[1])
        if official or went_off:
            log.info(f"race {race_num} has been run; moving to the next race")
            self.finished.add(race_num)
            return 1                             # pick up the next race right away
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
