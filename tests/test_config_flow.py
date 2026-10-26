"""Tests for the Ghostfolio config and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ghostfolio.api import GhostfolioApiError, GhostfolioAuthError
from custom_components.ghostfolio.const import (
    CONF_ACCESS_TOKEN,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from .const import MOCK_TOKEN, MOCK_URL

USER_INPUT = {
    CONF_URL: f"{MOCK_URL}/",
    CONF_ACCESS_TOKEN: MOCK_TOKEN,
    CONF_VERIFY_SSL: True,
    CONF_SCAN_INTERVAL_MINUTES: "15",
}


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_client: dict[str, AsyncMock]
) -> None:
    """A valid token creates an entry with a normalised URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ghostfolio (ghostfolio.local:3333)"
    # The trailing slash is stripped so the API paths concatenate cleanly.
    assert result["data"] == {
        CONF_URL: MOCK_URL,
        CONF_ACCESS_TOKEN: MOCK_TOKEN,
        CONF_VERIFY_SSL: True,
    }
    assert result["options"] == {CONF_SCAN_INTERVAL_MINUTES: 15}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (GhostfolioAuthError("bad token"), "invalid_auth"),
        (GhostfolioApiError("unreachable"), "cannot_connect"),
        (RuntimeError("kaboom"), "unknown"),
    ],
)
async def test_user_flow_errors_are_recoverable(
    hass: HomeAssistant,
    mock_client: dict[str, AsyncMock],
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Failures show an error and let the user try again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # The same flow succeeds once the problem is resolved.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_for_duplicate_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """The same Ghostfolio host cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_updates_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Reauth replaces the stored access token and reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
        side_effect=GhostfolioAuthError("still bad"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "still-wrong"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new-token"
    # The rest of the configuration is left untouched.
    assert mock_config_entry.data[CONF_URL] == MOCK_URL


async def test_options_flow_changes_scan_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """The options flow stores the interval as an int."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL_MINUTES: "60"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL_MINUTES: 60}


async def test_reconfigure_moves_entry_to_new_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Switching from a plain-HTTP IP to an HTTPS host keeps the same entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.ghostfolio.api.GhostfolioClient.async_validate",
        side_effect=GhostfolioApiError("unreachable"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "https://ghostfolio.example.com/"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://ghostfolio.example.com/", CONF_VERIFY_SSL: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # An empty token field keeps the stored token.
    assert mock_config_entry.data == {
        CONF_URL: "https://ghostfolio.example.com",
        CONF_ACCESS_TOKEN: MOCK_TOKEN,
        CONF_VERIFY_SSL: True,
    }
    assert mock_config_entry.unique_id == "ghostfolio.example.com"
    assert mock_config_entry.title == "Ghostfolio (ghostfolio.example.com)"
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL_MINUTES: 5}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reconfigure_can_replace_token_and_keeps_custom_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """A new token is stored and a title the user chose is left alone."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="My portfolio")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MOCK_URL,
            CONF_ACCESS_TOKEN: "new-token",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new-token"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False
    assert mock_config_entry.unique_id == "ghostfolio.local:3333"
    assert mock_config_entry.title == "My portfolio"


async def test_reconfigure_aborts_when_url_belongs_to_other_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Two entries cannot end up pointing at the same Ghostfolio host."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="other.example.com",
        data={
            CONF_URL: "https://other.example.com",
            CONF_ACCESS_TOKEN: MOCK_TOKEN,
            CONF_VERIFY_SSL: True,
        },
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "https://other.example.com"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_URL] == MOCK_URL
