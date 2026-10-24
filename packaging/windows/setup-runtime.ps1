#requires -Version 5.1
<#
.SYNOPSIS
    Prepara o ambiente do Nicx neste computador.

.DESCRIPTION
    Executado pelo instalador NicxSetup.exe logo depois de copiar os arquivos.
    Verifica o que o computador já tem e baixa somente o que faltar:

      1. Sistema: versão do Windows, memória RAM e espaço livre em disco
         (com pouca memória escolhe um modelo e um contexto menores).
      2. uv (gerenciador de Python): usa o que acompanha o instalador.
      3. Python 3.12 exclusivo do Nicx, dentro da pasta do aplicativo.
      4. Pacotes do Nicx: os dois wheels do instalador + dependências do PyPI
         (servidor, memória, PDF e, se escolhido, voz em português).
      5. Configuração inicial em ~/.nicx (só se ainda não existir).
      6. Ollama: detecta, inicia ou instala (instalador oficial, sem admin).
      7. Modelo de IA local (qwen3.5:4b ou menor), baixado só se faltar.
      8. Modelos de voz (opcional).

    Pode ser executado sozinho para reparar uma instalação. Com -DryRun apenas
    mostra o plano, sem alterar nada. Não pede nem guarda senhas ou chaves e
    não envia dados de uso.

.PARAMETER AppDir
    Pasta do aplicativo. Padrão: a pasta acima deste script, quando instalado;
    senão %LOCALAPPDATA%\Programs\Nicx.

.PARAMETER PackageDir
    Pasta com wheels\ e constraints.txt. Padrão: a pasta deste script (instalado)
    ou packaging\windows\dist (repositório).

.PARAMETER Voice
    Instala também a voz em português (fala e escuta; inclui o PyTorch).

.PARAMETER Model
    Modelo do Ollama a usar no lugar da escolha automática.

.PARAMETER DryRun
    Só mostra o plano.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup-runtime.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string] $AppDir,
    [string] $PackageDir,
    [switch] $Voice,
    [string] $Model,
    [switch] $SkipOllama,
    [switch] $SkipModel,
    [switch] $DryRun,
    [switch] $KeepCache,
    [string] $CancelFile,
    [string] $LogFile,
    [switch] $WizardProgress
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$ProgressPreference = 'SilentlyContinue'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
try { [Console]::OutputEncoding = $Utf8NoBom } catch { }
$OutputEncoding = $Utf8NoBom

# O Python e a extensão nativa são x64; rode sempre no PowerShell de 64 bits.
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
    $native = Join-Path $env:WINDIR 'sysnative\WindowsPowerShell\v1.0\powershell.exe'
    $argsList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    foreach ($kv in $PSBoundParameters.GetEnumerator()) {
        if ($kv.Value -is [System.Management.Automation.SwitchParameter]) {
            if ($kv.Value.IsPresent) { $argsList += "-$($kv.Key)" }
        } else { $argsList += "-$($kv.Key)"; $argsList += [string] $kv.Value }
    }
    & $native @argsList
    exit $LASTEXITCODE
}

$ScriptDir = $PSScriptRoot
$GB = 1GB
$MB = 1MB

# ---------------------------------------------------------------------------
# Saída, registro e progresso
# ---------------------------------------------------------------------------

$script:LogPath = $null
$script:Steps = @()
$script:StepIndex = 0
$script:DoneWeight = 0.0
$script:TotalWeight = 1.0
$script:CurrentWeight = 0.0
$script:LastProgress = -1
$script:LastProgressAt = [DateTime]::MinValue

function Write-Log([string] $text) {
    if (-not $script:LogPath) { return }
    try {
        [IO.File]::AppendAllText($script:LogPath, ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $text) + "`r`n", $Utf8NoBom)
    } catch { }
}

function Out-Line([string] $text, [string] $color = '') {
    if ($WizardProgress -or -not $color) {
        [Console]::Out.WriteLine($text)
    } else {
        Write-Host $text -ForegroundColor $color
    }
    Write-Log $text
}

function Out-Marker([string] $kind, [string] $value) {
    if ($WizardProgress) { [Console]::Out.WriteLine("##nicx:$kind $value") }
}

function Write-StatusOk([string] $t) { Out-Line "  [ok] $t" 'Green' }
function Write-StatusTodo([string] $t) { Out-Line "  [$(if ($DryRun) { 'faria' } else { 'fazer' })] $t" 'Cyan' }
function Write-StatusWarn([string] $t) { Out-Line "  [aviso] $t" 'Yellow' }
function Write-StatusInfo([string] $t) { Out-Line "  $t" }
function Write-StatusDetail([string] $t) {
    if (-not $t.Trim()) { return }
    Out-Line "    $t" 'DarkGray'
}

function Test-Cancel {
    if ($CancelFile -and (Test-Path -LiteralPath $CancelFile)) {
        throw (New-Object System.OperationCanceledException 'Preparação cancelada pelo usuário.')
    }
}

function Start-Step([string] $key) {
    Test-Cancel
    $step = $script:Steps | Where-Object { $_.Key -eq $key } | Select-Object -First 1
    $script:StepIndex++
    $script:CurrentWeight = [double] $step.Weight
    Out-Line ''
    Out-Line "[$($script:StepIndex)/$($script:Steps.Count)] $($step.Title)" 'White'
    Out-Marker 'step' $step.Title
    Set-StepProgress 0
}

function Set-StepProgress([double] $fraction) {
    if ($fraction -lt 0) { $fraction = 0 } elseif ($fraction -gt 1) { $fraction = 1 }
    $overall = [int] (1000 * ($script:DoneWeight + $script:CurrentWeight * $fraction) / $script:TotalWeight)
    if ($overall -ne $script:LastProgress) {
        $script:LastProgress = $overall
        Out-Marker 'progress' $overall
    }
}

function Complete-Step {
    $script:DoneWeight += $script:CurrentWeight
    $script:CurrentWeight = 0
    Set-StepProgress 0
}

