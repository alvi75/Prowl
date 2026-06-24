#!/usr/bin/env python3
"""
prowl_core.py — Windows engine behind Prowl (self-contained; no macOS deps).

Keeps a Windows PC awake by gently moving the cursor in cycles: it remembers
where the pointer is, glides to a spread of points across the screen, pauses at
each, then glides home. It ONLY moves the cursor — it never clicks.

Cursor movement uses Win32 SendInput (absolute mouse move), which registers as
genuine user input and resets the system idle timer. No special permission is
required on Windows.

Hardening (see CLAUDE.md "Windows: prowls one cycle then freezes"):
  * Process is made DPI-aware so absolute coordinates aren't virtualized/clamped
    under display scaling.
  * Moves target the *virtual* desktop (all monitors) and set MOVE_NOCOALESCE so
    Windows can't merge/drop our synthetic moves.
  * Every SendInput return value + GetLastError is checked; failures are counted
    and surfaced in the engine status so a frozen run is diagnosable.
  * If an absolute move doesn't register, a relative-move fallback is tried.
  * Keep-awake (SetThreadExecutionState) is asserted from the worker thread and
    re-asserted every cycle, because that state is per-thread.
"""

import ctypes
import random
import threading
import time
from ctypes import wintypes

INTERVAL = 60.0    # seconds between wander cycles
DURATION = 4.0     # approx seconds spent wandering each cycle

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_ULONG_PTR = wintypes.WPARAM            # pointer-sized on both 32- and 64-bit

_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_ABSOLUTE = 0x8000
_MOUSEEVENTF_VIRTUALDESK = 0x4000       # map ABSOLUTE coords across all monitors
_MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000   # don't let Windows merge/drop our moves
_INPUT_MOUSE = 0

# GetSystemMetrics indices
_SM_CXSCREEN = 0
_SM_CYSCREEN = 1
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

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


# Declare signatures so 64-bit pointer args aren't truncated.
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT
_user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
_user32.GetCursorPos.restype = wintypes.BOOL
_user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
_user32.GetSystemMetrics.restype = ctypes.c_int
_kernel32.SetThreadExecutionState.argtypes = (wintypes.DWORD,)
_kernel32.SetThreadExecutionState.restype = wintypes.DWORD


def _set_dpi_aware():
    """Opt into real pixel coordinates so scaled displays don't clamp moves."""
    # Per-Monitor-v2 (Win10 1703+); -4 == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    try:
        if _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:                                  # Win8.1+: 2 == PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:                                  # Vista+ system-DPI-aware
        _user32.SetProcessDPIAware()
    except Exception:
        pass


_set_dpi_aware()

# Live diagnostics — surfaced by the engine so a frozen run is explainable.
_STATS = {"ok": 0, "fail": 0, "last_err": 0}


def screen_size():
    return (_user32.GetSystemMetrics(_SM_CXSCREEN),
            _user32.GetSystemMetrics(_SM_CYSCREEN))


def _virtual_rect():
    return (_user32.GetSystemMetrics(_SM_XVIRTUALSCREEN),
            _user32.GetSystemMetrics(_SM_YVIRTUALSCREEN),
            _user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN),
            _user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))


def cursor_position():
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return float(pt.x), float(pt.y)


def _send(mi):
    inp = _INPUT(type=_INPUT_MOUSE, mi=mi)
    ctypes.set_last_error(0)
    n = _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if n == 1:
        _STATS["ok"] += 1
        return True
    _STATS["fail"] += 1
    _STATS["last_err"] = ctypes.get_last_error()
    return False


def post_move(x, y):
    """Move the cursor to absolute screen point (x, y) across the virtual desktop.

    Returns True if Windows accepted the synthetic input. Falls back to a
    relative move if the absolute move is rejected.
    """
    vx, vy, vw, vh = _virtual_rect()
    vw = max(1, vw)
    vh = max(1, vh)
    cx = max(vx, min(x, vx + vw - 1))
    cy = max(vy, min(y, vy + vh - 1))
    ax = int((cx - vx) * 65535 / max(1, vw - 1))
    ay = int((cy - vy) * 65535 / max(1, vh - 1))
    extra = ctypes.c_ulong(0)
    extra_ptr = ctypes.cast(ctypes.pointer(extra), ctypes.c_void_p).value or 0
    mi = _MOUSEINPUT(ax, ay, 0,
                     (_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE
                      | _MOUSEEVENTF_VIRTUALDESK | _MOUSEEVENTF_MOVE_NOCOALESCE),
                     0, extra_ptr)
    if _send(mi):
        return True
    # Fallback: relative nudge toward the target (not clamped, different path).
    sx, sy = cursor_position()
    rel = _MOUSEINPUT(int(cx - sx), int(cy - sy), 0,
                      _MOUSEEVENTF_MOVE | _MOUSEEVENTF_MOVE_NOCOALESCE, 0, 0)
    return _send(rel)


def can_move():
    """Best-effort proof we can actually move the pointer (nudge + read back)."""
    try:
        w, h = screen_size()
        x, y = cursor_position()
        dx = 1 if x < w - 2 else -1
        dy = 1 if y < h - 2 else -1
        post_move(x + dx, y + dy)
        time.sleep(0.05)
        nx, ny = cursor_position()
        post_move(x, y)                       # restore
        return (round(nx), round(ny)) != (round(x), round(y))
    except Exception:
        return True      # never block the app on a failed self-check


def _keep_awake(on):
    flags = _ES_CONTINUOUS
    if on:
        flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    try:
        _kernel32.SetThreadExecutionState(flags)
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
        # Assert keep-awake from THIS thread; the execution state is per-thread.
        _keep_awake(True)
        while not self._stop.is_set():
            self.cycles += 1
            _keep_awake(True)                 # re-assert each cycle
            self._status(f"Prowling… (cycle {self.cycles})")
            before = _STATS["fail"]
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
            if _STATS["fail"] > before:
                # Windows rejected our synthetic moves this cycle — say why.
                err = _STATS["last_err"]
                self._status(f"⚠ Cursor move blocked (err {err}) — "
                             f"try Run as administrator")
            else:
                self._status(f"Resting — next prowl in {self.interval:.0f}s")
            slept = 0.0
            while slept < self.interval and not self._stop.is_set():
                time.sleep(0.2)
                slept += 0.2
        _keep_awake(False)
        self._status("Stopped")
