# Running the packet-level validation

The multi-seed packet-level validation needs an ns-3 environment. This file
records what that environment requires, what was tried on the machine this
study was prepared on, and the exact commands for each route, so the next
attempt does not have to re-derive any of it.

## What the validation needs

The scenario already exposes everything the run needs, so no code change is
required on the ns-3 side:

```
./ns3 run "scratch/mtim_uav_trust --nUavs=15 --maliciousRatio=0.30 \
          --seed=2000 --duration=5000 --csv=/out/trace_seed2000.csv"
```

* `--duration 5000` at the scenario's 10-second interval gives a 500-step
  trace. The evaluation harness rewrites the warm-up to one fifth of the
  trace, so 100 warm-up steps and 400 post-warm-up steps remain, which is
  exactly the geometry the model was trained on.
* `--seed` selects both the malicious node set (`std::mt19937(seed)` shuffles
  the node ids) and, through it, the attack-type assignment, so several seeds
  give several traces with different attackers in different places.
* The attack parameters in a trace are never in the training set: training
  uses the synthetic trust-stream generator and the trace uses the packet
  domain, with the malicious set drawn from an independent seed.

## Two properties the scenario now guarantees

Both were defects in the earlier revision, and both would have made the
validation meaningless rather than merely inaccurate.

1. **The packet counters are real.** The earlier scenario never incremented
   `tx_packets` or `rx_packets`, so they stayed at zero, the converter's
   packet-delivery ratio was constant at 1.0, the T2 channel carried no
   information, and several input columns became degenerate. The counters are
   now read from the MAC layer through the standard net-device trace sources,
   and the run aborts with a non-zero exit code if no packet was counted.
2. **The mobility is scenario-driven.** The positions written to the trace
   come from `MobilityModel::SetPosition`, which every ns-3 release
   provides, rather than from `RandomWaypointMobilityModel`, whose `Speed`
   attribute was renamed to `MinSpeed`/`MaxSpeed` in ns-3 3.36 and removed
   later, or from `RandomRectanglePositionAllocator`, whose `X`/`Y`
   attributes were renamed to `Length`/`Width` at the same time. The scenario
   therefore compiles against both the old and the current API.

   The packet counters are read from the MAC layer, through the paths ns-3's
   own examples use, for instance `examples/wireless/wifi-ap.cc`:

   ```
   /NodeList/<node>/DeviceList/<device>/Mac/MacTx
   /NodeList/<node>/DeviceList/<device>/Mac/MacRx
   /NodeList/<node>/DeviceList/<device>/Mac/MacTxDrop
   /NodeList/<node>/DeviceList/<device>/Mac/MacRxDrop
   ```

   `WifiMac` registers `MacTx` and `MacRx` as
   `TracedCallback<Ptr<const Packet>>`, so the callback takes a single packet
   argument and the node index is bound to it with
   `MakeCallback(&MacTxCallback, i)`. These are MAC-layer counters: they
   count every frame the node handed to the MAC and every frame the MAC
   accepted, not only the frames of the node's own echo partner, and the
   trace's header comment says so.

   Two paths were tried and rejected before this one. `PacketCounter` was
   removed from ns-3 master, only `PacketCounterCalculator` remains, and the
   `TxList/$ns3::PacketCounter/MacTx` form the earlier revision used is not a
   path any current ns-3 provides. `FlowMonitor` would give exact per-flow
   loss, but its `FlowStats` carries no addresses, so the flow-to-node mapping
   needs an `Ipv4FlowClassifier` in parallel with the statistics container,
   which is more moving parts than the MAC counters need.

## Checking the scenario without building ns-3

`artifacts/analysis/syntax_check_scenario.py` compiles the scenario for
syntax and type checking only, against the minimal stand-in headers in
`artifacts/ns3/stubs/`. It cannot check the real ns-3 API, but it catches the
mistakes a rewrite introduces: syntax errors, undeclared names, wrong argument
counts, wrong types. It found three of them in the first version of the
rewrite: a missing `<iostream>`, a use of `M_PI` that is not portable to a
strict `-std=c++17` compiler, and a `Ptr<Node>` passed to a parameter declared
as `Node`.

```powershell
python -u artifacts/analysis/syntax_check_scenario.py
```

The compiler it uses is the MinGW-w64 toolchain that ships with Vagrant
(`C:\Program Files\Vagrant\embedded\mingw64\bin\g++.exe`), which needs its own
`bin` directory on `PATH`; the script sets that itself. Visual Studio 2019
would do as well, but the Windows SDK it needs is not installed on this
machine.

