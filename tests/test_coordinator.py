"""Tests for the coordinator's refresh behaviour and response normalisation."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.ghostfolio.api import GhostfolioApiError, GhostfolioAuthError
from custom_components.ghostfolio.coordinator import _normalise


async def test_api_error_marks_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """A transient API error is reported without dropping the entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    mock_client["details"].side_effect = GhostfolioApiError("boom")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert hass.states.get("sensor.ghostfolio_total_portfolio_value").state == (
        "unavailable"
    )


async def test_revoked_token_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """An auth failure during a refresh asks the user for a new token."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_client["user"].side_effect = GhostfolioAuthError("revoked")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("ghostfolio")
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


def test_normalise_with_per_account_holdings() -> None:
    """Holdings split over accounts become one position per account."""
    raw = {
        "summary": {"baseCurrency": "USD", "currentValueInBaseCurrency": 1500.0},
        "accounts": {
            "acc-1": {
                "name": "Brokerage",
                "currency": "USD",
                "valueInBaseCurrency": 1000,
            },
            "acc-2": {
                "name": "Crypto",
                "currency": "USD",
                "valueInBaseCurrency": 500,
            },
        },
        "holdings": {
            "AAPL": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 5,
                "marketPrice": 200,
                "currency": "USD",
                "dataSource": "YAHOO",
                "assetClass": "EQUITY",
                "accounts": [
                    {
                        "id": "acc-1",
                        "name": "Brokerage",
                        "valueInBaseCurrency": 1000,
                        "quantity": 5,
                    },
                ],
            },
            "BTC": {
                "symbol": "BTC",
                "name": "Bitcoin",
                "quantity": 0.01,
                "marketPrice": 50000,
                "currency": "USD",
                "dataSource": "COINGECKO",
                "assetClass": "CRYPTO",
                "accounts": [
                    {
                        "id": "acc-2",
                        "name": "Crypto",
                        "valueInBaseCurrency": 500,
                        "quantity": 0.01,
                    },
                ],
            },
        },
    }

    result = _normalise(raw)

    assert result["currency"] == "USD"
    assert result["total_value"] == 1500.0
    assert set(result["accounts"]) == {"acc-1", "acc-2"}
    assert len(result["positions"]) == 2

    aapl = next(p for p in result["positions"] if p["symbol"] == "AAPL")
    assert aapl["account_id"] == "acc-1"
    assert aapl["account_name"] == "Brokerage"
    assert aapl["value"] == 1000


def test_normalise_accepts_list_shaped_payloads() -> None:
    """Ghostfolio has shipped both list- and dict-shaped collections."""
    raw = {
        "summary": {"baseCurrency": "USD", "currentValueInBaseCurrency": 1000.0},
        "accounts": [{"id": "acc-1", "name": "Brokerage", "value": 1000}],
        "holdings": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 5,
                "marketPrice": 200,
                "accounts": [{"id": "acc-1", "name": "Brokerage", "value": 1000}],
            }
        ],
    }

    result = _normalise(raw)

    assert set(result["accounts"]) == {"acc-1"}
    assert result["positions"][0]["account_id"] == "acc-1"


def test_normalise_uses_user_base_currency_when_summary_missing_it() -> None:
    """The user's base currency wins over the USD fallback."""
    raw = {
        "summary": {"currentValueInBaseCurrency": 1000.0},
        "accounts": {},
        "holdings": [],
    }
    user = {"settings": {"baseCurrency": "EUR"}}
    result = _normalise(raw, user)
    assert result["currency"] == "EUR"
    assert result["total_value"] == 1000.0


def test_normalise_user_currency_overrides_summary_default() -> None:
    """The user's base currency also wins over the summary currency."""
    raw = {
        "summary": {"baseCurrency": "USD", "currentValueInBaseCurrency": 1000.0},
        "accounts": {},
        "holdings": [],
    }
    user = {"settings": {"baseCurrency": "EUR"}}
    result = _normalise(raw, user)
    assert result["currency"] == "EUR"


def test_normalise_falls_back_to_quantity_times_price() -> None:
    """A holding without accounts is reported as a single portfolio position."""
    raw = {
        "summary": {},
        "accounts": {},
        "holdings": [
            {
                "symbol": "VOO",
                "name": "Vanguard S&P 500",
                "quantity": 2,
                "marketPrice": 400,
                "currency": "USD",
            }
        ],
    }
    result = _normalise(raw)
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["account_id"] is None
    assert pos["value"] == 800


def test_normalise_totals_accounts_when_summary_has_no_value() -> None:
    """Without a summary value the account values are summed."""
    raw = {
        "summary": {},
        "accounts": {
            "acc-1": {"name": "Brokerage", "valueInBaseCurrency": 700},
            "acc-2": {"name": "Crypto", "valueInBaseCurrency": 300},
        },
        "holdings": {},
    }
    assert _normalise(raw)["total_value"] == 1000
