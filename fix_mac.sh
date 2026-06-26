#!/bin/bash
# Prowl — one-shot macOS Accessibility fixer.
#
# RUN FROM TERMINAL: double-click `fix_mac.command`, or `bash fix_mac.sh` in
# Terminal. On the Terminal route the *responsible* TCC principal is Terminal
# itself (Apple-signed, stable Designated Requirement) — Terminal is the entity
# that actually needs the Accessibility grant, NOT the ad-hoc Prowl.app.
#
# Fixes the classic "Accessibility shows ON but Prowl still can't move the
# cursor / keeps asking" loop: that ON checkbox is usually the orphaned
# `com.zahidul.prowl` row (the ad-hoc .app, which never works), while the real
# grant lives on Terminal and may have gone stale after a macOS re-sign.
set -u
cd "$(dirname "$0")"

# 1) Clear the MISLEADING stale ad-hoc .app entry (the row the user kept
#    toggling). Harmless to Terminal — different client id.
tccutil reset Accessibility com.zahidul.prowl 2>/dev/null

# 2) Find a python3 with Prowl's deps (same search as the launcher).
PY=""
for c in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         "$HOME/miniconda3/bin/python3" "$HOME/anaconda3/bin/python3"; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import rumps, Quartz" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "No python3 with rumps+Quartz. Run: pip3 install rumps pyobjc-framework-Quartz"
  read -p "Press Enter to close…"; exit 1
fi

# 3) Classify the state: already working / trusted-but-stale / ungranted.
STATE=$("$PY" - <<'PY'
import ctypes, ctypes.util, time, Quartz
def loc():
    l = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None)); return l.x, l.y
def post(x, y):
    Quartz.CGEventPost(Quartz.kCGHIDEventTap,
        Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), 0))
b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
w, h = int(b.size.width), int(b.size.height)
x, y = loc(); dx = 1 if x < w-2 else -1; dy = 1 if y < h-2 else -1
post(x+dx, y+dy); time.sleep(0.05); nx, ny = loc(); post(x, y)
can = (round(nx), round(ny)) == (round(x+dx), round(y+dy))
AS = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
AS.AXIsProcessTrusted.restype = ctypes.c_bool
trusted = bool(AS.AXIsProcessTrusted())
print("OK" if can else ("STALE" if trusted else "UNGRANTED"))
PY
)
echo "State: $STATE"

if [ "$STATE" = "OK" ]; then
  echo "Accessibility already works. Launching Prowl…"
  exec "$PY" prowl_menubar.py
fi

if [ "$STATE" = "STALE" ]; then
  # Terminal shows ON but its grant is stale (e.g. macOS re-signed Terminal).
  # Reset it so the row can be re-granted cleanly. NOTE: this momentarily revokes
  # Terminal's Accessibility for ALL terminal tools, and the running Terminal
  # must be fully quit + relaunched to pick up the new grant.
  echo "Terminal's Accessibility grant is stale. Resetting it…"
  tccutil reset Accessibility com.apple.Terminal 2>/dev/null
fi

# 4) Fire the native one-click prompt (registers Terminal) + deep-link the pane.
"$PY" - <<'PY'
import ctypes, ctypes.util
AS = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
CF = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
CF.CFDictionaryCreate.restype = ctypes.c_void_p
kPrompt = ctypes.c_void_p.in_dll(AS, "kAXTrustedCheckOptionPrompt")
kTrue = ctypes.c_void_p.in_dll(CF, "kCFBooleanTrue")
opts = CF.CFDictionaryCreate(None, (ctypes.c_void_p*1)(kPrompt),
                             (ctypes.c_void_p*1)(kTrue), 1, None, None)
AS.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
AS.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
print("Trusted now:", AS.AXIsProcessTrustedWithOptions(opts))
PY
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

echo
echo "In the pane that opened: turn Terminal ON (you can DELETE any 'Prowl' row)."
if [ "$STATE" = "STALE" ]; then
  echo "Because Terminal's grant was reset, FULLY QUIT Terminal (Cmd-Q), then"
  echo "double-click 'Launch Prowl.command' again. (A running Terminal won't pick"
  echo "up the new grant until relaunched.)"
  read -p "Press Enter to close…"
else
  read -p "Press Enter AFTER Terminal is ON to start Prowl…"
  exec "$PY" prowl_menubar.py
fi