function Format-Size([double] $bytes) {
    if ($bytes -ge $GB) { return ('{0:N1} GB' -f ($bytes / $GB)) }
    return ('{0:N0} MB' -f ($bytes / $MB))
}

# ---------------------------------------------------------------------------
# Programas externos e downloads
# ---------------------------------------------------------------------------

function ConvertTo-CmdArg([string] $a) {
    if ($a -eq '') { return '""' }
    if ($a -notmatch '[\s"]') { return $a }
    $e = $a -replace '(\\*)"', '$1$1\"'
    $e = $e -replace '(\\+)$', '$1$1'
    return '"' + $e + '"'
}

# Runs a program, showing stderr line by line (uv writes its progress there)
# and collecting stdout. Returns @{ ExitCode; StdOut }.
function Invoke-Tool {
    param(
        [string] $FilePath,
        [string[]] $Arguments,
        [hashtable] $Environment = @{},
        [switch] $Quiet
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = (@($Arguments) | ForEach-Object { ConvertTo-CmdArg $_ }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = $Utf8NoBom
    $psi.StandardErrorEncoding = $Utf8NoBom
    $psi.CreateNoWindow = $true
    foreach ($k in $Environment.Keys) {
        if ($null -eq $Environment[$k]) { $psi.EnvironmentVariables.Remove($k) }
        else { $psi.EnvironmentVariables[$k] = [string] $Environment[$k] }
    }
    Write-Log ("executando: $FilePath $($psi.Arguments)" -replace '\r?\n', ' ; ')
    $proc = [System.Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errorLine = ''
    try {
        while ($null -ne ($line = $proc.StandardError.ReadLine())) {
            if ($Quiet) { Write-Log "    $line" } else { Write-StatusDetail $line }
            # uv: "error: ..." / "  × ..." / "  Caused by: ..."; Python: "XxxError: ..."
            if ($line -match '^\s*(error:|×|Caused by:|\w+Error:)') { $errorLine = $line.Trim() }
            Test-Cancel
        }
        $proc.WaitForExit()
    } catch {
        if (-not $proc.HasExited) { try { $proc.Kill() } catch { } }
        throw
    }
    $stdout = $outTask.Result
    if ($stdout) { foreach ($l in ($stdout -split "`r?`n")) { if ($l) { Write-Log "    $l" } } }
    return [pscustomobject]@{ ExitCode = $proc.ExitCode; StdOut = $stdout; ErrorLine = $errorLine }
}

function Get-ToolError($result, [string] $what) {
    $msg = "$what (código $($result.ExitCode))."
    if ($result.ErrorLine) { $msg += " Detalhe: $($result.ErrorLine)" }
    return $msg
}

[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function New-WebRequest([string] $url, [string] $method = 'GET', [int] $timeoutMs = 30000) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = $method
    $req.Timeout = $timeoutMs
    $req.ReadWriteTimeout = 600000
    $req.UserAgent = 'NicxSetup'
    $req.AllowAutoRedirect = $true
    $uri = [Uri] $url
    if ($uri.IsLoopback) {
        $req.Proxy = $null
    } elseif ($req.Proxy) {
        $req.Proxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials
    }
    return $req
}

function Get-Json([string] $url, [int] $timeoutMs = 3000) {
    try {
        $req = New-WebRequest $url 'GET' $timeoutMs
        $resp = $req.GetResponse()
        try {
            $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), $Utf8NoBom)
            return ($reader.ReadToEnd() | ConvertFrom-Json)
        } finally { $resp.Close() }
    } catch {
        return $null
    }
}

# Downloads with resume (Range) and progress; returns the file path.
function Get-Download([string] $url, [string] $dest, [string] $label) {
    $partial = "$dest.partial"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    $existing = 0
    if (Test-Path -LiteralPath $partial) { $existing = (Get-Item -LiteralPath $partial).Length }
    $req = New-WebRequest $url
    if ($existing -gt 0) { $req.AddRange([long] $existing) }
    $resp = $req.GetResponse()
    try {
        $status = [int] $resp.StatusCode
        $append = ($existing -gt 0 -and $status -eq 206)
        if (-not $append) { $existing = 0 }
        $total = $resp.ContentLength
        if ($total -gt 0) { $total += $existing }
        $mode = if ($append) { [IO.FileMode]::Append } else { [IO.FileMode]::Create }
        $out = New-Object IO.FileStream($partial, $mode, [IO.FileAccess]::Write)
        try {
            $in = $resp.GetResponseStream()
            $buf = New-Object byte[] (1MB)
            $done = $existing
            $lastShown = [DateTime]::MinValue
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
                $out.Write($buf, 0, $n)
                $done += $n
                Test-Cancel
                if (((Get-Date) - $lastShown).TotalSeconds -ge 2) {
                    $lastShown = Get-Date
                    if ($total -gt 0) {
                        $frac = $done / $total
                        Set-StepProgress ($frac * 0.85)
                        Write-StatusDetail ('{0}: {1:N0}% ({2} de {3})' -f $label, ($frac * 100), (Format-Size $done), (Format-Size $total))
                    } else {
                        Write-StatusDetail ('{0}: {1}' -f $label, (Format-Size $done))
                    }
                }
            }
        } finally { $out.Close() }
    } finally { $resp.Close() }
    Move-Item -LiteralPath $partial -Destination $dest -Force
    return $dest
}

# ---------------------------------------------------------------------------
# Detecção
# ---------------------------------------------------------------------------

function Get-NicxHome {
    if ($env:NICX_HOME) { return [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($env:NICX_HOME)) }
    if ($env:XDG_DATA_HOME) { return (Join-Path $env:XDG_DATA_HOME 'nicx') }
    return (Join-Path $env:USERPROFILE '.nicx')
}

function Get-OllamaBase {
    $h = $env:OLLAMA_HOST
    if (-not $h) { return 'http://127.0.0.1:11434' }
    if ($h -notmatch '^https?://') { $h = "http://$h" }
    $u = [Uri] $h
    $hostName = if ($u.Host -in @('0.0.0.0', '::', '[::]', '')) { '127.0.0.1' } else { $u.Host }
    $port = if ($u.IsDefaultPort -and $h -notmatch ':\d+') { 11434 } else { $u.Port }
    return "$($u.Scheme)://${hostName}:$port"
}

