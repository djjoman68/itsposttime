"""Run with:  python3 -m unittest discover tests

No LED panel or internet needed: a fake rgbmatrix module stands in for the
panel, and a saved sample page stands in for nyra.com.
"""
import os
import re
import sys
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "fakes"))
sys.path.insert(0, ROOT)

from utilities import nyra                       # noqa: E402
from utilities import race_render as rr          # noqa: E402

PAGE = open(os.path.join(HERE, "fixtures", "race_page.html"), encoding="utf-8").read()


class TestNyraReader(unittest.TestCase):
    def test_current_race(self):
        self.assertEqual(nyra.current_race(PAGE), ("3", "2026-10-01T15:12:00"))

    def test_parse_race(self):
        r = nyra.parse_race(PAGE)
        self.assertEqual((r["race"], r["distance"], r["surface"]), ("3", "1 1/16M", "Turf"))
        self.assertEqual([h["program"] for h in r["horses"]], ["1", "2", "3", "4"])
        self.assertEqual(r["horses"][0], {"program": "1", "odds": "5/2", "ml": "3/1"})
        self.assertEqual(r["horses"][2]["odds"], "SCR")

    def test_mtp_rounds_up_and_uses_eastern_time(self):
        post = "2026-10-01T15:12:00"
        now = nyra.parse_post_time(post) - timedelta(minutes=3, seconds=10)
        self.assertEqual(nyra.minutes_to_post(post, now=now), 4)
        self.assertEqual(nyra.minutes_to_post(post, now=now + timedelta(hours=1)), 0)

    def test_unrecognized_page(self):
        self.assertIsNone(nyra.parse_race("<html>maintenance</html>"))
        self.assertEqual(nyra.current_race("<html></html>"), (None, None))


class TestDesignRules(unittest.TestCase):
    """The display rules Joe signed off on. Change only if he asks."""

    def test_mtp_colors(self):
        self.assertEqual(rr.mtp_color(11), rr.WHITE)
        self.assertEqual(rr.mtp_color(10), rr.YELLOW)
        self.assertEqual(rr.mtp_color(4), rr.YELLOW)
        self.assertEqual(rr.mtp_color(3), rr.RED)
        self.assertEqual(rr.mtp_color(0), rr.RED)

    def test_odds_vs_morning_line(self):
        self.assertEqual(rr.odds_color("6/1", "12/1"), rr.RED)     # bet down
        self.assertEqual(rr.odds_color("33/1", "20/1"), rr.GREEN)  # drifting out
        self.assertEqual(rr.odds_color("9/2", "9/2"), rr.WHITE)
        self.assertEqual(rr.odds_color("EVN", "2/1"), rr.WHITE)    # unknown format

    def test_drop_slash_one(self):
        self.assertEqual(rr.display_odds("6/1"), "6")
        self.assertEqual(rr.display_odds("33/1"), "33")
        self.assertEqual(rr.display_odds("9/2"), "9/2")
        self.assertEqual(rr.display_odds("3/10"), "3/10")

    def test_surface_and_distance(self):
        self.assertEqual(rr.short_surface("Turf"), "TRF")
        self.assertEqual(rr.short_surface("Dirt"), "DRT")
        self.assertEqual(rr.short_distance("6 1/2F"), "6.5F")
        self.assertEqual(rr.short_distance("1 1/16M"), "8.5F")

    def test_scratches_omitted_and_paging(self):
        race = nyra.parse_race(PAGE)
        self.assertEqual([h["program"] for h in rr.active_horses(race)], ["1", "2", "4"])
        big = {"horses": [{"program": str(i), "odds": "5/1", "ml": "5/1"} for i in range(1, 13)]}
        self.assertEqual(rr.page_count(race), 1)
        self.assertEqual(rr.page_count(big), 2)

    def test_screens_render(self):
        race = dict(nyra.parse_race(PAGE), mtp=8)
        for img in (rr.render_full_board(race), rr.render_big_mtp(race)):
            self.assertEqual(img.size, (64, 32))
            self.assertIsNotNone(img.getbbox())


