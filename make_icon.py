#!/usr/bin/env python3
"""Generate Prowl's app icon (icon.icns) from scratch with PIL.

Design: dark rounded-square, a soft glowing motion trail (the cursor's path
across the screen), and a white arrow pointer at the end of the trail.
Run:  python3 make_icon.py   ->   produces icon.icns (+ icon.iconset/)
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter

S = 1024  # master size


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def vertical_gradient(size, top, bottom):
    base = Image.new("RGB", (size, size), top)
    top_r, top_g, top_b = top
    bot_r, bot_g, bot_b = bottom
    px = base.load()
    for y in range(size):
        t = y / (size - 1)
        r = int(top_r + (bot_r - top_r) * t)
        g = int(top_g + (bot_g - top_g) * t)
        b = int(top_b + (bot_b - top_b) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return base


def make_master():
    # Background: deep indigo -> near-black gradient
    bg = vertical_gradient(S, (46, 49, 88), (18, 18, 30)).convert("RGBA")

    # Motion trail: a glowing curved dashed path (the "prowl" route)
    trail = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    td = ImageDraw.Draw(trail)
    cx, cy, rad = S * 0.46, S * 0.52, S * 0.26
    pts = []
    for i in range(0, 240):
        a = math.radians(i * 1.5)            # ~1 turn, spiraling slightly
        r = rad * (1 - i / 700.0)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    # draw as a series of fading dots for a comet-trail feel
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / n
        alpha = int(40 + 180 * t)
        rr = 6 + 10 * t
        td.ellipse([x - rr, y - rr, x + rr, y + rr],
                   fill=(120, 200, 255, alpha))
    trail = trail.filter(ImageFilter.GaussianBlur(6))

    # Arrow cursor at the trail's end (classic macOS-ish pointer)
    cur = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cur)
    ex, ey = pts[-1]
    sc = S * 0.0011
    # pointer polygon relative to tip (ex,ey)
    poly = [(0, 0), (0, 330), (92, 250), (150, 380),
            (205, 356), (150, 228), (270, 228)]
    poly = [(ex + px_ * sc * 1.0, ey + py_ * sc * 1.0) for (px_, py_) in poly]
    # subtle drop shadow
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(p[0] + 8, p[1] + 10) for p in poly],
                               fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    cd.polygon(poly, fill=(255, 255, 255, 255),
               outline=(30, 30, 40, 255))

    comp = Image.alpha_composite(bg, trail)
    comp = Image.alpha_composite(comp, sh)
    comp = Image.alpha_composite(comp, cur)

    # apply rounded-rect mask
    mask = rounded_mask(S, int(S * 0.225))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(comp, (0, 0), mask)
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    master = make_master()
    master_path = os.path.join(here, "icon_1024.png")
    master.save(master_path)

    iconset = os.path.join(here, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    specs = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for px, name in specs:
        master.resize((px, px), Image.LANCZOS).save(
            os.path.join(iconset, f"icon_{name}.png"))

    subprocess.run(["iconutil", "-c", "icns", iconset,
                    "-o", os.path.join(here, "icon.icns")], check=True)
    print("wrote icon.icns")


if __name__ == "__main__":
    main()
