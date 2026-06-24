# CLAUDE.md — Prowl project guide

Context for working on **Prowl**, a cross-platform "keep-awake" tool that gently
moves the cursor every minute so a machine stays active (SSH/RDP sessions and
long-running tasks survive idle). **It only moves the cursor — never clicks.**

- Repo: https://github.com/alvi75/Prowl  (**PUBLIC**)
- Local: `~/Prowl`
- License: MIT (author Zahidul Alvi)

---

## Repository layout

```
prowl_core.py        macOS engine: Quartz cursor backend + ProwlEngine (the loop)
prowl_menubar.py     macOS menu-bar widget (rumps) — the primary daily app
prowl_window.py      macOS Tkinter Start/Stop window
make_icon.py         generates icon.icns (+ windows ico is made from icon_1024.png)
setup.py             py2app config for building Prowl.app
build_app.sh         one-command macOS build -> dist/Prowl.app
Launch Prowl.command double-click launcher (runs menubar via Terminal; see gotchas)
icon.icns            macOS app icon

make_video.py        renders prowl_launch.mp4 (PIL frames -> ffmpeg) + voiceover
prowl_launch.mp4     1080p launch/promo video (kinetic, music + Samantha VO)

windows/             SELF-CONTAINED Windows version (does NOT import the mac code)
  prowl_core.py        ctypes SendInput backend + ProwlEngine (copy of the loop)
  prowl_window.py      Tkinter Start/Stop window (Windows)
  build_exe.bat        local PyInstaller build -> windows/dist/Prowl.exe
  installer.iss        Inno Setup script -> Prowl-Setup.exe
  Run Prowl.bat        run from source if Python is present
  Prowl.ico            Windows icon

.github/workflows/
  build-macos.yml      builds + zips Prowl.app -> artifact "Prowl-macOS"
  build-windows.yml    builds Prowl.exe (portable) + Prowl-Setup.exe (installer)
```

Build outputs (`build/`, `dist/`, `*.spec`, `installer_out/`, icon intermediates)
are gitignored.

---

## Architecture

- **`ProwlEngine`** (in each `prowl_core.py`) runs the keep-alive loop on a daemon
  thread. Each cycle: record cursor pos → glide to ~7 spread-out waypoints
  (pausing briefly) → glide home → sleep `interval` (default 60s). `cycles` counts
  spins and resets to 1 on each `start()`. `last_status` holds a human string.
- **Cursor backend is per-OS and intentionally separated:**
  - macOS: Quartz `CGEventCreateMouseEvent` / `CGEventPost` (posting a real move
    event resets the idle timer). **Requires Accessibility permission.**
  - Windows: Win32 `SendInput` absolute move via `ctypes` (counts as real input;
    resets idle). **No permission needed.** Also calls `SetThreadExecutionState`
    to keep display/system awake while running.
- **Front-ends are thin** over the engine: macOS menu-bar (rumps), macOS window
  (Tk), Windows window (Tk). The mac and Windows trees are deliberately
  independent so the working mac app is never at risk from Windows changes.

---

## Run / build / release

### Run from source
- macOS menu-bar: `pip3 install rumps pyobjc-framework-Quartz && python3 prowl_menubar.py`
- macOS window: `python3 prowl_window.py`
- Windows window: `cd windows && python prowl_window.py` (only stdlib needed)

### Build locally
- macOS app: `./build_app.sh` → `dist/Prowl.app`
- Windows exe: `cd windows && build_exe.bat` → `windows/dist/Prowl.exe`

### CI + releases (the easy distribution path)
- Pushing to `main` triggers the matching workflow (path-filtered). Both build
  green. Download artifacts from the Actions run, or — for **no-login** download —
  from a **Release**.
- Release process (what was done for v1.0.0):
  `gh run download <id> -n <artifact> -D /tmp/dl/...` for each, then
  `gh release create vX.Y.Z --title ... --notes ... <files>`.
- v1.0.0 assets: `Prowl-Setup.exe`, `Prowl.exe`, `Prowl-macOS.zip`.

---

