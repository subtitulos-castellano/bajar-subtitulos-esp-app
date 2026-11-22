; Instalador de Bajar Subtítulos ESP (Inno Setup 6). Lo compila packaging/compilar.py:
;   ISCC /DVersion=0.5.0 /DOrigen=dist\BajarSubtitulosESP /DSalida=dist packaging\instalador.iss
; Instalación por usuario: no pide permisos de administrador.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Origen
  #define Origen "..\dist\BajarSubtitulosESP"
#endif
#ifndef Salida
  #define Salida "..\dist"
#endif
#define Nombre "Bajar Subtítulos ESP"
#define Exe "BajarSubtitulosESP.exe"
; Los crea la app al arrancar (app/actualizar.py): el primero indica que está abierta y el segundo dura
; hasta que su proceso termina.
#define MutexApp "BajarSubtitulosESP"
#define MutexProceso "BajarSubtitulosESP-proceso"

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
OutputBaseFilename=BajarSubtitulosESP-{#Version}-instalador
SetupIconFile=build\icono.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Si la app está abierta, el instalador pide cerrarla (la app crea este mutex al arrancar).
AppMutex={#MutexApp}
CloseApplications=yes
LicenseFile=..\LICENSE

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

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
Filename: "{app}\{#Exe}"; Parameters: "--menu-contextual-instalar"; Flags: runasoriginaluser waituntilterminated
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
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

// Al actualizar desde la app, esperar (como mucho 30 s) a que termine de cerrarse antes de tocar
// sus archivos.
function InitializeSetup(): Boolean;
var
  Espera: Integer;
begin
  if Reabrir() then
  begin
    Espera := 0;
    while CheckForMutexes('{#MutexProceso}') and (Espera < 300) do
    begin
      Sleep(100);
      Espera := Espera + 1;
    end;
  end;
  Result := True;
end;
