"""Stand-in for the rgbmatrix panel library so the display loop can run on any computer (tests only)."""
from PIL import Image
from . import graphics
class RGBMatrixOptions: pass
class Canvas:
    def __init__(self): self.img = Image.new("RGB", (64, 32))
    def Clear(self): self.img.paste((0, 0, 0), (0, 0, 64, 32))
    def SetImage(self, im, x=0, y=0): self.img.paste(im.convert("RGB"), (x, y))
    def SetPixel(self, x, y, r, g, b):
        if 0 <= x < 64 and 0 <= y < 32: self.img.putpixel((x, y), (r, g, b))
class RGBMatrix:
    def __init__(self, options=None): self.brightness = 100; self.c = Canvas()
    def CreateFrameCanvas(self): return self.c
    def SwapOnVSync(self, c): return c
