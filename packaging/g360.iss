; Instalación por usuario: evita pedir elevación y mantiene la escritura de la app
; en el perfil del usuario, incluso cuando Program Files no es accesible.
;
; FUENTE DE VERDAD DE LA VERSIÓN: pyproject.toml [project].version.
; AppVersion y OutputBaseFilename de acá DEBEN coincidir con ella; si no,
; tests/test_packaging_installer.py falla. No se parametriza con /D para
; que el comando documentado (ISCC packaging\g360.iss) siga compilando sin
; argumentos extra.
[Setup]
AppId={{8F307F60-AC65-4E66-9E3E-9F8869BCBB71}}
AppName=G360 NC Sustentor
AppVersion=1.2.2
AppPublisher=CIPSA
DefaultDirName={localappdata}\Programs\G360 NC Sustentor
DefaultGroupName=G360 NC Sustentor
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=G360-NC-Sustentor-1.2.2-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\g360-nc-sustentor.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
ChangesAssociations=no

; Se ofrece español como idioma principal y se conserva inglés como alternativa.
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

; El acceso directo del escritorio es opcional para no alterar el escritorio sin permiso.
[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

; Solo se empaqueta el resultado del build; los datos de usuario quedan fuera del instalador.
[Files]
Source: "..\build\windows\x64\runner\Release\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Los accesos directos apuntan al ejecutable instalado y al desinstalador registrado.
[Icons]
Name: "{group}\G360 NC Sustentor"; Filename: "{app}\g360-nc-sustentor.exe"
Name: "{group}\Desinstalar G360 NC Sustentor"; Filename: "{uninstallexe}"
Name: "{autodesktop}\G360 NC Sustentor"; Filename: "{app}\g360-nc-sustentor.exe"; Tasks: desktopicon

; El instalador NO arranca la app automáticamente: el antivirus/EDR de la máquina
; bloquea los sockets que Flet necesita (WinError 10013). El usuario arranca
; manualmente cuando quiera.
;[Run]
;Filename: "{app}\g360-nc-sustentor.exe"; Description: "Ejecutar G360 NC Sustentor"; Flags: nowait postinstall skipifsilent

; Solo se consulta al desinstalar; actualizar o instalar nunca modifica la carpeta de datos.
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    UserDataDir := ExpandConstant('{userappdata}\g360-erp-nc-sustentor');
    if DirExists(UserDataDir) and
       (MsgBox('¿Desea eliminar también los datos de usuario (historial, logs, configuración)?' + #13#10 +
               'Se eliminarán: ' + UserDataDir + #13#10 +
               'Recomendado: No (los datos se conservan para una futura reinstalación).',
               mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = idYes) then
      DelTree(UserDataDir, True, True, True);
  end;
end;

