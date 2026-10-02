"""Picture of the clock & weather screen for the web UI's Board page.

The idle scenes (from the plane tracker) draw straight onto the LED panel, so
there is no image to copy. Instead each scene notes what it drew - text, font,
colour, position, weather icons - with record(), and render_idle() redraws it
with Pillow using the panel's own .bdf pixel fonts, so the web picture matches
the LEDs. Pure Pillow: no panel library needed.
"""
import os

from PIL import Image

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

# setup/fonts.py attribute name -> font file, so scenes can record which font they used
FONT_FILES = {
    "extrasmall": "4x6.bdf",
    "small": "5x8.bdf",
    "regular": "6x13.bdf",
    "regular_bold": "6x13B.bdf",
    "regularplus": "7x13.bdf",
    "regularplus_bold": "7x13B.bdf",
    "large": "8x13.bdf",
    "large_bold": "8x13B.bdf",
}

# Scenes in drawing order; each owns its own part of the panel
REGIONS = ("clock", "temperature", "date", "forecast")

_glyph_cache = {}


def _load_bdf(name):
    """{codepoint: (advance, (w, h, xoff, yoff), [(row_bits, n_bits), ...])}"""
    if name in _glyph_cache:
        return _glyph_cache[name]
    glyphs, enc, adv, bbx, rows = {}, None, 0, None, None
    with open(os.path.join(FONT_DIR, name), encoding="latin-1") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            key = parts[0]
            if rows is not None:
                if key == "ENDCHAR":
                    if enc is not None and enc >= 0 and bbx:
                        glyphs[enc] = (adv, bbx, rows)
                    rows = None
                else:
                    rows.append((int(key, 16), len(key) * 4))
            elif key == "ENCODING":
                enc = int(parts[1])
            elif key == "DWIDTH":
                adv = int(parts[1])
            elif key == "BBX":
                bbx = tuple(int(v) for v in parts[1:5])
            elif key == "BITMAP":
                rows = []
    _glyph_cache[name] = glyphs
    return glyphs


def draw_text(img, font_file, x, y, color, text):
    """Same placement as rgbmatrix graphics.DrawText: y is the baseline.
    Returns the width drawn, like DrawText."""
    glyphs = _load_bdf(font_file)
    px = img.load()
    start = x
    for ch in text:
        g = glyphs.get(ord(ch)) or glyphs.get(0xFFFD)
        if g is None:
            continue
        adv, (w, h, xoff, yoff), rows = g
        top = y - h - yoff
        for r, (bits, n) in enumerate(rows):
            for c in range(w):
                if bits & (1 << (n - 1 - c)):
                    gx, gy = x + xoff + c, top + r
                    if 0 <= gx < img.width and 0 <= gy < img.height:
                        px[gx, gy] = color
        x += adv
    return x - start


def font_file(font):
    """Font file for a font object from setup/fonts.py."""
    from setup import fonts
    for attr, name in FONT_FILES.items():
        if getattr(fonts, attr, None) is font:
            return name
    return FONT_FILES["small"]


def rgb(colour):
    return (colour.red, colour.green, colour.blue)


def text_op(font, x, y, colour, text):
    return ("text", font_file(font), x, y, rgb(colour), text)


def image_op(x, y, image):
    return ("image", x, y, image.convert("RGB"))


def record(scene, region, ops):
    """Note what a scene just drew in its region. Bumps a version number only when
    something changed, so the display re-renders the picture only then."""
    view = scene.__dict__.setdefault("_idle_view", {})
    if view.get(region) != ops:
        view[region] = ops
        scene._idle_version = getattr(scene, "_idle_version", 0) + 1


def render_idle(view):
    """64x32 picture of the clock & weather screen from the recorded drawing."""
    img = Image.new("RGB", (64, 32), (0, 0, 0))
    for region in REGIONS:
        for op in view.get(region, []):
            if op[0] == "text":
                _, name, x, y, color, text = op
                draw_text(img, name, x, y, color, text)
            elif op[0] == "image":
                _, x, y, im = op
                img.paste(im, (x, y))
    return img
