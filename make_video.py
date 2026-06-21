#!/usr/bin/env python3
"""
Render a professional product-launch video for Prowl (1920x1080, 30fps) with a
synced voiceover (macOS `say`), Avenir Next typography, the real 🐭/🐾 emoji,
and the live spin counter.

    python3 make_video.py        # -> prowl_launch.mp4  (with narration)

Pipeline: generate per-scene narration audio, measure each clip, lay out scenes
to match, render frames with PIL piped to ffmpeg, mux the voiceover track.
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))

AV = "/System/Library/Fonts/Avenir Next.ttc"
AV_BOLD, AV_BOLDIT, AV_DEMI, AV_DEMIIT, AV_IT, AV_MED, AV_MEDIT, AV_REG = range(8)
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"

ACCENT = (110, 200, 255)
GREEN = (64, 210, 130)
RED = (240, 100, 96)
WHITE = (245, 247, 252)
SUB = (150, 154, 178)

# ---- narration (one line per scene) ----
NARRATION = [
    "Meet Prowl.",
    "Step away, and your Mac drifts to sleep. S S H sessions drop. Background tasks die.",
    "Prowl keeps it awake — a gentle nudge of the cursor, every minute. Never a click.",
    "It lives in your menu bar. Start it, and watch every spin count. One. Two. Three.",
    "Run it as a clean window, or share it with your whole team.",
    "Prowl. Keeps your Mac awake.",
]
SCENE_NAMES = ["intro", "problem", "solution", "menubar", "options", "outro"]
PAD = [0.9, 0.7, 0.8, 1.0, 0.8, 1.8]   # trailing silence/breeze per scene


# ---------- fonts ----------
_fonts = {}
def font(size, index=AV_DEMI):
    key = (size, index)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(AV, size, index=index)
    return _fonts[key]


# ---------- emoji ----------
_emoji = {}
def emoji_img(char, target):
    key = (char, target)
    if key not in _emoji:
        f = ImageFont.truetype(EMOJI, 96)
        tmp = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((8, 8), char, font=f, embedded_color=True)
        crop = tmp.crop(tmp.getbbox())
        scale = target / crop.height
        _emoji[key] = crop.resize((max(1, int(crop.width * scale)), target),
                                   Image.LANCZOS)
    return _emoji[key]


# ---------- helpers ----------
def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def fade(s, D, start=0.0, fin=0.5, fout=0.6):
    """Element alpha 0..1 within a scene of length D, appearing at `start`."""
    if s < start:
        return 0.0
    a = min(1.0, (s - start) / fin) if fin else 1.0
    b = min(1.0, (D - s) / fout) if fout else 1.0
    return max(0.0, min(a, b))


def make_bg():
    top, bot = (30, 33, 60), (9, 10, 17)
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        f = y / (H - 1)
        px_row = (int(top[0] + (bot[0] - top[0]) * f),
                  int(top[1] + (bot[1] - top[1]) * f),
                  int(top[2] + (bot[2] - top[2]) * f))
        for x in range(W):
            px[x, y] = px_row
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([W // 2 - 760, -360, W // 2 + 760, 720], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(240))
    img = Image.composite(Image.new("RGB", (W, H), (64, 86, 150)), img, glow)
    return img.convert("RGBA")


BG = make_bg()
ICON = Image.open(os.path.join(HERE, "icon_1024.png")).convert("RGBA")
_icon = {}
def icon_at(size):
    if size not in _icon:
        _icon[size] = ICON.resize((size, size), Image.LANCZOS)
    return _icon[size]


_text_cache = {}
def text_img(s, fnt, fill):
    key = (s, id(fnt), fill)
    if key not in _text_cache:
        dummy = Image.new("RGBA", (10, 10))
        bb = ImageDraw.Draw(dummy).textbbox((0, 0), s, font=fnt)
        w, h = bb[2] - bb[0] + 8, bb[3] - bb[1] + 8
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((4 - bb[0], 4 - bb[1]), s, font=fnt, fill=fill + (255,))
        _text_cache[key] = img
    return _text_cache[key]


def paste_alpha(base, img, center, alpha):
    a = int(alpha)
    if a <= 0:
        return
    if a < 255:
        ch = img.getchannel("A").point(lambda p: p * a // 255)
        img = img.copy()
        img.putalpha(ch)
    base.alpha_composite(img, (int(center[0] - img.width / 2),
                               int(center[1] - img.height / 2)))


def text(base, center, s, fnt, fill, alpha):
    if alpha > 0:
        paste_alpha(base, text_img(s, fnt, fill), center, alpha)


def cursor(base, x, y, scale, alpha):
    if alpha <= 0:
        return
    poly = [(0, 0), (0, 330), (92, 250), (150, 380),
            (205, 356), (150, 228), (270, 228)]
    poly = [(x + px * scale, y + py * scale) for (px, py) in poly]
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(poly, fill=WHITE + (int(alpha),),
                                  outline=(20, 20, 30, int(alpha)))
    base.alpha_composite(layer)


def trail(base, path_fn, u, alpha):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(20):
        uu = u - i * 0.011
        if uu < 0:
            break
        px, py = path_fn(uu)
        a = int(alpha * (1 - i / 20) * 0.5)
        r = 5 + (1 - i / 20) * 9
        d.ellipse([px - r, py - r, px + r, py + r], fill=ACCENT + (a,))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)))


def menu_dropdown(base, x, y, alpha, cycle):
    if alpha <= 0:
        return
    pw, rh = 380, 56
    rows = [("Start Prowling", "start"),
            (f"Status:  Prowling… (cycle {cycle})", "plain"),
            ("Interval", "submenu"), ("—", None), ("Quit", "plain")]
    ph = 28 + sum(18 if lbl == "—" else rh for lbl, _ in rows)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x, y, x + pw, y + ph], radius=18,
                        fill=(40, 40, 54, int(0.97 * alpha)),
                        outline=(255, 255, 255, int(0.10 * alpha)), width=1)
    fnt = font(25, AV_MED)
    cy = y + 14
    for lbl, kind in rows:
        if lbl == "—":
            d.line([x + 16, cy + 9, x + pw - 16, cy + 9],
                   fill=(255, 255, 255, int(0.12 * alpha)))
            cy += 18
            continue
        tx, col = x + 24, (232, 233, 244)
        mid = cy + rh / 2
        if kind == "start":
            d.rounded_rectangle([x + 8, cy + 4, x + pw - 8, cy + rh - 8],
                                radius=10, fill=ACCENT + (int(0.92 * alpha),))
            col = (14, 18, 30)
            d.polygon([(x + 24, mid - 11), (x + 24, mid + 11), (x + 44, mid)],
                      fill=col + (int(alpha),))
            tx = x + 58
        d.text((tx, mid), lbl, font=fnt, fill=col + (int(alpha),), anchor="lm")
        if kind == "submenu":
            d.line([(x + pw - 34, mid - 9), (x + pw - 24, mid)],
                   fill=col + (int(alpha),), width=3)
            d.line([(x + pw - 34, mid + 9), (x + pw - 24, mid)],
                   fill=col + (int(alpha),), width=3)
        cy += rh
    base.alpha_composite(layer)


def window_mock(base, cx, cy, alpha, running=True, cyc=2):
    if alpha <= 0:
        return
    w, h = 520, 360
    x, y = cx - w // 2, cy - h // 2
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x, y, x + w, y + h], radius=22,
                        fill=(22, 22, 32, int(0.98 * alpha)),
                        outline=(255, 255, 255, int(0.12 * alpha)), width=1)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([x + 22 + i * 26, y + 20, x + 36 + i * 26, y + 34],
                  fill=c + (int(alpha),))
    base.alpha_composite(layer)
    paste_alpha(base, icon_at(86), (cx, y + 110), alpha)
    text(base, (cx, y + 180), "Prowl", font(40, AV_BOLD), WHITE, alpha)
    text(base, (cx, y + 222),
         f"running 02:0{cyc} · {cyc} cycles" if running else "Stopped",
         font(24, AV_MED), SUB, alpha)
    layer2 = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d2 = ImageDraw.Draw(layer2)
    d2.rounded_rectangle([x + 70, y + 260, x + 230, y + 318], radius=12,
                         fill=GREEN + (int(alpha),))
    d2.rounded_rectangle([x + 290, y + 260, x + 450, y + 318], radius=12,
                         fill=RED + (int(alpha),))
    base.alpha_composite(layer2)
    text(base, (x + 150, y + 289), "START", font(26, AV_BOLD), (10, 30, 18), alpha)
    text(base, (x + 370, y + 289), "STOP", font(26, AV_BOLD), (40, 12, 12), alpha)


def menubar(base, alpha, glyph_char, count=None):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 0, W, 52], fill=(0, 0, 0, int(0.5 * alpha)))
    d.text((W - 40, 26), "100%   9:41", font=font(24, AV_MED),
           fill=(235, 235, 245, int(alpha)), anchor="rm")
    base.alpha_composite(layer)
    gx = W - 260
    paste_alpha(base, emoji_img(glyph_char, 34), (gx, 26), alpha)
    if count is not None:
        text(base, (gx + 46, 26), str(count), font(28, AV_BOLD), WHITE, alpha)


# ---------- scenes (s = local seconds, D = scene duration) ----------
def scene_intro(img, s, D):
    sc = ease(min(1.0, s / 0.9))
    size = int(170 + 210 * sc)
    if 0.85 < s < 1.4:
        size += int(20 * math.sin((s - 0.85) / 0.55 * math.pi))
    paste_alpha(img, icon_at(max(40, size)), (W // 2, H // 2 - 60),
                255 * min(1.0, s / 0.85) * fade(s, D, 0, 0.01, 0.5))
    text(img, (W // 2, H // 2 + 175), "Meet Prowl", font(110, AV_BOLD),
         WHITE, 255 * fade(s, D, 0.7, 0.5, 0.5))


def scene_problem(img, s, D):
    lines = [("You step away…", 0.3, WHITE),
             ("your Mac falls asleep.", 1.4, WHITE),
             ("SSH drops.  Tasks die.", 2.6, RED)]
    for txt, t0, col in lines:
        text(img, (W // 2, H // 2 - 130 + lines.index((txt, t0, col)) * 135),
             txt, font(66, AV_DEMI), col, 255 * fade(s, D, t0, 0.5, 0.4))


def scene_solution(img, s, D):
    def path(u):
        cx, cy, r = W * 0.5, H * 0.40, 360
        a = u * math.pi * 2.2
        return (cx + r * math.cos(a) * 1.5, cy + r * math.sin(a) * 0.7)
    u = ease(min(1.0, (s - 0.2) / (D - 1.0)))
    cx_, cy_ = path(u)
    trail(img, path, u, 255 * fade(s, D, 0.1, 0.4, 0.6))
    cursor(img, cx_, cy_, 0.32, 255 * fade(s, D, 0.1, 0.3, 0.6))
    text(img, (W // 2, H // 2 + 200), "Prowl keeps it awake.",
         font(86, AV_BOLD), WHITE, 255 * fade(s, D, 0.5, 0.5, 0.5))
    text(img, (W // 2, H // 2 + 300),
         "a gentle nudge of the cursor, every minute — never a click",
         font(38, AV_MED), SUB, 255 * fade(s, D, 1.1, 0.6, 0.5))


def scene_menubar(img, s, D):
    cyc = max(1, min(3, int((s - 1.0) / 1.0) + 1)) if s > 1.0 else 1
    glyph = "🐭" if s < 0.9 else "🐾"
    show_count = None if s < 0.9 else cyc
    a = 255 * fade(s, D, 0.0, 0.5, 0.5)
    menubar(img, a, glyph, show_count)
    menu_dropdown(img, W - 260 - 380 + 70, 70, 255 * fade(s, D, 0.5, 0.5, 0.5), cyc)
    text(img, (560, 360), "Lives in your menu bar", font(64, AV_BOLD),
         WHITE, 255 * fade(s, D, 0.4, 0.5, 0.5))
    text(img, (560, 470), "Click Start — every spin counts:", font(40, AV_MED),
         (225, 228, 240), 255 * fade(s, D, 1.0, 0.5, 0.5))
    if s > 1.0:
        big = "🐾  " + " ".join(str(i) for i in range(1, cyc + 1))
        text(img, (560, 600), big.replace("🐾  ", ""), font(120, AV_BOLD),
             ACCENT, 255 * fade(s, D, 1.0, 0.4, 0.5))
    text(img, (560, 720), "resets to 1 each time you Start", font(32, AV_IT),
         SUB, 255 * fade(s, D, 1.6, 0.6, 0.5))


def scene_options(img, s, D):
    text(img, (W // 2, 250), "Runs your way", font(72, AV_BOLD),
         WHITE, 255 * fade(s, D, 0.2, 0.5, 0.5))
    window_mock(img, W * 0.32, H * 0.60, 255 * fade(s, D, 0.6, 0.5, 0.5))
    # menu-bar mini + share note on the right
    rx = W * 0.72
    paste_alpha(img, emoji_img("🐾", 90), (rx, H * 0.50),
                255 * fade(s, D, 1.0, 0.5, 0.5))
    text(img, (rx, H * 0.50 + 90), "menu-bar widget", font(36, AV_MED),
         (225, 228, 240), 255 * fade(s, D, 1.0, 0.5, 0.5))
    text(img, (rx, H * 0.68), "Share the app", font(44, AV_DEMI),
         WHITE, 255 * fade(s, D, 1.6, 0.5, 0.5))
    text(img, (rx, H * 0.68 + 56), "with your whole team", font(36, AV_MED),
         SUB, 255 * fade(s, D, 1.6, 0.5, 0.5))


def scene_outro(img, s, D):
    a = 255 * fade(s, D, 0.2, 0.6, 0.0)
    paste_alpha(img, icon_at(290), (W // 2, H // 2 - 110), a)
    text(img, (W // 2, H // 2 + 120), "Prowl", font(118, AV_BOLD), WHITE, a)
    text(img, (W // 2, H // 2 + 220), "keeps your Mac awake.",
         font(46, AV_MED), SUB, a)
    text(img, (W // 2, H - 90), "github.com/alvi75/Prowl",
         font(34, AV_DEMI), ACCENT, 255 * fade(s, D, 0.9, 0.7, 0.0))


SCENE_FN = {"intro": scene_intro, "problem": scene_problem,
            "solution": scene_solution, "menubar": scene_menubar,
            "options": scene_options, "outro": scene_outro}


def draw_frame(t, starts, durs):
    img = BG.copy()
    for i, name in enumerate(SCENE_NAMES):
        if starts[i] <= t < starts[i] + durs[i] or (i == len(SCENE_NAMES) - 1
                                                     and t >= starts[i]):
            SCENE_FN[name](img, t - starts[i], durs[i])
            break
    return img.convert("RGB")


def ffprobe_dur(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(out.strip())


def build_voice(durs):
    """Per-scene narration padded to scene length, concatenated -> voice.wav."""
    scene_wavs = []
    for i in range(len(NARRATION)):
        aiff = f"/tmp/prowl_vo_{i}.aiff"
        wav = f"/tmp/prowl_scene_{i}.wav"
        subprocess.run(["say", "-v", "Samantha", "-r", "172", "-o", aiff,
                        NARRATION[i]], check=True)
        # pad with trailing silence to exactly the scene duration
        subprocess.run(["ffmpeg", "-y", "-i", aiff, "-af", "apad",
                        "-t", f"{durs[i]:.3f}", "-ar", "44100", "-ac", "2",
                        wav], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        scene_wavs.append(wav)
    listf = "/tmp/prowl_concat.txt"
    with open(listf, "w") as f:
        for w in scene_wavs:
            f.write(f"file '{w}'\n")
    voice = "/tmp/prowl_voice.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf,
                    "-c", "copy", voice], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return voice


def main():
    # 1) narration -> per-scene durations
    raw = []
    for i in range(len(NARRATION)):
        aiff = f"/tmp/prowl_vo_{i}.aiff"
        subprocess.run(["say", "-v", "Samantha", "-r", "172", "-o", aiff,
                        NARRATION[i]], check=True)
        raw.append(ffprobe_dur(aiff))
    durs = [raw[i] + PAD[i] for i in range(len(raw))]
    starts = [sum(durs[:i]) for i in range(len(durs))]
    total = sum(durs)
    print(f"scene durations: {[round(d,1) for d in durs]}  total={total:.1f}s")

    # 2) voice track
    voice = build_voice(durs)

    # 3) render frames -> ffmpeg, mux voice
    out = os.path.join(HERE, "prowl_launch.mp4")
    nframes = int(total * FPS)
    cmd = ["ffmpeg", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-",
           "-i", voice,
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
           "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(nframes):
        proc.stdin.write(draw_frame(i / FPS, starts, durs).tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{nframes}")
    proc.stdin.close()
    proc.wait()
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
