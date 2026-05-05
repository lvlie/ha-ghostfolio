"""Config flow for the Ghostfolio integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class GhostfolioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the user-driven config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            unique_id = urlparse(url).netloc or url
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = GhostfolioClient(
                session=session,
                url=url,
                access_token=user_input[CONF_ACCESS_TOKEN],
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
            )
            try:
                await client.async_validate()
            except GhostfolioAuthError:
                errors["base"] = "invalid_auth"
            except GhostfolioApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Ghostfolio credentials")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Ghostfolio ({unique_id})",
                    data={
                        CONF_URL: url,
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, True),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
