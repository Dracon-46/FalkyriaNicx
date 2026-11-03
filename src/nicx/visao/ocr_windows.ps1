# Lê texto de uma janela, da imagem copiada ou de um arquivo de imagem com o OCR do Windows.
# Só lê: a imagem fica na memória e nunca é gravada em disco. Saída: JSON em UTF-8.
#   -Modo janela -Hwnd 1234       (PrintWindow: funciona mesmo com outra janela na frente)
#   -Modo area                    (imagem da área de transferência)
#   -Modo arquivo -Arquivo C:\x.png
param(
    [ValidateSet('janela', 'area', 'arquivo')][string]$Modo = 'janela',
    [long]$Hwnd = 0,
    [string]$Arquivo = '',
    [string]$Idioma = 'pt-BR'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Sair($obj) { [Console]::Out.Write(($obj | ConvertTo-Json -Compress -Depth 4)); exit 0 }

try {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    Add-Type @"
using System; using System.Runtime.InteropServices;
public static class NicxJanela {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
}
"@
    [NicxJanela]::SetProcessDPIAware() | Out-Null

    $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    function Esperar($operacao, [Type]$tipo) {
        $tarefa = $asTask.MakeGenericMethod($tipo).Invoke($null, @($operacao))
        $tarefa.Wait(-1) | Out-Null
        return $tarefa.Result
    }

    $imagem = $null
    if ($Modo -eq 'janela') {
        $h = [IntPtr]$Hwnd
        if ([NicxJanela]::IsIconic($h)) { Sair @{ ok = $false; motivo = 'minimizada' } }
        $r = New-Object NicxJanela+RECT
        if (-not [NicxJanela]::GetWindowRect($h, [ref]$r)) { Sair @{ ok = $false; motivo = 'sem_janela' } }
        $w = $r.Right - $r.Left; $a = $r.Bottom - $r.Top
        if ($w -lt 10 -or $a -lt 10) { Sair @{ ok = $false; motivo = 'sem_janela' } }
        $imagem = New-Object System.Drawing.Bitmap $w, $a
        $g = [System.Drawing.Graphics]::FromImage($imagem)
        $hdc = $g.GetHdc()
        [NicxJanela]::PrintWindow($h, $hdc, 2) | Out-Null   # 2 = PW_RENDERFULLCONTENT
        $g.ReleaseHdc($hdc); $g.Dispose()
    } elseif ($Modo -eq 'area') {
        if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) { Sair @{ ok = $false; motivo = 'sem_imagem' } }
        $imagem = [System.Windows.Forms.Clipboard]::GetImage()
    } else {
        if (-not (Test-Path -LiteralPath $Arquivo)) { Sair @{ ok = $false; motivo = 'sem_arquivo' } }
        $imagem = [System.Drawing.Bitmap]::FromFile($Arquivo)
    }

    # o OCR aceita no máximo MaxImageDimension por lado
    $limite = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
    if ($imagem.Width -gt $limite -or $imagem.Height -gt $limite) {
        $escala = [Math]::Min($limite / $imagem.Width, $limite / $imagem.Height)
        $menor = New-Object System.Drawing.Bitmap $imagem, ([int]($imagem.Width * $escala)), ([int]($imagem.Height * $escala))
        $imagem.Dispose(); $imagem = $menor
    }
    $memoria = New-Object System.IO.MemoryStream
    $imagem.Save($memoria, [System.Drawing.Imaging.ImageFormat]::Png)
    $imagem.Dispose()
    $memoria.Position = 0
    $fluxo = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($memoria)
    $decoder = Esperar ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($fluxo)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Esperar ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $motor = $null
    try { $motor = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language $Idioma)) } catch { $motor = $null }
    if ($null -eq $motor) { $motor = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
    if ($null -eq $motor) { Sair @{ ok = $false; motivo = 'sem_idioma' } }
    $resultado = Esperar ($motor.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $linhas = @($resultado.Lines | ForEach-Object { $_.Text })
    Sair @{ ok = $true; texto = ($linhas -join "`n"); linhas = $linhas.Count; idioma = $motor.RecognizerLanguage.LanguageTag }
} catch {
    Sair @{ ok = $false; motivo = 'erro'; detalhe = $_.Exception.Message }
}
