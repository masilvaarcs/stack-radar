<#
.SYNOPSIS
    Gera o PDF do Showcase a partir do SHOWCASE.html.

.DESCRIPTION
    Utiliza Microsoft Edge ou Google Chrome (headless) para converter
    o Showcase HTML em PDF landscape com gráficos de fundo preservados.

.EXAMPLE
    .\Gerar_Showcase_PDF.ps1
    .\Gerar_Showcase_PDF.ps1 -AbrirAoFinalizar
#>

param(
    [switch]$AbrirAoFinalizar
)

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ════════════════════════════════════════════════════════════

$NomeArquivoPDF = "Stack Radar_Marcos Silva.pdf"
$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Definition
$HtmlSource     = Join-Path $ScriptDir "SHOWCASE.html"
$PdfOutput      = Join-Path $ScriptDir $NomeArquivoPDF

# ════════════════════════════════════════════════════════════
# DETECTAR BROWSER (Edge ou Chrome)
# ════════════════════════════════════════════════════════════

$BrowserPath = $null
$BrowserName = ""

$candidates = @(
    @{ Path = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"; Name = "Microsoft Edge" },
    @{ Path = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"; Name = "Microsoft Edge" },
    @{ Path = "C:\Program Files\Google\Chrome\Application\chrome.exe"; Name = "Google Chrome" },
    @{ Path = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"; Name = "Google Chrome" }
)

foreach ($c in $candidates) {
    if (Test-Path $c.Path) {
        $BrowserPath = $c.Path
        $BrowserName = $c.Name
        break
    }
}

if (-not $BrowserPath) {
    Write-Host "[ERRO] Nenhum browser compativel encontrado (Edge ou Chrome)." -ForegroundColor Red
    exit 1
}

# ════════════════════════════════════════════════════════════
# VALIDAR HTML SOURCE
# ════════════════════════════════════════════════════════════

if (-not (Test-Path $HtmlSource)) {
    Write-Host "[ERRO] SHOWCASE.html nao encontrado: $HtmlSource" -ForegroundColor Red
    exit 1
}

# ════════════════════════════════════════════════════════════
# GERAR PDF
# ════════════════════════════════════════════════════════════

$HtmlUri = "file:///" + ($HtmlSource -replace '\\', '/' -replace ' ', '%20')

Write-Host ""
Write-Host "══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   SHOWCASE PDF — Stack Radar" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "[i] Browser: $BrowserName" -ForegroundColor DarkGray
Write-Host "[i] HTML:    $HtmlSource" -ForegroundColor DarkGray
Write-Host "[i] PDF:     $PdfOutput" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[*] Gerando PDF..." -ForegroundColor Yellow

if (Test-Path $PdfOutput) {
    Remove-Item $PdfOutput -Force
}

$arguments = @(
    "--headless=new",
    "--disable-gpu",
    "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw",
    "--print-to-pdf=`"$PdfOutput`"",
    "`"$HtmlUri`""
)

$process = Start-Process -FilePath $BrowserPath -ArgumentList $arguments -PassThru -WindowStyle Hidden
$process | Wait-Process -Timeout 45

# ════════════════════════════════════════════════════════════
# VERIFICAR RESULTADO
# ════════════════════════════════════════════════════════════

if (Test-Path $PdfOutput) {
    $fileSize = (Get-Item $PdfOutput).Length / 1KB
    Write-Host ""
    Write-Host "[OK] PDF gerado com sucesso!" -ForegroundColor Green
    Write-Host "     Arquivo: $PdfOutput" -ForegroundColor Green
    Write-Host "     Tamanho: $([math]::Round($fileSize, 1)) KB" -ForegroundColor Green
    Write-Host ""

    if ($AbrirAoFinalizar) {
        Write-Host "[*] Abrindo PDF..." -ForegroundColor Yellow
        Start-Process $PdfOutput
    }
} else {
    Write-Host ""
    Write-Host "[ERRO] Falha ao gerar PDF." -ForegroundColor Red
    Write-Host "       Alternativa: abra SHOWCASE.html no browser > Ctrl+P > Salvar como PDF" -ForegroundColor Yellow
    Write-Host "       Margens: Nenhuma | Graficos de fundo: ON | Cabecalho/Rodape: OFF" -ForegroundColor Yellow
}
