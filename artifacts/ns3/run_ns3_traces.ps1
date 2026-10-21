# Build ns-3 under WSL2 and generate the packet-level traces.
#
# The Windows host has no ns-3 toolchain that works: ns-3 master refuses
# Visual Studio outright and wants CMake 3.25, and the standalone CMake
# archive was unreachable. WSL2 with a newer compiler from the Ubuntu
# toolchain PPA and a current CMake from PyPI is the supported route, and the
# WSL2 virtual machine needs the Windows hypervisor, which is loaded by the
# boot configuration rather than by a service. If WSL2 cannot start, the
# script says which single command arms it and stops, rather than failing
# obscurely.
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
#
# The build this driver reproduces is the one that produced the traces
# reported in the manuscript: ns-3 master, CMake 4.4.4 from PyPI, g++-12 from
# the Ubuntu toolchain PPA, and the module set restricted to the ones the
# scenario needs. The module restriction is not an optimisation only; it takes
# the build from several thousand targets to a few hundred, and it is the
# configuration the reported traces came from.

# The native wsl tool writes warnings about Windows PATH entries that have no
# Linux equivalent to stderr, and under the default ErrorActionPreference a
# native command writing to stderr is a terminating error. The exit codes are
# checked explicitly instead.
$ErrorActionPreference = 'Continue'
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
# The ns-3 release to build. ns-3 master is what the reported traces came
# from; an older tag such as ns-3.45 is also accepted by prepare_ns3.sh.
$ns3Tag = 'master'
# The modules the scenario needs and nothing else.
$ns3Modules = 'core,network,internet,mobility,applications,wifi,flow-monitor'
# Linux paths for the repository's ns-3 directory and the trace output.
$wslSrc = (& wsl -d $distro -e wslpath -a (Join-Path $repo 'artifacts\ns3')).Trim()
$wslOut = (& wsl -d $distro -e wslpath -a $outDir).Trim()
$wslNs3Script = "$wslSrc/prepare_ns3.sh"

if ($args.Count -gt 0) { $seedList = $args[0] -split ',' } else { $seedList = @('2000','2001','2002','2003','2004') }
if ($args.Count -gt 1) { $duration = $args[1] } else { $duration = '5000' }
$seedsJoined = [string]::Join(' ', $seedList)

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Both helpers return an object with the command's exit code and its output
# kept apart. Returning them together would make an exit-code check compare
# an array, and a pipeline inside the bash command would otherwise report the
# status of the last filter rather than of the command it filters.
function Invoke-Wsl([string]$cmd) {
    $out = & wsl -d $distro -e bash -lc $cmd 2>&1
    $code = $LASTEXITCODE
    $text = ($out | Where-Object { $_ -notmatch 'Failed to translate' } | Out-String).Trim()
    return [pscustomobject]@{ Code = $code; Output = $text }
}

function Invoke-WslRoot([string]$cmd) {
    # The default distribution user has a password-protected sudo, so the
    # package installation runs as root directly rather than through sudo,
    # which would block waiting for a prompt.
    $out = & wsl -d $distro -u root -e bash -lc $cmd 2>&1
    $code = $LASTEXITCODE
    $text = ($out | Where-Object { $_ -notmatch 'Failed to translate' } | Out-String).Trim()
    return [pscustomobject]@{ Code = $code; Output = $text }
}

# ---------------------------------------------------------------- environment
Write-Output '=== ns-3 environment ==='
$probe = (& wsl -d $distro -e bash -lc 'echo WSL_OK' 2>&1 | Out-String)
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
# The toolchain PPA is what carries a compiler new enough for ns-3 master;
# the distribution's own GCC 9.4 is too old.
$deps = Invoke-WslRoot 'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq software-properties-common >/dev/null 2>&1; add-apt-repository -y ppa:ubuntu-toolchain-r/test >/dev/null 2>&1; apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq ninja-build gcc-12 g++-12 python3 python3-pip git unzip curl zip >/dev/null 2>&1; echo DEPS_DONE'
if ($deps.Code -ne 0) { throw "the dependency installation failed: $($deps.Output)" }
$cfi = Invoke-WslRoot 'python3 -c "import cffi" 2>/dev/null || pip3 install --quiet cffi 2>&1 | tail -2'
if ($cfi.Code -ne 0) { throw "the cffi installation failed: $($cfi.Output)" }
# The distribution ships CMake 3.16, and ns-3 master wants 3.25 or newer, so
# one is installed from PyPI, which puts it in /usr/local/bin ahead of the
# distribution's copy.
$cml = Invoke-WslRoot 'python3 -c "import cmake" 2>/dev/null || pip3 install --quiet cmake 2>&1 | tail -3'
if ($cml.Code -ne 0) { throw "the cmake installation failed: $($cml.Output)" }
$ver = Invoke-Wsl 'export PATH=$PATH:/usr/local/bin; cmake --version | head -1; g++-12 --version | head -1; python3 --version'
Write-Output $ver.Output

Write-Output ''
Write-Output '=== ns-3 source ==='
# The source is copied into the Linux filesystem before the build, because
# building on the Windows mount is far slower.
if ((Invoke-Wsl "test -d ~/$ns3Home/.git").Code -ne 0) {
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
Write-Output '=== select the release and configure ==='
$prep = Invoke-Wsl "set -o pipefail; bash '$wslNs3Script' $ns3Tag 2>&1 | tail -6"
Write-Output $prep.Output
if ($prep.Code -ne 0) { throw "the ns-3 checkout failed: $($prep.Output)" }
# The CMake cache records the compiler it was configured with, so a cache
# left from an earlier attempt would keep selecting the distribution's
# default GCC even with CXX pointing at the newer one.
Invoke-Wsl "rm -rf ~/$ns3Home/cmake-cache ~/$ns3Home/build" | Out-Null
$conf = Invoke-Wsl "set -o pipefail; export PATH=`$PATH:/usr/local/bin; export CXX=g++-12 CC=gcc-12; cd ~/$ns3Home && ./ns3 configure --enable-modules=$ns3Modules --build-profile=release 2>&1 | tail -12"
Write-Output $conf.Output
if ($conf.Code -ne 0) { throw "the ns-3 configure failed: $($conf.Output)" }
$bld = Invoke-Wsl "set -o pipefail; export PATH=`$PATH:/usr/local/bin; export CXX=g++-12 CC=gcc-12; cd ~/$ns3Home && ./ns3 build -j 16 2>&1 | tail -20"
Write-Output $bld.Output
if ($bld.Code -ne 0) { throw "the ns-3 build failed: $($bld.Output)" }

Write-Output ''
Write-Output '=== generate the traces ==='
$gen = Invoke-Wsl "set -o pipefail; SEEDS='$seedsJoined' DURATION='$duration' NS3_ROOT=~/$ns3Home SCENARIO_SRC='$wslSrc/mtim_uav_trust.cc' OUTDIR='$wslOut' bash '$wslSrc/generate_traces.sh' 2>&1 | tail -25"
Write-Output $gen.Output
if ($gen.Code -ne 0) { throw "the trace generation failed: $($gen.Output)" }

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
