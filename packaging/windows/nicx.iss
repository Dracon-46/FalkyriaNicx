; Instalador do Nicx para Windows 10/11 x64 (Inno Setup 6).
;
; Não compile este arquivo diretamente: use build-installer.ps1, que gera os
; wheels, as imagens e os demais arquivos de build\ e dist\ e passa as versões
; por /D. O instalador copia poucos arquivos; o trabalho pesado (Python,
; dependências, Ollama e modelo) é feito por setup-runtime.ps1, executado logo
; depois da cópia, com o progresso mostrado no próprio assistente.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef FileVersion
  #define FileVersion "0.1.0.0"
#endif
#ifndef NicxWheel
  #error Defina NicxWheel (use build-installer.ps1).
#endif
#ifndef RustWheel
  #error Defina RustWheel (use build-installer.ps1).
#endif

[Setup]
AppId={{98206AB1-7B8E-4F41-BB98-2AC1C255E448}
AppName=Nicx
AppVersion={#AppVersion}
AppVerName=Nicx {#AppVersion}
AppPublisher=Falkyria
AppCopyright=Copyright © 2026 Falkyria
VersionInfoVersion={#FileVersion}
VersionInfoCompany=Falkyria
VersionInfoDescription=Instalador do Nicx, a IA da Falkyria
VersionInfoProductName=Nicx
VersionInfoProductVersion={#FileVersion}
; Instalação por usuário, sem administrador: %LOCALAPPDATA%\Programs\Nicx.
PrivilegesRequired=lowest
DefaultDirName={autopf}\Nicx
DefaultGroupName=Nicx
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputBaseFilename=NicxSetup
OutputDir=dist
SetupIconFile=build\brand\nicx.ico
UninstallDisplayIcon={app}\nicx.ico
UninstallDisplayName=Nicx
WizardStyle=modern dynamic
WizardImageFile=build\brand\wizard-164.png,build\brand\wizard-246.png,build\brand\wizard-328.png
WizardSmallImageFile=build\brand\small-55.png,build\brand\small-83.png,build\brand\small-110.png
LicenseFile=build\termos-de-uso.txt
DisableWelcomePage=no
ShowLanguageDialog=no
Compression=lzma2/max
SolidCompression=yes
SetupLogging=yes
SetupMutex=NicxSetupMutex
CloseApplications=yes
RestartApplications=no
; O uv cria junções NTFS (ex.: python\cpython-3.12-windows-x86_64-none) e o
; ambiente do Nicx passa por elas. Com o RedirectionGuard, herdado pelos
; processos filhos, o Windows bloqueia essa travessia (erro 448). A proteção
; visa instaladores elevados; este roda sem privilégios de administrador.
RedirectionGuard=no
; Python e dependências na pasta do aplicativo (os downloads do Ollama e do
; modelo são conferidos pelo setup-runtime.ps1, que avisa se faltar espaço).
ExtraDiskSpaceRequired=1610612736

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
ptbr.WelcomeLabel1=Bem-vindo ao instalador do Nicx
ptbr.WelcomeLabel2=O Nicx é a inteligência artificial da Falkyria. Ele roda inteiramente neste computador, com um modelo de IA local, sem enviar suas conversas para a internet.%n%nO instalador verifica o que o computador já tem e baixa somente o que faltar: o Python, os componentes do Nicx, o Ollama (motor de IA local) e o modelo de IA. Dependendo da internet, isso pode levar de alguns minutos a mais de meia hora.%n%nNão é preciso ser administrador.
ptbr.WizardLicense=Termos de Uso
ptbr.LicenseLabel=Leia os Termos de Uso do Nicx antes de continuar.
ptbr.LicenseLabel3=Para instalar o Nicx, você precisa aceitar os Termos de Uso abaixo. A política de privacidade também pode ser consultada no aplicativo, em Configurações.
ptbr.LicenseAccepted=Eu &aceito os Termos de Uso
ptbr.LicenseNotAccepted=Eu &não aceito os Termos de Uso
ptbr.SelectComponentsLabel2=Escolha o que instalar e clique em Avançar.
ptbr.FinishedHeadingLabel=O Nicx está pronto
ptbr.FinishedLabelNoIcons=O Nicx foi instalado neste computador.
ptbr.FinishedLabel=O Nicx foi instalado neste computador. Para abri-lo depois, procure "Nicx" no menu Iniciar.
ptbr.ConfirmUninstall=Deseja remover o Nicx deste computador?%n%nO Ollama e os modelos de IA baixados continuam instalados; eles podem ser removidos separadamente em Configurações > Aplicativos.

[Types]
Name: "completa"; Description: "Completa, com voz em português (recomendada)"
Name: "compacta"; Description: "Compacta, sem voz"
Name: "personalizada"; Description: "Personalizada"; Flags: iscustom

[Components]
Name: "nicx"; Description: "Nicx: aplicativo, servidor local e modelo de IA"; Types: completa compacta personalizada; Flags: fixed
Name: "voz"; Description: "Voz em português: falar e ouvir o Nicx (baixa cerca de 1 GB a mais)"; Types: completa; ExtraDiskSpaceRequired: 2684354560

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Pacotes de versões anteriores.
Type: files; Name: "{app}\setup\wheels\*.whl"

[Files]
Source: "nicx-launcher.pyw"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "build\brand\nicx.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\brand\splash-*.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\uv\uv.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "setup-runtime.ps1"; DestDir: "{app}\setup"; Flags: ignoreversion
Source: "dist\constraints.txt"; DestDir: "{app}\setup"; Flags: ignoreversion
Source: "dist\wheels\{#NicxWheel}"; DestDir: "{app}\setup\wheels"; Flags: ignoreversion
Source: "dist\wheels\{#RustWheel}"; DestDir: "{app}\setup\wheels"; Flags: ignoreversion
; Wheels pré-gerados de dependências que o PyPI só oferece como código-fonte.
Source: "dist\wheels\*.whl"; Excludes: "nicx-*.whl,nicx_rust-*.whl"; DestDir: "{app}\setup\wheels"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Nicx"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\nicx-launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\nicx.ico"; Comment: "Abrir o Nicx, a IA da Falkyria"
Name: "{group}\Parar o Nicx"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\nicx-launcher.pyw"" --stop"; WorkingDir: "{app}"; IconFilename: "{app}\nicx.ico"; Comment: "Encerrar o servidor local do Nicx"
Name: "{autodesktop}\Nicx"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\nicx-launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\nicx.ico"; Comment: "Abrir o Nicx, a IA da Falkyria"; Tasks: desktopicon

[Run]
Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\nicx-launcher.pyw"""; WorkingDir: "{app}"; Description: "Abrir o Nicx agora"; Flags: postinstall nowait skipifsilent; Check: RuntimeReady

[UninstallRun]
Filename: "{app}\venv\Scripts\python.exe"; Parameters: """{app}\nicx-launcher.pyw"" --stop --quiet"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "PararNicx"
; Algumas dependências (ex.: PyTorch) têm caminhos com mais de 260 caracteres;
; o "rd" com o prefixo \\?\ consegue apagá-los.
Filename: "{cmd}"; Parameters: "/d /c if exist ""{app}\venv"" rd /s /q ""\\?\{app}\venv"""; Flags: runhidden waituntilterminated; RunOnceId: "ApagarVenv"
Filename: "{cmd}"; Parameters: "/d /c if exist ""{app}\python"" rd /s /q ""\\?\{app}\python"""; Flags: runhidden waituntilterminated; RunOnceId: "ApagarPython"
Filename: "{cmd}"; Parameters: "/d /c if exist ""{app}\uv-cache"" rd /s /q ""\\?\{app}\uv-cache"""; Flags: runhidden waituntilterminated; RunOnceId: "ApagarCache"

[UninstallDelete]
; Criados pelo setup-runtime.ps1 depois da cópia dos arquivos.
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\uv-cache"
Type: filesandordirs; Name: "{app}\downloads"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\setup"
Type: filesandordirs; Name: "{app}\bin"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: dirifempty; Name: "{app}"

[Code]
const
  RuntimeFailedExitCode = 10;

var
  ProgressPage: TOutputProgressWizardPage;
  StopButton: TNewButton;
  CancelFlagFile: String;
  RuntimeExitCode: Integer;
  RuntimeError: String;
  RuntimeLastLine: String;
  RuntimeDone: Boolean;

function RuntimeReady: Boolean;
begin
  Result := RuntimeDone and (RuntimeExitCode = 0);
end;

procedure StopButtonClick(Sender: TObject);
begin
  if MsgBox('Interromper a preparação do Nicx?' + #13#10#13#10 +
    'O que já foi baixado é mantido. Para continuar depois, execute o instalador de novo.',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
  begin
    SaveStringToFile(CancelFlagFile, 'cancelar', False);
    StopButton.Enabled := False;
    ProgressPage.SetText('Interrompendo...', '');
  end;
end;

procedure InitializeWizard;
begin
  ProgressPage := CreateOutputProgressPage('Preparando o Nicx',
    'O instalador verifica o que este computador já tem e baixa somente o que faltar.');
  StopButton := TNewButton.Create(ProgressPage);
  StopButton.Parent := ProgressPage.Surface;
  StopButton.Caption := 'Interromper';
  StopButton.Width := ScaleX(100);
  StopButton.Height := WizardForm.CancelButton.Height;
  StopButton.Left := ProgressPage.SurfaceWidth - StopButton.Width;
  StopButton.Top := ProgressPage.ProgressBar.Top + ProgressPage.ProgressBar.Height + ScaleY(24);
  StopButton.OnClick := @StopButtonClick;
end;

{ Linhas do setup-runtime.ps1: "##nicx:step <título>", "##nicx:progress <0-1000>",
  "##nicx:error <mensagem>"; as demais aparecem como detalhe. }
procedure RuntimeOutput(const S: String; const Error, FirstLine: Boolean);
var
  Line, Kind, Value: String;
  P: Integer;
begin
  Log('runtime: ' + S);
  Line := S;
  if Copy(Line, 1, 7) = '##nicx:' then
  begin
    Delete(Line, 1, 7);
    P := Pos(' ', Line);
    if P > 0 then
    begin
      Kind := Copy(Line, 1, P - 1);
      Value := Copy(Line, P + 1, Length(Line));
    end else
    begin
      Kind := Line;
      Value := '';
    end;
    if Kind = 'step' then
      ProgressPage.SetText(Value, '')
    else if Kind = 'progress' then
      ProgressPage.SetProgress(StrToIntDef(Value, 0), 1000)
    else if Kind = 'error' then
      RuntimeError := Value;
  end
  else if Trim(Line) <> '' then
  begin
    RuntimeLastLine := Trim(Line);
    ProgressPage.Msg2Label.Caption := RuntimeLastLine;
  end;
end;

procedure RunRuntimeSetup;
var
  Params: String;
  ResultCode: Integer;
  Ran: Boolean;
begin
  CancelFlagFile := ExpandConstant('{tmp}\interromper-nicx.flag');
  DeleteFile(CancelFlagFile);
  RuntimeError := '';
  RuntimeExitCode := -1;
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\setup\setup-runtime.ps1') + '"' +
    ' -AppDir "' + ExpandConstant('{app}') + '" -WizardProgress -CancelFile "' + CancelFlagFile + '"';
  if WizardIsComponentSelected('voz') then
    Params := Params + ' -Voice';
  ProgressPage.SetText('Iniciando...', '');
  ProgressPage.SetProgress(0, 1000);
  ProgressPage.Show;
  try
    try
      Ran := ExecAndLogOutput(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params,
        ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode, @RuntimeOutput);
      if Ran then
        RuntimeExitCode := ResultCode
      else
        RuntimeError := SysErrorMessage(ResultCode);
    except
      RuntimeError := GetExceptionMessage;
    end;
  finally
    ProgressPage.Hide;
  end;
  RuntimeDone := True;
  Log(Format('setup-runtime.ps1 terminou com código %d', [RuntimeExitCode]));

  if RuntimeExitCode = 2 then
    SuppressibleMsgBox('A preparação do Nicx foi interrompida.' + #13#10#13#10 +
      'O que já foi baixado foi mantido. Para terminar, execute o instalador de novo.',
      mbInformation, MB_OK, IDOK)
  else if RuntimeExitCode <> 0 then
  begin
    if RuntimeError = '' then
      RuntimeError := RuntimeLastLine;
    SuppressibleMsgBox('Não foi possível concluir a preparação do Nicx.' + #13#10#13#10 +
      RuntimeError + #13#10#13#10 +
      'O registro completo está em ' + ExpandConstant('{app}\logs') + '.' + #13#10 +
      'Para tentar de novo, execute o instalador outra vez: ele reaproveita o que já foi baixado.',
      mbError, MB_OK, IDOK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunRuntimeSetup;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and RuntimeDone and (RuntimeExitCode <> 0) then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Instalação incompleta';
    WizardForm.FinishedLabel.Caption :=
      'Os arquivos do Nicx foram copiados, mas a preparação não terminou.' + #13#10#13#10 +
      'Execute o instalador de novo para concluir. O registro está em ' + ExpandConstant('{app}\logs') + '.';
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  if RuntimeDone and (RuntimeExitCode <> 0) then
    Result := RuntimeFailedExitCode
  else
    Result := 0;
end;

{ ---------------------------------------------------------------- Desinstalação }

function NicxHomeDir: String;
begin
  Result := GetEnv('NICX_HOME');
  if Result = '' then
  begin
    Result := GetEnv('XDG_DATA_HOME');
    if Result <> '' then
      Result := AddBackslash(Result) + 'nicx'
    else
      Result := ExpandConstant('{%USERPROFILE}\.nicx');
  end;
  Result := RemoveBackslashUnlessRoot(Result);
end;

{ Só apaga uma pasta que é claramente a pasta de dados do Nicx. }
function LooksLikeNicxHome(const Dir: String): Boolean;
var
  D: String;
begin
  D := AddBackslash(Dir);
  Result := DirExists(Dir) and (Length(Dir) > 3) and
    (CompareText(Dir, RemoveBackslashUnlessRoot(ExpandConstant('{%USERPROFILE}'))) <> 0) and
    (FileExists(D + 'config.toml') or FileExists(D + 'SOUL.md') or FileExists(D + 'memory.db'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Home: String;
  Remove: Boolean;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  Home := NicxHomeDir;
  if not LooksLikeNicxHome(Home) then
    Exit;
  Remove := ExpandConstant('{param:APAGARDADOS|0}') = '1';
  if not Remove then
    Remove := SuppressibleMsgBox('Deseja apagar também os seus dados do Nicx?' + #13#10#13#10 +
      Home + #13#10#13#10 +
      'Conversas, memória, configurações e personalidade do Nicx ficam nessa pasta. ' +
      'Esta ação não pode ser desfeita. Escolha "Não" para mantê-los (recomendado se for reinstalar).',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
  if Remove then
    DelTree(Home, True, True, True);
end;
