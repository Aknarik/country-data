#!/usr/bin/env python3
"""One command to refresh the data and the Copilot agents.

    python update_all.py              # quick: central bank bulletins + agents (about 5 minutes)
    python update_all.py --imf        # + IMF WEO / FSI / MFS and BIS data (long: 30+ minutes)
    python update_all.py --local      # + iMaPP database and bank data files saved in this folder
    python update_all.py --all        # everything
    python update_all.py --agents     # only rebuild, test and package the agents

Then upload what changed from copilot_agents_package/ (each agent folder: INSTRUCTIONS.txt + knowledge/).
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
M = ROOT / "m365-agent"
AG = M / "agents"


def run(label, *args):
    t = time.time()
    print(f"\n=== {label} ===", flush=True)
    r = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT)
    print(f"--- {label}: {'OK' if r.returncode == 0 else 'FAILED'} ({time.time() - t:.0f}s)", flush=True)
    return r.returncode == 0


def main():
    a = set(sys.argv[1:])
    full = "--all" in a
    ok = True
    if "--agents" not in a:
        if full or "--imf" in a:
            # IMF and BIS APIs; if the BIS site is down, recompute gaps from the stored ratios instead
            if not run("IMF and BIS data (WEO, FSI, MFS, BIS credit)", M / "build_data_file.py"):
                run("Credit gaps from stored ratios (APIs down)", M / "recompute_credit_gaps.py")
        if full or "--local" in a:
            ok &= run("iMaPP and bank data files", M / "build_local_sources.py")
        ok &= run("GCC central bank bulletins (CBK, SAMA, CBO, CBB)", M / "build_gcc_central_banks.py")
    ok &= run("Agents: build instructions (8,000-character check)", AG / "build_agents.py")
    run("Agents: tests", AG / "test_agents.py")
    ok &= run("Agents: package", AG / "build_package.py")
    print("\nDone." if ok else "\nFinished with errors - see FAILED above.")
    print(f"Upload from: {ROOT / 'copilot_agents_package'}")


if __name__ == "__main__":
    main()
