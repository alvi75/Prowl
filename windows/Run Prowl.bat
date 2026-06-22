@echo off
REM Run Prowl directly from source (needs Python 3 installed).
REM For a no-Python option, build Prowl.exe with build_exe.bat instead.
cd /d "%~dp0"
python prowl_window.py
