# Build the focal-loss arm and snapshot it.
#
# The arm changes the risk loss only. The generator, the attack mix, the
# feature set, the seeds, the thresholds and the auxiliary weights are those
# of the published spatial configuration, and the learned comparators are
# trained with the same objective inside the same run.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_focal_arm.ps1

param(
    [string]$Repo = 'F:\zero trust\gitwork'
)

$ErrorActionPreference = 'Continue'
Set-Location $Repo

$arm = 'spatial_position_focal'
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
Write-Output "arm done"
