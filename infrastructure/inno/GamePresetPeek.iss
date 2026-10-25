; Installer of the Nuitka build folder: a normal per-user installation or a portable copy in any folder.

#define AppName "GamePreset Peek"
#define AppExeName "GamePresetPeek.exe"
#define DistDir "..\..\build\GamePresetPeek.dist"
; The version comes from the executable's properties; Windows pads it to four numbers, the app's has three.
#define VerMajor
#define VerMinor
#define VerPatch
#define VerBuild
#expr GetVersionComponents(DistDir + "\" + AppExeName, VerMajor, VerMinor, VerPatch, VerBuild)
#define AppVersion Str(VerMajor) + "." + Str(VerMinor) + "." + Str(VerPatch)

[Setup]
AppId={{6F0D3C52-8B1E-4E8B-9A43-2C5D7E1F9B60}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=iRingil
AppPublisherURL=https://github.com/iRingil/gamepreset-peek
AppSupportURL=https://github.com/iRingil/gamepreset-peek/issues
AppCopyright=Copyright (c) 2026 iRingil
VersionInfoVersion={#AppVersion}
; Per-user: the program updates its database in its own folder, which Program Files would not allow.
PrivilegesRequired=lowest
DefaultDirName={autopf}\GamePresetPeek
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; A portable copy leaves nothing in the registry: no uninstaller entry.
Uninstallable=not IsPortable
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
SetupIconFile=..\..\src\app\data\app.ico
OutputDir=..\..\build
OutputBaseFilename=GamePresetPeek-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
; Light or dark as Windows is set, like the program itself.
WizardStyle=modern dynamic
; The logo is shown on the Welcome and Finished pages only, so the Welcome page stays on.
DisableWelcomePage=no
; One file per display scale (100, 125, 150, 200 %); Setup picks the one closest to the image area.
WizardImageFile=wizard-image-100.png,wizard-image-125.png,wizard-image-150.png,wizard-image-200.png
WizardImageFileDynamicDark=wizard-image-100.png,wizard-image-125.png,wizard-image-150.png,wizard-image-200.png
WizardSmallImageFile=wizard-small-100.png,wizard-small-125.png,wizard-small-150.png,wizard-small-200.png,wizard-small-250.png
WizardSmallImageFileDynamicDark=wizard-small-100.png,wizard-small-125.png,wizard-small-150.png,wizard-small-200.png,wizard-small-250.png
ShowLanguageDialog=auto

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
en.ModeCaption=Installation type
en.ModeDescription=How should {#AppName} be installed?
en.ModeNormal=Normal: for this Windows user, with a Start menu shortcut and an uninstaller
en.ModePortable=Portable: into any folder (a USB stick, for example); settings, log and cache stay in that folder
en.DeleteUserData=Delete the settings and the log of {#AppName} as well?
ru.ModeCaption=Тип установки
ru.ModeDescription=Как установить {#AppName}?
ru.ModeNormal=Обычная: для этого пользователя Windows, с ярлыком в меню «Пуск» и деинсталлятором
ru.ModePortable=Портативная: в любую папку (например, на флешку); настройки, лог и кэш остаются в этой папке
ru.DeleteUserData=Удалить также настройки и лог {#AppName}?
de.ModeCaption=Installationsart
de.ModeDescription=Wie soll {#AppName} installiert werden?
de.ModeNormal=Normal: für diesen Windows-Benutzer, mit Startmenü-Verknüpfung und Deinstallationsprogramm
de.ModePortable=Portabel: in einen beliebigen Ordner (z. B. einen USB-Stick); Einstellungen, Protokoll und Cache bleiben dort
de.DeleteUserData=Auch die Einstellungen und das Protokoll von {#AppName} löschen?
fr.ModeCaption=Type d'installation
fr.ModeDescription=Comment installer {#AppName} ?
fr.ModeNormal=Normale : pour cet utilisateur Windows, avec un raccourci dans le menu Démarrer et un programme de désinstallation
fr.ModePortable=Portable : dans n'importe quel dossier (une clé USB, par exemple) ; réglages, journal et cache restent dans ce dossier
fr.DeleteUserData=Supprimer aussi les réglages et le journal de {#AppName} ?
es.ModeCaption=Tipo de instalación
es.ModeDescription=¿Cómo instalar {#AppName}?
es.ModeNormal=Normal: para este usuario de Windows, con acceso directo en el menú Inicio y desinstalador
es.ModePortable=Portátil: en cualquier carpeta (una memoria USB, por ejemplo); la configuración, el registro y la caché se quedan en ella
es.DeleteUserData=¿Eliminar también la configuración y el registro de {#AppName}?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; Check: not IsPortable

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "portable.txt"; DestDir: "{app}"; Flags: ignoreversion; Check: IsPortable

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Check: not IsPortable
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Pictures the program downloaded or extracted: a cache, deleted without asking.
Type: filesandordirs; Name: "{%TEMP}\GamePresetPeek"

[Code]
var
  ModePage: TInputOptionWizardPage;

function IsPortable: Boolean;
begin
  Result := (ModePage <> nil) and ModePage.Values[1];
end;

procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpWelcome, CustomMessage('ModeCaption'), CustomMessage('ModeDescription'), '', True, False);
  ModePage.Add(CustomMessage('ModeNormal'));
  ModePage.Add(CustomMessage('ModePortable'));
  // /PORTABLE=1 on the command line chooses the portable type, also for a silent installation.
  ModePage.Values[1] := ExpandConstant('{param:portable|0}') = '1';
  ModePage.Values[0] := not ModePage.Values[1];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  NormalDir, PortableDir: String;
begin
  Result := True;
  if CurPageID = ModePage.ID then
  begin
    NormalDir := ExpandConstant('{autopf}\GamePresetPeek');
    PortableDir := ExpandConstant('{userdesktop}\GamePresetPeek');
    // Only the other type's suggestion is swapped: a folder from /DIR, a previous installation or the user stays.
    if IsPortable and SameText(WizardForm.DirEdit.Text, NormalDir) then
      WizardForm.DirEdit.Text := PortableDir
    else if not IsPortable and SameText(WizardForm.DirEdit.Text, PortableDir) then
      WizardForm.DirEdit.Text := NormalDir;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserData: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserData := ExpandConstant('{localappdata}\GamePresetPeek');
    if DirExists(UserData) and
       (SuppressibleMsgBox(CustomMessage('DeleteUserData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES) then
      DelTree(UserData, True, True, True);
  end;
end;
