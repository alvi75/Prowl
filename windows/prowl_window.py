#!/usr/bin/env python3
"""
Prowl for Windows — Start/Stop window.

Click START and walk away; the cursor prowls the screen every minute so your PC
stays awake (RDP/SSH sessions and long tasks don't drop). Click STOP or close
the window to end. It never clicks anything.

Run from source:   python prowl_window.py
Or just double-click the built Prowl.exe (no Python needed).
"""

import time
import tkinter as tk

from prowl_core import ProwlEngine, can_move

BG = "#15151f"
FG = "#e8e8f0"
SUB = "#8a8aa0"
GREEN = "#2ecc71"
RED = "#e74c3c"


class App:
    def __init__(self, root):
        self.root = root
        self.engine = ProwlEngine(on_status=self.on_status)

        root.title("Prowl")
        root.geometry("340x230")
        root.resizable(False, False)
        root.configure(bg=BG)

        tk.Label(root, text="Prowl", font=("Segoe UI", 22, "bold"),
                 bg=BG, fg=FG).pack(pady=(18, 0))
        tk.Label(root, text="keeps your PC awake", font=("Segoe UI", 11),
                 bg=BG, fg=SUB).pack(pady=(0, 4))

        self.status = tk.Label(root, text="Stopped", font=("Segoe UI", 12),
                               bg=BG, fg=SUB)
        self.status.pack(pady=(6, 2))
        self.timer = tk.Label(root, text="", font=("Segoe UI", 11), bg=BG, fg=SUB)
        self.timer.pack()

        btns = tk.Frame(root, bg=BG)
        btns.pack(pady=12)
        self.start_btn = tk.Button(btns, text="START", width=10, height=2,
                                   bg=GREEN, fg="black", relief="flat",
                                   font=("Segoe UI", 12, "bold"), command=self.start)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = tk.Button(btns, text="STOP", width=10, height=2,
                                  bg=RED, fg="black", relief="flat",
                                  font=("Segoe UI", 12, "bold"),
                                  state=tk.DISABLED, command=self.stop)
        self.stop_btn.grid(row=0, column=1, padx=6)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()

    def on_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text, fg=FG))

    def _tick(self):
        if self.engine.running and self.engine.started_at:
            secs = int(time.time() - self.engine.started_at)
            m, s = divmod(secs, 60)
            self.timer.config(
                text=f"running {m:02d}:{s:02d}  ·  {self.engine.cycles} cycles")
        else:
            self.timer.config(text="")
        self.root.after(500, self._tick)

    def start(self):
        self.engine.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

    def stop(self):
        self.engine.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status.config(text="Stopped", fg=SUB)

    def on_close(self):
        self.engine.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
