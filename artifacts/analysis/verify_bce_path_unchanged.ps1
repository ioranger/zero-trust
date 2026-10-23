# Confirm that the published path is bit-for-bit unchanged after the focal-loss
# change to train_marl_pytorch.py.
#
# The same short configuration is trained twice in the git worktree: once with
# the script as it was at HEAD, once with the script as it is now. The two
# training traces and the two trained parameter sets must be identical, because
# the published configurations do not set marl_training.risk_loss and therefore
# take the `bce` branch, which calls the same nn.BCEWithLogitsLoss object.
#
# The worktree's artifacts/outputs is restored from git afterwards, so the
# published tables are not disturbed.

$ErrorActionPreference = 'Stop'

$Repo = 'F:\zero trust\gitwork'
$Git = 'F:\zero trust\tools\MinGit\cmd\git.exe'
$Py = 'F:\zero trust\py310\python.exe'
$Cfg = 'artifacts/configs/smoke_regression_bce.json'
$Old = 'artifacts/scripts/train_marl_pytorch_old.py'
$Scratch = 'F:\zero trust\realdata\bce_regression'

New-Item -ItemType Directory -Force -Path $Scratch | Out-Null

Push-Location $Repo
try {
    $oldText = & $Git show HEAD:artifacts/scripts/train_marl_pytorch.py
    [System.IO.File]::WriteAllText(
        (Join-Path $Repo $Old),
        (($oldText -join "`n") + "`n"),
        (New-Object System.Text.UTF8Encoding($false)))

    Write-Output "=== run 1: the script as it was at HEAD ==="
    & $Py -u $Old --config $Cfg 2>&1 | Select-Object -Last 3
    Copy-Item 'artifacts\outputs\logs\marl_training_trace.csv' "$Scratch\trace_old.csv" -Force
    Copy-Item 'artifacts\outputs\checkpoints\stim_marl_policy.pt' "$Scratch\ckpt_old.pt" -Force

    Write-Output "=== run 2: the script as it is now ==="
    & $Py -u 'artifacts/scripts/train_marl_pytorch.py' --config $Cfg 2>&1 | Select-Object -Last 3
    Copy-Item 'artifacts\outputs\logs\marl_training_trace.csv' "$Scratch\trace_new.csv" -Force
    Copy-Item 'artifacts\outputs\checkpoints\stim_marl_policy.pt' "$Scratch\ckpt_new.pt" -Force
}
finally {
    Pop-Location
    # restore the published tables and remove the temporary script
    Push-Location $Repo
    try {
        & $Git checkout -- artifacts/outputs 2>&1 | Out-Null
        Remove-Item (Join-Path $Repo $Old) -Force -ErrorAction SilentlyContinue
    }
    finally { Pop-Location }
}

$hOld = (Get-FileHash "$Scratch\trace_old.csv" -Algorithm SHA256).Hash
$hNew = (Get-FileHash "$Scratch\trace_new.csv" -Algorithm SHA256).Hash
Write-Output ""
Write-Output "training trace old : $hOld"
Write-Output "training trace new : $hNew"
Write-Output ("trace identical    : " + ($hOld -eq $hNew))

$cmp = & $Py -c @"
import torch
a = torch.load(r'$Scratch\ckpt_old.pt', map_location='cpu')
b = torch.load(r'$Scratch\ckpt_new.pt', map_location='cpu')
same = all(torch.equal(a['model_state'][k], b['model_state'][k]) for k in a['model_state'])
print('parameter sets identical :', same)
"@
$cmp
