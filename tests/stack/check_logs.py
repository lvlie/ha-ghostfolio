"""Wait for the Ghostfolio integration to load, then scan the log for errors.

Used by the integration job: Home Assistant runs in its official container
with this integration staged into the config directory, and this script
asserts on ``home-assistant.log`` that the integration was set up, that the
sensor platform was forwarded, and that the coordinator actually fetched data
from the live Ghostfolio instance.

Usage:
    python check_logs.py ha_config/home-assistant.log [--wait 240]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time

# Lines we consider fatal. Treat anything at ERROR/CRITICAL referencing
# ghostfolio (or that comes from a generic HA component while ghostfolio is
# the only loaded custom integration) as a failure.
ERROR_PATTERNS = [
    re.compile(r"\bERROR\b.*ghostfolio", re.IGNORECASE),
    re.compile(r"\bCRITICAL\b.*ghostfolio", re.IGNORECASE),
    re.compile(r"Error setting up entry .* for ghostfolio", re.IGNORECASE),
    re.compile(r"Unexpected exception.*ghostfolio", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)"),
    # The coordinator logs this when a refresh fails.
    re.compile(r"Finished fetching ghostfolio data.*success: False", re.IGNORECASE),
]

# Evidence that the integration did its job, from setup through to a
# successful poll of the live Ghostfolio instance. Every entry must be seen.
REQUIRED_MARKERS: dict[str, re.Pattern[str]] = {
    "integration set up": re.compile(
        r"Setup of domain ghostfolio took|Setting up ghostfolio", re.IGNORECASE
    ),
    # Home Assistant logs this as "<platform>.<domain>", i.e.
    # "Setting up ghostfolio.sensor" — not "sensor.ghostfolio".
    "sensor platform forwarded": re.compile(
        r"Setting up ghostfolio\.sensor|Registered new sensor\.ghostfolio entity"
    ),
    "portfolio data fetched": re.compile(
        r"Finished fetching ghostfolio data.*success: True", re.IGNORECASE
    ),
}


def _read(path: Path) -> str:
    """Return the log contents, or an empty string if it does not exist yet."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _missing(log: str) -> list[str]:
    """Return the names of the markers that have not been logged yet."""
    return [
        name for name, pattern in REQUIRED_MARKERS.items() if not pattern.search(log)
    ]


def _collect_errors(log: str) -> list[str]:
    """Return the offending lines, including the body of any traceback."""
    errors: list[str] = []
    in_traceback = False
    for line in log.splitlines():
        if any(pattern.search(line) for pattern in ERROR_PATTERNS):
            errors.append(line)
            in_traceback = "Traceback" in line
            continue
        if in_traceback:
            errors.append(line)
            if line and not line.startswith((" ", "\t")):
                in_traceback = False
    return errors


def _wait_for_markers(path: Path, timeout: int) -> str:
    """Poll the log until the run resolves, either way, or the timeout passes.

    A logged error is final — there is nothing to wait for once setup or a
    refresh has failed — so a real failure reports in seconds instead of
    burning the whole timeout.
    """
    deadline = time.monotonic() + timeout
    log = _read(path)
    while _missing(log) and not _collect_errors(log) and time.monotonic() < deadline:
        time.sleep(2)
        log = _read(path)
    return log


def main() -> int:
    """Return 0 when the integration loaded and fetched data without errors."""
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument(
        "--wait",
        type=int,
        default=240,
        help="seconds to wait for the integration to finish loading",
    )
    args = parser.parse_args()

    log = _wait_for_markers(args.log, args.wait)

    errors = _collect_errors(log)
    if errors:
        print("::error::Found errors in the Home Assistant log:")
        for line in errors:
            print(line)
        return 1

    missing = _missing(log)
    if missing:
        print(
            f"::error::Timed out after {args.wait}s waiting for: {', '.join(missing)}.",
            file=sys.stderr,
        )
        if not log:
            print(f"{args.log} was never written.", file=sys.stderr)
        else:
            print("----- last 100 log lines -----", file=sys.stderr)
            print("\n".join(log.splitlines()[-100:]), file=sys.stderr)
        return 1

    print(
        "Home Assistant loaded the ghostfolio integration, set up its sensors "
        "and fetched portfolio data without errors."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
