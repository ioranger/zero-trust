# Finish the focal arm: the training is already on disk, so this runs the
# evaluation, the summary and the snapshot, and does not retrain.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File finish_focal_arm.ps1

param(
    [string]$Repo = 'F:\zero trust\gitwork'
)

$ErrorActionPreference = 'Continue'
Set-Location $Repo

$arm = 'spatial_position_focal'
$cfg = "artifacts/configs/$arm.json"

Write-Output "=== evaluating $arm ==="
& python -u artifacts/scripts/run_reference_experiment.py --config $cfg
if ($LASTEXITCODE -ne 0) { throw "the experiment failed for $arm" }

Write-Output "=== summarising $arm ==="
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
Write-Output "arm done"
