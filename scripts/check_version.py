#!/usr/bin/env python3
"""Check that the manifest version is released in the changelog.

HACS installs a custom integration by the ``version`` field in
``manifest.json``, so a code change that never bumps it silently ships under
the previous version. This guard keeps ``manifest.json``, ``CHANGELOG.md`` and
(when present) the latest git tag telling the same story.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "custom_components" / "ghostfolio" / "manifest.json"
CHANGELOG = REPO / "CHANGELOG.md"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
HEADING = re.compile(r"^##\s*\[?(?P<version>\d+\.\d+\.\d+)\]?", re.MULTILINE)


def main() -> int:
    """Return 0 when the manifest version is documented, 1 otherwise."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest.get("version")

    if not version:
        print("manifest.json has no 'version' key (HACS requires one)")
        return 1

    if not SEMVER.match(version):
        print(f"manifest.json version {version!r} is not a plain x.y.z version")
        return 1

    released = HEADING.findall(CHANGELOG.read_text(encoding="utf-8"))
    if not released:
        print("CHANGELOG.md has no '## [x.y.z]' release headings")
        return 1

    if version not in released:
        print(
            f"manifest.json is at {version} but CHANGELOG.md documents "
            f"{', '.join(released[:5])}. Add a changelog entry for {version}."
        )
        return 1

    if released[0] != version:
        print(
            f"CHANGELOG.md's newest entry is {released[0]} but manifest.json "
            f"is at {version}. The newest entry should be the released version."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