## Gotchas & hard-won lessons (READ before debugging)

**macOS**
- The **ad-hoc-signed `Prowl.app` CANNOT control the cursor** even with
  Accessibility granted — un-notarized apps are blocked from input synthesis.
  Reliable route is **`Launch Prowl.command`** (runs the menubar via Terminal,
  borrowing Terminal's permission). A **Developer ID signed + notarized** build
  would fix the `.app` (needs a paid Apple Developer account) — top roadmap item.
- Ad-hoc signing gives a new cdhash each build, so macOS **drops the Accessibility
  grant on every rebuild** — must re-add. `tccutil reset Accessibility com.zahidul.prowl`
  clears stale state.
- rumps/AppKit is **not thread-safe**: the menu-bar app must update title/menu
  ONLY on the main thread (via `rumps.Timer` polling the engine). Updating from
  the worker thread froze the menu (Start/Stop/Quit unresponsive). Don't regress.
- `ProwlEngine.start()` joins a winding-down thread and `running` reports False
  once `stop()` is set — this fixes "Start does nothing right after Stop."
- py2app on conda Python misses `libffi.8.dylib`; `build_app.sh` copies it into
  `Contents/Frameworks/` and ad-hoc-signs. Other conda `@rpath` dylibs are latent
  landmines if new imports (ssl, sqlite3, tkinter in the bundle…) get added.

**Windows**
- "**The process has no package identity**" from `python.exe` = Python NOT
  installed (you're hitting the Microsoft Store alias stub). Don't build — use the
  prebuilt exe from Releases.
- Same error when running an `.exe` = **Windows S Mode** (Store apps only) →
  Settings → System → Activation → Switch out of S mode (free, one-way).
- "**pyinstaller is not recognized**" → call `python -m PyInstaller` (Scripts dir
  not on PATH). Fixed in `build_exe.bat`.
- Unsigned exe → SmartScreen "unknown publisher" → More info → Run anyway. A
  code-signing cert would remove this (roadmap).
- "**Prowls one cycle then freezes (counter keeps climbing, cursor stops)**":
  the loop is fine (identical to mac); `SendInput` was silently no-op'ing after
  the first burst. `windows/prowl_core.py` was hardened: process is made
  DPI-aware (un-virtualized coords), moves use the *virtual* desktop with
  `MOUSEEVENTF_VIRTUALDESK | MOVE_NOCOALESCE`, every `SendInput` return +
  `GetLastError` is checked and counted, a relative-move fallback runs if an
  absolute move is rejected, and keep-awake is asserted from the worker thread
  (per-thread state) each cycle. On rejection the UI now shows
  `⚠ Cursor move blocked (err N)` — if that appears, the OS is dropping
  synthetic input (UIPI: foreground window is elevated → run Prowl as admin; or
  full-screen-exclusive/secure-desktop has focus). Verify on a real Windows box.

**Corporate machines**
- A mouse jiggler on a managed PC (e.g. user's Halliburton laptop) may violate IT
  policy and be flagged by EDR (synthetic input is a watched behavior). Advise
  personal machines / IT-sanctioned alternatives. (Real risk is policy/EDR, not
  malware — the app is harmless and offline.)

**Privacy**
- Repo is public. Real email `alvi7075@gmail.com` is in the FIRST TWO commits'
  history; newer commits use `alvi75@users.noreply.github.com`. User declined a
  history-scrub force-push. No secrets/API keys anywhere (scanned).

---

## Roadmap / nice next steps

- **Sign + notarize** the macOS `.app` (fixes cursor control without Terminal) and
  **code-sign** the Windows exe (removes SmartScreen). Biggest UX wins.
- Windows **system-tray** app (pystray) to mirror the macOS menu-bar widget.
- Auto-stop after N minutes; pause when the user is actually active; multi-monitor.
- Tag-driven CI that auto-publishes a Release with all three binaries.
- The video: tweakable in `make_video.py` (Apple Loops music in
  `/Library/Audio/Apple Loops/Apple/02 Electro House`, `say -v Samantha` VO).