def track_page(post_time, races=3, track="belmont"):
    """Bare-bones NYRA track page: the header countdown (if any) and the race tabs."""
    badge = (f'<span>Race 2 - </span><span class="mtp-badge" data-mtp-variant="header" '
             f'data-post-time="{post_time}">5</span>') if post_time else ""
    tabs = "".join(f'<a hx-get="/{track}/rdl/race/?race={n}">{n}</a>' for n in range(1, races + 1))
    return f"<html><body><div>{badge}</div><nav>{tabs}</nav></body></html>"


class TestTodaysCard(unittest.TestCase):
    CARD = [{"race": "1", "post_time": "2026-10-02T13:10:00"},
            {"race": "2", "post_time": "2026-10-02T13:40:00"},
            {"race": "3", "post_time": "2026-10-02T14:10:00"}]

    def test_racing_today(self):
        day = datetime(2026, 10, 2).date()
        self.assertTrue(nyra.racing_on(track_page("2026-10-02T13:10:00"), day))
        self.assertFalse(nyra.racing_on(track_page("2026-10-03T13:10:00"), day))   # next racing day
        self.assertFalse(nyra.racing_on(track_page(None), day))                    # dark track

    def test_race_numbers(self):
        self.assertEqual(nyra.race_numbers(track_page(None, races=10)), [str(n) for n in range(1, 11)])

    def test_states_follow_the_header_countdown(self):
        # Race 2 is late going off: still "next" even though its post time has passed
        late = nyra.parse_post_time("2026-10-02T13:45:00")
        self.assertEqual(nyra.card_states(self.CARD, "2", now=late), ["done", "next", "later"])

    def test_states_fall_back_to_post_times(self):
        t = nyra.parse_post_time
        self.assertEqual(nyra.card_states(self.CARD, None, now=t("2026-10-02T13:30:00")), ["done", "next", "later"])
        self.assertEqual(nyra.card_states(self.CARD, None, now=t("2026-10-02T18:00:00")), ["done"] * 3)

    def test_auto_follows_the_track_racing_today_and_reads_its_card(self):
        import config
        from utilities import racefeed
        post = (datetime.now(nyra.NYRA_TZ) + timedelta(minutes=1)).replace(tzinfo=None).isoformat(timespec="seconds")
        pages = {nyra.track_page_url("saratoga"): track_page(None, track="saratoga"),
                 nyra.track_page_url("belmont"): track_page(post)}
        saved = config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP
        config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP = (lambda: None), "auto", 0
        try:
            feed = racefeed.RaceFeed(start=False)
            feed._get = lambda url: pages.get(url, PAGE)     # every race page is the sample race
            feed._cycle()
        finally:
            config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP = saved
        self.assertEqual(feed.track, "belmont")
        self.assertEqual(len(feed.card), 3)
        self.assertEqual(feed.card[0], {"race": "3", "post_time": "2026-10-01T15:12:00",
                                        "distance": "1 1/16M", "surface": "Turf", "runners": 3})
        self.assertEqual(feed.next_race, "2")
        self.assertEqual(feed.race["track"], "belmont")


def race_page(race, post_time, official=False):
    """The sample race page as race `race` with post time `post_time`; official = countdown gone."""
    html = PAGE.replace("2026-10-01T15:12:00", post_time).replace(">Race 3</header>", f">Race {race}</header>")
    if official:
        html = re.sub(r'<span class="mtp-badge[^>]*data-mtp-variant="default"[^>]*>[^<]*</span>', "", html)
    return html


