"""Config flow for the Ghostfolio integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

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
import voluptuous as vol

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
    """Return the dropdown selector for the polling interval."""
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
    """Return the schema shown during initial setup."""
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


def _unique_id(url: str) -> str:
    """Return the unique ID for a normalised Ghostfolio URL (its host:port)."""
    return urlparse(url).netloc or url


def _default_title(unique_id: str) -> str:
    """Return the entry title generated for a Ghostfolio instance."""
    return f"Ghostfolio ({unique_id})"


class GhostfolioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the user-driven config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            unique_id = _unique_id(url)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            error = await self._async_validate(
                url,
                user_input[CONF_ACCESS_TOKEN],
                user_input.get(CONF_VERIFY_SSL, True),
            )
            if error:
                errors["base"] = error
            else:
                scan_interval = int(
                    user_input.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    )
                )
                return self.async_create_entry(
                    title=_default_title(unique_id),
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a token that Ghostfolio no longer accepts."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new access token for an existing entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate(
                entry.data[CONF_URL],
                user_input[CONF_ACCESS_TOKEN],
                entry.data.get(CONF_VERIFY_SSL, True),
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at a new URL, e.g. after moving to HTTPS."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            # Leaving the token empty keeps the one already stored.
            access_token = (
                user_input.get(CONF_ACCESS_TOKEN) or entry.data[CONF_ACCESS_TOKEN]
            )
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            unique_id = _unique_id(url)

            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            error = await self._async_validate(url, access_token, verify_ssl)
            if error:
                errors["base"] = error
            else:
                # Keep a title the user renamed; only refresh the generated one.
                title = (
                    _default_title(unique_id)
                    if entry.title == _default_title(entry.unique_id or "")
                    else entry.title
                )
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=title,
                    data_updates={
                        CONF_URL: url,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        current = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=current[CONF_URL]): str,
                vol.Optional(CONF_ACCESS_TOKEN): str,
                vol.Optional(
                    CONF_VERIFY_SSL, default=current.get(CONF_VERIFY_SSL, True)
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    async def _async_validate(
        self, url: str, access_token: str, verify_ssl: bool
    ) -> str | None:
        """Return an error key if the credentials cannot be used, else None."""
        client = GhostfolioClient(
            session=async_get_clientsession(self.hass),
            url=url,
            access_token=access_token,
            verify_ssl=verify_ssl,
        )
        try:
            await client.async_validate()
        except GhostfolioAuthError:
            return "invalid_auth"
        except GhostfolioApiError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating Ghostfolio credentials")
            return "unknown"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for this entry."""
        return GhostfolioOptionsFlow()


class GhostfolioOptionsFlow(OptionsFlow):
    """Allow the user to change the scan interval after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and persist the polling interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL_MINUTES: int(
                        user_input[CONF_SCAN_INTERVAL_MINUTES]
                    )
                },
            )

        current = self.config_entry.options.get(
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
