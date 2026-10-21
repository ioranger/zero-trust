# Build ns-3 under WSL2 and generate the packet-level traces.
#
# The Windows host has no ns-3 toolchain that works: ns-3 master refuses
# Visual Studio outright and wants CMake 3.25, and the standalone CMake
# archive was unreachable. WSL2 with the distribution's own gcc and cmake is
# the supported route, and the WSL2 virtual machine needs the Windows
# hypervisor, which is loaded by the boot configuration rather than by a
# service. If WSL2 cannot start, the script says which single command arms
# it and stops, rather than failing obscurely.
#
# After the traces are generated the driver hands them to
# artifacts/analysis/multitrace_validation.py, which converts them, checks
# that each one is a measurement the feature extractor can make, evaluates
# the survivors and aggregates them.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File '.\artifacts\ns3\run_ns3_traces.ps1'
#
# Optional arguments: a comma-separated seed list and the mission duration in
# seconds. The duration has to be large enough for the trace to land in the
# feature extractor's training regime; 5000 s gives 500 steps, of which the
# harness keeps 100 as warm-up and 400 for the features.

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repo
$py = 'F:\zero trust\py310\python.exe'
$outDir = Join-Path $repo 'artifacts\outputs\logs\ns3_traces'
$distro = 'Ubuntu-20.04'
$ns3Home = 'ns3'
# Where the ns-3 source was cloned on the Windows side, if it is there. The
# git transport to github.com is unreliable from this machine, so an existing
# clone is preferred over a fresh one.
$winClone = 'F:\zero trust\ns3-dev'

if ($args.Count -gt 0) { $seedList = $args[0] -split ',' } else { $seedList = @('2000','2001','2002','2003','2004') }
if ($args.Count -gt 1) { $duration = $args[1] } else { $duration = '5000' }
$seedsJoined = [string]::Join(' ', $seedList)

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Invoke-Wsl([string]$cmd) {
    $out = & wsl -d $distro -e bash -lc $cmd 2>&1
    $code = $LASTEXITCODE
    $out | ForEach-Object { $_ }
    return $code
}

# ---------------------------------------------------------------- environment
Write-Output '=== ns-3 environment ==='
$probe = & wsl -d $distro -e bash -lc 'echo WSL_OK' 2>&1 | Out-String
if ($probe -notmatch 'WSL_OK') {
    Write-Output ''
    Write-Output 'WSL2 cannot start on this machine.'
    Write-Output ''
    Write-Output 'The Windows hypervisor is what WSL2 needs, and it is loaded by the'
    Write-Output 'boot configuration, not by a service. Check and arm it with:'
    Write-Output ''
    Write-Output '  bcdedit /set hypervisorlaunchtype auto'
    Write-Output ''
    Write-Output 'then restart Windows once. Until that restart happens no Linux'
    Write-Output 'environment is available, and the native Visual Studio route is'
    Write-Output 'closed because ns-3 master refuses MSVC.'
    Write-Output ''
    throw 'no usable ns-3 environment'
}
Write-Output 'WSL2 is up'

Write-Output ''
Write-Output '=== build dependencies ==='
Invoke-Wsl 'sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cmake ninja-build gcc g++ python3 python3-pip git unzip curl zip 2>&1 | tail -3' | Out-Null
Invoke-Wsl 'python3 -c "import cffi" 2>/dev/null || pip3 install --quiet cffi 2>&1 | tail -2' | Out-Null
$ver = Invoke-Wsl 'cmake --version | head -1; gcc --version | head -1; python3 --version'
Write-Output ($ver | Out-String).Trim()

Write-Output ''
Write-Output '=== ns-3 source ==='
# The source is copied into the Linux filesystem before the build, because
# building on the Windows mount is far slower.
if ((Invoke-Wsl "test -d ~/$ns3Home/.git") -ne 0) {
    if (Test-Path $winClone) {
        Write-Output 'copying the existing ns-3 clone into the distribution'
        Invoke-Wsl "mkdir -p ~/$ns3Home" | Out-Null
        $winSrcUnix = (& wsl -d $distro -e wslpath -a "$winClone").Trim()
        Invoke-Wsl "cp -a '$winSrcUnix/.' ~/$ns3Home/" | Out-Null
    }
    else {
        Write-Output 'cloning ns-3 into the distribution'
        Invoke-Wsl "git clone --depth 1 https://github.com/nsnam/ns-3-dev-git.git ~/$ns3Home" | Out-Null
    }
} else {
    Write-Output 'ns-3 source already present'
}

Write-Output ''
Write-Output '=== configure and build ==='
$build = Invoke-Wsl "cd ~/$ns3Home && ./ns3 configure --enable-examples --build-profile=release 2>&1 | tail -5"
Write-Output ($build | Out-String).Trim()
$build = Invoke-Wsl "cd ~/$ns3Home && ./ns3 build -j 16 2>&1 | tail -15"
Write-Output ($build | Out-String).Trim()

Write-Output ''
Write-Output '=== generate the traces ==='
$wslSrc = (& wsl -d $distro -e wslpath -a (Join-Path $repo 'artifacts\ns3')).Trim()
$wslOut = (& wsl -d $distro -e wslpath -a $outDir).Trim()
$gen = Invoke-Wsl "SEEDS='$seedsJoined' DURATION='$duration' SCENARIO_SRC='$wslSrc/mtim_uav_trust.cc' OUTDIR='$wslOut' bash '$wslSrc/generate_traces.sh' 2>&1 | tail -20"
Write-Output ($gen | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'the trace generation failed' }

Write-Output ''
Write-Output '=== validate the models on the traces ==='
$argsList = @()
Get-ChildItem $outDir -Filter 'trace_seed*.csv' | ForEach-Object {
    $argsList += '--trace'
    $argsList += $_.FullName
}
if ($argsList.Count -eq 0) { throw 'no traces were produced' }
& $py -u artifacts/analysis/multitrace_validation.py @argsList
if ($LASTEXITCODE -ne 0) { throw 'multi-trace validation failed' }
