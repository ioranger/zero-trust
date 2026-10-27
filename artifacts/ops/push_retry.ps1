$ErrorActionPreference = 'Continue'
$git = 'F:\zero trust\tools\MinGit\cmd\git.exe'
Set-Location 'F:\zero trust\gitwork'

$deadline = (Get-Date).AddMinutes(30)
$attempt = 0
$ok = $false

while ((Get-Date) -lt $deadline) {
    $attempt++
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] push attempt $attempt"
    & $git push origin ioranger-patch-1 2>&1 | Select-Object -Last 4
    if ($LASTEXITCODE -eq 0) {
        Write-Output "PUSH_OK after $attempt attempt(s)"
        $ok = $true
        break
    }
    # back off: 45s, 60s, 90s, then 120s
    $wait = @(45, 60, 90, 120)[[Math]::Min($attempt - 1, 3)]
    Start-Sleep -Seconds $wait
}

if (-not $ok) {
    Write-Output "PUSH_FAILED after $attempt attempt(s); the commit is safe in the local worktree"
    & $git log --oneline -1
    exit 1
}
& $git log --oneline -2
& $git status -sb
