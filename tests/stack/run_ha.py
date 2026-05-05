"""Run Home Assistant for a bounded amount of time and stream its logs.

Exits 0 once HA has logged that it has finished startup, or after the timeout.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

READY_MARKER = "Home Assistant initialized"
ALT_READY_MARKER = "Starting Home Assistant"
DONE_MARKER = "Home Assistant started"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "homeassistant",
            "--config",
            args.config_dir,
            "--log-rotate-days",
            "1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=1,
        text=True,
    )

    start = time.monotonic()
    saw_done = False
    saw_started = False

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

            if DONE_MARKER in line:
                saw_done = True

            # Once we see the "started" line, keep collecting logs for a few
            # seconds so we capture the coordinator's first refresh, then stop.
            if saw_done and not saw_started:
                saw_started = True
                deadline = time.monotonic() + 20

            if saw_started and time.monotonic() > deadline:
                break

            if time.monotonic() - start > args.timeout:
                print(
                    f"::error::Home Assistant did not finish startup within {args.timeout}s",
                    file=sys.stderr,
                )
                break
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

    if not saw_done:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
