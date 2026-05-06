"""Config flow for the Ghostfolio integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_URL,
    DOMAIN,
    SCAN_INTERVAL_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def _scan_interval_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": str(opt), "label": f"{opt} minutes"}
                for opt in SCAN_INTERVAL_OPTIONS
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=DEFAULT_URL): str,
            vol.Required(CONF_ACCESS_TOKEN): str,
            vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            vol.Required(
                CONF_SCAN_INTERVAL_MINUTES,
                default=str(DEFAULT_SCAN_INTERVAL_MINUTES),
            ): _scan_interval_selector(),
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
                scan_interval = int(
                    user_input.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    )
                )
                return self.async_create_entry(
                    title=f"Ghostfolio ({unique_id})",
                    data={
                        CONF_URL: url,
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                        CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, True),
                    },
                    options={CONF_SCAN_INTERVAL_MINUTES: scan_interval},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GhostfolioOptionsFlow(config_entry)


class GhostfolioOptionsFlow(OptionsFlow):
    """Allow the user to change the scan interval after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        # Stored under a private name because in HA 2024.12+ ``config_entry``
        # is a read-only property on ``OptionsFlow`` and assigning to it
        # raises an error.
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL_MINUTES: int(
                        user_input[CONF_SCAN_INTERVAL_MINUTES]
                    )
                },
            )

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=str(current),
                ): _scan_interval_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
