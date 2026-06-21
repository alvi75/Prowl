<div align="center">

# 🐭 Prowl

**Keeps your Mac awake.**

A tiny tool that gently moves your cursor every minute so your machine stays
active — SSH sessions, VS Code Remote, and long-running background tasks don't
die when you step away. It **only moves the cursor; it never clicks**, so it
can't disturb whatever you're running.

</div>

---

## Why

If your Mac sleeps or goes idle, SSH connections drop and background jobs can be
interrupted. Prowl simulates a little activity — the cursor "prowls" across the
screen (visiting the menu bar, Dock, and app areas) and returns home — just
often enough to keep things alive. Take a shower, grab coffee, leave it running.

## Three ways to run it

| Form | File | Best for |
|---|---|---|
| 🖥️ **Window** | `prowl_window.py` | A clear Start/Stop window with a live timer |
| 📌 **Menu-bar widget** | `prowl_menubar.py` | Quiet "set & forget" — lives in the menu bar |
| 📦 **Prowl.app** | `dist/Prowl.app` | Sharing with colleagues — no Python needed |

The packaged **Prowl.app** is the menu-bar widget — double-clickable, with an
icon, ready to hand to teammates.

---

## Quick start (from source)

Requires Python 3 with these packages:

```bash
pip install pyobjc-framework-Quartz rumps
```

Then:

```bash
python3 prowl_window.py      # window with Start/Stop
# or
python3 prowl_menubar.py     # menu-bar 🐭 icon
```

## ⚠️ One-time permission (required)

macOS silently ignores programmatic cursor movement until you grant
**Accessibility** access:

> **System Settings → Privacy & Security → Accessibility** → enable the app that
> runs Prowl (your Terminal when running from source, or **Prowl** itself when
> using Prowl.app). If it's already listed, toggle it off→on.

Symptom if not granted: Prowl runs with no error but the cursor never moves.
The apps detect this and tell you.

> **Security note:** Accessibility is a *local* capability — it does **not** open
> a network port or let anyone in remotely. The only real risk is running
> untrusted code in a Terminal that has it; Prowl's source is short and readable.

---

## For colleagues — installing Prowl.app

1. Copy **`Prowl.app`** to `/Applications` (or anywhere).
2. First launch: because the app isn't notarized by Apple, right-click it →
   **Open** → **Open** (only needed once). If macOS says it's "damaged", run:
   ```bash
   xattr -dr com.apple.quarantine /Applications/Prowl.app
   ```
3. Grant **Accessibility** (see above) — the app will appear as **Prowl** in the
   list. Reopen it.
4. A 🐭 appears in the menu bar. Click it → **Start Prowling**. It turns into 🐾
   while active. Pick an interval, or **Quit** from the same menu.

---

## Building Prowl.app yourself

```bash
./build_app.sh          # -> dist/Prowl.app
```

This regenerates the icon, runs py2app, bundles the conda `libffi` dylib (a
known quirk), and ad-hoc-signs the result. See `build_app.sh` for details.

To tweak the icon, edit `make_icon.py` and re-run the build.

---

## Bulletproof companion: never sleep

Cursor movement keeps the Mac *active*, but to **guarantee** it never sleeps,
pair Prowl with Apple's built-in `caffeinate` in a spare terminal:

```bash
caffeinate -dimsu
```

---

## How it works

Each cycle (default every 60s): remember the cursor's spot → glide to ~7 points
spread across the screen, pausing briefly at each → glide home → wait → repeat.
Motion uses real `CGEventMouseMoved` events posted via Quartz, which is what
resets the system idle timer. All the logic lives in `prowl_core.py`
(`ProwlEngine`); the window and menu-bar apps are thin front-ends over it.

## Files

```
prowl_core.py      engine: cursor motion + the prowl loop (ProwlEngine)
prowl_window.py    tkinter Start/Stop window
prowl_menubar.py   rumps menu-bar widget
make_icon.py       generates icon.icns
setup.py           py2app config for building Prowl.app
build_app.sh       one-command reproducible build
icon.icns          app icon
```

## Tuning

- **Interval / duration**: `INTERVAL` / `DURATION` in `prowl_core.py`, or via the
  menu-bar "Interval" submenu at runtime.
- **Where it moves**: `waypoints()` in `prowl_core.py`.
- **Speed / smoothness**: `steps` and `duration` of `glide_to()`.

## Ideas / roadmap

- [ ] Auto-stop after N minutes / countdown
- [ ] Pause automatically when you're actually using the Mac
- [ ] Multi-monitor support (currently the main display)
- [ ] Real app-switching (cycle visible windows) instead of screen regions
- [ ] Notarized, signed release so colleagues skip the Gatekeeper step

## Troubleshooting

| Symptom | Fix |
|---|---|
| Cursor doesn't move, no error | Grant Accessibility (above) and reopen. |
| `ModuleNotFoundError: Quartz` / `rumps` | `pip install pyobjc-framework-Quartz rumps` |
| App "is damaged / can't be opened" | `xattr -dr com.apple.quarantine Prowl.app` |
| Window doesn't appear | Run on a logged-in GUI session, not pure SSH. |
| Mac still sleeps | Add `caffeinate -dimsu` in a separate terminal. |

---

<div align="center">
Made to survive dropped connections. 🐾
</div>
