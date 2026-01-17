; Inno Setup script for DayzModManager
; Build input: dist\DayzModManager\ (PyInstaller --onedir output)
; Build output: installer_output\DayzModManager_Setup_<version>.exe

#define AppId "DayzModManager"
#define AppExeName "DayzModManager.exe"
#define AppPublisher "HoangLuu"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={#AppId}
AppName=DayZ Mod Manager
AppVersion={#AppVersion}
AppVerName=DayZ Mod Manager v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
DefaultDirName={autopf}\DayzModManager
DefaultGroupName=DayzModManager
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=installer_output
OutputBaseFilename=DayzModManager_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

; Also stamp Windows version info on the setup EXE
VersionInfoVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}

; Use the generated ICO if available (build scripts generate it before compiling installer).
SetupIconFile=assets\icons\app_icon.ico

LicenseFile=LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Package the entire onedir output
Source: "dist\DayzModManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Dayz Mod Manager"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\Dayz Mod Manager"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch DayZ Mod Manager"; Flags: nowait postinstall skipifsilent
