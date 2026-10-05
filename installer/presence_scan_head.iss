#define MyAppName "Presence Scan Head of University"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Presence Scan Team"
#define MyAppURL "https://example.com"
#define MyAppExeName "HeadOfUniversity.exe"

[Setup]
AppId={{F3C4B8A2-1D9E-4E1D-8F6B-2B4B6D7C9A02}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
Compression=lzma
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=PresenceScanHeadInstaller
SetupIconFile=..\qr_attendance_system\assets\icons\Presence_Scan.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\qr_attendance_system\dist\HeadOfUniversity.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\qr_attendance_system\assets\icons\Presence_Scan.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\presence_scan.db"; DestDir: "{localappdata}\Presence Scan Head\data"; Flags: onlyifdoesntexist ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\Presence_Scan.ico"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\Presence_Scan.ico"

