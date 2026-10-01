"""Run with:  python3 -m unittest discover tests

No LED panel or internet needed: a fake rgbmatrix module stands in for the
panel, and a saved sample page stands in for nyra.com.
"""
import os
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


class TestDisplayLoop(unittest.TestCase):
    def test_idle_race_idle(self):
        import display

        class FakeFeed:
            def __init__(self):
                self.race, self.last_update, self.last_error = None, None, None

            def refresh_now(self):
                pass

        display.RaceFeed = FakeFeed
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
