# Build the two remaining arms of the focal gamma sweep, in sequence.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_focal_gamma_sweep.ps1

param(
    [string]$Repo = 'F:\zero trust\gitwork'
)

$ErrorActionPreference = 'Continue'
Set-Location $Repo

$arms = @('spatial_position_focal_g05', 'spatial_position_focal_g10')

foreach ($arm in $arms) {
    Write-Output ""
    Write-Output ("=" * 96)
    Write-Output "ARM: $arm"
    Write-Output ("=" * 96)
    $cfg = "artifacts/configs/$arm.json"

    & python -u artifacts/scripts/train_marl_pytorch.py --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "training failed for $arm" }

    & python -u artifacts/scripts/run_reference_experiment.py --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "the experiment failed for $arm" }

    & python -u artifacts/scripts/summarize_results.py --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "the summary failed for $arm" }

    $dest = Join-Path $Repo "artifacts/runs/$arm"
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($sub in @('checkpoints', 'logs', 'tables', 'figures')) {
        $src = Join-Path $Repo "artifacts/outputs/$sub"
        if (Test-Path $src) {
            Copy-Item -Recurse -Force $src (Join-Path $dest $sub)
        }
    }
    Write-Output "snapshotted $arm to artifacts/runs/$arm"
}

Write-Output ""
Write-Output "both sweep arms done"
