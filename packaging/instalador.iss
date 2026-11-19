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
AppMutex=BajarSubtitulosESP
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
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent

; La configuración (%APPDATA%\BajarSubtitulosEsp), la contraseña guardada en el Administrador de
; credenciales y las copias de seguridad (%USERPROFILE%\.subtitulos-esp) se conservan al
; desinstalar: son del usuario y las comparte con la skill.
