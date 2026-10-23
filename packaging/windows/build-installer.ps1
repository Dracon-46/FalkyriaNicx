#requires -Version 5.1
<#
.SYNOPSIS
    Gera o instalador NicxSetup.exe (Windows 10/11 x64).

.DESCRIPTION
    Etapas:
      1. Interface: `npm run build` em frontend/ (grava src/nicx/server/static).
      2. Pacote Python `nicx` (wheel), conferindo que a interface e os textos
         legais (src/nicx/legal/*.md) foram incluídos.
      3. Extensão nativa `nicx-rust` (wheel cp312 win_amd64) com o maturin.
      4. Versões fixadas das dependências (constraints.txt), exportadas do uv.lock.
      5. Cópia do uv.exe, ícone, imagens do assistente e texto dos termos de uso.
      6. Compilação do instalador com o Inno Setup 6 (ISCC.exe).

    Tudo o que é gerado fica em packaging/windows/build (intermediários) e
    packaging/windows/dist (wheels, constraints.txt e NicxSetup.exe), ambos
    ignorados pelo git. Nada é publicado.

.PARAMETER Version
    Versão gravada no pacote e no instalador. Padrão: a tag vX.Y.Z do commit
    atual, se houver; senão 0.1.0.

.PARAMETER SkipFrontend
    Não recompila a interface; usa o que já estiver em src/nicx/server/static.

.PARAMETER SkipRust
    Não recompila a extensão; reaproveita o wheel nicx_rust mais recente de
    dist/wheels ou rust/target/wheels.

.PARAMETER UvExe
    uv.exe a embutir no instalador. Padrão: o uv encontrado no PATH.

.PARAMETER Iscc
    Caminho do ISCC.exe. Padrão: procura o Inno Setup 6 instalado e, se não
    houver, instala com o winget (somente para o usuário atual).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
#>
[CmdletBinding()]
param(
    [string] $Version,
    [switch] $SkipFrontend,
    [switch] $SkipRust,
    [string] $UvExe,
    [string] $Iscc
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false

$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here '..\..')).Path
$BuildDir = Join-Path $Here 'build'
$DistDir = Join-Path $Here 'dist'
$WheelDir = Join-Path $DistDir 'wheels'
$BrandDir = Join-Path $BuildDir 'brand'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
$Utf8Bom = New-Object System.Text.UTF8Encoding $true

function Write-Step($msg) { Write-Host ''; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    ok  $msg" -ForegroundColor Green }
function Write-Note($msg) { Write-Host "    $msg" }
function Stop-Build($msg) { Write-Host "    ERRO  $msg" -ForegroundColor Red; throw $msg }

# Runs a native program, streaming its output, and fails on a non-zero exit.
# PowerShell 5.1 turns native stderr into terminating errors under
# ErrorActionPreference=Stop, so relax it just for the call.
function Invoke-Native {
    param([string] $FilePath, [string[]] $Arguments, [string] $WorkingDirectory = $Repo)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
        $ErrorActionPreference = $prev
    }
    if ($code -ne 0) { Stop-Build "$FilePath $($Arguments -join ' ') terminou com código $code" }
}

function Get-Sha256($path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }

# ---------------------------------------------------------------------------
# Ferramentas
# ---------------------------------------------------------------------------

Write-Step 'Conferindo as ferramentas'

$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if ((Test-Path $cargoBin) -and ($env:Path -notlike "*$cargoBin*")) { $env:Path = "$cargoBin;$env:Path" }

$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) { Stop-Build 'uv não encontrado no PATH (https://docs.astral.sh/uv/).' }
$uv = $uvCmd.Source
Write-Ok "uv: $uv ($(& $uv --version))"

if (-not $UvExe) { $UvExe = $uv }
if (-not (Test-Path -LiteralPath $UvExe)) { Stop-Build "uv.exe para embutir não encontrado: $UvExe" }

if (-not $SkipFrontend) {
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
    if (-not $npm) { Stop-Build 'npm não encontrado (Node.js 22+). Use -SkipFrontend para reaproveitar a interface já compilada.' }
    Write-Ok "npm: $($npm.Source)"
}
if (-not $SkipRust -and -not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Stop-Build 'cargo (Rust) não encontrado. Instale o Rust ou use -SkipRust.'
}

function Find-Iscc {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    foreach ($root in 'HKCU:', 'HKLM:') {
        foreach ($view in 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', 'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall') {
            $key = "$root\$view\Inno Setup 6_is1"
            $props = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
            if ($props -and $props.PSObject.Properties['InstallLocation'] -and $props.InstallLocation) {
                $candidates += (Join-Path $props.InstallLocation 'ISCC.exe')
            }
        }
    }
    foreach ($c in $candidates) { if ($c -and (Test-Path -LiteralPath $c)) { return $c } }
    return $null
}

if (-not $Iscc) { $Iscc = Find-Iscc }
if (-not $Iscc) {
    Write-Note 'Inno Setup 6 não encontrado; instalando com o winget (somente para este usuário)...'
    Invoke-Native 'winget' @('install', '-e', '--id', 'JRSoftware.InnoSetup', '--scope', 'user', '--silent',
        '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity')
    $Iscc = Find-Iscc
    if (-not $Iscc) { Stop-Build 'Inno Setup 6 não foi encontrado depois da instalação.' }
}
Write-Ok "Inno Setup: $Iscc"

# ---------------------------------------------------------------------------
# Versão
# ---------------------------------------------------------------------------

if (-not $Version) {
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $tag = & git -C $Repo describe --tags --exact-match --match 'v[0-9]*' 2>$null
    $ErrorActionPreference = $prev
    if ($LASTEXITCODE -eq 0 -and $tag -match '^v(\d+\.\d+\.\d+)$') { $Version = $Matches[1] } else { $Version = '0.1.0' }
}
if ($Version -notmatch '^(\d+)\.(\d+)\.(\d+)') { Stop-Build "Versão inválida: $Version (use X.Y.Z)" }
$FileVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
Write-Ok "versão $Version"

New-Item -ItemType Directory -Force -Path $BuildDir, $DistDir, $WheelDir, $BrandDir | Out-Null

# ---------------------------------------------------------------------------
# 1. Interface
# ---------------------------------------------------------------------------

$staticIndex = Join-Path $Repo 'src\nicx\server\static\index.html'
if ($SkipFrontend) {
    Write-Step 'Interface: reaproveitando src/nicx/server/static (-SkipFrontend)'
} else {
    Write-Step 'Interface: npm run build'
    Invoke-Native 'npm.cmd' @('run', 'build') (Join-Path $Repo 'frontend')
}
if (-not (Test-Path -LiteralPath $staticIndex)) { Stop-Build "Interface ausente: $staticIndex" }
Write-Ok "interface em src\nicx\server\static ($((Get-Item $staticIndex).LastWriteTime))"

# ---------------------------------------------------------------------------
# 2. Wheel do nicx
# ---------------------------------------------------------------------------

Write-Step "Pacote Python nicx $Version"
Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx-*.whl' -ErrorAction SilentlyContinue | Remove-Item -Force
$env:SETUPTOOLS_SCM_PRETEND_VERSION = $Version
try {
    Invoke-Native $uv @('build', '--wheel', '--out-dir', $WheelDir, $Repo)
} finally {
    Remove-Item Env:\SETUPTOOLS_SCM_PRETEND_VERSION -ErrorAction SilentlyContinue
}
$nicxWheel = Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx-*.whl' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $nicxWheel) { Stop-Build 'o wheel do nicx não foi gerado' }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($nicxWheel.FullName)
try {
    $names = @($zip.Entries | ForEach-Object { $_.FullName })
} finally { $zip.Dispose() }
$required = @(
    'nicx/server/static/index.html',
    'nicx/legal/termos-de-uso.md',
    'nicx/legal/politica-de-privacidade.md',
    'nicx/legal/consentimento.md'
)
foreach ($r in $required) {
    if ($names -notcontains $r) { Stop-Build "o wheel não contém $r" }
}
$staticCount = @($names | Where-Object { $_ -like 'nicx/server/static/*' }).Count
Write-Ok "$($nicxWheel.Name) ($([math]::Round($nicxWheel.Length / 1MB, 1)) MB; $staticCount arquivos da interface; textos legais incluídos)"

# ---------------------------------------------------------------------------
# 3. Wheel do nicx-rust
# ---------------------------------------------------------------------------

$venvPython = Join-Path $Repo '.venv\Scripts\python.exe'
if ($SkipRust) {
    Write-Step 'Extensão nicx-rust: reaproveitando wheel existente (-SkipRust)'
    $existing = @(Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx_rust-*-cp312-*win_amd64.whl' -ErrorAction SilentlyContinue) +
                @(Get-ChildItem -LiteralPath (Join-Path $Repo 'rust\target\wheels') -Filter 'nicx_rust-*-cp312-*win_amd64.whl' -ErrorAction SilentlyContinue)
    $rustWheel = $existing | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $rustWheel) { Stop-Build 'nenhum wheel nicx_rust cp312 win_amd64 encontrado' }
    if ($rustWheel.DirectoryName -ne $WheelDir) {
        Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx_rust-*.whl' | Remove-Item -Force
        Copy-Item -LiteralPath $rustWheel.FullName -Destination $WheelDir
        $rustWheel = Get-Item (Join-Path $WheelDir $rustWheel.Name)
    }
} else {
    Write-Step 'Extensão nicx-rust (maturin, release; pode levar alguns minutos)'
    if (-not (Test-Path -LiteralPath $venvPython)) { Stop-Build "Python do projeto não encontrado: $venvPython" }
    Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx_rust-*.whl' -ErrorAction SilentlyContinue | Remove-Item -Force
    Invoke-Native $uv @('run', '--no-sync', 'maturin', 'build', '--release',
        '--manifest-path', (Join-Path $Repo 'rust\crates\nicx-python\Cargo.toml'),
        '--interpreter', $venvPython, '--out', $WheelDir)
    $rustWheel = Get-ChildItem -LiteralPath $WheelDir -Filter 'nicx_rust-*-cp312-*win_amd64.whl' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $rustWheel) { Stop-Build 'o wheel cp312 win_amd64 do nicx-rust não foi gerado' }
}
Write-Ok "$($rustWheel.Name) ($([math]::Round($rustWheel.Length / 1MB, 1)) MB)"

# ---------------------------------------------------------------------------
# 4. Versões fixadas (constraints)
# ---------------------------------------------------------------------------

Write-Step 'Versões das dependências (uv.lock -> constraints.txt)'
$constraints = Join-Path $DistDir 'constraints.txt'
Invoke-Native $uv @('export', '--quiet', '--frozen', '--format', 'requirements.txt', '--no-hashes', '--no-header',
    '--no-annotate', '--no-default-groups', '--no-emit-project', '--no-emit-local',
    '--extra', 'server', '--extra', 'memory-bm25', '--extra', 'pdf', '--extra', 'speech', '--extra', 'voice',
    '--output-file', $constraints)
$pins = @(Get-Content -LiteralPath $constraints | Where-Object { $_ -match '^[A-Za-z0-9]' }).Count
Write-Ok "$pins versões fixadas em dist\constraints.txt"

# Dependências publicadas só como código-fonte (sdist) seriam compiladas na
# máquina do usuário, o que é lento e falha com caminhos longos. Gera os wheels
# aqui; o setup-runtime.ps1 instala com --find-links e --no-build.
Write-Step 'Dependências sem wheel no PyPI'
Get-ChildItem -LiteralPath $WheelDir -Filter '*.whl' |
    Where-Object { $_.Name -notlike 'nicx-*' -and $_.Name -notlike 'nicx_rust-*' } |
    Remove-Item -Force
$finder = Join-Path $BuildDir 'sdist_only.py'
[IO.File]::WriteAllText($finder, @'
import re, sys, tomllib
lock = tomllib.load(open(sys.argv[1], "rb"))
pins = {}
for line in open(sys.argv[2], encoding="utf-8"):
    m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line.strip())
    if m:
        pins[m.group(1).lower().replace("_", "-")] = m.group(2)
for pkg in lock["package"]:
    sdist = pkg.get("sdist") or {}
    version = pkg.get("version")
    if version and pins.get(pkg["name"].lower()) == version and not pkg.get("wheels") and sdist.get("url"):
        print(pkg["name"], pkg["version"], sdist["url"], sdist.get("hash", ""))
'@, $Utf8NoBom)
$sdistOnly = @(& $venvPython -I $finder (Join-Path $Repo 'uv.lock') $constraints)
if ($LASTEXITCODE -ne 0) { Stop-Build 'não foi possível ler o uv.lock' }
$sdistDir = Join-Path $BuildDir 'sdist'
foreach ($entry in $sdistOnly) {
    if (-not $entry.Trim()) { continue }
    $name, $ver, $url, $hash = $entry -split ' '
    New-Item -ItemType Directory -Force -Path $sdistDir | Out-Null
    $file = Join-Path $sdistDir ([IO.Path]::GetFileName(([Uri] $url).AbsolutePath))
    if (-not (Test-Path -LiteralPath $file)) { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $file }
    if ($hash -match '^sha256:(.+)$' -and (Get-Sha256 $file) -ne $Matches[1].ToLowerInvariant()) {
        Remove-Item -LiteralPath $file -Force
        Stop-Build "hash inválido para $name $ver"
    }
    Invoke-Native $uv @('build', '--wheel', '--python', $venvPython, '--out-dir', $WheelDir, $file) $BuildDir
    Write-Ok "$name $ver (wheel gerado a partir do código-fonte)"
}
if ($sdistOnly.Count -eq 0) { Write-Ok 'todas as dependências têm wheel' }

# ---------------------------------------------------------------------------
# 5. uv.exe, ícone, imagens e termos
# ---------------------------------------------------------------------------

Write-Step 'Arquivos de apoio'
$uvDir = Join-Path $BuildDir 'uv'
New-Item -ItemType Directory -Force -Path $uvDir | Out-Null
Copy-Item -LiteralPath $UvExe -Destination (Join-Path $uvDir 'uv.exe') -Force
Write-Ok "uv.exe embutido ($(& (Join-Path $uvDir 'uv.exe') --version))"

$icon = Join-Path $Repo 'frontend\src-tauri\icons\icon.ico'
if (-not (Test-Path -LiteralPath $icon)) { Stop-Build "ícone não encontrado: $icon" }
Copy-Item -LiteralPath $icon -Destination (Join-Path $BrandDir 'nicx.ico') -Force

Add-Type -AssemblyName System.Drawing
$mascotPath = Join-Path $Repo 'assets\nicx-mascot.png'
$markPath = Join-Path $Repo 'frontend\src-tauri\icons\icon.png'
foreach ($p in $mascotPath, $markPath) { if (-not (Test-Path -LiteralPath $p)) { Stop-Build "imagem não encontrada: $p" } }

function New-Canvas([int] $w, [int] $h) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    return @($bmp, $g)
}

function Save-Png($bmp, $g, $path) {
    $g.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

$mascot = [System.Drawing.Image]::FromFile($mascotPath)
$mark = [System.Drawing.Image]::FromFile($markPath)
try {
    $bg = [System.Drawing.ColorTranslator]::FromHtml('#121211')
    $fg = [System.Drawing.ColorTranslator]::FromHtml('#fcfcfb')
    $muted = [System.Drawing.ColorTranslator]::FromHtml('#a8a7a2')
    $amber = [System.Drawing.ColorTranslator]::FromHtml('#eda100')

    # Imagem lateral das páginas de boas-vindas/conclusão (vários DPIs).
    $wizardImages = @()
    foreach ($size in @(@(164, 314), @(246, 471), @(328, 628))) {
        $w = $size[0]; $h = $size[1]
        $c = New-Canvas $w $h; $bmp = $c[0]; $g = $c[1]
        $g.Clear($bg)
        $glow = New-Object System.Drawing.Drawing2D.GraphicsPath
        $gs = [int]($w * 1.1)
        $glow.AddEllipse([int](($w - $gs) / 2), [int]($h * 0.16), $gs, $gs)
        $pgb = New-Object System.Drawing.Drawing2D.PathGradientBrush $glow
        $pgb.CenterColor = [System.Drawing.Color]::FromArgb(70, 134, 182, 239)
        $pgb.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 18, 18, 17))
        $g.FillPath($pgb, $glow)
        $pgb.Dispose(); $glow.Dispose()
        $ms = [int]($w * 0.74)
        $g.DrawImage($mascot, [int](($w - $ms) / 2), [int]($h * 0.25), $ms, $ms)
        $title = New-Object System.Drawing.Font('Segoe UI', [single]($w * 0.19), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        $sub = New-Object System.Drawing.Font('Segoe UI', [single]($w * 0.072), [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
        $fmt = New-Object System.Drawing.StringFormat
        $fmt.Alignment = [System.Drawing.StringAlignment]::Center
        $ty = [single]($h * 0.25 + $ms + $h * 0.02)
        $g.DrawString('Nicx', $title, (New-Object System.Drawing.SolidBrush $fg), [single]($w / 2), $ty, $fmt)
        $tw = $g.MeasureString('Nicx', $title).Width
        $dot = [single]($w * 0.05)
        $g.FillEllipse((New-Object System.Drawing.SolidBrush $amber), [single]($w / 2 + $tw / 2 - $dot * 0.6), [single]($ty + $title.Size * 0.28), $dot, $dot)
        $g.DrawString('a IA da Falkyria', $sub, (New-Object System.Drawing.SolidBrush $muted), [single]($w / 2), [single]($ty + $title.Size * 1.35), $fmt)
        $title.Dispose(); $sub.Dispose()
        $out = Join-Path $BrandDir "wizard-$w.png"
        Save-Png $bmp $g $out
        $wizardImages += $out
    }

    # Marca pequena do cabeçalho (55/83/110 px).
    foreach ($s in 55, 83, 110) {
        $c = New-Canvas $s $s; $bmp = $c[0]; $g = $c[1]
        $g.Clear([System.Drawing.Color]::Transparent)
        $g.DrawImage($mark, 0, 0, $s, $s)
        Save-Png $bmp $g (Join-Path $BrandDir "small-$s.png")
    }

    # Mascote da janela "Iniciando o Nicx" do lançador.
    foreach ($s in 96, 144, 192) {
        $c = New-Canvas $s $s; $bmp = $c[0]; $g = $c[1]
        $g.Clear([System.Drawing.Color]::Transparent)
        $g.DrawImage($mascot, 0, 0, $s, $s)
        Save-Png $bmp $g (Join-Path $BrandDir "splash-$s.png")
    }
} finally {
    $mascot.Dispose(); $mark.Dispose()
}
Write-Ok 'ícone, imagens do assistente e do lançador'

# Termos de uso como texto simples (página de licença do assistente).
$termsMd = Join-Path $Repo 'src\nicx\legal\termos-de-uso.md'
$termsTxt = Join-Path $BuildDir 'termos-de-uso.txt'
$md = [IO.File]::ReadAllText($termsMd, [Text.Encoding]::UTF8)
$md = [regex]::Replace($md, '\*\*(.+?)\*\*', '$1', [Text.RegularExpressions.RegexOptions]::Singleline)
$md = [regex]::Replace($md, '(?<![\w*])\*([^*\r\n]+)\*(?![\w*])', '$1')
$md = $md -replace '`([^`]+)`', '$1' -replace '\[([^\]]+)\]\(([^)]+)\)', '$1 ($2)'
$lines = foreach ($t in ($md -split "\r?\n")) {
    if ($t -match '^#\s+(.*)$') { $Matches[1].ToUpperInvariant() }
    elseif ($t -match '^#{2,}\s+(.*)$') { $Matches[1] }
    else { $t }
}
[IO.File]::WriteAllText($termsTxt, (($lines -join "`r`n") + "`r`n"), $Utf8Bom)
Write-Ok 'termos de uso convertidos para a página de licença'

# ---------------------------------------------------------------------------
# 6. Inno Setup
# ---------------------------------------------------------------------------

Write-Step 'Compilando o instalador (Inno Setup)'
$setupExe = Join-Path $DistDir 'NicxSetup.exe'
if (Test-Path -LiteralPath $setupExe) { Remove-Item -LiteralPath $setupExe -Force }
Invoke-Native $Iscc @('/Qp',
    "/DAppVersion=$Version",
    "/DFileVersion=$FileVersion",
    "/DNicxWheel=$($nicxWheel.Name)",
    "/DRustWheel=$($rustWheel.Name)",
    "/O$DistDir",
    (Join-Path $Here 'nicx.iss')) $Here
if (-not (Test-Path -LiteralPath $setupExe)) { Stop-Build 'NicxSetup.exe não foi gerado' }

$exe = Get-Item -LiteralPath $setupExe
$hash = Get-Sha256 $exe.FullName
[IO.File]::WriteAllText((Join-Path $DistDir 'NicxSetup.exe.sha256'), "$hash  NicxSetup.exe`n", $Utf8NoBom)

Write-Host ''
Write-Host "Pronto: $($exe.FullName)" -ForegroundColor Green
Write-Host ("  tamanho: {0:N1} MB ({1:N0} bytes)" -f ($exe.Length / 1MB), $exe.Length)
Write-Host "  SHA-256: $hash"
Write-Host "  versão:  $Version"
