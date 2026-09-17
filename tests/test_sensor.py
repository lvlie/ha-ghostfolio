"""Tests for the Ghostfolio sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .const import MOCK_DETAILS

TOTAL_VALUE = "sensor.ghostfolio_total_portfolio_value"
AAPL = "sensor.ghostfolio_brokerage_aapl"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_total_value_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """The total value sensor reports the portfolio value in the base currency."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(TOTAL_VALUE)
    assert state is not None
    assert state.state == "1500.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL


async def test_position_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Each (account, symbol) pair becomes a sensor carrying its details."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(AAPL)
    assert state is not None
    assert state.state == "1000.0"
    assert state.attributes["account_name"] == "Brokerage"
    assert state.attributes["symbol"] == "AAPL"
    assert state.attributes["quantity"] == 5
    assert state.attributes["market_price"] == 200
    assert state.attributes["asset_class"] == "EQUITY"


async def test_zero_value_positions_are_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """Sold-out holdings do not create sensors."""
    await _setup(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_ids = {entity.unique_id for entity in entities}

    assert any(uid.endswith("acc-1::AAPL") for uid in unique_ids)
    assert any(uid.endswith("acc-2::BTC") for uid in unique_ids)
    assert not any(uid.endswith("SOLD") for uid in unique_ids)


async def test_new_position_is_added_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """A holding that appears later gets its own sensor without a reload."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get("sensor.ghostfolio_brokerage_msft") is None

    details = {
        **MOCK_DETAILS,
        "holdings": {
            **MOCK_DETAILS["holdings"],
            "MSFT": {
                "symbol": "MSFT",
                "name": "Microsoft",
                "quantity": 2,
                "marketPrice": 300,
                "currency": "EUR",
                "accounts": [
                    {
                        "id": "acc-1",
                        "name": "Brokerage",
                        "valueInBaseCurrency": 600,
                        "quantity": 2,
                    }
                ],
            },
        },
    }
    mock_client["details"].return_value = details

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ghostfolio_brokerage_msft")
    assert state is not None
    assert state.state == "600.0"


async def test_position_becomes_unavailable_when_it_disappears(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: dict[str, AsyncMock],
) -> None:
    """A holding removed in Ghostfolio leaves its sensor unavailable."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(AAPL).state == "1000.0"

    mock_client["details"].return_value = {
        **MOCK_DETAILS,
        "holdings": {"BTC": MOCK_DETAILS["holdings"]["BTC"]},
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()

    assert hass.states.get(AAPL).state == "unavailable"
