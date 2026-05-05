"""The Ghostfolio integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import CONF_ACCESS_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
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

    coordinator = GhostfolioCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Ghostfolio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
