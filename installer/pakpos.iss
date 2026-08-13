; Inno Setup Script for PakPOS Windows Installer
; Compiles dist/PakPOS directory into PakPOS-Setup.exe

#define MyAppName "PakPOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PakPOS Software"
#define MyAppExeName "PakPOS.exe"

[Setup]
AppId={{D1A3F7B2-08E4-4C7E-B9D1-3456789ABCDE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=PakPOS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Elevation is required to write to Program Files.
; Business data goes to %PROGRAMDATA%\PakPOS (writable by standard users).
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; Pre-create all mutable data directories under %PROGRAMDATA%\PakPOS.
; Permissions: users-modify  — standard (non-admin) users can write business data.
; Flags: uninsneveruninstall — Inno Setup will NEVER remove these directories on
;        uninstall, preserving the database, backups, logs, config, and exports.
Name: "{commonappdata}\PakPOS";         Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\PakPOS\data";    Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\PakPOS\backups"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\PakPOS\logs";    Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\PakPOS\config";  Permissions: users-modify; Flags: uninsneveruninstall
Name: "{commonappdata}\PakPOS\exports"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "..\dist\PakPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
