#!/usr/bin/env python3
"""
Respawner for *.pn miner binaries.

Usage:
    python3 respawner.py -o <pool> -u <wallet> -p <pass> -a <algo> [-k]

All arguments after the script name are forwarded directly to the *.pn binary.
The binary is discovered automatically (first .pn file in the script's directory).

When the process exits, waits a random 30-60 seconds, then respawns with the
same arguments.  Loops forever.

The binary is made executable automatically on first run (Linux/macOS).
"""

import glob
import os
import random
import signal
import subprocess
import stat
import sys
import time


# ── Configuration ──────────────────────────────────────────────────────────
MIN_DELAY = 30          # minimum seconds before respawn
MAX_DELAY = 60          # maximum seconds before respawn
# ──────────────────────────────────────────────────────────────────────────


def find_pn_binary(script_dir: str) -> str | None:
    """Return the path to the first .pn file found, or None."""
    pattern = os.path.join(script_dir, "*.pn")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]


def ensure_executable(path: str) -> None:
    """Add execute permission on Linux/macOS if missing."""
    if sys.platform == "win32":
        return
    st = os.stat(path)
    if not (st.st_mode & stat.S_IXUSR):
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[respawner] Made {path} executable")


def build_command(binary: str, mining_args: list[str]) -> list[str]:
    """Build the full command list for subprocess."""
    return [binary] + mining_args


def run_and_stream(cmd: list[str]) -> int:
    """
    Run *cmd*, stream stdout + stderr line-by-line to the terminal,
    and return the process exit code.
    """
    print(f"[respawner] Starting: {' '.join(cmd)}")
    print("-" * 72)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,      # merge stderr into stdout
        text=True,                      # decode as UTF-8
        bufsize=1,                      # line-buffered
    )

    print(f"[respawner] Process started (PID {proc.pid})")

    # Forward SIGTERM / SIGINT to the child so it can shut down cleanly.
    def _forward_signal(signum, frame):
        if proc.poll() is None:
            proc.send_signal(signum)

    signal.signal(signal.SIGTERM, _forward_signal)
    signal.signal(signal.SIGINT, _forward_signal)

    # Stream output
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

    proc.wait()
    print("-" * 72)
    return proc.returncode


def countdown(delay: int) -> None:
    """Print a countdown timer to stdout."""
    print(f"[respawner] Respawning in {delay} seconds...")
    for remaining in range(delay, 0, -1):
        sys.stdout.write(f"\r[respawner] Countdown: {remaining:>3}s remaining  ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write(f"\r[respawner] Countdown:   0s remaining  \n")
    sys.stdout.flush()


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Check for .pn binary first
    binary = find_pn_binary(script_dir)
    if binary is None:
        print(f"[respawner] ERROR: No .pn file found in {script_dir}")
        print(f"[respawner] Rename your compiled miner binary to <name>.pn and try again.")
        sys.exit(1)

    ensure_executable(binary)
    print(f"[respawner] Found binary: {binary}")

    # All CLI args after the script name are forwarded to the binary
    mining_args = sys.argv[1:]

    if not mining_args:
        print("[respawner] WARNING: No arguments provided. The binary will run with defaults.")
        print(f"[respawner] Usage: python3 {sys.argv[0]} -o <pool> -u <wallet> -p <pass> -a <algo> [-k]")

    print(f"[respawner] Arguments: {' '.join(mining_args)}")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n{'=' * 72}")
        print(f"[respawner] Cycle #{cycle}")
        print(f"{'=' * 72}")

        cmd = build_command(binary, mining_args)
        exit_code = run_and_stream(cmd)

        print(f"[respawner] Process exited with code {exit_code}")

        delay = random.randint(MIN_DELAY, MAX_DELAY)
        countdown(delay)

        print(f"[respawner] Restarting...\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[respawner] Interrupted by user — exiting.")
        sys.exit(0)
