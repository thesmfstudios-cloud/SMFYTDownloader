[Setup]
AppName=SMF YT Downloader
AppVersion=1.0.0
DefaultDirName={autopf}\SMF YT Downloader
DefaultGroupName=SMF YT Downloader
OutputDir=output
OutputBaseFilename=SMF_YT_Downloader_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\SMF_YT_Downloader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\SMF YT Downloader"; Filename: "{app}\SMF YT Downloader.exe"
Name: "{autodesktop}\SMF YT Downloader"; Filename: "{app}\SMF YT Downloader.exe"

[Run]
Filename: "{app}\SMF YT Downloader.exe"; Description: "Launch SMF YT Downloader"; Flags: nowait postinstall skipifsilent
