#!/usr/bin/env python3
"""
Prowl — menu-bar widget edition.

Lives quietly in the macOS menu bar. Click it for a menu: Start/Stop, a live
status line, interval choices, and Quit. While running it gently moves the
cursor every minute so your Mac stays awake. Never clicks anything.

Run:  python3 prowl_menubar.py

Threading note: ALL menu/title updates happen on the main thread via a
rumps.Timer that polls the engine. The engine's background worker never touches
AppKit — doing so would freeze the menu (Start/Stop/Quit stop responding).
"""

import rumps

import subprocess

from prowl_core import ProwlEngine, can_move, is_trusted, request_accessibility

IDLE_TITLE = "🐭"        # menu-bar glyph when idle
RUN_TITLE = "🐾"         # menu-bar glyph while prowling
# Deep-link straight to System Settings → Privacy & Security → Accessibility.
AX_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


class ProwlApp(rumps.App):
    def __init__(self):
        super().__init__("Prowl", title=IDLE_TITLE, quit_button=None)
        self.engine = ProwlEngine()          # NO cross-thread callback
        self.want_running = False            # user intent
        self._asked = False                  # fire the native AX prompt once/launch

        self.toggle_item = rumps.MenuItem("Start Prowling", callback=self.toggle)
        self.status_item = rumps.MenuItem("Status: stopped", callback=None)
        self.interval_menu = rumps.MenuItem("Interval")
        for secs in (30, 60, 120, 300):
            label = f"{secs}s" if secs < 60 else f"{secs // 60} min"
            self.interval_menu.add(
                rumps.MenuItem(label, callback=self._make_interval_setter(secs)))

        self.menu = [
            self.toggle_item,
            self.status_item,
            None,
            self.interval_menu,
            None,
            rumps.MenuItem("Quit", callback=self.quit),
        ]
        self._mark_interval()

        if not can_move():
            self.status_item.title = (
                "Status: Accessibility stale — re-grant Terminal →"
                if is_trusted() else "Status: grant Accessibility →")
            self._prompt_accessibility()

        # main-thread UI refresher (thread-safe). 0.5s cadence.
        self._timer = rumps.Timer(self._refresh, 0.5)
        self._timer.start()

    # ---- accessibility prompt (native one-click, at most once per launch) ----
    def _prompt_accessibility(self):
        if self._asked:
            return
        self._asked = True
        request_accessibility()                       # native one-click dialog
        subprocess.Popen(["open", AX_PANE])           # deep-link to the pane

    # ---- interval handling ----
    def _make_interval_setter(self, secs):
        def setter(_):
            self.engine.interval = float(secs)
            self._mark_interval()
        return setter

    def _mark_interval(self):
        for item in self.interval_menu.values():
            base = item.title.lstrip("✓ ").strip()
            secs = int(base[:-1]) if base.endswith("s") else int(base.split()[0]) * 60
            item.title = ("✓ " if secs == int(self.engine.interval) else "") + base

    # ---- main-thread UI refresh (the ONLY place title/menu are updated) ----
    def _refresh(self, _):
        if self.engine.running:
            self.title = f"{RUN_TITLE} {self.engine.cycles}"
            self.toggle_item.title = "Stop Prowling"
            self.status_item.title = f"Status: {self.engine.last_status}"
        else:
            self.title = IDLE_TITLE
            self.toggle_item.title = "Start Prowling"
            self.status_item.title = "Status: stopped"

    # ---- toggle (main thread; only sets intent + drives engine) ----
    def toggle(self, _):
        if self.engine.running:
            self.want_running = False
            self.engine.stop()
        else:
            if not can_move():
                self._prompt_accessibility()
                rumps.alert(
                    "Accessibility needed",
                    "Turn ON Terminal in the pane that just opened (not 'Prowl'), "
                    "then click Start again. If Terminal is already ON but Prowl "
                    "still won't run, run fix_mac.command once.")
                return
            self.want_running = True
            self.engine.start()
        self._refresh(None)

    def quit(self, _):
        self.want_running = False
        self.engine.stop()
        rumps.quit_application()


if __name__ == "__main__":
    ProwlApp().run()
