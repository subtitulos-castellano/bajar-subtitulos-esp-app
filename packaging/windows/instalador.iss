; Instalador de Bajar Subtítulos ESP (Inno Setup 6). Lo compila packaging/windows/compilar.py:
;   ISCC /DVersion=0.5.0 /DOrigen=dist\BajarSubtitulosESP /DSalida=dist packaging\windows\instalador.iss
; Instalación por usuario: no pide permisos de administrador.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Origen
  #define Origen "..\..\dist\BajarSubtitulosESP"
#endif
#ifndef Salida
  #define Salida "..\..\dist"
#endif
#define Nombre "Bajar Subtítulos ESP"
#define Exe "BajarSubtitulosESP.exe"
; Los crea la app al arrancar (app/actualizar.py): el primero indica que está abierta y el segundo dura
; hasta que su proceso termina.
#define MutexApp "BajarSubtitulosESP"
#define MutexProceso "BajarSubtitulosESP-proceso"
; Donde Windows apunta la versión instalada (DisplayVersion). Sale de AppId: cambiarlos a la vez.
#define ClaveDesinstalar "Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F0C2D8E-3B7A-4E51-9C2F-8A1D5E7B4C93}_is1"

[Setup]
; No cambiar nunca AppId: identifica la app para actualizar y desinstalar.
AppId={{6F0C2D8E-3B7A-4E51-9C2F-8A1D5E7B4C93}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=subtitulos-castellano
VersionInfoVersion={#Version}
VersionInfoProductName={#Nombre}
DefaultDirName={autopf}\{#Nombre}
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Salida}
OutputBaseFilename=BajarSubtitulosESP-{#Version}-windows-instalador
SetupIconFile=..\build\icono.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Si la app está abierta, el instalador pide cerrarla (la app crea este mutex al arrancar).
AppMutex={#MutexApp}
CloseApplications=yes
LicenseFile=..\..\LICENSE
; Idioma: se pregunta en la primera instalación (propone el de Windows) y vale también para la app. Al
; actualizar o reinstalar se usa el de la vez anterior sin preguntar; en la app se cambia en Configuración.
ShowLanguageDialog=yes
UsePreviousLanguage=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
es.SelectLanguageLabel=Elige el idioma de la instalación y del programa:
en.SelectLanguageLabel=Select the language for the installation and for the app:

[CustomMessages]
es.VersionMasNueva=Ya tienes instalada la versión %1, más nueva que esta (%2).%n%n¿Quieres sustituirla por esta versión anterior? Tus preferencias se conservan.
en.VersionMasNueva=You already have version %1 installed, which is newer than this one (%2).%n%nDo you want to replace it with this older version? Your settings are kept.

[Tasks]
Name: "escritorio"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Al actualizar, quitar las librerías de la versión anterior (pueden haber cambiado de nombre).
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
; Menú contextual del Explorador («Bajar subtítulos»): lo añade la propia app (app/menu_contextual.py) en
; el registro del usuario, salvo que se haya quitado en Configuración. Al actualizar, lo deja apuntando aquí.
; Con --idioma-inicial, la app apunta el idioma de la instalación si aún no tenía ninguno (ver app/main.py).
Filename: "{app}\{#Exe}"; Parameters: "--menu-contextual-instalar --idioma-inicial {language}"; Flags: runasoriginaluser waituntilterminated
Filename: "{app}\{#Exe}"; Description: "{cm:LaunchProgram,{#Nombre}}"; Flags: nowait postinstall skipifsilent
; Actualización desde la propia app (/REABRIR=1): se vuelve a abrir sola al terminar.
Filename: "{app}\{#Exe}"; Flags: nowait runasoriginaluser; Check: Reabrir

[UninstallRun]
; Quita el menú contextual (solo si apunta a este programa: puede apuntar a la versión portable).
Filename: "{app}\{#Exe}"; Parameters: "--menu-contextual-quitar"; Flags: waituntilterminated; RunOnceId: "QuitarMenuContextual"

; La configuración (%APPDATA%\BajarSubtitulosEsp), la contraseña guardada en el Administrador de
; credenciales y las copias de seguridad (%USERPROFILE%\.subtitulos-esp) se conservan al
; desinstalar: son del usuario y las comparte con la skill.

[Code]
// La app lanza el instalador con /VERYSILENT /REABRIR=1 y se cierra al momento.
function Reabrir(): Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

var
  VersionAnterior: String;   // la que ya está instalada ('' si no hay ninguna)

function LeerVersionAnterior(): String;
begin
  if not RegQueryStringValue(HKA, '{#ClaveDesinstalar}', 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKCU, '{#ClaveDesinstalar}', 'DisplayVersion', Result) then
      if not RegQueryStringValue(HKLM, '{#ClaveDesinstalar}', 'DisplayVersion', Result) then
        Result := '';
end;

// Quita y devuelve el primer número de una versión «X.Y.Z».
function PrimerNumero(var Version: String): Integer;
var
  P: Integer;
begin
  P := Pos('.', Version);
  if P = 0 then
  begin
    Result := StrToIntDef(Version, 0);
    Version := '';
  end
  else
  begin
    Result := StrToIntDef(Copy(Version, 1, P - 1), 0);
    Version := Copy(Version, P + 1, Length(Version));
  end;
end;

// 1 si A es más nueva que B, -1 si es más antigua y 0 si son la misma.
function CompararVersiones(A, B: String): Integer;
var
  I, X, Y: Integer;
begin
  Result := 0;
  for I := 1 to 3 do
  begin
    X := PrimerNumero(A);
    Y := PrimerNumero(B);
    if X <> Y then
    begin
      if X > Y then Result := 1 else Result := -1;
      Exit;
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  Espera: Integer;
begin
  Result := True;
  VersionAnterior := LeerVersionAnterior();
  // Al actualizar desde la app, esperar (como mucho 30 s) a que termine de cerrarse antes de tocar
  // sus archivos.
  if Reabrir() then
  begin
    Espera := 0;
    while CheckForMutexes('{#MutexProceso}') and (Espera < 300) do
    begin
      Sleep(100);
      Espera := Espera + 1;
    end;
  end
  // Instalar una versión más antigua encima de una más nueva: solo si se confirma (en silencio con
  // /SUPPRESSMSGBOXES, no).
  else if (VersionAnterior <> '') and (CompararVersiones(VersionAnterior, '{#Version}') > 0) then
    Result := SuppressibleMsgBox(FmtMessage(CustomMessage('VersionMasNueva'), [VersionAnterior, '{#Version}']),
                                 mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
end;

// Al actualizar (ya hay una versión instalada), la licencia ya se aceptó: no se vuelve a enseñar.
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpLicense) and (VersionAnterior <> '');
end;
