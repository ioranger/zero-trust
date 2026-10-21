"""Generate the stub ns-3 headers and syntax-check the scenario with MSVC.

The scenario is a real ns-3 program, but on a machine where ns-3 is not built
it cannot be compiled against the real headers. This script writes minimal
stand-ins for the headers the scenario includes and asks the C++ compiler for a
syntax-only pass over the file, which catches the mistakes a rewrite can
introduce: syntax errors, undeclared names, wrong argument counts, wrong
types.

    python -u artifacts/analysis/syntax_check_scenario.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:\zero trust\zero-trust")
STUB_DIR = ROOT / "artifacts" / "ns3" / "stubs"
SCENARIO = ROOT / "artifacts" / "ns3" / "mtim_uav_trust.cc"
STUB_CORE = STUB_DIR / "ns3" / "stub-core.h"
HEADERS = ["core-module", "network-module", "mobility-module",
           "internet-module", "applications-module", "wifi-module"]

VCVARS = (r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community"
          r"\VC\Auxiliary\Build\vcvars64.bat")
MINGW = r"C:\Program Files\Vagrant\embedded\mingw64\bin"


def find_cl() -> str | None:
    base = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community")
    hits = sorted(base.glob(r"VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"))
    return str(hits[-1]) if hits else None


def find_gxx() -> str | None:
    cand = Path(MINGW) / "g++.exe"
    if cand.exists():
        return str(cand)
    from shutil import which
    return which("g++")


def main() -> int:
    if not STUB_CORE.exists():
        print(f"stub header missing: {STUB_CORE}")
        return 2
    if not SCENARIO.exists():
        print(f"scenario missing: {SCENARIO}")
        return 2

    for h in HEADERS:
        p = STUB_DIR / "ns3" / f"{h}.h"
        p.write_text('#pragma once\n#include "ns3/stub-core.h"\n', encoding="utf-8")

    gxx = find_gxx()
    cl = find_cl()
    env = dict(os.environ)
    if gxx:
        # The MinGW toolchain needs its own bin directory on PATH for the
        # runtime it links against.
        env["PATH"] = str(Path(gxx).parent) + os.pathsep + env.get("PATH", "")
        print(f"compiling (syntax only) with:\n  {gxx}\n")
        cmd = (f'"{gxx}" -fsyntax-only -std=c++17 -Wall '
               f'-I"{STUB_DIR}" -I"{STUB_DIR / "ns3"}" "{SCENARIO}"')
        r = subprocess.run(cmd, capture_output=True, shell=False, env=env)
        rc = r.returncode
    elif cl:
        print(f"compiling (syntax only) with:\n  {cl}\n")
        cmd = (f'call "{VCVARS}" >nul 2>&1 && '
               f'"{cl}" /nologo /Zs /EHsc /std:c++17 /W3 '
               f'/I"{STUB_DIR}" /I"{STUB_DIR / "ns3"}" '
               f'"{SCENARIO}"')
        r = subprocess.run(f'cmd /c {cmd}', capture_output=True, shell=False)
        rc = r.returncode
    else:
        print("no C++ compiler found; the syntax check needs g++ or cl.exe")
        return 2

    out_text = ((r.stdout or b"") + (r.stderr or b"")).decode(
        "utf-8", errors="replace")
    print(out_text.strip() or "(no diagnostics)")
    if rc != 0:
        print(f"\nSYNTAX CHECK FAILED (exit {rc})")
        return 1
    print("\nSYNTAX CHECK PASSED: the scenario parses and type-checks against the stubs.")
    print("This does not check the real ns-3 API; building ns-3 does that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
