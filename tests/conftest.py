"""Fixtures for the Ghostfolio integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ghostfolio.const import (
    CONF_ACCESS_TOKEN,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from .const import MOCK_DETAILS, MOCK_TOKEN, MOCK_URL, MOCK_USER


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ghostfolio in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry pointing at a fake Ghostfolio instance."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Ghostfolio ({MOCK_URL})",
        unique_id="ghostfolio.local:3333",
        data={
            CONF_URL: MOCK_URL,
            CONF_ACCESS_TOKEN: MOCK_TOKEN,
            CONF_VERIFY_SSL: True,
        },
        options={CONF_SCAN_INTERVAL_MINUTES: 5},
    )


@pytest.fixture
def mock_client() -> Generator[dict[str, AsyncMock]]:
    """Patch the Ghostfolio API client with canned responses."""
    with (
        patch(
            "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
            return_value=None,
        ) as validate,
        patch(
            "custom_components.ghostfolio.api.GhostfolioClient.async_get_user",
            return_value=MOCK_USER,
        ) as user,
        patch(
            "custom_components.ghostfolio.api.GhostfolioClient.async_get_details",
            return_value=MOCK_DETAILS,
        ) as details,
    ):
        yield {"validate": validate, "user": user, "details": details}
