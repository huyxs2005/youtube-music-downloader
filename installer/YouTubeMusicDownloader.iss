#define MyAppName "YouTube Music Downloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "huyxs2005"
#define MyAppURL "https://github.com/huyxs2005/youtube-music-downloader"
#define MyAppExeName "YouTubeMusicDownloader.exe"

[Setup]
AppId={{6F370C9E-58D5-45DB-98B3-A31F620FF33A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\YouTube Music Downloader
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
OutputBaseFilename=YouTube-Music-Downloader-Setup-v1.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
SetupLogging=yes
InfoBeforeFile=..\installer\INSTALLER_NOTICE.txt
InfoAfterFile=..\installer\AFTER_INSTALL.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\YouTubeMusicDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "setup-prerequisites.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YouTube Music Downloader"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Finish Setup or Repair Prerequisites"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup-prerequisites.ps1"""; WorkingDir: "{app}"
Name: "{group}\Documentation"; Filename: "{app}\README.md"
Name: "{autodesktop}\YouTube Music Downloader"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup-prerequisites.ps1"""; Description: "Set up WSL, Docker, the PO-token provider, and optional cookies"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\tools"

[Code]
function InitializeSetup(): Boolean;
begin
  if not IsWin64 then
  begin
    MsgBox('YouTube Music Downloader v1.0 requires 64-bit Windows.', mbError, MB_OK);
    Result := False;
    exit;
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if FileExists(ExpandConstant('{app}\cookies.txt')) then
      if MsgBox('Remove cookies.txt from the application folder? Your downloaded music will never be removed.', mbConfirmation, MB_YESNO) = IDYES then
        DeleteFile(ExpandConstant('{app}\cookies.txt'));
  end;
end;
