#!/usr/bin/env python3
"""
prowl_core.py — the engine behind Prowl.

Keeps a Mac active by gently moving the cursor in cycles: it remembers where
the pointer is, glides to a spread of points across the screen (menu bar, Dock,
app windows), pauses at each, then glides home. It ONLY moves the cursor — it
never clicks. Posting real CGEventMouseMoved events resets the system idle
timer, which is what keeps the machine awake.

Both the window app (prowl_window.py) and the menu-bar widget
(prowl_menubar.py) drive this ProwlEngine.
"""

import random
import threading
import time

import Quartz

# Defaults (overridable per ProwlEngine instance)
INTERVAL = 60.0    # seconds between wander cycles
DURATION = 4.0     # approx seconds spent wandering each cycle


def screen_size():
    b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return int(b.size.width), int(b.size.height)


def cursor_position():
    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return float(loc.x), float(loc.y)


def post_move(x, y):
    evt = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)


def can_move():
    """True if cursor control actually works (Accessibility granted).

    Posting CGEvents never raises even when permission is missing — the move is
    just silently ignored. So we detect for real: nudge the cursor 1px, read it
    back, then restore. A no-op visually, but it proves we can move the pointer.
    """
    try:
        x, y = cursor_position()
        post_move(x + 1, y + 1)
        time.sleep(0.05)
        nx, ny = cursor_position()
        post_move(x, y)                       # restore
        return (round(nx), round(ny)) == (round(x + 1), round(y + 1))
    except Exception:
        return False


def glide_to(tx, ty, duration, stop_event=None, steps=30):
    sx, sy = cursor_position()
    for i in range(1, steps + 1):
        if stop_event is not None and stop_event.is_set():
            return
        t = i / steps
        ease = t * t * (3 - 2 * t)            # smoothstep easing
        post_move(sx + (tx - sx) * ease, sy + (ty - sy) * ease)
        time.sleep(duration / steps)


def waypoints(w, h):
    m = 60
    pts = [
        (m, m), (w - m, m), (w // 2, h - m), (m, h // 2), (w - m, h // 2),
        (random.randint(m, w - m), random.randint(m, h - m)),
        (random.randint(m, w - m), random.randint(m, h - m)),
    ]
    random.shuffle(pts)
    return pts


class ProwlEngine:
    """Runs the keep-alive loop on a background thread.

    on_status(text): optional callback invoked with human-readable status.
    """

    def __init__(self, interval=INTERVAL, duration=DURATION, on_status=None):
        self.interval = interval
        self.duration = duration
        self.on_status = on_status or (lambda *_: None)
        self._stop = None
        self._thread = None
        self.started_at = None
        self.cycles = 0

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop = threading.Event()
        self.cycles = 0
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._stop:
            self._stop.set()

    def _status(self, text):
        try:
            self.on_status(text)
        except Exception:
            pass

    def _run(self):
        w, h = screen_size()
        while not self._stop.is_set():
            self.cycles += 1
            self._status(f"Prowling… (cycle {self.cycles})")
            home_x, home_y = cursor_position()
            pts = waypoints(w, h)
            per_leg = max(0.3, self.duration / (len(pts) + 1))
            for (x, y) in pts:
                if self._stop.is_set():
                    break
                glide_to(x, y, per_leg, self._stop)
                time.sleep(0.15)
            glide_to(home_x, home_y, per_leg, self._stop)
            if self._stop.is_set():
                break
            self._status(f"Resting — next prowl in {self.interval:.0f}s")
            slept = 0.0
            while slept < self.interval and not self._stop.is_set():
                time.sleep(0.2)
                slept += 0.2
        self._status("Stopped")
