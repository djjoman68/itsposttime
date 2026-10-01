"""Race-mode screen: full odds board or big MTP, drawn whenever race data is present.

The idle scenes (clock, date, temperature, forecast) all step aside while
self._data has a race in it - the same hand-off the plane tracker uses
when a plane is overhead.
"""
import time

import config
from setup import frames
from utilities.animator import Animator
from utilities.nyra import minutes_to_post
from utilities.race_render import render_full_board, render_big_mtp, page_count


class RaceScene(object):
    def __init__(self):
        super().__init__()

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def race_board(self, count):
        if not self._data:
            return
        race = dict(self._data[0])
        race["mtp"] = minutes_to_post(race["post_time"])

        if config.RACE_VIEW == "big_mtp":
            image = render_big_mtp(race)
        else:
            pages = page_count(race)
            page = int(time.time() // config.RACE_PAGE_SECONDS) % pages
            image = render_full_board(race, page)

        self.last_race_image = image   # also shown in the web UI
        self.canvas.SetImage(image, 0, 0)
