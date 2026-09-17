"""DataUpdateCoordinator for Ghostfolio."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GhostfolioApiError, GhostfolioAuthError, GhostfolioClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GhostfolioConfigEntry = ConfigEntry[GhostfolioCoordinator]


class GhostfolioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches portfolio data from Ghostfolio on a schedule."""

    config_entry: GhostfolioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GhostfolioConfigEntry,
        client: GhostfolioClient,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialise the coordinator for a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval or DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and normalise the current portfolio state."""
        try:
            user = await self.client.async_get_user()
            details = await self.client.async_get_details()
        except GhostfolioAuthError as err:
            # Surface this as a reauth flow instead of endless failed updates:
            # the access token was revoked or changed in Ghostfolio.
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except GhostfolioApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching portfolio: {err}") from err

        return _normalise(details, user)


def _user_base_currency(user: dict[str, Any] | None) -> str | None:
    """Return the base currency configured for the Ghostfolio user."""
    if not isinstance(user, dict):
        return None
    settings = user.get("settings")
    if isinstance(settings, dict):
        currency = settings.get("baseCurrency")
        if currency:
            return currency
    return user.get("baseCurrency")


def _normalise_accounts(accounts_raw: Any) -> dict[str, dict[str, Any]]:
    """Return the accounts keyed by id, whether the API sent a list or a dict."""
    if isinstance(accounts_raw, list):
        accounts_iter: Any = ((acc.get("id"), acc) for acc in accounts_raw)
    else:
        accounts_iter = accounts_raw.items()

    accounts: dict[str, dict[str, Any]] = {}
    for acc_id, acc in accounts_iter:
        if not acc_id:
            continue
        accounts[acc_id] = {
            "name": acc.get("name") or acc_id,
            "currency": acc.get("currency"),
            "value": acc.get("valueInBaseCurrency", acc.get("value")),
            "balance": acc.get("balanceInBaseCurrency", acc.get("balance")),
        }
    return accounts


def _total_value(summary: dict[str, Any], accounts: dict[str, dict[str, Any]]) -> float:
    """Return the portfolio total, falling back to the sum of the accounts."""
    for key in ("currentValueInBaseCurrency", "currentValue"):
        value = summary.get(key)
        if value is not None:
            return value
    return sum(acc.get("value") or 0 for acc in accounts.values())


def _holding_positions(
    holding: dict[str, Any],
    accounts: dict[str, dict[str, Any]],
    base_currency: str,
) -> list[dict[str, Any]]:
    """Return one position per account the holding is held in."""
    symbol = holding.get("symbol") or holding.get("name")
    if not symbol:
        return []

    quantity = holding.get("quantity") or 0
    market_price = holding.get("marketPrice") or holding.get("netPerformance")
    shared = {
        "symbol": symbol,
        "name": holding.get("name") or symbol,
        "market_price": market_price,
        "currency": holding.get("currency") or base_currency,
        "data_source": holding.get("dataSource"),
        "asset_class": holding.get("assetClass") or holding.get("assetSubClass"),
    }

    holding_accounts = [
        acc for acc in holding.get("accounts") or [] if isinstance(acc, dict)
    ]
    if not holding_accounts:
        value = (
            holding.get("valueInBaseCurrency")
            or holding.get("value")
            or (quantity * market_price if quantity and market_price else 0)
        )
        return [
            {
                **shared,
                "account_id": None,
                "account_name": "Portfolio",
                "quantity": quantity,
                "value": value,
            }
        ]

    positions: list[dict[str, Any]] = []
    for acc_ref in holding_accounts:
        acc_id = acc_ref.get("id")
        known_name = accounts.get(acc_id, {}).get("name") if acc_id else None
        acc_quantity = acc_ref.get("quantity")
        positions.append(
            {
                **shared,
                "account_id": acc_id,
                "account_name": acc_ref.get("name") or known_name or "Portfolio",
                "quantity": quantity if acc_quantity is None else acc_quantity,
                "value": acc_ref.get("valueInBaseCurrency")
                or acc_ref.get("value")
                or 0,
            }
        )
    return positions


def _normalise(
    details: dict[str, Any], user: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Reshape the raw /portfolio/details response into a stable structure.

    Output:
        {
            "currency": "USD",
            "total_value": 12345.67,
            "accounts": {account_id: {"name": ..., "currency": ..., "value": ...}},
            "positions": [
                {
                    "account_id": ..., "account_name": ...,
                    "symbol": ..., "name": ...,
                    "quantity": ..., "market_price": ...,
                    "value": ..., "currency": ...,
                    "data_source": ..., "asset_class": ...,
                },
                ...
            ],
        }
    """
    summary = details.get("summary") or {}
    accounts = _normalise_accounts(details.get("accounts") or {})

    holdings_raw = details.get("holdings") or {}
    holdings = holdings_raw if isinstance(holdings_raw, list) else holdings_raw.values()

    base_currency = (
        _user_base_currency(user)
        or summary.get("baseCurrency")
        or summary.get("currency")
        or "USD"
    )

    positions: list[dict[str, Any]] = []
    for holding in holdings:
        if isinstance(holding, dict):
            positions.extend(_holding_positions(holding, accounts, base_currency))

    return {
        "currency": base_currency,
        "total_value": _total_value(summary, accounts) or 0,
        "accounts": accounts,
        "positions": positions,
    }
