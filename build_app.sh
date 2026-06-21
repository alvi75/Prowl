#!/usr/bin/env bash
# Build a distributable Prowl.app (menu-bar widget) from source.
#
#   ./build_app.sh
#
# Produces dist/Prowl.app — a standalone bundle (no Python needed on the
# target Mac). Handles the conda libffi quirk and ad-hoc-signs the result.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> regenerating icon"
python3 make_icon.py

echo "==> cleaning previous build"
rm -rf build dist

echo "==> py2app (standalone)"
python3 setup.py py2app >/tmp/prowl_build.log 2>&1 || { tail -30 /tmp/prowl_build.log; exit 1; }

# conda's _ctypes.so links @rpath/libffi.8.dylib which py2app misses — bundle it
FFI="$(find "$(python3 -c 'import sys; print(sys.prefix)')" -name 'libffi.8.dylib' 2>/dev/null | head -1)"
if [ -n "${FFI:-}" ]; then
  echo "==> bundling $FFI"
  mkdir -p dist/Prowl.app/Contents/Frameworks
  cp "$FFI" dist/Prowl.app/Contents/Frameworks/
fi

echo "==> ad-hoc codesign"
codesign --force --deep --sign - dist/Prowl.app || echo "   (codesign skipped)"

echo "==> done: dist/Prowl.app"
du -sh dist/Prowl.app