`artifacts/analysis/trace_regime.py` checks the result before any number is
reported, and `artifacts/analysis/multitrace_validation.py` excludes the
traces that fail the check and states how many of the traces were valid
measurements.

## Routes to an ns-3 environment

### Route 1: the official Docker image (recommended)

```bash
docker pull ns3:dev
docker run --rm -v <repo>/artifacts/ns3:/scenario:ro -v <outdir>:/out \
    -e "SEEDS=2000 2001 2002 2003 2004" -e "DURATION=5000" \
    -e SCENARIO_SRC=/scenario/mtim_uav_trust.cc -e OUTDIR=/out \
    ns3:dev bash /scenario/generate_traces.sh
```

Docker Desktop's Linux engine needs WSL2, so this route needs the virtual
machine platform to be loaded. On the machine this study was prepared on, the
blocker was more specific than a missing feature. `VirtualMachinePlatform` was
enabled and the firmware had virtualisation on, and all four Hyper-V
requirements were satisfied, but `bcdedit /enum {current}` reported
`hypervisorlaunchtype Off`, so the hypervisor was never launched and every
WSL2 request failed with `HCS/HCS_E_NOT_INSTALLED`. The hypervisor is loaded
by the boot configuration rather than by a service, so no amount of starting
or restarting `vmcompute` or `WslService` helps, and `wsl --set-version
Ubuntu-20.04 1` fails for the same reason: the conversion itself is driven by
the WSL service, which cannot start.

The fix is one command and one restart:

```
bcdedit /set hypervisorlaunchtype auto
```

After that restart, `HypervisorPresent` becomes true, WSL2 starts, and both
this route and route 2 work. `realdata/run_ns3_traces.ps1` checks for this
and prints the command rather than failing obscurely.

### Route 2: ns-3 under WSL2

```bash
wsl -d Ubuntu-20.04 -- bash -c "sudo apt update && sudo apt install -y \
    cmake ninja-build gcc g++ python3 pip git && pip3 install cffi"
wsl -d Ubuntu-20.04 -- bash -c "git clone https://github.com/nsnam/ns-3-dev-git.git ~/ns-3 \
    && cd ~/ns-3 && ./ns3 configure --enable-examples && ./ns3 build"
```

Same virtualisation requirement as route 1.

### Route 3: WSL1

`wsl --set-version Ubuntu-20.04 1` converts the distribution to WSL1, which
does not need the virtual machine platform. It fails on the machine this
study was prepared on, for the reason above: the conversion is driven by the
WSL service, which cannot start without the hypervisor. Once the hypervisor
is loaded, route 2 is preferable anyway, because a full ns-3 build under
WSL1's syscall translation layer is slow.

## What does not work, and why it is worth recording

* **Visual Studio.** MSVC 2019 with the bundled CMake 3.20 and Ninja 1.10 is
  installed on this machine, so a native build looks available. It is not:
  ns-3 master's `build-support/custom-modules/ns3-vcpkg-hunter.cmake` ends
  the vcpkg setup with `FATAL_ERROR "vcpkg: Visual Studio is unsupported"`,
  and ns-3 master also requires `cmake_minimum_required(VERSION 3.25..3.25)`
  against the bundled 3.20. An ns-3 release from before the MSVC drop
  (3.40) would build with the installed toolchain, but it is an old
  simulator and the trace it produces would be from an older network stack.
* **CMake from cmake.org.** The standalone archive could not be fetched from
  this machine, so the bundled 3.20 was the only CMake available.
* **ns-3 sources.** The shallow clone of `ns-3-dev-git` succeeded, but
  fetching a release tag over the same connection failed repeatedly.

## The driver

`realdata/run_ns3_traces.ps1` tries route 1, then route 2, then route 3, and
reports which one it found. When none is available it prints the commands
above and stops, rather than failing obscurely. Once an environment exists,
the whole validation is that one command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\realdata\run_ns3_traces.ps1'
```

It generates the traces, converts them, checks each one's regime, evaluates
the survivors and writes the aggregate to
`artifacts/outputs/tables/ns3_multitrace.csv` together with a verdict file
recording how many of the traces were valid measurements.

Before the run it is worth checking that the harness still works, which needs
no ns-3:

```powershell
python -u artifacts/analysis/selftest_multitrace_harness.py
```
