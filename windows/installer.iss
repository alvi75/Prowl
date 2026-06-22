; Inno Setup script — builds Prowl-Setup.exe, a normal Windows installer.
; Installs Prowl, adds Start Menu (and optional desktop) shortcuts, an optional
; "start with Windows" entry, and a proper uninstaller (Add/Remove Programs).
; Installs per-user (no admin needed). Built in CI; needs dist\Prowl.exe first.

[Setup]
AppName=Prowl
AppVersion=1.0.0
AppPublisher=Zahidul Alvi
AppPublisherURL=https://github.com/alvi75/Prowl
DefaultDirName={autopf}\Prowl
DefaultGroupName=Prowl
DisableProgramGroupPage=yes
OutputDir=installer_out
OutputBaseFilename=Prowl-Setup
SetupIconFile=Prowl.ico
UninstallDisplayIcon={app}\Prowl.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\Prowl.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Start Prowl automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Icons]
Name: "{group}\Prowl"; Filename: "{app}\Prowl.exe"
Name: "{group}\Uninstall Prowl"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Prowl"; Filename: "{app}\Prowl.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "Prowl"; ValueData: """{app}\Prowl.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Prowl.exe"; Description: "Launch Prowl now"; Flags: nowait postinstall skipifsilent
