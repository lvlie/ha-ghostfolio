"""The Ghostfolio integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from .coordinator import GhostfolioCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ghostfolio from a config entry."""
    session = async_get_clientsession(hass)
    client = GhostfolioClient(
        session=session,
        url=entry.data[CONF_URL],
        access_token=entry.data[CONF_ACCESS_TOKEN],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )

    try:
        await client.async_validate()
    except GhostfolioAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except GhostfolioApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    interval = timedelta(minutes=_resolve_scan_interval(entry))
    coordinator = GhostfolioCoordinator(hass, client, update_interval=interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Ghostfolio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (e.g. scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _resolve_scan_interval(entry: ConfigEntry) -> int:
    raw = entry.options.get(
        CONF_SCAN_INTERVAL_MINUTES,
        entry.data.get(CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES),
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL_MINUTES
