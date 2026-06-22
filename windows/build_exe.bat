@echo off
REM Build a standalone Prowl.exe (end users won't need Python).
REM Run this on a Windows machine that has Python 3 installed.
cd /d "%~dp0"
echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller
echo Building Prowl.exe...
REM call via "python -m PyInstaller" so it works even when the pyinstaller
REM script folder isn't on PATH (avoids "pyinstaller is not recognized").
python -m PyInstaller --onefile --windowed --name Prowl --icon Prowl.ico prowl_window.py
echo.
echo Done.  ->  %~dp0dist\Prowl.exe
pause
