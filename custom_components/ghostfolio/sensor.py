"""Sensors for the Ghostfolio integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACCOUNT_ID,
    ATTR_ACCOUNT_NAME,
    ATTR_ASSET_CLASS,
    ATTR_CURRENCY,
    ATTR_DATA_SOURCE,
    ATTR_MARKET_PRICE,
    ATTR_NAME,
    ATTR_QUANTITY,
    ATTR_SYMBOL,
    DOMAIN,
)
from .coordinator import GhostfolioCoordinator

_LOGGER = logging.getLogger(__name__)


def _position_key(position: dict[str, Any]) -> str:
    account = position.get("account_id") or "portfolio"
    symbol = position.get("symbol") or position.get("name") or "unknown"
    return f"{account}::{symbol}"


def _has_nonzero_value(position: dict[str, Any]) -> bool:
    """Return True if the position has a meaningful (non-zero) value."""
    value = position.get("value")
    if value is None:
        return False
    try:
        return float(value) != 0.0
    except (TypeError, ValueError):
        return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ghostfolio sensors based on the coordinator data."""
    coordinator: GhostfolioCoordinator = hass.data[DOMAIN][entry.entry_id]

    known: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        new_entities: list[SensorEntity] = []
        data = coordinator.data or {}
        for position in data.get("positions", []):
            key = _position_key(position)
            if key in known:
                continue
            if not _has_nonzero_value(position):
                # Skip 0-valued positions on first sight so we don't litter
                # the registry with sensors for sold-out / empty holdings.
                # Existing sensors are preserved on purpose.
                continue
            known.add(key)
            new_entities.append(
                GhostfolioPositionSensor(coordinator, entry.entry_id, key)
            )
        if new_entities:
            async_add_entities(new_entities)

    initial_entities: list[SensorEntity] = [
        GhostfolioTotalValueSensor(coordinator, entry.entry_id)
    ]
    async_add_entities(initial_entities)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


class _GhostfolioBaseEntity(CoordinatorEntity[GhostfolioCoordinator], SensorEntity):
    """Base class for all Ghostfolio sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: GhostfolioCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Ghostfolio",
            manufacturer="Ghostfolio",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.base_url,
        )


class GhostfolioTotalValueSensor(_GhostfolioBaseEntity):
    """Sensor for the total portfolio value."""

    _attr_translation_key = "total_value"
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator: GhostfolioCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_total_value"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        value = data.get("total_value")
        return round(float(value), 2) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("currency")


class GhostfolioPositionSensor(_GhostfolioBaseEntity):
    """Sensor for the value of a single position within an account."""

    _attr_icon = "mdi:chart-line"

    def __init__(
        self,
        coordinator: GhostfolioCoordinator,
        entry_id: str,
        position_key: str,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._position_key = position_key
        self._attr_unique_id = f"{entry_id}_{position_key}"
        position = self._find_position()
        account_name = (position or {}).get("account_name") or "Portfolio"
        symbol = (position or {}).get("symbol") or "Unknown"
        self._attr_name = f"{account_name} {symbol}"

    def _find_position(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        for pos in data.get("positions", []):
            if _position_key(pos) == self._position_key:
                return pos
        return None

    @property
    def available(self) -> bool:
        return super().available and self._find_position() is not None

    @property
    def native_value(self) -> float | None:
        position = self._find_position()
        if not position:
            return None
        value = position.get("value")
        return round(float(value), 2) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        position = self._find_position()
        if position and position.get("currency"):
            return position["currency"]
        data = self.coordinator.data or {}
        return data.get("currency")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        position = self._find_position() or {}
        return {
            ATTR_ACCOUNT_ID: position.get("account_id"),
            ATTR_ACCOUNT_NAME: position.get("account_name"),
            ATTR_SYMBOL: position.get("symbol"),
            ATTR_NAME: position.get("name"),
            ATTR_QUANTITY: position.get("quantity"),
            ATTR_MARKET_PRICE: position.get("market_price"),
            ATTR_CURRENCY: position.get("currency"),
            ATTR_DATA_SOURCE: position.get("data_source"),
            ATTR_ASSET_CLASS: position.get("asset_class"),
        }
