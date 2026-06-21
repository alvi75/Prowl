"""
Build Prowl.app (the menu-bar widget) with py2app.

    python3 setup.py py2app          # full standalone bundle -> dist/Prowl.app
    python3 setup.py py2app -A       # fast "alias" build for local testing only
                                     # (references your local Python; NOT for
                                     #  sharing with colleagues)

The standalone bundle in dist/ is what you hand to colleagues. It needs no
Python install on their machine, but each user must grant it Accessibility
(System Settings → Privacy & Security → Accessibility) on first run.
"""
from setuptools import setup

APP = ["prowl_menubar.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "packages": ["rumps"],
    "includes": ["Quartz", "prowl_core"],
    "plist": {
        "CFBundleName": "Prowl",
        "CFBundleDisplayName": "Prowl",
        "CFBundleIdentifier": "com.zahidul.prowl",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSUIElement": True,   # menu-bar only, no Dock icon
        "NSHumanReadableCopyright": "Prowl — keeps your Mac awake.",
    },
}

setup(
    app=APP,
    name="Prowl",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
