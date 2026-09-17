"""Tests for setting up and tearing down the Ghostfolio config entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ghostfolio.api import GhostfolioApiError, GhostfolioAuthError
from custom_components.ghostfolio.const import CONF_SCAN_INTERVAL_MINUTES


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """The entry loads, exposes its coordinator and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.data["currency"] == "EUR"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_ghostfolio_is_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A connection problem leaves the entry in the retry state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
        side_effect=GhostfolioApiError("boom"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_starts_reauth_on_invalid_token(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A rejected token puts the entry into the reauth state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
        side_effect=GhostfolioAuthError("nope"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler("ghostfolio")
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_options_update_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Changing the scan interval reloads the entry with the new interval."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_SCAN_INTERVAL_MINUTES: 60}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.update_interval.total_seconds() == 3600


async def test_invalid_scan_interval_falls_back_to_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """A garbage stored interval does not prevent the entry from loading."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_SCAN_INTERVAL_MINUTES: "not-a-number"}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.update_interval.total_seconds() == 300
