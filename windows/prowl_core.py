#!/usr/bin/env python3
"""
prowl_core.py — Windows engine behind Prowl (self-contained; no macOS deps).

Keeps a Windows PC awake by gently moving the cursor in cycles: it remembers
where the pointer is, glides to a spread of points across the screen, pauses at
each, then glides home. It ONLY moves the cursor — it never clicks.

Cursor movement uses Win32 SendInput (absolute mouse move), which registers as
genuine user input and resets the system idle timer. No special permission is
required on Windows.
"""

import ctypes
import random
import threading
import time
from ctypes import wintypes

INTERVAL = 60.0    # seconds between wander cycles
DURATION = 4.0     # approx seconds spent wandering each cycle

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)
_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_ABSOLUTE = 0x8000
_INPUT_MOUSE = 0

# keep the display + system awake while running (belt-and-suspenders)
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


def screen_size():
    return (_user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1))


def cursor_position():
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return float(pt.x), float(pt.y)


def post_move(x, y):
    w, h = screen_size()
    ax = int(max(0, min(x, w - 1)) * 65535 / max(1, w - 1))
    ay = int(max(0, min(y, h - 1)) * 65535 / max(1, h - 1))
    extra = ctypes.c_ulong(0)
    mi = _MOUSEINPUT(ax, ay, 0, _MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE,
                     0, ctypes.cast(ctypes.pointer(extra), _ULONG_PTR))
    inp = _INPUT(type=_INPUT_MOUSE, mi=mi)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def can_move():
    return True      # Windows needs no special permission to move the cursor


def _keep_awake(on):
    flags = _ES_CONTINUOUS
    if on:
        flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    try:
        _user32_kernel = ctypes.windll.kernel32
        _user32_kernel.SetThreadExecutionState(flags)
    except Exception:
        pass


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
    """Runs the keep-alive loop on a background thread."""

    def __init__(self, interval=INTERVAL, duration=DURATION, on_status=None):
        self.interval = interval
        self.duration = duration
        self.on_status = on_status or (lambda *_: None)
        self._stop = None
        self._thread = None
        self.started_at = None
        self.cycles = 0
        self.last_status = "Stopped"

    @property
    def running(self):
        return (self._thread is not None and self._thread.is_alive()
                and self._stop is not None and not self._stop.is_set())

    def start(self):
        if self.running:
            return
        if self._thread is not None and self._thread.is_alive():
            if self._stop is not None:
                self._stop.set()
            self._thread.join(timeout=2.0)
        self._stop = threading.Event()
        self.cycles = 0
        self.started_at = time.time()
        self.last_status = "Starting…"
        _keep_awake(True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._stop:
            self._stop.set()
        self.last_status = "Stopped"
        _keep_awake(False)

    def _status(self, text):
        self.last_status = text
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
