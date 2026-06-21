#!/bin/bash
# Double-click this to start Prowl's menu-bar widget.
# It runs via Terminal, which has the Accessibility permission that actually
# lets the cursor move (the standalone Prowl.app can't, being un-notarized).
# A small Terminal window stays open while Prowl runs — closing it stops Prowl.
cd "$(dirname "$0")"
echo "Starting Prowl…  (close this window to stop)"
exec /Users/zahidul.alvi/miniconda3/bin/python3 prowl_menubar.py
