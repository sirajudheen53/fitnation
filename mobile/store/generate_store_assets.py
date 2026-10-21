#!/usr/bin/env python3
"""Generate FitNation Play-store icon assets from the brand palette.

palette = app_theme.dart: primaryDark #4B0E9F, primary #6C13E2,
primaryLight #9D54F0, accent mint #00E5A0.
"""
from PIL import Image, ImageDraw, ImageFont
import os

MOBILE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = f"{MOBILE}/android/app/src/main/res"
STORE = f"{MOBILE}/store"

DARK, PRIMARY, LIGHT, MINT = (0x4B, 0x0E, 0x9F), (0x6C, 0x13, 0xE2), (0x9D, 0x54, 0xF0), (0x00, 0xE5, 0xA0)
WHITE = (255, 255, 255, 255)


def gradient(w=1024, h=1024):
    """Diagonal dark->primary->light gradient, 2x2 corner trick + bilinear."""
    small = Image.new("RGB", (3, 3))
    px = small.load()
    px[0, 0] = px[0, 1] = px[0, 2] = DARK          # left column dark
    px[1, 0] = px[1, 1] = px[1, 2] = PRIMARY       # middle column primary
    px[2, 0] = px[2, 1] = px[2, 2] = LIGHT         # right column light
    return small.resize((w, h), Image.BILINEAR)


def dumbbell(canvas, cx, cy, gw=460, gh=368, colour=WHITE, alpha=255):
    """White dumbbell: two side plates + centre handle, rounded ends.

    Glyph spans gw x gh around (cx, cy); at gw=460/1024 the corners stay
    inside the adaptive-icon safe zone (33dp/108dp = ~30.5% radius).
    """
    d = ImageDraw.Draw(canvas, "RGBA")
    hw = gw // 2
    plate_w = int(gw * 0.191)
    y0, y1 = cy - gh // 2, cy + gh // 2
    c = colour + (alpha,) if len(colour) == 3 else colour
    # left plate, right plate
    d.rounded_rectangle([cx - hw, y0, cx - hw + plate_w, y1], radius=40, fill=c)
    d.rounded_rectangle([cx + hw - plate_w, y0, cx + hw, y1], radius=40, fill=c)
    # handle between the plates
    hy = int(gw * 0.12)
    d.rounded_rectangle([cx - hw + plate_w + 12, cy - hy // 2,
                         cx + hw - plate_w - 12, cy + hy // 2],
                        radius=hy // 2, fill=c)


def master(size=1024):
    img = gradient(size, size).convert("RGBA")
    dumbbell(img, size // 2, size // 2, size // 1024 * 460, size // 1024 * 368)
    return img


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("wrote", path)


os.makedirs(STORE, exist_ok=True)

# 1. Play store icon: exactly 512x512, opaque square. Play rounds/parallax-masks it.
save(master().resize((512, 512), Image.LANCZOS), f"{STORE}/app-icon-512.png")

# 2. Feature graphic 1024x500 (Play listing required asset).
fg = gradient(1024, 500).convert("RGBA")
d = ImageDraw.Draw(fg, "RGBA")
bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 104)
reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
d.text((72, 128), "FitNation", font=bold, fill=WHITE)
d.text((74, 268), "Every gym in your pocket.", font=reg, fill=MINT + (255,))
mini = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
dumbbell(mini, 512, 512, 460, 368)
# scale to ~72% and paste right side, slightly translucent
g2 = mini.resize((int(1024 * 0.72),) * 2, Image.LANCZOS)
g2.putalpha(g2.split()[3].point(lambda a: int(a * 0.9)))
fg.alpha_composite(g2, dest=(int(1024 * 0.63) - 130, 250 - int(1024 * 0.72) // 2))
save(fg, f"{STORE}/feature-graphic-1024x500.png")

# 3. Legacy launcher icons (density-1x full-bleed sizes).
for dpi, px in [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)]:
    save(master().resize((px, px), Image.LANCZOS), f"{RES}/mipmap-{dpi}/ic_launcher.png")

# 4. Adaptive icon layers: background = gradient only; foreground = glyph
#    (glyph already inside the 33dp safe zone) at 108dp densities.
for dpi, px in [("mdpi", 108), ("hdpi", 162), ("xhdpi", 216), ("xxhdpi", 324), ("xxxhdpi", 432)]:
    f = master  # glyph margin is fine, reuse master
    save(gradient(px, px).convert("RGBA").convert("RGBA"), f"{RES}/mipmap-{dpi}/ic_launcher_background.png")
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dumbbell(img, px // 2, px // 2, px * 460 // 1024, px * 368 // 1024)
    save(img, f"{RES}/mipmap-{dpi}/ic_launcher_foreground.png")
    # monochrome (Android 13 themed icons): transparent bg + glyph mask
    save(img, f"{RES}/mipmap-{dpi}/ic_launcher_mono.png")

print("done")