function Find-Ollama {
    $candidates = @()
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe')
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles 'Ollama\ollama.exe') }
    foreach ($c in $candidates) { if ($c -and (Test-Path -LiteralPath $c)) { return (Resolve-Path -LiteralPath $c).Path } }
    return $null
}

function Get-OllamaVersion([string] $base) {
    $v = Get-Json "$base/api/version" 2000
    if ($v -and $v.version) { return [string] $v.version }
    return $null
}

function Get-OllamaModels([string] $base) {
    $tags = Get-Json "$base/api/tags" 5000
    if (-not $tags -or -not $tags.PSObject.Properties['models']) { return $null }
    return @($tags.models | ForEach-Object { [string] $_.name })
}

function Test-ModelPresent([string[]] $names, [string] $wanted) {
    $w = $wanted.ToLowerInvariant()
    if ($w -notmatch ':') { $w = "$w`:latest" }
    foreach ($n in $names) {
        $x = $n.ToLowerInvariant()
        if ($x -notmatch ':') { $x = "$x`:latest" }
        if ($x -eq $w) { return $true }
    }
    return $false
}

function Get-ModelDownloadSize([string] $name) {
    $parts = $name.Split(':')
    $repo = $parts[0]; $tag = if ($parts.Count -gt 1) { $parts[1] } else { 'latest' }
    if ($repo -notmatch '/') { $repo = "library/$repo" }
    try {
        $req = New-WebRequest "https://registry.ollama.ai/v2/$repo/manifests/$tag" 'GET' 8000
        $req.Accept = 'application/vnd.docker.distribution.manifest.v2+json'
        $resp = $req.GetResponse()
        try {
            $m = (New-Object System.IO.StreamReader($resp.GetResponseStream())).ReadToEnd() | ConvertFrom-Json
        } finally { $resp.Close() }
        $sum = [double] $m.config.size
        foreach ($l in $m.layers) { $sum += [double] $l.size }
        if ($sum -gt 0) { return $sum }
    } catch { }
    $fallback = @{ '0.8b' = 1.3; '2b' = 2.6; '4b' = 3.2 }
    if ($fallback.ContainsKey($tag)) { return $fallback[$tag] * $GB }
    return 4 * $GB
}

function Read-ConfigValue([string] $path, [string] $section, [string] $key) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $current = ''
    foreach ($line in [IO.File]::ReadAllLines($path, $Utf8NoBom)) {
        $t = $line.Trim()
        if ($t -match '^\[([^\]]+)\]') { $current = $Matches[1].Trim(); continue }
        if ($current -eq $section -and $t -match ('^' + [regex]::Escape($key) + '\s*=\s*"([^"]*)"')) { return $Matches[1] }
    }
    return $null
}

function Get-FreeBytes([string] $path) {
    try {
        $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($path))
        return (New-Object IO.DriveInfo($root)).AvailableFreeSpace
    } catch { return $null }
}

function Get-VenvPythonVersion([string] $venv) {
    $cfg = Join-Path $venv 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $cfg)) { return $null }
    foreach ($line in [IO.File]::ReadAllLines($cfg)) {
        if ($line -match '^\s*version(_info)?\s*=\s*(\S+)') { return $Matches[2] }
    }
    return $null
}

# True when the Whisper base and Kokoro (pt-BR voices) files are already in the
# Hugging Face cache that the Nicx server will read.
function Test-VoiceModelsCached {
    $hub = if ($env:HF_HUB_CACHE) { $env:HF_HUB_CACHE }
           elseif ($env:HF_HOME) { Join-Path $env:HF_HOME 'hub' }
           elseif ($env:XDG_CACHE_HOME) { Join-Path $env:XDG_CACHE_HOME 'huggingface\hub' }
           else { Join-Path $env:USERPROFILE '.cache\huggingface\hub' }
    $need = @(
        @('models--Systran--faster-whisper-base', 'model.bin'),
        @('models--hexgrad--Kokoro-82M', 'kokoro-v1_0.pth'),
        @('models--hexgrad--Kokoro-82M', 'voices\pf_dora.pt')
    )
    foreach ($n in $need) {
        $found = Get-ChildItem -Path (Join-Path $hub "$($n[0])\snapshots\*\$($n[1])") -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $found) { return $false }
    }
    return $true
}

function Get-InstalledDist([string] $venv, [string] $name) {
    $sp = Join-Path $venv 'Lib\site-packages'
    if (-not (Test-Path -LiteralPath $sp)) { return $null }
    $d = Get-ChildItem -LiteralPath $sp -Directory -Filter "$name-*.dist-info" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($d -and $d.Name -match "^$([regex]::Escape($name))-(.+)\.dist-info$") { return $Matches[1] }
    return $null
}

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------

if (-not $AppDir) {
    $parent = Split-Path -Parent $ScriptDir
    if ((Split-Path -Leaf $ScriptDir) -eq 'setup' -and (Test-Path (Join-Path $parent 'nicx-launcher.pyw'))) {
        $AppDir = $parent
    } else {
        $AppDir = Join-Path $env:LOCALAPPDATA 'Programs\Nicx'
    }
}
$AppDir = [IO.Path]::GetFullPath($AppDir)
if (-not $PackageDir) {
    $PackageDir = if (Test-Path (Join-Path $ScriptDir 'wheels')) { $ScriptDir } else { Join-Path $ScriptDir 'dist' }
}
$PackageDir = [IO.Path]::GetFullPath($PackageDir)
$VenvDir = Join-Path $AppDir 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$PythonDir = Join-Path $AppDir 'python'
$CacheDir = Join-Path $AppDir 'uv-cache'
$DownloadDir = Join-Path $AppDir 'downloads'
$NicxHome = Get-NicxHome
$ConfigPath = Join-Path $NicxHome 'config.toml'
$OllamaBase = Get-OllamaBase
$OllamaModelsDir = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $env:USERPROFILE '.ollama\models' }

