; ============================================================================
;  Inno Setup script — WhatsApp Bulk Messenger
;  Compile:    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;  Output:     Output\WhatsAppBulkMessenger_Setup.exe
; ============================================================================

#define MyAppName        "WhatsApp Bulk Messenger"
#define MyAppShortName   "WhatsAppBulkMessenger"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "MNB EC"
#define MyAppURL         "https://mnbec.com"
#define MyAppExeName     "WhatsAppBulkMessenger.exe"

[Setup]
; AppId uniquely identifies the app for upgrade/uninstall.
; DO NOT change it once you've shipped a release — Windows uses it to detect
; previous installs.
AppId={{B6E1B4F0-2C9A-4F0E-9D2A-7A8C9F2E1B4F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Install to "C:\Program Files\WhatsApp Bulk Messenger" on 64-bit Windows.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes

; License + wizard polish
LicenseFile=LICENSE.txt
WizardStyle=modern

; Output
OutputDir=Output
OutputBaseFilename=WhatsAppBulkMessenger_Setup
Compression=lzma2/ultra
SolidCompression=yes

; Architecture / privileges
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Add/Remove Programs entry — these show up in "Apps & features"
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
;SetupIconFile=icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; Flags: checkablealone

[Dirs]
; Pre-create the per-user data directory so it exists before first launch.
; The app would create these itself on first run, but doing it here means
; uploads/ is visible in the user's AppData immediately after install.
Name: "{userappdata}\WhatsAppBulkMessenger";         Permissions: users-modify
Name: "{userappdata}\WhatsAppBulkMessenger\uploads"; Permissions: users-modify

[Files]
; Ship the entire one-folder PyInstaller output (the .exe plus _internal\).
; recursesubdirs + createallsubdirs mirrors dist\WhatsAppBulkMessenger\ to {app}.
Source: "dist\WhatsAppBulkMessenger\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; --- Optional database seeding ----------------------------------------------
; Uncomment the next line if you want to ship a pre-populated whatsapp_tracker.db
; with the installer. The "onlyifdoesntexist" flag means we never overwrite the
; user's existing tracker history on reinstall/upgrade.
;
; Source: "whatsapp_tracker.db"; DestDir: "{userappdata}\WhatsAppBulkMessenger"; \
;     Flags: onlyifdoesntexist uninsneveruninstall
; ----------------------------------------------------------------------------

[Icons]
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up runtime artifacts from the install folder so uninstall leaves no
; residue. We deliberately do NOT delete %APPDATA%\WhatsAppBulkMessenger here
; — that's the user's data (sent-numbers history, uploads). Comment in the
; line below if you want a "scorched earth" uninstall.
Type: filesandordirs; Name: "{app}\__pycache__"
; Type: filesandordirs; Name: "{userappdata}\WhatsAppBulkMessenger"