class TestMovingOn(unittest.TestCase):
    """After a race is run the board moves to the next race without waiting ~10 minutes
    for NYRA to make it official (sequence watched live at Belmont, Oct 2 2026)."""

    def test_went_off(self):
        t = nyra.parse_post_time
        seen = t("2026-10-02T13:47:08")   # when the board first saw the new post time
        self.assertTrue(nyra.went_off("2026-10-02T13:43:00", "2026-10-02T13:45:20", seen))    # off-time rewrite
        self.assertFalse(nyra.went_off("2026-10-02T13:43:00", "2026-10-02T13:43:00", seen))   # unchanged
        self.assertFalse(nyra.went_off("2026-10-02T13:43:00", "2026-10-02T13:48:00", seen))   # delayed, whole minute
        self.assertFalse(nyra.went_off(None, "2026-10-02T13:45:20", seen))                    # never saw the schedule
        # Delay (race 3): new post time set ahead of time; it passing later doesn't mean the race was run
        self.assertFalse(nyra.went_off("2026-10-02T14:16:00", "2026-10-02T14:29:48", t("2026-10-02T14:27:30")))
        # ...but the off time, written after the fact, does
        self.assertTrue(nyra.went_off("2026-10-02T14:16:00", "2026-10-02T14:31:48", t("2026-10-02T14:34:22")))

    def test_race_finished(self):
        self.assertFalse(nyra.race_finished(PAGE))
        self.assertTrue(nyra.race_finished(race_page("3", "2026-10-01T15:12:00", official=True)))
        self.assertFalse(nyra.race_finished("<html>maintenance</html>"))

    def _feed(self, pages):
        import config
        from utilities import racefeed
        self._saved = config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP
        config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP = (lambda: None), "belmont", 0
        feed = racefeed.RaceFeed(start=False)
        feed._get = lambda url: pages[url]
        return feed

    def tearDown(self):
        import config
        from utilities import racefeed
        if hasattr(self, "_saved"):
            config.reload, config.RACE_TRACK, racefeed.CARD_FETCH_GAP = self._saved

    def _day(self):
        now = datetime.now(nyra.NYRA_TZ).replace(tzinfo=None)
        iso = lambda dt: dt.isoformat(timespec="seconds")
        post3 = now.replace(second=0) - timedelta(minutes=3)
        track = (f'<html><div><span>Race 3 - </span><span class="mtp-badge" data-mtp-variant="header" '
                 f'data-post-time="{iso(post3)}">0</span></div>'
                 '<a hx-get="/belmont/rdl/race/?race=3">3</a><a hx-get="/belmont/rdl/race/?race=4">4</a></html>')
        pages = {nyra.track_page_url("belmont"): track,
                 nyra.race_fragment_url("belmont", "3"): race_page("3", iso(post3)),
                 nyra.race_fragment_url("belmont", "4"): race_page("4", iso(post3 + timedelta(minutes=30)))}
        return pages, post3, iso

    def test_moves_on_when_nyra_posts_the_off_time(self):
        pages, post3, iso = self._day()
        feed = self._feed(pages)
        feed._cycle()
        self.assertEqual(feed.race["race"], "3")
        # ~2 minutes after the off NYRA rewrites post time to the off time; header still says race 3
        pages[nyra.race_fragment_url("belmont", "3")] = race_page("3", iso(post3 + timedelta(seconds=97)))
        self.assertEqual(feed._cycle(), 1)
        self.assertEqual(feed.finished, {"3"})
        feed._cycle()
        self.assertEqual((feed.race["race"], feed.next_race), ("4", "4"))

    def test_moves_on_when_the_race_is_official(self):
        pages, post3, iso = self._day()
        feed = self._feed(pages)
        feed._cycle()
        pages[nyra.race_fragment_url("belmont", "3")] = race_page("3", iso(post3), official=True)
        self.assertEqual(feed._cycle(), 1)
        feed._cycle()
        self.assertEqual(feed.race["race"], "4")


