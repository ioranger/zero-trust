# Build two spatial arms in sequence and snapshot each one.
#
# The arms share the outputs directory, so they cannot run concurrently: the
# second arm would overwrite the first one's results. Each arm is trained,
# evaluated, summarised, and then its outputs are copied into its own run
# directory, which is where the analysis scripts read them from.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_spatial_arms.ps1

param(
    [string[]]$Arms = @('spatial_position_riskonly', 'spatial_position_gated'),
    [string]$Repo = 'F:\zero trust\gitwork'
)

$ErrorActionPreference = 'Continue'
Set-Location $Repo

foreach ($arm in $Arms) {
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
Write-Output "both arms done"
