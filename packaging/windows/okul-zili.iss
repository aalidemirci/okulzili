#define MyAppName "Okul Zili"
#define MyAppVersion "0.8.0"
#define MyAppExeName "OkulZili.exe"

[Setup]
AppId={{B460F042-A7A9-4D52-8518-9F32A2257BAA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Okul Zili
DefaultGroupName=Okul Zili
OutputDir=..\..\dist\installer
OutputBaseFilename=OkulZili-Kurulum-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\..\assets\branding\okul-zili.ico
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductVersion={#MyAppVersion}.0
VersionInfoCompany=Okul Zili Projesi
VersionInfoDescription=Okul Zili kurulum programı

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "autostart"; Description: "Kullanıcı oturum açtığında Okul Zili'ni başlat"; Flags: checkedonce
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; Flags: unchecked

[Files]
Source: "..\..\dist\OkulZili-Windows-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install-task.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall-stop.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\KURULUM.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\DONANIM.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\KULLANIM.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\SORUN-GIDERME.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\MIMARI.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\SURUM-NOTLARI.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\BAGIMLILIKLAR.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\GEREKSINIM-IZLENEBILIRLIK.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\SAHA-KABUL.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\SES-KAYNAKLARI.md"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\NOTICE"; DestDir: "{app}\Belgeler"; Flags: ignoreversion
Source: "..\..\tools\verify-windows-install.ps1"; DestDir: "{app}\Araclar"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_LICENSES\*"; DestDir: "{app}\Belgeler\Lisanslar"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Okul Zili"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Okul Zili"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; runasoriginaluser: görev, UAC'ye kimlik giren yönetici hesabına değil
; kurulumu başlatan (günlük kullanılan) hesaba yazılır (D13).
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install-task.ps1"""; Flags: runhidden waituntilterminated runasoriginaluser; Tasks: autostart
Filename: "{app}\{#MyAppExeName}"; Description: "Okul Zili'ni çalıştır ve ses testini yap"; Flags: nowait postinstall skipifsilent

[Code]
{ Yükseltme: uygulama her oturumda otomatik açılır ve çarpı onu kapatmaz;
  önceki kurulumun durdurma betiği varsa dosyalar kopyalanmadan önce çalışan
  süreç kapatılır. Aksi hâlde dosyalar kilitli kalır (D13). }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  StopScript: String;
  ResultCode: Integer;
begin
  Result := '';
  StopScript := ExpandConstant('{app}\uninstall-stop.ps1');
  if FileExists(StopScript) then
    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -ExecutionPolicy Bypass -File "' + StopScript + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall-stop.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "StopOkulZili"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Okul Zili"" /F"; Flags: runhidden; RunOnceId: "RemoveOkulZiliTask"
