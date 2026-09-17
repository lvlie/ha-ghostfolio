"""Tests for the integration job's log checker.

The markers in ``check_logs.py`` are Home Assistant's own log strings, so a
typo in one of them is invisible until the integration job has burned its
whole timeout waiting for a line that is never written. The sample below is
copied verbatim from a passing CI run against Home Assistant 2026.9.2.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]

PASSING_LOG = """\
2026-09-17 15:02:44.675 INFO (MainThread) [homeassistant.setup] Setting up ghostfolio
2026-09-17 15:02:44.675 INFO (MainThread) [homeassistant.setup] Setup of domain ghostfolio took 0.00 seconds
2026-09-17 15:02:44.707 INFO (MainThread) [homeassistant.setup] Setting up default_config
2026-09-17 15:02:44.870 DEBUG (MainThread) [custom_components.ghostfolio.coordinator] Finished fetching ghostfolio data in 0.176 seconds (success: True)
2026-09-17 15:02:44.873 INFO (MainThread) [homeassistant.components.sensor] Setting up ghostfolio.sensor
2026-09-17 15:02:44.874 INFO (MainThread) [homeassistant.helpers.entity_registry] Registered new sensor.ghostfolio entity: sensor.ghostfolio_total_portfolio_value
2026-09-17 15:02:44.875 INFO (MainThread) [homeassistant.core] Starting Home Assistant 2026.9.2
"""

FAILED_REFRESH = (
    "2026-09-17 15:02:44.870 DEBUG (MainThread) "
    "[custom_components.ghostfolio.coordinator] Finished fetching ghostfolio "
    "data in 0.176 seconds (success: False)\n"
)

SETUP_ERROR = (
    "2026-09-17 15:02:44.870 ERROR (MainThread) [homeassistant.config_entries] "
    "Error setting up entry Ghostfolio for ghostfolio\n"
)


def _load_check_logs() -> Any:
    """Import check_logs.py, which lives outside the importable test package."""
    spec = importlib.util.spec_from_file_location(
        "_gf_check_logs", REPO / "tests" / "stack" / "check_logs.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["_gf_check_logs"] = module
    spec.loader.exec_module(module)
    return module


check_logs = _load_check_logs()


def _run(tmp_path: Path, contents: str | None, wait: int = 0) -> int:
    log = tmp_path / "home-assistant.log"
    if contents is not None:
        log.write_text(contents, encoding="utf-8")
    argv = ["check_logs.py", str(log), "--wait", str(wait)]
    original, sys.argv = sys.argv, argv
    try:
        return check_logs.main()
    finally:
        sys.argv = original


def test_passing_log_is_accepted(tmp_path: Path) -> None:
    """A real successful startup satisfies every marker."""
    assert _run(tmp_path, PASSING_LOG) == 0


def test_every_marker_is_matched_by_the_sample() -> None:
    """Each marker must match the real log, not just the set as a whole.

    Guards against the failure this test was written for: a marker whose
    pattern never appears in a Home Assistant log at all.
    """
    for name, pattern in check_logs.REQUIRED_MARKERS.items():
        assert pattern.search(PASSING_LOG), f"marker {name!r} matches nothing"


@pytest.mark.parametrize("marker", list(check_logs.REQUIRED_MARKERS))
def test_each_marker_is_required(tmp_path: Path, marker: str) -> None:
    """Removing the evidence for any one marker fails the check."""
    pattern = check_logs.REQUIRED_MARKERS[marker]
    trimmed = "\n".join(
        line for line in PASSING_LOG.splitlines() if not pattern.search(line)
    )
    assert _run(tmp_path, trimmed) == 1


def test_failed_refresh_is_an_error(tmp_path: Path) -> None:
    """A refresh that did not succeed fails even with the other markers present."""
    assert _run(tmp_path, PASSING_LOG + FAILED_REFRESH) == 1


def test_setup_error_is_an_error(tmp_path: Path) -> None:
    """An entry that failed to set up fails the check."""
    assert _run(tmp_path, PASSING_LOG + SETUP_ERROR) == 1


def test_missing_log_file_fails(tmp_path: Path) -> None:
    """A log that was never written fails instead of hanging."""
    assert _run(tmp_path, None) == 1
