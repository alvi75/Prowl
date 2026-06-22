#!/bin/bash
# Double-click to start Prowl's menu-bar widget (macOS).
# Runs via Terminal, which has the Accessibility permission that lets the cursor
# move (the un-notarized Prowl.app can't). A small Terminal window stays open
# while Prowl runs — close it to stop Prowl.
cd "$(dirname "$0")"
echo "Starting Prowl…  (close this window to stop)"

# Find a Python 3 that has Prowl's deps (rumps + Quartz), trying common spots.
for PY in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 \
          "$HOME/miniconda3/bin/python3" "$HOME/anaconda3/bin/python3"; do
  if command -v "$PY" >/dev/null 2>&1 && "$PY" -c "import rumps, Quartz" >/dev/null 2>&1; then
    exec "$PY" prowl_menubar.py
  fi
done

echo
echo "Couldn't find a Python 3 with Prowl's dependencies."
echo "Install them with:  pip3 install rumps pyobjc-framework-Quartz"
read -p "Press Enter to close…"
