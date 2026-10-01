"""Save an LED-style picture of the race screens, no panel needed.

    python3 tools/preview.py                     # uses the sample page in tests/fixtures
    python3 tools/preview.py saved_page.html     # or a page saved from nyra.com (Ctrl+S, HTML only)

Writes preview.png in the current folder.
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
