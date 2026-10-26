# Build the leave-one-factor-out arms and snapshot them.
#
# Every arm uses the published configuration in every respect except which
# trust factor the proposed model is allowed to see. The rule-based
# comparators keep all five factors in every arm.
#
#   published_recheck     the published configuration, re-run, so that the
#                          arms can be compared with a number produced by the
#                          same code path on the same day
#   drop_T1 ... drop_T5   the proposed model without that factor
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_factor_ablation.ps1

param(
    [string]$Repo = 'F:\zero trust\gitwork',
    [string[]]$Arms = @('published_recheck', 'drop_T1', 'drop_T2', 'drop_T3', 'drop_T4', 'drop_T5')
)

$ErrorActionPreference = 'Continue'
Set-Location $Repo

$py = 'F:\zero trust\py310\python.exe'

# When the script is invoked through `powershell -File`, a comma-separated
# argument arrives as one string, so the list is split here as well.
$armList = @()
foreach ($item in $Arms) {
    foreach ($part in ($item -split ',')) {
        if ($part.Trim()) { $armList += $part.Trim() }
    }
}

foreach ($arm in $armList) {
    $cfg = switch -Regex ($arm) {
        '^published_recheck$' { 'artifacts/configs/default.json'; break }
        '^spatial_recheck$'   { 'artifacts/configs/spatial_position.json'; break }
        '^spatial_drop_(.+)$' { "artifacts/configs/spatial_factor_ablation_drop_$($Matches[1]).json"; break }
        '^spatial_col_(.+)$'  { "artifacts/configs/spatial_factor_ablation_col_$($Matches[1]).json"; break }
        default                { "artifacts/configs/factor_ablation_$arm.json" }
    }
    Write-Output "=== $arm ($cfg) ==="

    # Remove the previous arm's artefacts first. A stale checkpoint or policy
    # file that does not match the configuration is the one way this run can
    # produce a width mismatch instead of a measurement.
    foreach ($stale in @('logs/marl_policy.json', 'logs/learned_baselines.json',
                          'logs/training_policy.json', 'checkpoints/stim_marl_policy.pt',
                          'checkpoints/lr_trust.pt', 'checkpoints/mlp_trust.pt')) {
        $p = Join-Path $Repo "artifacts/outputs/$stale"
        if (Test-Path $p) { Remove-Item -Force $p }
    }

    & $py -u artifacts/scripts/train_marl_pytorch.py --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "training failed for $arm" }

    & $py -u artifacts/scripts/run_reference_experiment.py --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "the experiment failed for $arm" }

    & $py -u artifacts/scripts/summarize_results.py --config $cfg
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
    Write-Output "snapshotted $arm"
    Write-Output ""
}

Write-Output "factor ablation arms done"
