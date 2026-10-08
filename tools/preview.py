"""Save an LED-style picture of the race screens, clock & weather, and today's card, no panel needed.

    python3 tools/preview.py                     # uses the sample page in tests/fixtures
    python3 tools/preview.py saved_page.html     # or a page saved from nyra.com (Ctrl+S, HTML only)

Writes preview.png in the current folder. The clock screen uses made-up sample weather.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw                                   # noqa: E402
from utilities import nyra                                         # noqa: E402
from utilities.race_render import render_full_board, render_big_mtp, led_preview, page_count  # noqa: E402

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "fixtures", "race_page.html")
race = nyra.parse_race(open(src, encoding="utf-8").read())
if race is None:
    sys.exit("Couldn't read a race from that page.")

frames = []
for mtp in (25, 8, 2):
    r = dict(race, mtp=mtp)
    for p in range(page_count(r)):
        frames.append((f"Full board, {mtp} MTP" + (f", page {p + 1}" if page_count(r) > 1 else ""), render_full_board(r, p)))
    frames.append((f"Big MTP, {mtp} MTP", render_big_mtp(r)))


def idle_frame():
    """Run the real display loop on the stand-in panel with sample weather, and
    return the web UI's picture of the clock & weather screen."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_board                                              # adds the stand-in panel
    import display
    from utilities.idle_render import render_idle

    class NoRaces:
        race, last_update, last_error = None, None, None
        track, card, next_race = "belmont", [], None

        def refresh_now(self):
            pass

    display.RaceFeed = NoRaces
    test_board._use_sample_weather()
    d = display.Display()
    for frame in range(12):
        d.frame = frame
        for kf in d.keyframes:
            p = kf.properties
            if frame == 0 and p["divisor"] == 0:
                kf()
            if frame > 0 and p["divisor"] and not ((frame - p["offset"]) % p["divisor"]):
                kf(p["count"])
    return render_idle(d._idle_view)


frames.append(("Clock & weather (sample weather)", idle_frame()))

from test_board import SAMPLE_CARD                                 # noqa: E402  (path added by idle_frame)
from utilities.race_render import render_card, card_page_count    # noqa: E402
for p in range(card_page_count(SAMPLE_CARD)):
    frames.append((f"Today's card (sample), page {p + 1}", render_card("belmont", SAMPLE_CARD, p)))
from utilities.race_render import render_pick5                    # noqa: E402
frames.append(("Today's card, Pick 5 page (Belmont, Oct 8 2026)", render_pick5("belmont", [
    {"label": "EARLY", "first": "1", "last": "5", "post_time": "2026-10-08T13:10:00"},
    {"label": "MANDATORY PAY", "first": "3", "last": "7", "post_time": "2026-10-08T14:16:00"},
    {"label": "LATE", "first": "5", "last": "9", "post_time": "2026-10-08T15:23:00"}])))

pad, cap = 20, 26
tiles = [(t, led_preview(img, dot=8)) for t, img in frames]
w = tiles[0][1].width + 2 * pad
sheet = Image.new("RGB", (w, sum(t.height + cap + pad for _, t in tiles) + pad), (245, 245, 245))
d, y = ImageDraw.Draw(sheet), pad
for title, tile in tiles:
    d.text((pad, y + 6), title, fill=(30, 30, 30))
    sheet.paste(tile, (pad, y + cap))
    y += tile.height + cap + pad
sheet.save("preview.png")
print("Wrote preview.png")
