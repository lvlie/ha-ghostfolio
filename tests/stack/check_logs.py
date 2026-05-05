"""Scan a captured Home Assistant log for errors related to this integration."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Lines we consider fatal. Treat anything at ERROR/CRITICAL referencing
# ghostfolio (or that comes from a generic HA component while ghostfolio is
# the only loaded custom integration) as a failure.
ERROR_PATTERNS = [
    re.compile(r"\bERROR\b.*ghostfolio", re.IGNORECASE),
    re.compile(r"\bCRITICAL\b.*ghostfolio", re.IGNORECASE),
    re.compile(r"Error setting up entry .* for ghostfolio", re.IGNORECASE),
    re.compile(r"Unexpected exception.*ghostfolio", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)"),
]

# Lines that prove the integration actually loaded. We require at least one.
SUCCESS_PATTERNS = [
    re.compile(r"Setting up ghostfolio", re.IGNORECASE),
    re.compile(r"Setup of domain ghostfolio took", re.IGNORECASE),
    re.compile(r"custom_components\.ghostfolio", re.IGNORECASE),
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_logs.py <ha.log>", file=sys.stderr)
        return 2
    log = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

    errors: list[str] = []
    in_traceback = False
    for line in log.splitlines():
        if any(p.search(line) for p in ERROR_PATTERNS):
            errors.append(line)
            in_traceback = "Traceback" in line
            continue
        if in_traceback:
            errors.append(line)
            if line and not line.startswith(" ") and not line.startswith("\t"):
                in_traceback = False

    success = any(p.search(log) for p in SUCCESS_PATTERNS)

    if errors:
        print("::error::Found errors in Home Assistant log:")
        for line in errors:
            print(line)
        return 1

    if not success:
        print(
            "::error::Did not see any evidence that the ghostfolio integration "
            "was set up. The log probably never reached integration setup.",
            file=sys.stderr,
        )
        return 1

    print("Home Assistant started cleanly with the ghostfolio integration loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