if (-not $DryRun) {
    if (-not $LogFile) { $LogFile = Join-Path $AppDir ("logs\setup-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date)) }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
    $script:LogPath = $LogFile
}

# ---------------------------------------------------------------------------
# Plano
# ---------------------------------------------------------------------------

$os = [Environment]::OSVersion.Version
$osName = 'Windows'
try { $osName = (Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).Caption -replace '^Microsoft\s+', '' } catch { }
$arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$ramTotal = 0.0; $ramFree = 0.0
try {
    $ramTotal = [double] (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory
    $ramFree = [double] (Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).FreePhysicalMemory * 1KB
} catch {
    try {
        Add-Type -AssemblyName Microsoft.VisualBasic
        $ci = New-Object Microsoft.VisualBasic.Devices.ComputerInfo
        $ramTotal = [double] $ci.TotalPhysicalMemory; $ramFree = [double] $ci.AvailablePhysicalMemory
    } catch { }
}
$ramGB = $ramTotal / $GB

$configExists = Test-Path -LiteralPath $ConfigPath
$configModel = if ($configExists) { Read-ConfigValue $ConfigPath 'intelligence' 'default_model' } else { $null }
$configEngine = if ($configExists) { Read-ConfigValue $ConfigPath 'engine' 'default' } else { $null }

$numCtx = 8192
if ($Model) {
    $chosenModel = $Model; $modelReason = 'escolhido manualmente'
    if ($ramGB -gt 0 -and $ramGB -lt 12) { $numCtx = 4096 }
} elseif ($configModel) {
    $chosenModel = $configModel; $modelReason = 'da configuração existente'
} elseif ($ramGB -gt 0 -and $ramGB -lt 4) {
    $chosenModel = 'qwen3.5:0.8b'; $numCtx = 2048; $modelReason = 'pouca memória'
} elseif ($ramGB -gt 0 -and $ramGB -lt 8) {
    $chosenModel = 'qwen3.5:2b'; $numCtx = 4096; $modelReason = 'menos de 8 GB de RAM'
} elseif ($ramGB -gt 0 -and $ramGB -lt 12) {
    $chosenModel = 'qwen3.5:4b'; $numCtx = 4096; $modelReason = 'padrão, com contexto reduzido'
} else {
    $chosenModel = 'qwen3.5:4b'; $modelReason = 'padrão'
}
$useOllama = (-not $configEngine) -or ($configEngine -eq 'ollama')

$bundledUv = @((Join-Path $AppDir 'bin\uv.exe'), (Join-Path $ScriptDir 'build\uv\uv.exe')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$uvExe = $bundledUv
$uvSource = 'embutido no instalador'
if (-not $uvExe) {
    $c = Get-Command uv -ErrorAction SilentlyContinue
    if ($c) { $uvExe = $c.Source; $uvSource = 'encontrado no PATH' }
    elseif (Test-Path (Join-Path $env:USERPROFILE '.local\bin\uv.exe')) { $uvExe = Join-Path $env:USERPROFILE '.local\bin\uv.exe'; $uvSource = 'encontrado em ~\.local\bin' }
}

$wheelDir = Join-Path $PackageDir 'wheels'
$nicxWheel = Get-ChildItem -LiteralPath $wheelDir -Filter 'nicx-*.whl' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$rustWheel = Get-ChildItem -LiteralPath $wheelDir -Filter 'nicx_rust-*.whl' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$constraints = Join-Path $PackageDir 'constraints.txt'
$nicxVersion = if ($nicxWheel -and $nicxWheel.Name -match '^nicx-([^-]+)-') { $Matches[1] } else { $null }

$venvVersion = Get-VenvPythonVersion $VenvDir
$venvOk = (Test-Path -LiteralPath $VenvPython) -and $venvVersion -and $venvVersion.StartsWith('3.12')
$installedNicx = if ($venvOk) { Get-InstalledDist $VenvDir 'nicx' } else { $null }
$installedKokoro = if ($venvOk) { Get-InstalledDist $VenvDir 'kokoro' } else { $null }
$managedPython = @(Get-ChildItem -LiteralPath $PythonDir -Directory -Filter 'cpython-3.12*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '*.lock' })

$ollamaExe = Find-Ollama
$ollamaVersion = Get-OllamaVersion $OllamaBase
$ollamaRunning = [bool] $ollamaVersion
if (-not $ollamaVersion -and $ollamaExe) {
    try { $ollamaVersion = (Get-Item -LiteralPath $ollamaExe).VersionInfo.ProductVersion } catch { }
}
$models = if ($ollamaRunning) { Get-OllamaModels $OllamaBase } else { $null }
$modelPresent = $null
if ($models) { $modelPresent = Test-ModelPresent $models $chosenModel }
elseif ($ollamaRunning) { $modelPresent = $false }
if ($null -eq $modelPresent) {
    # Ollama parado: procura o manifesto do modelo direto na pasta de modelos.
    $p = $chosenModel.Split(':'); $tag = if ($p.Count -gt 1) { $p[1] } else { 'latest' }
    $repoPath = if ($p[0] -match '/') { $p[0] -replace '/', '\' } else { "library\$($p[0])" }
    $manifest = Join-Path $OllamaModelsDir "manifests\registry.ollama.ai\$repoPath\$tag"
    if (Test-Path -LiteralPath $manifest) { $modelPresent = $true }
}

$needOllamaInstall = $useOllama -and -not $SkipOllama -and -not $ollamaExe -and -not $ollamaRunning
$needModel = $useOllama -and -not $SkipModel -and ($modelPresent -ne $true)
$modelBytes = if ($needModel) { Get-ModelDownloadSize $chosenModel } else { 0 }
$wantVoice = [bool] $Voice

$script:Steps = @(
    @{ Key = 'system'; Title = 'Verificando o computador'; Weight = 1 },
    @{ Key = 'uv'; Title = 'Gerenciador de pacotes (uv)'; Weight = 1 },
    @{ Key = 'python'; Title = 'Python 3.12'; Weight = $(if ($managedPython.Count -gt 0) { 1 } else { 4 }) },
    @{ Key = 'packages'; Title = 'Componentes do Nicx'; Weight = $(if ($wantVoice) { 40 } else { 20 }) },
    @{ Key = 'config'; Title = 'Configuração inicial'; Weight = 2 }
)
if ($useOllama) {
    $script:Steps += @{ Key = 'ollama'; Title = 'Ollama (motor de IA local)'; Weight = $(if ($needOllamaInstall) { 35 } else { 2 }) }
    $script:Steps += @{ Key = 'model'; Title = "Modelo de IA ($chosenModel)"; Weight = $(if ($needModel) { 45 } else { 1 }) }
}
if ($wantVoice) { $script:Steps += @{ Key = 'voice'; Title = 'Modelos de voz em português'; Weight = 10 } }
$script:Steps += @{ Key = 'finish'; Title = 'Finalizando'; Weight = 1 }
$script:TotalWeight = [double] (($script:Steps | ForEach-Object { $_.Weight }) | Measure-Object -Sum).Sum

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

$uvEnv = @{
    UV_PYTHON_INSTALL_DIR = $PythonDir
    UV_CACHE_DIR = $CacheDir
    UV_PYTHON_PREFERENCE = 'only-managed'
    UV_PYTHON_DOWNLOADS = 'automatic'
    UV_NO_PROGRESS = '1'
    NO_COLOR = '1'
    VIRTUAL_ENV = $null
}
$pythonRequest = 'cpython-3.12-windows-x86_64-none'

function Stop-AppServer {
    $pidFile = Join-Path $NicxHome 'server.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return }
    $serverPid = 0
    if (-not [int]::TryParse(([IO.File]::ReadAllText($pidFile)).Trim(), [ref] $serverPid)) { return }
    $proc = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if (-not $proc) { return }
    $path = $null
    try { $path = $proc.Path } catch { }
    if (-not $path -or -not $path.StartsWith($AppDir, [StringComparison]::OrdinalIgnoreCase)) { return }
    Write-StatusInfo "Encerrando o servidor do Nicx em execução (PID $serverPid)..."
    $nicxExe = Join-Path $VenvDir 'Scripts\nicx.exe'
    if (Test-Path -LiteralPath $nicxExe) {
        Invoke-Tool $nicxExe @('stop') @{ PYTHONUTF8 = '1' } -Quiet | Out-Null
    }
    if (-not $proc.HasExited) { try { $proc.WaitForExit(10000) | Out-Null } catch { } }
    if (-not $proc.HasExited) { Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue }
}

function Start-Ollama([string] $exe) {
    $dir = Split-Path -Parent $exe
    $app = Join-Path $dir 'ollama app.exe'
    if (Test-Path -LiteralPath $app) {
        Start-Process -FilePath $app -WorkingDirectory $dir | Out-Null
    } else {
        Start-Process -FilePath $exe -ArgumentList 'serve' -WorkingDirectory $dir -WindowStyle Hidden | Out-Null
    }
}

function Wait-Ollama([int] $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $v = Get-OllamaVersion $OllamaBase
        if ($v) { return $v }
        Test-Cancel
        Start-Sleep -Milliseconds 1000
    }
    return $null
}

function Invoke-ModelPull([string] $name) {
    $req = New-WebRequest "$OllamaBase/api/pull" 'POST' 60000
    $req.ContentType = 'application/json'
    $req.ReadWriteTimeout = 900000
    $body = $Utf8NoBom.GetBytes((@{ model = $name; name = $name; stream = $true } | ConvertTo-Json -Compress))
    $req.ContentLength = $body.Length
    $rs = $req.GetRequestStream(); $rs.Write($body, 0, $body.Length); $rs.Close()
    $resp = $req.GetResponse()
    $layers = @{}
    $lastStatus = ''
    $lastShown = [DateTime]::MinValue
    try {
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), $Utf8NoBom)
        while ($null -ne ($line = $reader.ReadLine())) {
            Test-Cancel
            if (-not $line.Trim()) { continue }
            $msg = $line | ConvertFrom-Json
            if ($msg.PSObject.Properties['error'] -and $msg.error) { throw "O Ollama recusou o download: $($msg.error)" }
            $status = [string] $msg.status
            if ($msg.PSObject.Properties['digest'] -and $msg.PSObject.Properties['total'] -and $msg.total) {
                $completed = if ($msg.PSObject.Properties['completed']) { [double] $msg.completed } else { 0 }
                $layers[[string] $msg.digest] = @([double] $msg.total, $completed)
                $tot = 0.0; $got = 0.0
                foreach ($v in $layers.Values) { $tot += $v[0]; $got += $v[1] }
                if ($tot -gt 0 -and ((Get-Date) - $lastShown).TotalSeconds -ge 2) {
                    $lastShown = Get-Date
                    Set-StepProgress (0.97 * $got / $tot)
                    Write-StatusDetail ('Baixando {0}: {1:N0}% ({2} de {3})' -f $name, (100 * $got / $tot), (Format-Size $got), (Format-Size $tot))
                }
            } elseif ($status -ne $lastStatus) {
                $lastStatus = $status
                $friendly = switch -Regex ($status) {
                    '^pulling manifest' { 'Consultando o modelo...' }
                    '^verifying' { 'Conferindo a integridade do modelo...' }
                    '^writing manifest' { 'Registrando o modelo...' }
                    '^success' { 'Modelo pronto.' }
                    default { $status }
                }
                Write-StatusDetail $friendly
            }
        }
    } finally { $resp.Close() }
    if ($lastStatus -ne 'success') { throw "O download do modelo $name não terminou (último estado: $lastStatus)." }
}

$exitCode = 0
try {
    if ($DryRun) {
        Out-Line 'Nicx: preparação do ambiente (simulação; nada será alterado)' 'White'
    } else {
        Out-Line 'Nicx: preparação do ambiente' 'White'
        Write-Log "AppDir=$AppDir PackageDir=$PackageDir NicxHome=$NicxHome Voice=$wantVoice Model=$chosenModel"
    }
    Out-Line "  Pasta do aplicativo: $AppDir"
    Out-Line "  Dados do usuário:    $NicxHome"

    # 1. Sistema -------------------------------------------------------------
    Start-Step 'system'
    if ($os.Build -lt 17763) { throw "É necessário o Windows 10 versão 1809 ou mais recente (build atual: $($os.Build))." }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'O Nicx precisa do Windows de 64 bits.' }
    Write-StatusOk "$osName (build $($os.Build)), $arch"
    if ($arch -eq 'ARM64') { Write-StatusWarn 'Processador ARM: o Nicx roda em modo de emulação x64 e pode ficar mais lento.' }
    if ($ramGB -gt 0) {
        $ramText = '{0:N1} GB de RAM (livres agora: {1:N1} GB)' -f $ramGB, ($ramFree / $GB)
        if ($ramGB -lt 8) {
            Write-StatusWarn "$ramText. Recomendamos 8 GB ou mais; as respostas podem ficar lentas."
        } else { Write-StatusOk $ramText }
    } else { Write-StatusWarn 'Não foi possível medir a memória RAM.' }
    if ($configExists) { Write-StatusInfo "Modelo: $chosenModel ($modelReason)" }
    else { Write-StatusInfo "Modelo: $chosenModel ($modelReason); contexto: $numCtx tokens" }

    $needApp = 1.5 * $GB + $(if ($wantVoice) { 2.5 * $GB } else { 0 })
    $freeApp = Get-FreeBytes $AppDir
    $appRoot = [IO.Path]::GetPathRoot($AppDir)
    $modelsRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($OllamaModelsDir))
    $needOllamaDisk = $(if ($needOllamaInstall) { 4.5 * $GB } else { 0 })
    $needModels = $modelBytes + $needOllamaDisk
    if ($null -ne $freeApp) {
        $needSame = $needApp + $(if ($modelsRoot -eq $appRoot) { $needModels } else { 0 })
        $msg = 'Espaço livre em {0} {1} (necessário: cerca de {2})' -f $appRoot, (Format-Size $freeApp), (Format-Size $needSame)
        if ($freeApp -lt $needSame) {
            if ($DryRun) { Write-StatusWarn "$msg - insuficiente" } else { throw "Espaço em disco insuficiente em $appRoot. Livre: $(Format-Size $freeApp); necessário: cerca de $(Format-Size $needSame)." }
        } else { Write-StatusOk $msg }
        if ($modelsRoot -ne $appRoot -and $needModels -gt 0) {
            $freeModels = Get-FreeBytes $OllamaModelsDir
            if ($null -ne $freeModels -and $freeModels -lt $needModels) {
                if ($DryRun) { Write-StatusWarn "Pouco espaço em $modelsRoot para o modelo" } else { throw "Espaço em disco insuficiente em $modelsRoot para o modelo de IA." }
            }
        }
    }
    Complete-Step

    # 2. uv ------------------------------------------------------------------
    Start-Step 'uv'
    if ($uvExe) {
        $uvVer = (Invoke-Tool $uvExe @('--version') -Quiet).StdOut.Trim()
        Write-StatusOk "$uvVer ($uvSource)"
    } elseif ($DryRun) {
        Write-StatusTodo 'baixaria o uv (cerca de 20 MB) de github.com/astral-sh/uv'
    } else {
        Write-StatusInfo 'Baixando o uv...'
        $zip = Get-Download 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' (Join-Path $DownloadDir 'uv.zip') 'uv'
        $bin = Join-Path $AppDir 'bin'
        New-Item -ItemType Directory -Force -Path $bin | Out-Null
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $za = [IO.Compression.ZipFile]::OpenRead($zip)
        try {
            $entry = $za.Entries | Where-Object { $_.Name -eq 'uv.exe' } | Select-Object -First 1
            if (-not $entry) { throw 'uv.exe não encontrado no pacote baixado.' }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $bin 'uv.exe'), $true)
        } finally { $za.Dispose() }
        $uvExe = Join-Path $bin 'uv.exe'
        Write-StatusOk "uv instalado em $uvExe"
    }
    Complete-Step

    # 3. Python --------------------------------------------------------------
    Start-Step 'python'
    if ($venvOk) {
        Write-StatusOk "ambiente do Nicx já existe (Python $venvVersion)"
    } elseif ($managedPython.Count -gt 0) {
        Write-StatusOk "Python 3.12 já baixado em $PythonDir"
    } elseif ($DryRun) {
        Write-StatusTodo "baixaria o Python 3.12 (cerca de 30 MB) para $PythonDir"
    } else {
        $r = Invoke-Tool $uvExe @('python', 'install', $pythonRequest) $uvEnv
        if ($r.ExitCode -ne 0) { throw (Get-ToolError $r 'Não foi possível baixar o Python 3.12') }
        Write-StatusOk 'Python 3.12 instalado'
    }
    Complete-Step

    # 4. Pacotes -------------------------------------------------------------
    Start-Step 'packages'
    $extras = @('server', 'memory-bm25', 'pdf')
    if ($wantVoice) { $extras += @('speech', 'voice') }
    if (-not $nicxWheel -or -not $rustWheel) {
        if ($DryRun) { Write-StatusWarn "wheels do Nicx não encontrados em $wheelDir (gere-os com build-installer.ps1)" }
        else { throw "Pacotes do Nicx não encontrados em $wheelDir." }
    } else {
        Write-StatusInfo "Pacotes: $($nicxWheel.Name), $($rustWheel.Name)"
    }
    Write-StatusInfo "Extras: $($extras -join ', ')$(if (-not $wantVoice -and $installedKokoro) { ' (a voz já instalada é mantida)' })"
    if ($DryRun) {
        if ($venvOk) { Write-StatusOk "ambiente em $VenvDir (Python $venvVersion)" } else { Write-StatusTodo "criaria o ambiente Python em $VenvDir" }
        if ($installedNicx) { Write-StatusInfo "nicx instalado: $installedNicx; seria reinstalado com $nicxVersion" }
        $sizeHint = if ($wantVoice) { 'cerca de 1,5 GB; inclui o PyTorch' } else { 'cerca de 300 MB' }
        Write-StatusTodo "instalaria o Nicx $nicxVersion e as dependências do PyPI que faltarem ($sizeHint)"
    } else {
        Stop-AppServer
        if (-not $venvOk) {
            $r = Invoke-Tool $uvExe @('venv', '--clear', '--python', $pythonRequest, $VenvDir) $uvEnv
            if ($r.ExitCode -ne 0) { throw (Get-ToolError $r 'Não foi possível criar o ambiente Python') }
        }
        Set-StepProgress 0.05
        $nicxUrl = ([Uri] $nicxWheel.FullName).AbsoluteUri
        $rustUrl = ([Uri] $rustWheel.FullName).AbsoluteUri
        # --no-build: nada é compilado neste computador. Dependências que o
        # PyPI só oferece como código-fonte vão pré-geradas em wheels\.
        $pipArgs = @('pip', 'install', '--python', $VenvPython, '--compile-bytecode', '--no-build',
            '--find-links', $wheelDir, '--reinstall-package', 'nicx', '--reinstall-package', 'nicx-rust')
        if (Test-Path -LiteralPath $constraints) { $pipArgs += @('--constraints', $constraints) }
        $pipArgs += @("nicx[$($extras -join ',')] @ $nicxUrl", "nicx-rust @ $rustUrl")
        Write-StatusInfo 'Baixando e instalando as dependências (pode levar alguns minutos)...'
        $r = Invoke-Tool $uvExe $pipArgs $uvEnv
        if ($r.ExitCode -ne 0) { throw (Get-ToolError $r 'A instalação dos componentes do Nicx falhou. Verifique a conexão com a internet e tente de novo') }
        Set-StepProgress 0.95
        $check = Invoke-Tool $VenvPython @('-X', 'utf8', '-c', 'import nicx, nicx_rust, fastapi, uvicorn; print(nicx.__version__)') -Quiet
        if ($check.ExitCode -ne 0) { throw 'Os pacotes foram instalados, mas o Nicx não pôde ser carregado. Veja o registro.' }
        Write-StatusOk "Nicx $($check.StdOut.Trim()) instalado"
    }
    Complete-Step

    # 5. Configuração --------------------------------------------------------
    Start-Step 'config'
    if ($configExists) {
        Write-StatusOk "configuração existente mantida: $ConfigPath"
        if ($configEngine -and $configEngine -ne 'ollama') { Write-StatusInfo "Motor configurado: $configEngine (o Ollama não será verificado)" }
    } elseif ($DryRun) {
        Write-StatusTodo "criaria $ConfigPath (Ollama + $chosenModel, contexto $numCtx, voz pt-BR, estatísticas de uso desligadas)"
    } else {
        New-Item -ItemType Directory -Force -Path $NicxHome | Out-Null
        $cpu = $env:PROCESSOR_IDENTIFIER
        try { $cpu = (Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1).Name.Trim() } catch { }
        $toml = @"
# Configuração do Nicx (criada pelo instalador em $(Get-Date -Format 'yyyy-MM-dd'))
# Computador: $cpu, $('{0:N1}' -f $ramGB) GB de RAM
# Referência completa: nicx init --full

[engine]
default = "ollama"

[engine.ollama]
# host = "http://localhost:11434"
# Janela de contexto (tokens). Menor = menos memória. Se o Ollama acusar falta
# de memória, use 4096.
num_ctx = $numCtx

[intelligence]
default_model = "$chosenModel"

[agent]
default_agent = "simple"

[tools]
enabled = ["code_interpreter", "web_search", "file_read", "shell_exec"]

[security]
profile = "personal"

[analytics]
# Desligado até você decidir no aplicativo (Configurações > Privacidade).
enabled = false

[speech]
# Voz em português do Brasil, tudo local (faster-whisper + Kokoro).
backend = "faster-whisper"
model = "base"
language = "pt"
device = "cpu"
compute_type = "int8"
vad_filter = true
hotwords = "Nicx Falkyria"
tts_backend = "kokoro"
voice_id = "pf_dora"
voice_speed = 1.0
"@
        [IO.File]::WriteAllText($ConfigPath, ($toml -replace "`r?`n", "`r`n"), $Utf8NoBom)
        Write-StatusOk "configuração criada: $ConfigPath"
    }
    if (-not $DryRun) {
        $seed = Invoke-Tool $VenvPython @('-X', 'utf8', '-c', 'from nicx.comandos._bootstrap import _seed_memory_files; _seed_memory_files()') @{ PYTHONUTF8 = '1' } -Quiet
        if ($seed.ExitCode -eq 0) { Write-StatusOk 'personalidade e memória do Nicx prontas (SOUL.md, MEMORY.md, USER.md)' }
        else { Write-StatusWarn 'não foi possível criar SOUL.md/MEMORY.md/USER.md; o Nicx usa a persona padrão.' }
    }
    Complete-Step

    # 6. Ollama --------------------------------------------------------------
    if ($useOllama) {
        Start-Step 'ollama'
        if ($ollamaRunning) {
            Write-StatusOk "Ollama $ollamaVersion em execução ($OllamaBase)"
        } elseif ($ollamaExe) {
            if ($DryRun) {
                Write-StatusOk "Ollama $ollamaVersion instalado em $ollamaExe"
                Write-StatusTodo 'iniciaria o Ollama'
            } else {
                Write-StatusInfo 'Iniciando o Ollama...'
                Start-Ollama $ollamaExe
                $v = Wait-Ollama 60
                if (-not $v) { throw 'O Ollama está instalado, mas não respondeu. Abra o Ollama pelo menu Iniciar e execute o instalador de novo.' }
                Write-StatusOk "Ollama $v em execução"
            }
        } elseif ($SkipOllama) {
            Write-StatusWarn 'Ollama não encontrado (instalação pulada por -SkipOllama)'
        } elseif ($DryRun) {
            Write-StatusTodo 'baixaria e instalaria o Ollama (instalador oficial, cerca de 1,6 GB; só para este usuário, sem pedir administrador)'
        } else {
            Write-StatusInfo 'Baixando o Ollama (instalador oficial, cerca de 1,6 GB)...'
            $setup = Get-Download 'https://ollama.com/download/OllamaSetup.exe' (Join-Path $DownloadDir 'OllamaSetup.exe') 'Ollama'
            $sig = Get-AuthenticodeSignature -LiteralPath $setup
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Ollama Inc\.') {
                Remove-Item -LiteralPath $setup -Force -ErrorAction SilentlyContinue
                throw "O instalador do Ollama baixado não tem uma assinatura digital válida ($($sig.Status)). Por segurança, ele não foi executado."
            }
            Set-StepProgress 0.88
            Write-StatusInfo 'Instalando o Ollama...'
            $p = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-' -PassThru -Wait
            if ($p.ExitCode -ne 0) { throw "O instalador do Ollama terminou com código $($p.ExitCode)." }
            Remove-Item -LiteralPath $setup -Force -ErrorAction SilentlyContinue
            $ollamaExe = Find-Ollama
            if (-not $ollamaExe) { throw 'O Ollama foi instalado, mas o programa não foi encontrado.' }
            $v = Get-OllamaVersion $OllamaBase
            if (-not $v) { Start-Ollama $ollamaExe; $v = Wait-Ollama 90 }
            if (-not $v) { throw 'O Ollama foi instalado, mas não respondeu. Reinicie o computador e execute o instalador de novo.' }
            Write-StatusOk "Ollama $v instalado e em execução"
        }
        Complete-Step

        # 7. Modelo ----------------------------------------------------------
        Start-Step 'model'
        if ($SkipModel) {
            Write-StatusWarn 'download do modelo pulado (-SkipModel)'
        } elseif ($modelPresent -eq $true) {
            Write-StatusOk "$chosenModel já está baixado"
        } elseif ($DryRun) {
            Write-StatusTodo "baixaria o modelo $chosenModel ($(Format-Size $modelBytes)) com o Ollama"
        } else {
            $names = Get-OllamaModels $OllamaBase
            if ($names -and (Test-ModelPresent $names $chosenModel)) {
                Write-StatusOk "$chosenModel já está baixado"
            } else {
                Write-StatusInfo "Baixando o modelo $chosenModel ($(Format-Size $modelBytes)). Esta é a etapa mais demorada."
                Invoke-ModelPull $chosenModel
                Write-StatusOk "$chosenModel pronto"
            }
        }
        Complete-Step
    }

    # 8. Voz -----------------------------------------------------------------
    if ($wantVoice) {
        Start-Step 'voice'
        if (Test-VoiceModelsCached) {
            Write-StatusOk 'modelos de voz já baixados (Whisper base e Kokoro pt-BR)'
        } elseif ($DryRun) {
            Write-StatusTodo 'baixaria os modelos de voz (Whisper base e Kokoro, cerca de 500 MB) para o cache do Hugging Face'
        } else {
            Write-StatusInfo 'Baixando os modelos de voz (reconhecimento e fala, cerca de 500 MB)...'
            $py = @'
import sys
from faster_whisper.utils import download_model
print('Reconhecimento de fala (Whisper base)...', file=sys.stderr, flush=True)
download_model('base')
from huggingface_hub import hf_hub_download
for name in ('config.json', 'kokoro-v1_0.pth', 'voices/pf_dora.pt', 'voices/pm_alex.pt', 'voices/pm_santa.pt'):
    print('Voz (Kokoro): ' + name, file=sys.stderr, flush=True)
    hf_hub_download('hexgrad/Kokoro-82M', name)
'@
            $r = Invoke-Tool $VenvPython @('-X', 'utf8', '-c', $py) @{ HF_HUB_DISABLE_PROGRESS_BARS = '1'; PYTHONUNBUFFERED = '1' }
            if ($r.ExitCode -eq 0) { Write-StatusOk 'modelos de voz prontos' }
            else { Write-StatusWarn 'não foi possível baixar os modelos de voz agora; eles serão baixados no primeiro uso.' }
        }
        Complete-Step
    }

    # 9. Finalização ---------------------------------------------------------
    Start-Step 'finish'
    if ($DryRun) {
        if (Test-Path -LiteralPath $CacheDir) { Write-StatusTodo "apagaria o cache temporário $CacheDir" }
        Out-Line ''
        Out-Line 'Simulação concluída. Nada foi alterado.' 'Green'
    } else {
        if (-not $KeepCache -and (Test-Path -LiteralPath $CacheDir)) {
            Write-StatusInfo 'Limpando arquivos temporários...'
            $null = Invoke-Tool $uvExe @('cache', 'clean') $uvEnv -Quiet
            Remove-Item -LiteralPath $CacheDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $DownloadDir) { Remove-Item -LiteralPath $DownloadDir -Recurse -Force -ErrorAction SilentlyContinue }
        Complete-Step
        Out-Line ''
        Out-Line 'O Nicx está pronto.' 'Green'
        Out-Line "Registro desta preparação: $script:LogPath"
    }
} catch [System.OperationCanceledException] {
    Out-Line ''
    Out-Line 'Preparação cancelada. Execute o instalador de novo para continuar de onde parou.' 'Yellow'
    $exitCode = 2
} catch {
    $msg = $_.Exception.Message
    Write-Log ($_ | Out-String)
    Out-Line ''
    Out-Line "ERRO: $msg" 'Red'
    if ($script:LogPath) { Out-Line "Registro completo: $script:LogPath" }
    Out-Marker 'error' $msg
    $exitCode = 1
}
exit $exitCode
