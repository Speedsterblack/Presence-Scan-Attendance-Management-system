#define MyAppName "Presence Scan Developer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Presence Scan Team"
#define MyAppURL "https://example.com"
#define MyAppExeName "DeveloperPresenceScan.exe"

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
OutputBaseFilename=PresenceScanDeveloperInstaller
SetupIconFile=..\qr_attendance_system\assets\icons\Presence_Scan.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\qr_attendance_system\dist\DeveloperPresenceScan.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\qr_attendance_system\assets\icons\Presence_Scan.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\presence_scan.db"; DestDir: "{localappdata}\Presence Scan Developer\data"; Flags: onlyifdoesntexist ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\Presence_Scan.ico"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\Presence_Scan.ico"

[Code]
var
	DatabasePage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
	DatabasePage := CreateInputQueryPage(
		wpSelectDir,
		'Shared database setup',
		'Connect this desktop to the shared Presence Scan database',
		'Enter the PostgreSQL/Supabase connection details for institution management.'
	);
	DatabasePage.Add('Database host:', False);
	DatabasePage.Add('Database port:', False);
	DatabasePage.Add('Database name:', False);
	DatabasePage.Add('Database user:', False);
	DatabasePage.Add('Database password:', True);
	DatabasePage.Values[1] := '5432';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
	Result := True;
	if CurPageID = DatabasePage.ID then
	begin
		if (Trim(DatabasePage.Values[0]) = '') or
			 (Trim(DatabasePage.Values[2]) = '') or
			 (Trim(DatabasePage.Values[3]) = '') or
			(Trim(DatabasePage.Values[4]) = '') then
		begin
			MsgBox('Database host, name, user and password are required.', mbError, MB_OK);
			Result := False;
		end;
	end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
	if CurStep = ssPostInstall then
	begin
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_HOST', DatabasePage.Values[0]);
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_PORT', DatabasePage.Values[1]);
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_NAME', DatabasePage.Values[2]);
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_USER', DatabasePage.Values[3]);
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_PASSWORD', DatabasePage.Values[4]);
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'DB_SSLMODE', 'require');
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'LOCAL_PRIMARY', '1');
		RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'PRESENCE_SCAN_ALL_UNIVERSITIES', '1');
		RegDeleteValue(HKEY_CURRENT_USER, 'Environment', 'PRESENCE_SCAN_UNIVERSITY_CODE');
	end;
end;