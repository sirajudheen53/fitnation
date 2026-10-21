#!/usr/bin/env python3
"""Generate FitNation Play-store icon assets from the brand palette.

palette = app_theme.dart: primaryDark #4B0E9F, primary #6C13E2,
primaryLight #9D54F0, accent mint #00E5A0.

FBOS-057: the glyph was rebuilt BOLD - thick plates, chunky rounded handle,
a soft darker-purple depth cue - sized to cover >=30% of the adaptive
66dp safe-zone box at 108dp. Everything is drawn once at 1024 and
LANCZOS-downscaled per density so every asset shares identical edges.
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

MOBILE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = f"{MOBILE}/android/app/src/main/res"
STORE = f"{MOBILE}/store"

DARK, PRIMARY, LIGHT, MINT = (0x4B, 0x0E, 0x9F), (0x6C, 0x13, 0xE2), (0x9D, 0x54, 0xF0), (0x00, 0xE5, 0xA0)
SHADOW = (0x2E, 0x08, 0x66, 230)  # depth cue: darker purple under the glyph
WHITE = (255, 255, 255, 255)

MASTER = 1024

# Glyph geometry, fractions of glyph width. The canvas-wide span
# GLYPH_W = 0.78 * 0.61 fills ~78% of the 66dp safe-zone box of a 108dp layer.
GLYPH_W = 0.476
GLYPH_H = 0.82            # glyph height / width
PLATE_W = 0.28            # plate thickness (was 0.191 -> thin line-art)
PLATE_R = 0.12            # plate corner radius
HANDLE_H = 0.26           # handle thickness (single-stroke ~0.12 before)
HANDLE_GAP = 0.04         # breathing gap between plates and handle
SHADOW_DXY = 8            # depth-cue offset at MASTER (~3px at 432)


def gradient(w=1024, h=1024):
    """Diagonal dark->primary->light gradient, 2x2 corner trick + bilinear."""
    small = Image.new("RGB", (3, 3))
    px = small.load()
    px[0, 0] = px[0, 1] = px[0, 2] = DARK          # left column dark
    px[1, 0] = px[1, 1] = px[1, 2] = PRIMARY       # middle column primary
    px[2, 0] = px[2, 1] = px[2, 2] = LIGHT         # right column light
    return small.resize((w, h), Image.BILINEAR)


def dumbbell(canvas, cx, cy, gw=460, gh=368, colour=WHITE, alpha=255):
    """Legacy thin glyph - kept ONLY for the feature graphic, which already
    shipped and must not change (FBOS-057 touches the icon set, not the art).
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


def bold_glyph(size=MASTER, shadow=False):
    """Bold filled dumbbell silhouette on a transparent size x size canvas."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gw = size * GLYPH_W
    gh, pw, hh = gw * GLYPH_H, gw * PLATE_W, gw * HANDLE_H
    gap, rp = gw * HANDLE_GAP, gw * PLATE_R
    cx = cy = size / 2
    x0, x1, y0, y1 = cx - gw / 2, cx + gw / 2, cy - gh / 2, cy + gh / 2
    layers = [(SHADOW, SHADOW_DXY, SHADOW_DXY), (WHITE, 0, 0)] if shadow else [(WHITE, 0, 0)]
    for colour, dx, dy in layers:
        d = ImageDraw.Draw(img, "RGBA")
        d.rounded_rectangle([x0, y0 + dy, x0 + pw, y1 + dy], radius=rp, fill=colour)
        d.rounded_rectangle([x1 - pw, y0 + dy, x1, y1 + dy], radius=rp, fill=colour)
        d.rounded_rectangle([x0 + pw + gap, cy - hh / 2 + dy,
                             x1 - pw - gap, cy + hh / 2 + dy], radius=hh / 2, fill=colour)
    return img


def master(size=MASTER):
    """Full-bleed brand gradient + bold glyph with depth cue."""
    img = gradient(size, size).convert("RGBA")
    img.alpha_composite(bold_glyph(size, shadow=True))
    return img


def highlight(img, cx_f=0.30, cy_f=0.24, reach=0.95, strength=0.08):
    """Soft top-left radial highlight so the gradient doesn't look flat."""
    s = img.size[0]
    m = Image.new("L", (64, 64), 0)
    p = m.load()
    hcx, hcy, R = cx_f * s, cy_f * s, reach * s
    for y in range(64):
        for x in range(64):
            dist = math.hypot((x + .5) / 64 * s - hcx, (y + .5) / 64 * s - hcy)
            p[x, y] = int(255 * strength * max(0.0, 1 - dist / R) ** 1.4)
    ov = Image.new("RGBA", (s, s), WHITE)
    ov.putalpha(m.resize((s, s), Image.BILINEAR))
    img.alpha_composite(ov)


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("wrote", path)


os.makedirs(STORE, exist_ok=True)
glyph = bold_glyph(MASTER, shadow=True)
glyph_flat = bold_glyph(MASTER, shadow=False)

# 1. Play store icon: exactly 512x512, opaque square. Play rounds/parallax-masks it.
store = master()
highlight(store)  # subtle top-left light so the gradient has depth
save(store.resize((512, 512), Image.LANCZOS), f"{STORE}/app-icon-512.png")

# 2. Feature graphic 1024x500 (Play listing required asset).
#    FBOS-057: UNCHANGED - asset already shipped, keep the legacy thin glyph.
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

# 4. Adaptive icon layers: background = gradient only; foreground = bold glyph
#    filling ~78% of the 66dp safe-zone box; mono = flat full silhouette
#    (Android 13 themed icons, no depth cue).
for dpi, px in [("mdpi", 108), ("hdpi", 162), ("xhdpi", 216), ("xxhdpi", 324), ("xxxhdpi", 432)]:
    save(gradient(px, px).convert("RGBA"), f"{RES}/mipmap-{dpi}/ic_launcher_background.png")
    save(glyph.resize((px, px), Image.LANCZOS), f"{RES}/mipmap-{dpi}/ic_launcher_foreground.png")
    save(glyph_flat.resize((px, px), Image.LANCZOS), f"{RES}/mipmap-{dpi}/ic_launcher_mono.png")

print("done")