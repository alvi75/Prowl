#!/usr/bin/env python3
"""
Prowl — menu-bar widget edition.

Lives quietly in the macOS menu bar as a small icon. Click it for a menu:
  ▶ Start Prowling / ■ Stop, a live status line, interval choices, and Quit.
While running it gently moves the cursor every minute so your Mac stays awake.
Never clicks anything.

Run:  python3 prowl_menubar.py
(For colleagues: use the bundled Prowl.app instead — no Python needed.)
"""

import rumps

from prowl_core import ProwlEngine, can_move

IDLE_TITLE = "🐭"        # menu-bar glyph when idle
RUN_TITLE = "🐾"         # menu-bar glyph while prowling


class ProwlApp(rumps.App):
    def __init__(self):
        super().__init__("Prowl", title=IDLE_TITLE, quit_button=None)
        self.engine = ProwlEngine(on_status=self._on_status)

        self.toggle_item = rumps.MenuItem("▶ Start Prowling", callback=self.toggle)
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
            self.status_item.title = "Status: grant Accessibility →"
            rumps.notification(
                "Prowl needs permission",
                "Enable Accessibility for this app",
                "System Settings → Privacy & Security → Accessibility, "
                "then reopen Prowl.")

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

    # ---- status / toggle ----
    def _on_status(self, text):
        self.status_item.title = f"Status: {text}"
        self.title = RUN_TITLE if self.engine.running else IDLE_TITLE

    def toggle(self, _):
        if self.engine.running:
            self.engine.stop()
            self.toggle_item.title = "▶ Start Prowling"
            self.title = IDLE_TITLE
            self.status_item.title = "Status: stopped"
        else:
            if not can_move():
                rumps.alert("Accessibility needed",
                            "Enable Prowl under System Settings → Privacy & "
                            "Security → Accessibility, then reopen Prowl.")
                return
            self.engine.start()
            self.toggle_item.title = "■ Stop Prowling"
            self.title = RUN_TITLE

    def quit(self, _):
        self.engine.stop()
        rumps.quit_application()


if __name__ == "__main__":
    ProwlApp().run()
