#!/usr/bin/env bash
# Build a LIGHTWEIGHT, Spotlight-launchable Prowl.app for THIS Mac.
#
#   ./make_launcher_app.sh
#
# Unlike build_app.sh (which makes a heavy ~80MB standalone py2app bundle for
# distributing to colleagues without Python), this makes a tiny launcher app
# that just runs the menu-bar widget from ~/Prowl using your own Python. That
# keeps a single, clean TCC identity (the .app itself), so once you grant
# Accessibility it sticks — and you can launch it with Cmd-Space → "Prowl".
#
# It is NOT for distribution (depends on ~/Prowl source + your Python+deps).
set -euo pipefail
cd "$(dirname "$0")"
SRC="$PWD"
ID="com.zahidul.prowl"

# Install to /Applications if writable (so Spotlight indexes it), else ~/Applications.
if [ -w /Applications ]; then DEST="/Applications/Prowl.app"; else
  mkdir -p "$HOME/Applications"; DEST="$HOME/Applications/Prowl.app"
fi

TMP="$(mktemp -d)"; B="$TMP/Prowl.app"
mkdir -p "$B/Contents/MacOS" "$B/Contents/Resources"
cp "$SRC/icon.icns" "$B/Contents/Resources/Prowl.icns"

cat > "$B/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Prowl</string>
  <key>CFBundleDisplayName</key><string>Prowl</string>
  <key>CFBundleExecutable</key><string>Prowl</string>
  <key>CFBundleIdentifier</key><string>$ID</string>
  <key>CFBundleIconFile</key><string>Prowl</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST

# The bundle executable: find a Python WITH deps via ABSOLUTE paths (a GUI launch
# has no shell PATH/conda), cd into the repo, exec the menu-bar widget.
cat > "$B/Contents/MacOS/Prowl" <<LAUNCHER
#!/bin/bash
cd "$SRC" || exit 1
for PY in /opt/homebrew/bin/python3 /usr/local/bin/python3 \\
          "\$HOME/miniconda3/bin/python3" "\$HOME/anaconda3/bin/python3" \\
          /usr/bin/python3; do
  if [ -x "\$PY" ] && "\$PY" -c "import rumps, Quartz" >/dev/null 2>&1; then
    exec "\$PY" prowl_menubar.py
  fi
done
osascript -e 'display alert "Prowl" message "No Python 3 with rumps + Quartz found. In Terminal run: pip3 install rumps pyobjc-framework-Quartz"'
LAUNCHER
chmod +x "$B/Contents/MacOS/Prowl"

# Ad-hoc sign. Stable as long as this bundle is not rebuilt; rebuilding makes a
# new cdhash and you'd re-grant Accessibility once (rare). For grant-survives-
# rebuild, swap '--sign -' for a stable self-signed identity (see CLAUDE.md).
codesign --force --sign - "$B"

rm -rf "$DEST"
mv "$B" "$DEST"
# clear any quarantine flag so it opens without the Gatekeeper warning
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
echo "Installed: $DEST"
echo "Launch with Cmd-Space → \"Prowl\"  (or: open \"$DEST\")"
