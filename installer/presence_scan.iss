#define MyAppName "Presence Scan"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Presence Scan Team"
#define MyAppURL "https://example.com"
#define MyAppExeName "PresenceScan.exe"

[Setup]
AppId={{B8E7A1D5-6B6E-4A70-9E4D-5D9D9D6E4A01}
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
OutputBaseFilename=PresenceScanInstaller
SetupIconFile=..\qr_attendance_system\assets\icons\Presence_Scan.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\qr_attendance_system\dist\PresenceScan.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\qr_attendance_system\assets\icons\Presence_Scan.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\presence_scan.db"; DestDir: "{localappdata}\Presence Scan\data"; Flags: onlyifdoesntexist ignoreversion


[Icons]
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\Presence_Scan.ico"

Name: "{userdesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\Presence_Scan.ico"

[Code]
var
  HeadPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  HeadPage := CreateInputQueryPage(
    wpSelectDir,
    'University LAN setup',
    'Connect this desktop to the Head of University',
    'Enter the Head hub address shown by the Head of University application.'
  );
  HeadPage.Add('Head hub URL:', False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = HeadPage.ID then
  begin
    if Trim(HeadPage.Values[0]) = '' then
    begin
      MsgBox('Head hub URL is required.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'PRESENCE_HEAD_URL', HeadPage.Values[0]);
    RegDeleteValue(HKEY_CURRENT_USER, 'Environment', 'PRESENCE_SCAN_UNIVERSITY_CODE');
    RegDeleteValue(HKEY_CURRENT_USER, 'Environment', 'MAIN_PRESENCE_SCAN_UNIVERSITY_CODE');
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;