SAMPLE_CARD = [  # Belmont, Oct 2 2026
    {"race": "1", "post_time": "2026-10-02T13:10:00", "distance": "7F", "surface": "Dirt", "runners": 9},
    {"race": "2", "post_time": "2026-10-02T13:43:00", "distance": "6 1/2F", "surface": "Turf", "runners": 7},
    {"race": "3", "post_time": "2026-10-02T14:16:00", "distance": "6 1/2F", "surface": "Turf", "runners": 7},
    {"race": "4", "post_time": "2026-10-02T14:49:00", "distance": "6F", "surface": "Dirt", "runners": 13},
    {"race": "5", "post_time": "2026-10-02T15:23:00", "distance": "1 1/16M", "surface": "Turf", "runners": 16},
]


class TestCardScreen(unittest.TestCase):
    def test_renders_four_races_a_page(self):
        self.assertEqual(rr.short_post("2026-10-02T13:10:00"), "1:10p")
        self.assertEqual(rr.short_post("2026-10-02T12:05:00"), "12:05p")
        self.assertEqual(rr.short_post("2026-10-02T11:30:00"), "11:30a")
        # Widest row stays in its columns: race 10 ends at x 6, "12:10p" spans x 10-30, distance starts at 35
        self.assertEqual(rr.text_width("10"), 7)
        self.assertEqual(rr.text_width("12:10p"), 21)
        self.assertEqual(rr.card_page_count(SAMPLE_CARD), 2)
        for page in (0, 1):
            img = rr.render_card("belmont", SAMPLE_CARD, page)
            self.assertEqual(img.size, (64, 32))
            self.assertIsNotNone(img.getbbox())
        # Page 2 has one race: nothing drawn below its row
        self.assertIsNone(rr.render_card("belmont", SAMPLE_CARD, 1).crop((0, 14, 64, 32)).getbbox())

    def test_track_names_fit(self):
        for name in rr.TRACK_LABELS.values():
            self.assertTrue(all(c in rr.GLYPHS for c in name + "TODAY:ap"))
            self.assertLess(rr.text_width(name) + 2 + rr.text_width("TODAY"), 63)
        self.assertEqual(rr.render_card("belmont", SAMPLE_CARD).getpixel((2, 1)), rr.TRACK_COLORS["belmont"])
        self.assertEqual(rr.render_card("saratoga", SAMPLE_CARD).getpixel((2, 1)), rr.TRACK_COLORS["saratoga"])

    def test_takes_turns_with_the_clock_and_skips_finished_races(self):
        import config
        import display

        class Feed:
            race, last_update, last_error = None, None, None
            track, card, next_race = "belmont", SAMPLE_CARD, "3"

            def refresh_now(self):
                pass

        display.RaceFeed = Feed
        _use_sample_weather()
        d = display.Display()
        saved = config.CARD_SECONDS, display.time
        try:
            config.CARD_SECONDS = 45
            display.time = type("Clock", (), {"time": staticmethod(lambda: 45.0)})    # card's turn
            screen = d._card_screen()
            self.assertEqual([r["race"] for r in screen["card"]], ["3", "4", "5"])
            d.check_for_race(0)
            d.race_board(0)
            # 3 races fit on one page, so the panel shows exactly the card screen
            self.assertEqual(d.canvas.img.tobytes(), rr.render_card("belmont", screen["card"], 0).tobytes())
            display.time = type("Clock", (), {"time": staticmethod(lambda: 90.0)})    # clock's turn
            self.assertIsNone(d._card_screen())
            config.CARD_SECONDS = 0                                                    # turned off
            display.time = type("Clock", (), {"time": staticmethod(lambda: 45.0)})
            self.assertIsNone(d._card_screen())
        finally:
            config.CARD_SECONDS, display.time = saved


