# Build the two architecture figures of the manuscript.
#
# Both are written as TikZ sources in paper/figures, because the MDPI class
# does not load TikZ and the manuscript therefore includes rasterised PNGs.
# This script compiles each source standalone, rasterises it at 300 dpi and
# writes the result to both paper/figures and artifacts/outputs/figures.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File build_architecture_figures.ps1

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Figures = Join-Path $Root 'paper\figures'
$Outputs = Join-Path $Root 'artifacts\outputs\figures'

$pdflatex = (Get-Command pdflatex -ErrorAction SilentlyContinue).Source
$pdftoppm = (Get-Command pdftoppm -ErrorAction SilentlyContinue).Source
if (-not $pdflatex -or -not $pdftoppm) {
    Write-Output "!! pdflatex and pdftoppm are needed to build the figures"
    exit 1
}

New-Item -ItemType Directory -Force -Path $Outputs | Out-Null

$FiguresToBuild = @(
    @{ Source = 'pipeline_tikz.tex'; Standalone = 'pipeline_standalone.tex'; Name = 'pipeline.png' },
    @{ Source = 'deployment_tikz.tex'; Standalone = 'deployment_standalone.tex'; Name = 'deployment.png' }
)

Push-Location $Figures
try {
    foreach ($f in $FiguresToBuild) {
        Write-Output "=== $($f.Standalone) -> $($f.Name) ==="
        & $pdflatex -interaction=nonstopmode $f.Standalone 2>&1 |
            Select-String -Pattern 'Output written|!' | Select-Object -First 2
        $pdf = [System.IO.Path]::ChangeExtension($f.Standalone, '.pdf')
        & $pdftoppm -png -r 300 -singlefile $pdf ([System.IO.Path]::GetFileNameWithoutExtension($f.Name)) 2>&1 | Out-Null
        Copy-Item $f.Name (Join-Path $Outputs $f.Name) -Force
        Write-Output "    wrote paper/figures/$($f.Name) and artifacts/outputs/figures/$($f.Name)"
    }
}
finally {
    Pop-Location
}