class TestIdlePicture(unittest.TestCase):
    """The web UI's picture of the clock & weather screen."""

    def test_font_matches_panel_placement(self):
        from PIL import Image
        from utilities import idle_render
        img = Image.new("RGB", (8, 8))
        # 4x6 "1", baseline at y=5 like graphics.DrawText: rows .X.. / XX.. / .X.. / .X.. / XXX.
        self.assertEqual(idle_render.draw_text(img, "4x6.bdf", 0, 5, (255, 0, 0), "1"), 4)
        lit = {(x, y) for y in range(8) for x in range(8) if img.getpixel((x, y)) != (0, 0, 0)}
        self.assertEqual(lit, {(1, 0), (0, 1), (1, 1), (1, 2), (1, 3), (0, 4), (1, 4), (2, 4)})

    def test_record_only_counts_changes(self):
        from utilities.idle_render import record

        class Scene:
            pass
        s = Scene()
        op = [("text", "5x8.bdf", 40, 6, (255, 255, 255), "72°")]
        record(s, "temperature", op)
        record(s, "temperature", list(op))
        self.assertEqual(s._idle_version, 1)


def sample_forecast():
    """Three days of made-up weather in the shape Tomorrow.io returns."""
    today = datetime.now().astimezone().replace(hour=6, minute=0, second=0, microsecond=0)
    days = []
    for i, (code, lo, hi) in enumerate([(1000, 61, 79), (4001, 58, 66), (1100, 55, 70)]):
        d = today + timedelta(days=i)
        days.append({"startTime": d.isoformat(), "values": {
            "weatherCodeFullDay": code, "temperatureMin": lo, "temperatureMax": hi, "moonPhase": 2,
            "sunriseTime": d.strftime("%Y-%m-%dT11:00:00Z"), "sunsetTime": d.strftime("%Y-%m-%dT22:30:00Z")}})
    return days


def _use_sample_weather():
    """Keep the idle screens off the internet: sample weather, no weather alerts."""
    from scenes import clock, date, daysforecast, temperature
    clock.grab_forecast = date.grab_forecast = daysforecast.grab_forecast = lambda tag="": sample_forecast()
    temperature.grab_temperature_and_humidity = lambda: (72.4, 40, 1000)
    clock.get_nws_alerts = lambda: []


class TestDisplayLoop(unittest.TestCase):
    def test_idle_race_idle(self):
        import display

        class FakeFeed:
            def __init__(self):
                self.race, self.last_update, self.last_error = None, None, None
                self.track, self.card, self.next_race = "belmont", [], None

            def refresh_now(self):
                pass

        display.RaceFeed = FakeFeed
        _use_sample_weather()
        d = display.Display()

        def step(n):
            for _ in range(n):
                for kf in d.keyframes:
                    p = kf.properties
                    if d.frame == 0 and p["divisor"] == 0:
                        kf()
                    if d.frame > 0 and p["divisor"] and not ((d.frame - p["offset"]) % p["divisor"]):
                        kf(p["count"])
                d.frame += 1

        step(12)
        self.assertEqual(d._data, [])
        # Idle: the clock screen is recorded and redrawn as a picture for the web UI
        from utilities.idle_render import render_idle
        self.assertEqual(set(d._idle_view), {"clock", "temperature", "date", "forecast"})
        self.assertEqual(d._idle_view["temperature"][0][5], "72°")
        self.assertEqual([op[5] for op in d._idle_view["forecast"] if op[0] == "text"][:3],
                         [datetime.now().strftime("%a"), "79", "61"])
        self.assertIsNotNone(render_idle(d._idle_view).getbbox())
        d.write_status(0)
        self.assertEqual(d._last_frame, ("idle", d._idle_version))
        race = nyra.parse_race(PAGE)
        race["post_time"] = (datetime.now(nyra.NYRA_TZ) + timedelta(minutes=30)).replace(tzinfo=None).isoformat(timespec="seconds")
        d.feed.race = race
        step(22)
        self.assertEqual(d._data[0]["race"], "3")
        self.assertIsNotNone(d.canvas.img.getbbox())
        d.feed.race = None
        step(12)
        self.assertEqual(d._data, [])


if __name__ == "__main__":
    unittest.main()
